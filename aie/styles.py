"""Style packs: one saved file per style that the agents read (typography, palette, captions, layouts, effects, sound
hits, pacing, storyboard shape). styles/<name>/style.json; the library screen lists them.

status: "built" (made from shipped reels; its components exist), "learned" (made by the Style Learner from a profile)
or "to learn" (named in the plan; waits for reference profiles and the Style Learner).
use: "own" (Paras's brand: AI-OS Blue only), "client" (a client's look; never in Paras's own reels), "any".
"captions" is a job.json captions block the Story Editor can drop into a job as is.
"""
import json
from pathlib import Path

from .settings import REPO

STATUS = {"built", "learned", "to learn"}
USE = {"own", "client", "any"}
KEYS = {"name", "title", "status", "use", "look", "best_for", "learned_from", "jobs", "type", "palette", "captions",
        "layouts", "effects", "components", "sfx", "hits", "pacing", "storyboard", "references", "notes", "preview",
        "version"}


def check(d: Path, data) -> list:
    w = f"styles/{d.name}"
    if not isinstance(data, dict):
        return [f"{w}: style.json must be an object"]
    errs = [f"{w}: unknown key {k!r}" for k in sorted(set(data) - KEYS)]
    if data.get("name") != d.name:
        errs.append(f'{w}: "name" must be {d.name!r}')
    for k in ("title", "look"):
        if not isinstance(data.get(k), str) or not data[k]:
            errs.append(f"{w}: {k!r} is required")
    if data.get("status") not in STATUS:
        errs.append(f"{w}: status must be one of {sorted(STATUS)}")
    if data.get("use") not in USE:
        errs.append(f"{w}: use must be one of {sorted(USE)}")
    if data.get("status") in ("built", "learned"):
        for k in ("palette", "type", "pacing"):
            if k not in data:
                errs.append(f"{w}: a {data['status']} style needs {k!r}")
    return errs


def load(root: Path | None = None) -> tuple:
    root = Path(root or REPO / "styles")
    packs, errors = {}, []
    for f in sorted(root.glob("*/style.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            errors.append(f"styles/{f.parent.name}: not valid JSON ({e})")
            continue
        e = check(f.parent, data)
        errors += e
        if not e:
            packs[f.parent.name] = {**data, "dir": f.parent}
    return packs, errors


def library(settings=None) -> dict:
    root = settings.path("styles") if settings and settings.data.get("styles") else None
    packs, errors = load(root)
    out = []
    for name, p in packs.items():
        item = {k: v for k, v in p.items() if k != "dir"}
        item["preview"] = f"/styles/{name}/preview.jpg" if (p["dir"] / "preview.jpg").exists() else None
        out.append(item)
    order = {"built": 0, "learned": 1, "to learn": 2}
    out.sort(key=lambda p: (order[p["status"]], p["title"]))
    return {"styles": out, "errors": errors}
