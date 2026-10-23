"""job.json: the one file that holds every editorial decision for a video. Everything else is computed from it.

load_job() reads and validates it; validate() returns every problem at once, each with the path of the field
("timeline[3].t: ..."), so a job can be fixed in one pass.
"""
import json
import re
from dataclasses import dataclass
from math import gcd
from pathlib import Path

from . import captions as captions_mod
from . import package as package_mod
from .effects import Catalog
from .settings import Settings, SettingsError, load_settings

MODES = {"footage", "avatar", "client", "longform"}
LAYOUTS = {"hook", "broll", "face", "split", "card", "full", "screen", "cam"}
FPS = {24, 25, 30, 50, 60}
TOP_KEYS = {"id", "title", "mode", "fps", "size", "language", "sources", "script", "cut", "timeline", "variants",
            "captions", "package", "graphics", "effects", "sfx", "music", "custom", "gates", "notes"}
SOURCE_KEYS = {"path", "offset", "voice_offset", "note"}
SEGMENT_KEYS = {"t", "layout", "src", "in", "speed", "zoom", "note"}
PIECE_KEYS = {"src", "in", "out", "text", "zoom", "tag", "note"}
SPAN_CUT_KEYS = {"mode", "source", "keep", "drop", "gap", "pad_in", "pad_out", "silence_db", "speech_db", "min_island"}
VARIANT_KEYS = {"ranges", "freeze", "mute_voice_after", "note"}
GATE_KEYS = {"storyboard_approved", "final_approved"}
EPS = 1e-6


class JobError(ValueError):
    def __init__(self, path, errors):
        self.errors = errors
        super().__init__(f"{path}: {len(errors)} problem(s)\n  " + "\n  ".join(errors))


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def on_grid(t: float, fps: int) -> bool:
    """True when t sits on a frame boundary (cue drift came from cuts that didn't)."""
    return abs(t * fps - round(t * fps)) < 0.01


def aspect(size) -> str:
    w, h = size
    g = gcd(w, h)
    return f"{w // g}:{h // g}"


def length(data: dict) -> float | None:
    """Output length in seconds when it's known before building: timeline end, or the sum of measured pieces."""
    if isinstance(data.get("timeline"), list) and data["timeline"]:
        try:
            return float(data["timeline"][-1]["t"][1])
        except (KeyError, IndexError, TypeError):
            return None
    cut = data.get("cut")
    if isinstance(cut, dict) and cut.get("mode") == "pieces":
        try:
            return float(sum(p["out"] - p["in"] for p in cut["pieces"]))
        except (KeyError, TypeError):
            return None
    return None


class _Check:
    def __init__(self):
        self.errors = []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def keys(self, obj, allowed, where):
        for k in sorted(set(obj) - allowed):
            self.err(where, f"unknown key {k!r} (allowed: {', '.join(sorted(allowed))})")

    def span(self, s, where, fps=None, labelled=False, noted=False) -> bool:
        """[t0, t1] with 0 <= t0 < t1, plus a text label when labelled and a text note after it when noted."""
        sizes = (2, 3, 4) if noted else (2, 3) if labelled else (2,)
        shape = ('[start, end, "label", "note"]' if noted else '[start, end, "label"]') if labelled else "[start, end]"
        if not isinstance(s, list) or len(s) not in sizes or not all(map(_num, s[:2])):
            self.err(where, f"must be {shape} in seconds (label and note optional)" if labelled
                     else f"must be {shape} in seconds")
            return False
        if not all(isinstance(x, str) for x in s[2:]):
            self.err(where, "items after the times must be text")
        if not 0 <= s[0] < s[1]:
            self.err(where, f"start {s[0]} must be >= 0 and before end {s[1]}")
            return False
        if fps and not (on_grid(s[0], fps) and on_grid(s[1], fps)):
            self.err(where, f"{s[0]}-{s[1]} is not on the {fps} fps frame grid")
        return True


def validate(data, catalog: Catalog | None = None, job_dir: Path | None = None, settings: Settings | None = None,
             check_files: bool = False) -> list:
    c = _Check()
    if not isinstance(data, dict):
        return ["job.json must be an object"]
    c.keys(data, TOP_KEYS, "job")

    if not isinstance(data.get("id"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", data.get("id") or ""):
        c.err("id", "required: lowercase letters, digits, - or _ (e.g. \"reel-06\")")
    mode = data.get("mode")
    if mode not in MODES:
        c.err("mode", f"must be one of {sorted(MODES)}")
    fps = data.get("fps")
    if fps not in FPS:
        c.err("fps", f"must be one of {sorted(FPS)}")
        fps = None
    size = data.get("size")
    if not (isinstance(size, list) and len(size) == 2 and all(isinstance(v, int) and v > 0 for v in size)):
        c.err("size", "must be [width, height] in pixels, e.g. [1080, 1920]")
        size = None
    elif any(v % 2 for v in size):
        c.err("size", "width and height must be even (yuv420 video needs it)")

    sources = data.get("sources")
    if not isinstance(sources, dict) or not sources:
        c.err("sources", "required: at least one named source, e.g. {\"a\": {\"path\": \"raw/take1.mp4\"}}")
        sources = {}
    for name, s in sources.items():
        w = f"sources.{name}"
        if not isinstance(s, dict) or not isinstance(s.get("path"), str):
            c.err(w, "must be {\"path\": \"...\"}")
            continue
        c.keys(s, SOURCE_KEYS, w)
        for k in ("offset", "voice_offset"):
            if k in s and not _num(s[k]):
                c.err(f"{w}.{k}", "must be a number of seconds")

    if "script" in data and not isinstance(data["script"], str):
        c.err("script", "must be a path to the script text")
    if "language" in data and not (isinstance(data["language"], str) and re.fullmatch(r"[a-z]{2}", data["language"])):
        c.err("language", "must be a two-letter code for transcription, e.g. \"hi\" for Hinglish or \"en\"")

    if "cut" not in data and "timeline" not in data:
        c.err("job", "needs a \"cut\" (camera footage) or a \"timeline\" (segments), or both")

    cut = data.get("cut")
    if cut is not None:
        if not isinstance(cut, dict) or cut.get("mode") not in ("spans", "pieces"):
            c.err("cut.mode", "must be \"spans\" (keep/drop on a source, measured by the cutter) or \"pieces\"")
        elif cut["mode"] == "spans":
            c.keys(cut, SPAN_CUT_KEYS, "cut")
            if cut.get("source") not in sources:
                c.err("cut.source", f"must name one of the sources ({', '.join(sources) or 'none'})")
            keep = cut.get("keep")
            if not isinstance(keep, list) or not keep:
                c.err("cut.keep", "required: a list of [start, end, \"label\"] spans to keep")
                keep = []
            for i, s in enumerate(keep):
                c.span(s, f"cut.keep[{i}]", labelled=True, noted=True)
            for i, s in enumerate(cut.get("drop", [])):
                c.span(s, f"cut.drop[{i}]", labelled=True)
            for k in ("gap", "pad_in", "pad_out", "min_island"):
                if k in cut and (not _num(cut[k]) or cut[k] < 0):
                    c.err(f"cut.{k}", "must be a number of seconds >= 0")
            for k in ("silence_db", "speech_db"):
                if k in cut and (not _num(cut[k]) or cut[k] >= 0):
                    c.err(f"cut.{k}", "must be a level in dBFS below 0, e.g. -55")
        else:
            c.keys(cut, {"mode", "pieces"}, "cut")
            pieces = cut.get("pieces")
            if not isinstance(pieces, list) or not pieces:
                c.err("cut.pieces", "required: a list of {src, in, out} pieces in output order")
                pieces = []
            for i, p in enumerate(pieces):
                w = f"cut.pieces[{i}]"
                if not isinstance(p, dict):
                    c.err(w, "must be {\"src\": ..., \"in\": ..., \"out\": ...}")
                    continue
                c.keys(p, PIECE_KEYS, w)
                if p.get("src") not in sources:
                    c.err(f"{w}.src", f"must name one of the sources ({', '.join(sources) or 'none'})")
                if not (_num(p.get("in")) and _num(p.get("out")) and 0 <= p["in"] < p["out"]):
                    c.err(w, "\"in\" and \"out\" must be source seconds with in < out")
                elif fps and not (on_grid(p["in"], fps) and on_grid(p["out"], fps)):
                    c.err(w, f"in/out {p['in']}-{p['out']} are not on the {fps} fps frame grid")
                if "zoom" in p and (not _num(p["zoom"]) or p["zoom"] <= 0):
                    c.err(f"{w}.zoom", "must be a positive number (1.0 = no zoom)")

    tl = data.get("timeline")
    if tl is not None:
        if not isinstance(tl, list) or not tl:
            c.err("timeline", "must be a list of segments")
            tl = []
        prev = 0.0
        for i, s in enumerate(tl):
            w = f"timeline[{i}]"
            if not isinstance(s, dict):
                c.err(w, "must be {\"t\": [start, end], \"layout\": ..., \"src\": ..., \"in\": ...}")
                continue
            c.keys(s, SEGMENT_KEYS, w)
            if c.span(s.get("t"), f"{w}.t", fps):
                if abs(s["t"][0] - prev) > EPS:
                    c.err(f"{w}.t", f"starts at {s['t'][0]} but the previous segment ends at {prev}: "
                                    "segments must follow each other with no gap or overlap")
                prev = s["t"][1]
            if s.get("layout") not in LAYOUTS:
                c.err(f"{w}.layout", f"must be one of {sorted(LAYOUTS)}")
            if s.get("src") not in sources:
                c.err(f"{w}.src", f"must name one of the sources ({', '.join(sources) or 'none'})")
            if not _num(s.get("in")) or s["in"] < 0:
                c.err(f"{w}.in", "must be the source time in seconds where this segment starts")
            for k in ("speed", "zoom"):
                if k in s and (not _num(s[k]) or s[k] <= 0):
                    c.err(f"{w}.{k}", "must be a positive number (1.0 = normal)")

    total = length(data)
    variants = data.get("variants")
    if not isinstance(variants, dict) or not variants:
        c.err("variants", "required: at least one, e.g. {\"instagram\": {\"ranges\": [[0, 54.4]]}}")
        variants = {}
    for name, v in variants.items():
        w = f"variants.{name}"
        if not isinstance(v, dict) or ("ranges" in v and (not isinstance(v["ranges"], list) or not v["ranges"])):
            c.err(w, "must be an object; \"ranges\": [[start, end], ...] on the output timeline (leave it out for "
                     "the whole video)")
            continue
        c.keys(v, VARIANT_KEYS, w)
        last = -1.0
        for i, r in enumerate(v.get("ranges", [])):
            if c.span(r, f"{w}.ranges[{i}]", fps):
                if r[0] < last - EPS:
                    c.err(f"{w}.ranges[{i}]", "ranges must be in order and must not overlap")
                if total is not None and r[1] > total + EPS:
                    c.err(f"{w}.ranges[{i}]", f"ends at {r[1]}, after the video ends ({total:.2f} s)")
                last = r[1]
        if "freeze" in v and (not _num(v["freeze"]) or v["freeze"] < 0):
            c.err(f"{w}.freeze", "must be seconds >= 0")
        if "mute_voice_after" in v and not _num(v["mute_voice_after"]):
            c.err(f"{w}.mute_voice_after", "must be a time in seconds")

    caps = data.get("captions")
    if caps is not None:
        c.errors += captions_mod.check(caps, data)
        for i, s in enumerate(caps.get("hide", []) if isinstance(caps, dict) else []):
            c.span(s, f"captions.hide[{i}]")
    if "package" in data:
        c.errors += package_mod.check(data["package"], data)
    gfx = data.get("graphics")
    if gfx is not None and (not isinstance(gfx, dict) or ("composition" in gfx and not isinstance(gfx["composition"], str))):
        c.err("graphics", "must be an object; \"composition\" is a path to the job's HyperFrames index.html")

    fx = data.get("effects", [])
    if not isinstance(fx, list):
        c.err("effects", "must be a list of {\"effect\": name, \"at\": seconds, \"params\": {...}}")
        fx = []
    if fx:
        catalog = catalog or Catalog.load(settings.path("effects") if settings else None)
        for i, p in enumerate(fx):
            for e in catalog.check_placement(p, f"effects[{i}]", mode, aspect(size) if size else None, total):
                c.errors.append(e)
            for vn in (p.get("variants", []) if isinstance(p, dict) else []):
                if vn not in variants:
                    c.err(f"effects[{i}].variants", f"{vn!r} is not one of the job's variants")

    sfx = data.get("sfx", [])
    if not isinstance(sfx, list) or not all(isinstance(s, dict) and isinstance(s.get("kind"), str) for s in sfx):
        c.err("sfx", "must be a list of cues, each with a \"kind\"")
    if "music" in data and not isinstance(data["music"], dict):
        c.err("music", "must be an object")
    custom = data.get("custom", [])
    if not isinstance(custom, list) or not all(isinstance(s, str) for s in custom):
        c.err("custom", "must be a list of script paths inside the job folder")
    gates = data.get("gates", {})
    if not isinstance(gates, dict) or not all(isinstance(v, bool) for v in gates.values()):
        c.err("gates", "must be {\"storyboard_approved\": true/false, \"final_approved\": true/false}")
    else:
        c.keys(gates, GATE_KEYS, "gates")

    if check_files and job_dir is not None:
        settings = settings or load_settings()
        refs = [(f"sources.{n}.path", s["path"]) for n, s in sources.items() if isinstance(s, dict) and "path" in s]
        refs += [("script", data["script"])] if isinstance(data.get("script"), str) else []
        refs += [("graphics.composition", gfx["composition"])] if isinstance(gfx, dict) and "composition" in gfx else []
        refs += [(f"custom[{i}]", s) for i, s in enumerate(custom) if isinstance(s, str)]
        for w, ref in refs:
            try:
                if not settings.resolve(ref, job_dir).exists():
                    c.err(w, f"file not found: {settings.resolve(ref, job_dir)}")
            except SettingsError as e:
                c.err(w, str(e))
    return c.errors


@dataclass
class Job:
    dir: Path
    data: dict

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def length(self) -> float | None:
        return length(self.data)

    def source(self, name: str, settings: Settings) -> Path:
        return settings.resolve(self.data["sources"][name]["path"], self.dir)


def dumps(data, indent: int = 0, width: int = 116, row: int = 170) -> str:
    """job.json as people read it: anything that fits in `width` stays on one line (a span, a source); a list or
    object whose entries each fit in `row` gets one entry per line (segments, pieces, styles); the rest is broken up."""
    one = json.dumps(data, ensure_ascii=False)
    if not isinstance(data, (dict, list)) or len(one) + indent <= width or not data:
        return one
    pad = " " * (indent + 2)
    if isinstance(data, list):
        heads, vals = [""] * len(data), list(data)
    else:
        heads, vals = [json.dumps(k, ensure_ascii=False) + ": " for k in data], list(data.values())
    flat = [h + json.dumps(v, ensure_ascii=False) for h, v in zip(heads, vals)]
    if all(len(f) + indent + 2 <= row for f in flat):
        items = [pad + f for f in flat]
    else:
        items = [pad + h + dumps(v, indent + 2, width, row) for h, v in zip(heads, vals)]
    o, c = ("[", "]") if isinstance(data, list) else ("{", "}")
    return o + "\n" + ",\n".join(items) + "\n" + " " * indent + c


def save_job(path: str | Path, data: dict) -> Path:
    f = job_file(path)
    f.write_text(dumps(data) + "\n", encoding="utf-8")
    return f


def job_file(path: str | Path) -> Path:
    p = Path(path)
    return p / "job.json" if p.is_dir() else p


def load_job(path: str | Path, settings: Settings | None = None, catalog: Catalog | None = None,
             check_files: bool = False) -> Job:
    f = job_file(path)
    if not f.exists():
        raise JobError(f, [f"no job.json at {f}"])
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise JobError(f, [f"not valid JSON: {e}"]) from None
    errors = validate(data, catalog, f.parent, settings, check_files)
    if errors:
        raise JobError(f, errors)
    return Job(f.parent, data)
