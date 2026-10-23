"""The effects catalog: one folder per effect under effects/, described by effects/<name>/effect.json.

A job places an effect by name, time and parameters:
    {"effect": "kw", "at": 19.30, "dur": 2.6, "params": {"KICK": "Edited by", "MAIN": "Claude Opus"}}
check_placement() rejects unknown effects, missing required parameters, unknown parameters and values outside
"choices" before anything renders. Effect.html() fills a hyperframes-template's {{PARAM}} slots for one use:
defaults, the job's values, DUR (the duration) and "derived" values looked up from another parameter
(kw's SIDE "right" -> SIDECSS "right: 80px; text-align: left;").
"""
import json
from dataclasses import dataclass
from pathlib import Path

from .settings import REPO

KINDS = {"overlay", "picture", "transition", "caption", "sound"}
ENGINES = {"hyperframes-template", "hyperframes-composition", "ffmpeg", "python", "synth"}
FORMATS = {"16:9", "9:16", "1:1"}
EFFECT_KEYS = {"name", "title", "description", "kind", "engine", "source", "params", "duration", "formats",
               "brand", "origin", "license", "tags", "preview", "derived"}
PARAM_KEYS = {"required", "default", "choices", "description"}
PLACEMENT_KEYS = {"effect", "at", "dur", "params", "id", "variants", "note"}


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


@dataclass
class Effect:
    name: str
    dir: Path
    data: dict

    @property
    def params(self) -> dict:
        return self.data.get("params", {})

    @property
    def formats(self) -> list:
        return self.data.get("formats", [])

    def filled(self, given: dict) -> dict:
        """Parameter values for one use: defaults overlaid with what the job gave."""
        return {**{k: p["default"] for k, p in self.params.items() if "default" in p}, **given}

    @property
    def source_path(self) -> Path:
        src = self.data["source"]
        return REPO / src if (REPO / src).exists() else self.dir / src

    def html(self, given: dict, dur: float, templates: Path | None = None) -> str:
        """The template with every {{SLOT}} filled for one use. templates overrides the folder of a source under
        templates/ (the "templates" machine setting)."""
        if self.data["engine"] != "hyperframes-template":
            raise ValueError(f"{self.name}: only hyperframes-template effects are filled from parameters")
        v = {**self.filled(given), "DUR": str(dur)}
        for name, d in self.data.get("derived", {}).items():
            v[name] = d["map"][v[d["from"]]]
        src = self.source_path
        if templates is not None and Path(self.data["source"]).parts[0] == "templates":
            src = Path(templates, *Path(self.data["source"]).parts[1:])
        html = src.read_text(encoding="utf-8")
        for k, val in v.items():
            html = html.replace("{{" + k + "}}", str(val))
        if "{{" in html:
            i = html.index("{{")
            raise ValueError(f"{self.name}: unfilled slot near {html[i:i + 30]!r}")
        return html


def _check_effect(d: Path, data, errs: list) -> None:
    w = f"effects/{d.name}"
    if not isinstance(data, dict):
        errs.append(f"{w}: effect.json must be an object")
        return
    for k in sorted(set(data) - EFFECT_KEYS):
        errs.append(f"{w}: unknown key {k!r}")
    if data.get("name") != d.name:
        errs.append(f"{w}: \"name\" must be {d.name!r} (the folder name)")
    for k in ("title", "kind", "engine", "source", "origin", "license"):
        if not isinstance(data.get(k), str) or not data.get(k):
            errs.append(f"{w}: {k!r} is required")
    if data.get("kind") not in KINDS:
        errs.append(f"{w}: kind must be one of {sorted(KINDS)}")
    if data.get("engine") not in ENGINES:
        errs.append(f"{w}: engine must be one of {sorted(ENGINES)}")
    src = data.get("source")
    if isinstance(src, str) and not ((REPO / src).exists() or (d / src).exists()):
        errs.append(f"{w}: source {src!r} not found (relative to the repo or the effect folder)")
    params = data.get("params", {})
    if not isinstance(params, dict):
        errs.append(f"{w}: params must be an object")
        params = {}
    for name, p in params.items():
        if not isinstance(p, dict):
            errs.append(f"{w}: param {name!r} must be an object")
            continue
        for k in sorted(set(p) - PARAM_KEYS):
            errs.append(f"{w}: param {name!r} has unknown key {k!r}")
        if p.get("required") and "default" in p:
            errs.append(f"{w}: param {name!r} is required, so it can't have a default")
        if "choices" in p and "default" in p and p["default"] not in p["choices"]:
            errs.append(f"{w}: param {name!r} default {p['default']!r} is not one of its choices")
    dur = data.get("duration", {})
    if not isinstance(dur, dict) or not all(_num(v) and v > 0 for v in dur.values()) \
            or set(dur) - {"default", "min", "max"}:
        errs.append(f"{w}: duration must be {{default, min, max}} with positive numbers")
    fm = data.get("formats", [])
    if not isinstance(fm, list) or set(fm) - FORMATS:
        errs.append(f"{w}: formats must be a list from {sorted(FORMATS)}")
    for name, dv in (data.get("derived") or {}).items() if isinstance(data.get("derived", {}), dict) else []:
        src_p = params.get(dv.get("from")) if isinstance(dv, dict) else None
        if not (isinstance(dv, dict) and set(dv) == {"from", "map"} and isinstance(dv["map"], dict) and src_p):
            errs.append(f'{w}: derived {name!r} must be {{"from": <param>, "map": {{value: text}}}}')
        elif "choices" in src_p and set(src_p["choices"]) - set(dv["map"]):
            errs.append(f"{w}: derived {name!r} has no text for {sorted(set(src_p['choices']) - set(dv['map']))}")
    if not isinstance(data.get("derived", {}), dict):
        errs.append(f"{w}: derived must be an object")
    if data.get("brand") not in (None, "own"):
        errs.append(f'{w}: brand must be "own" (Paras-only) or left out')


class Catalog:
    def __init__(self, effects: dict, errors: list):
        self.effects = effects
        self.errors = errors

    @classmethod
    def load(cls, root: Path | None = None) -> "Catalog":
        root = Path(root) if root else REPO / "effects"
        effects, errors = {}, []
        for f in sorted(root.glob("*/effect.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"effects/{f.parent.name}: effect.json is not valid JSON ({e})")
                continue
            n = len(errors)
            _check_effect(f.parent, data, errors)
            if len(errors) == n:
                effects[f.parent.name] = Effect(f.parent.name, f.parent, data)
        return cls(effects, errors)

    def get(self, name: str) -> Effect | None:
        return self.effects.get(name)

    def check_placement(self, p, where: str, mode: str | None = None, aspect: str | None = None,
                        length: float | None = None) -> list:
        if not isinstance(p, dict):
            return [f"{where}: must be an object like {{\"effect\": \"kw\", \"at\": 1.2}}"]
        errs = [f"{where}: unknown key {k!r}" for k in sorted(set(p) - PLACEMENT_KEYS)]
        name = p.get("effect")
        fx = self.get(name) if isinstance(name, str) else None
        if fx is None:
            known = ", ".join(sorted(self.effects)) or "none yet"
            return errs + [f"{where}: unknown effect {name!r} (catalog has: {known})"]
        at, dur = p.get("at"), p.get("dur", fx.data.get("duration", {}).get("default"))
        if not _num(at) or at < 0:
            errs.append(f"{where}: \"at\" must be a time in seconds >= 0")
        if dur is None:
            errs.append(f"{where}: \"dur\" is required ({name} has no default duration)")
        elif not _num(dur) or dur <= 0:
            errs.append(f"{where}: \"dur\" must be a positive number of seconds")
        else:
            lim = fx.data.get("duration", {})
            if "min" in lim and dur < lim["min"] or "max" in lim and dur > lim["max"]:
                errs.append(f"{where}: dur {dur} is outside {name}'s range {lim.get('min', 0)}-{lim.get('max', '...')} s")
            if length is not None and _num(at) and at + dur > length + 1e-6:
                errs.append(f"{where}: ends at {at + dur:.2f} s, after the video ends ({length:.2f} s)")
        given = p.get("params", {})
        if not isinstance(given, dict):
            return errs + [f"{where}: params must be an object"]
        for k in sorted(set(given) - set(fx.params)):
            errs.append(f"{where}: {name} has no parameter {k!r} (it has: {', '.join(fx.params) or 'none'})")
        for k, spec in fx.params.items():
            if spec.get("required") and k not in given:
                errs.append(f"{where}: {name} needs parameter {k!r}")
            if k in given and "choices" in spec and given[k] not in spec["choices"]:
                errs.append(f"{where}: {name} {k}={given[k]!r} is not one of {spec['choices']}")
        if fx.data.get("brand") == "own" and mode == "client":
            errs.append(f"{where}: {name} carries Paras's own brand and can't go into a client job")
        if aspect and fx.formats and aspect not in fx.formats:
            errs.append(f"{where}: {name} is built for {', '.join(fx.formats)}, not {aspect}")
        return errs
