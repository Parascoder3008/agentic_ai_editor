"""Projects: the job folders the app knows, what state each is in, and new ones made from a brief.

A project is a folder with a job.json (shorts/reel-05, jobs/<slug>, clients/<slug>, ...). A brief that can't be a
job yet (an avatar topic waiting for its script and render) is a folder with brief.json only.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

from ..job import JobError, load_job, save_job
from ..settings import REPO

ROOTS = ("jobs", "shorts", "clients", "ads")
# Stages in pipeline order with the file that shows each ran.
STAGE_FILES = [("transcribe", "build/words_*.json"), ("cut", "build/pieces.json"), ("captions", "build/words.json"),
               ("storyboard", "build/storyboard.json"), ("voice", "build/voice.wav"), ("sfx", "build/sfx.wav"),
               ("music", "build/music.wav"), ("mix", "build/mix.json"), ("graphics", "build/graphics.key"),
               ("effects", "build/effects/*/.rendered"), ("base", "build/base.mp4"), ("picture", "build/picture.json"), ("deliver", "build/deliver.json"),
               ("qa", "build/qa/qa.json")]
FPS = (24, 25, 30, 50, 60)


def discover(repo: Path = REPO) -> list:
    """Every folder under the job roots with a job.json or a brief.json, relative to the repo."""
    out = set()
    for root in ROOTS:
        for f in (repo / root).glob("*/job.json"):
            out.add(f.parent.relative_to(repo).as_posix())
        for f in (repo / root).glob("*/brief.json"):
            out.add(f.parent.relative_to(repo).as_posix())
    return sorted(out)


def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _has(name: str, data: dict) -> bool:
    """Whether this job has the stage at all (no graphics, no graphics stage)."""
    words = (data.get("captions") or {}).get("words") or {}
    return {"transcribe": any(str(v).startswith("build/words_") for v in (words.get("aligned") or {}).values()),
            "cut": "cut" in data, "captions": bool(words), "graphics": "graphics" in data, "effects": bool(data.get("effects")),
            "sfx": "sfx" in data, "music": "music" in data}.get(name, True)


def stages(d: Path, data: dict | None) -> list:
    """[{stage, done}] for the stages this job has, in pipeline order."""
    rendered = isinstance(data, dict) and (data.get("graphics") or {}).get("render")     # graphics made outside
    return [{"stage": name, "done": (d / rendered).exists() if name == "graphics" and rendered else any(d.glob(pat))}
            for name, pat in STAGE_FILES if not isinstance(data, dict) or _has(name, data)]


def state(repo: Path, rel: str, settings, catalog) -> dict:
    """Everything the Projects screen and a project's header show."""
    d = repo / rel
    brief = _read(d / "brief.json") or {}
    info = {"path": rel, "brief": brief, "errors": [], "has_job": (d / "job.json").exists()}
    data = None
    if info["has_job"]:
        try:
            data = load_job(d, settings, catalog).data
        except JobError as e:
            info["errors"] = e.errors
            data = _read(d / "job.json")
    info["job"] = data
    info["title"] = (data or {}).get("title") or brief.get("title") or rel.split("/")[-1]
    info["mode"] = (data or {}).get("mode") or brief.get("mode", "footage")
    info["stages"] = stages(d, data if isinstance(data, dict) else None) if info["has_job"] else []
    qa = _read(d / "build/qa/qa.json")
    info["qa"] = {"score": qa["score"], "passed": qa["passed"]} if qa else None
    gates = (data or {}).get("gates", {}) if isinstance(data, dict) else {}
    done = {s["stage"] for s in info["stages"] if s["done"]}
    if not info["has_job"]:
        if info["mode"] != "avatar":
            info["next"] = "brief"
        else:                                         # the avatar studio's steps, in order
            info["next"] = ("script" if not (d / "script.txt").exists() else
                            "avatar" if (brief.get("render") or {}).get("status") != "failed" else "avatar failed")
    elif info["errors"]:
        info["next"] = "fix job.json"
    elif "storyboard" in done and not gates.get("storyboard_approved"):
        info["next"] = "approve storyboard"
    elif not gates.get("storyboard_approved"):
        info["next"] = "storyboard"
    elif "deliver" in done and not gates.get("final_approved"):
        info["next"] = "approve final"
    elif "qa" in done:
        info["next"] = "delivered" if qa and qa["passed"] else "fix QA"
    else:
        info["next"] = "render"
    info["deliveries"] = (_read(d / "build/deliver.json") or {}).get("variants", {})
    return info


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:48] or "project"


def probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True)
    try:
        j = json.loads(out.stdout)
        st = j["streams"][0]
        num, den = st["r_frame_rate"].split("/")
        return {"size": [st["width"], st["height"]], "fps": int(num) / int(den), "duration": float(j["format"]["duration"])}
    except (ValueError, KeyError, IndexError, ZeroDivisionError):
        return {}


def brand_captions(sources: list) -> dict:
    """Captions in the house style (CLAUDE.md: Inter bold, white with a void outline, blue keyword), from the
    transcribe stage's words for each source."""
    return {"words": {"from": "pieces", "aligned": {s: f"build/words_{s}.json" for s in sources}},
            "styles": {"Cap": {"size": 70, "outline_color": "#0C0E0F", "back_color": "#0000009B", "outline": 6, "shadow": 2,
                               "margins": [150, 150], "baseline": 1440}},
            "highlight": {"color": "#3AB0D8"}, "break_at_cuts": True}


def variants(platforms: list, ranges=None) -> dict:
    out = {}
    if "instagram" in platforms:
        out["instagram"] = {"freeze": 0.6, "note": "follow + comment KEYWORD, link in DM"}
    if "youtube" in platforms:
        out["youtube"] = {"freeze": 0.4, "note": "channel description link"}
    return out or {"main": {"freeze": 0.4}}


def create(repo: Path, brief: dict, uploads: list) -> str:
    """A new project from the Brief screen. Footage and client briefs with a take become a runnable job: the whole take
    kept (the cutter removes the silences), transcribed, captioned in the house style, framed about the centre.
    Avatar briefs start as brief.json + script.txt until the avatar is rendered."""
    mode = brief.get("mode", "footage")
    if mode not in ("footage", "avatar", "client"):
        raise ValueError("mode must be footage, avatar or client")
    name = slug(brief.get("slug") or brief.get("title") or "project")
    root = repo / ("clients" if mode == "client" else "jobs")
    d = root / name
    n = 2
    while d.exists():
        d = root / f"{name}-{n}"
        n += 1
    (d / "raw").mkdir(parents=True)
    keep = {k: brief[k] for k in ("title", "mode", "platforms", "cta", "style", "language", "aspect", "topic", "client",
                                  "references", "notes") if k in brief}
    (d / "brief.json").write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding="utf-8")
    if brief.get("script"):
        (d / "script.txt").write_text(brief["script"].strip() + "\n", encoding="utf-8")
    files = []
    for up in uploads:
        dst = d / "raw" / Path(up["name"]).name
        shutil.move(str(up["path"]), dst)
        files.append(dst)
    takes = [f for f in files if f.suffix.lower() in (".mp4", ".mov", ".mkv", ".mxf", ".m4v")]
    if mode != "avatar" and takes:
        _footage_job(d, keep, takes)
    return d.relative_to(repo).as_posix()


def window(src: list, out: list) -> list:
    """[w, h, x, y]: the centred window of a source frame with the output's shape."""
    sw, sh = src
    if sw / sh > out[0] / out[1]:
        cw = int(sh * out[0] / out[1]) // 2 * 2
        return [cw, sh, (sw - cw) // 2, 0]
    ch = int(sw * out[1] / out[0]) // 2 * 2
    return [sw, ch, 0, (sh - ch) // 2]


def avatar_job(d: Path, brief: dict, video: Path):
    """The job for a rendered avatar: one face beat over the whole render (the Story Editor plans the beats, effects
    and B-roll from here), captions from the transcribe stage's words."""
    size = [1920, 1080] if brief.get("aspect") == "16:9" else [1080, 1920]
    info = probe(video)
    fps = min(FPS, key=lambda f: abs(f - info.get("fps", 25)))
    dur = round(int(info.get("duration", 10.0) * fps) / fps, 3)
    look = brief.get("look") or {}
    data = {"id": d.name, "title": brief.get("title", d.name), "mode": "avatar", "fps": fps, "size": size,
            "language": brief.get("language", "hi"),
            "sources": {"avatar": {"path": video.relative_to(d).as_posix(), "rights": "generated",
                                   "note": f"HeyGen render of look {look.get('name', look.get('id', '?'))}"}},
            "timeline": [{"t": [0.0, dur], "layout": "face", "src": "avatar", "in": 0.0,
                          "note": "the whole render; the Story Editor plans the beats"}],
            "layouts": {"face": {"crop": window(info.get("size", size), size)}},
            "variants": variants(brief.get("platforms", ["instagram", "youtube"])),
            "captions": {**{k: v for k, v in brand_captions(["avatar"]).items() if k != "break_at_cuts"},
                         "words": {"from": "aligned", "source": "avatar", "file": "build/words_avatar.json",
                                   "key": "words"}},
            "mix": {"voice": "avatar"}, "package": {"prefix": d.name.upper().replace("-", "")[:16]},
            "gates": {"storyboard_approved": False, "final_approved": False},
            "notes": "Made by the app from the HeyGen render. Captions come from the transcribe stage."}
    save_job(d, data)


def _footage_job(d: Path, brief: dict, takes: list):
    size = [1920, 1080] if brief.get("aspect") == "16:9" else [1080, 1920]
    names = [chr(ord("a") + i) for i in range(len(takes))]
    info = probe(takes[0])
    fps = min(FPS, key=lambda f: abs(f - info.get("fps", 25)))
    dur = int(info.get("duration", 10.0) * fps) / fps
    rights = "client" if brief["mode"] == "client" else "own"
    cam = {"head": [size[0] // 2, int(size[1] * 0.4)]}
    src = info.get("size", size)
    if abs(src[0] / src[1] - size[0] / size[1]) > 0.01:
        cam["crop"] = window(src, size)
    data = {"id": d.name, "title": brief.get("title", d.name), "mode": brief["mode"], "fps": fps, "size": size,
            "language": brief.get("language", "hi"),
            "sources": {n: {"path": f"raw/{t.name}", "rights": rights} for n, t in zip(names, takes)},
            "cut": {"mode": "spans", "source": "a", "keep": [[0.0, round(dur, 3), "take", "whole take; the cutter removes "
                                                                                       "silences, the Story Editor trims"]]},
            "layouts": {"camera": cam}, "variants": variants(brief.get("platforms", ["instagram", "youtube"])),
            "captions": brand_captions(["a"]), "mix": {}, "package": {"prefix": d.name.upper().replace("-", "")[:16]},
            "gates": {"storyboard_approved": False, "final_approved": False},
            "notes": "Made from the brief by the app. Every take is a source; the cut starts from take a."}
    save_job(d, data)
