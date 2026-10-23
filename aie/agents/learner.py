"""The Style Learner: a style pack from 1-3 Instagram profiles. Code does the measuring, one model call writes the pack.

1. Apify lists each profile's recent reels; the 6 with the most plays are kept.
2. Each is downloaded to a temp folder: 4 frames sampled, and its cuts counted (ffmpeg scene changes), so the pack's
   pacing is measured, not guessed. The scene score follows brightness, so jump cuts on one framing (and cuts
   between shots of similar brightness) aren't counted: the measured average shot is an upper bound.
3. Sonnet looks at the frames, captions and numbers and writes the pack's fields, choosing effects from our catalog.
4. The pack is validated like any other (and once more after one repair turn); styles/<name>/style.json is written
   with "status": "learned", "approved": false, plus a contact sheet as preview.jpg. Paras approves it once.

The scraped reels only teach: the videos are deleted after measuring, and nothing scraped goes into an edit.
"""
import base64
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from ..captions import check as check_captions
from ..connectors import apify, mcp
from ..effects import Catalog
from ..styles import check as check_style
from .roster import SONNET, cost

TOP, FRAMES = 6, (0.08, 0.35, 0.6, 0.88)
SYSTEM = """You turn reference reels into a style pack for an editing pipeline. Describe what the reels do (type,
colour, caption treatment, layouts, motion, sound hits, pacing, the shape of the story), as rules an editor can follow.
Choose effects only from the catalog you are given. Output one JSON object and nothing else."""
FIELDS = """Fields to write (JSON):
  "title": a short name; "look": one line on what defines it; "best_for": the content it suits;
  "type": {"display": "<font, weight, tracking>", "accent": "<optional>"};
  "palette": 3-6 hex colours seen in the reels;
  "captions": {"styles": {"Cap": {"size": <40-90>, "outline_color": "#RRGGBB", "back_color": "#RRGGBBAA", "outline": <0-16>,
               "border": "box" (optional), "margins": [<l>, <r>], "baseline": <y on a 1920-high frame>}},
               "highlight": {"color": "#RRGGBB"}};
  "layouts": names from: camera, split, face, broll, full, screen; "effects": catalog effect names;
  "sfx": kinds from: whoosh, impact, pop, chime, tick, typing, riser, pitch_drop; "hits": one line on the sound hits;
  "pacing": {"max_static_s": <number>, "hook_s": <seconds until the hook lands>};
  "storyboard": "beat -> beat -> ..."; "notes": what to copy, and what not to (logos, faces, music)."""


class LearnError(RuntimeError):
    pass


def _ff(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-hide_banner", *map(str, args)], capture_output=True, text=True)


def measure(video: Path, seconds: float, folder: Path, n: int) -> dict:
    """4 frames (360 px wide) and the cut count of one reel."""
    frames = []
    for k, f in enumerate(FRAMES):
        out = folder / f"r{n}_{k}.jpg"
        _ff("-v", "error", "-y", "-ss", f"{max(0.0, seconds * f):.2f}", "-i", video, "-frames:v", "1", "-vf", "scale=360:-2",
            "-q:v", "4", out)
        if out.exists():
            frames.append(out)
    r = _ff("-i", video, "-vf", "select='gt(scene,0.32)',showinfo", "-an", "-f", "null", "-")
    cuts = len(re.findall(r"pts_time:", r.stderr))
    return {"frames": frames, "cuts": cuts, "avg_shot_s": round(seconds / (cuts + 1), 2) if seconds else None}


def sheet(frames: list, out: Path):
    """The pack's preview: the first frame of each reel side by side."""
    from PIL import Image
    ims = [Image.open(f).convert("RGB") for f in frames]
    h = 480
    ims = [im.resize((round(im.width * h / im.height), h)) for im in ims]
    canvas = Image.new("RGB", (sum(im.width for im in ims) + 8 * (len(ims) + 1), h + 16), (12, 14, 15))
    x = 8
    for im in ims:
        canvas.paste(im, (x, 8))
        x += im.width + 8
    canvas.save(out, quality=85)


def _json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise LearnError("the model didn't write a JSON pack")
    return json.loads(m.group(0))


def _problems(d: Path, pack: dict, catalog) -> list:
    errs = check_style(d, pack)
    if isinstance(pack.get("captions"), dict):
        errs += check_captions(pack["captions"], {"size": [1080, 1920], "sources": {}})
    errs += [f"effects: {e!r} isn't in the catalog" for e in pack.get("effects", []) if not catalog.get(e)]
    return errs


def learn(name: str, handles: list, use: str, styles_root: Path, settings, api, scrape=None, log=print) -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", name or ""):
        raise LearnError("name: lowercase letters, digits and -")
    handles = [h.strip().lstrip("@") for h in handles if h.strip()][:3]
    if not handles:
        raise LearnError("name 1-3 Instagram profiles")
    if use not in ("any", "client"):
        raise LearnError('use: "any" or "client" (Paras\'s own reels keep AI-OS Blue)')
    d = styles_root / name
    old = json.loads((d / "style.json").read_text(encoding="utf-8")) if (d / "style.json").exists() else {}
    if old.get("status") == "built":
        raise LearnError(f"{name} is a built pack (from shipped reels); learn into a new name")
    log(f"style learner: scraping {', '.join('@' + h for h in handles)} ...")
    reels = (scrape or apify.reels)(handles)
    top = sorted(reels, key=lambda r: r["plays"], reverse=True)[:TOP]
    if len(top) < 2:
        raise LearnError(f"only {len(top)} reels came back; check the handles")
    catalog = Catalog.load(settings.path("effects"))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        rows, content = [], []
        for n, r in enumerate(top):
            log(f"style learner: measuring {r['url']} ({r['plays']} plays)")
            v = mcp.download(r["video"], tmp / f"r{n}.mp4")
            m = measure(v, float(r["seconds"] or 0), tmp, n)
            v.unlink()                                       # measured; the video itself is not kept
            rows.append({**{k: r[k] for k in ("url", "owner", "plays", "seconds", "caption")},
                         "cuts": m["cuts"], "avg_shot_s": m["avg_shot_s"], "frames": m["frames"]})
            content.append({"type": "text", "text": f"Reel {n + 1}: @{r['owner']}, {r['plays']} plays, {r['seconds']:.1f} s, "
                                                    f"{m['cuts']} cuts (avg shot {m['avg_shot_s']} s). Caption: {r['caption'][:300]}"})
            content += [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                     "data": base64.b64encode(f.read_bytes()).decode()}} for f in m["frames"]]
        shots = [r["avg_shot_s"] for r in rows if r["avg_shot_s"]]
        avg = round(sum(shots) / len(shots), 2) if shots else None
        fx = "\n".join(f"- {n}: {e.data['title']} ({', '.join(e.formats)})" for n, e in sorted(catalog.effects.items()))
        content.append({"type": "text", "text": f"Our effects catalog:\n{fx}\n\n{FIELDS}\n\nWrite the pack for these "
                                                f"{len(rows)} reels."})
        msgs = [{"role": "user", "content": content}]
        spent, pack, errs = 0.0, None, []
        for attempt in range(2):
            msg = api.messages.create(model=SONNET, max_tokens=6000, system=SYSTEM, output_config={"effort": "medium"},
                                      messages=msgs)
            spent += cost(SONNET, msg.usage)
            if msg.stop_reason == "refusal":
                raise LearnError("the model declined to describe these reels")
            text = "".join(b.text for b in msg.content if b.type == "text")
            try:
                draft = _json(text)
            except (ValueError, LearnError) as e:
                errs = [f"not a JSON object ({e})"]
                draft = None
            if draft is not None:
                pack = {k: v for k, v in draft.items() if k in ("title", "look", "best_for", "type", "palette", "captions",
                                                                 "layouts", "effects", "sfx", "hits", "pacing",
                                                                 "storyboard", "notes")}
                pack.update({"name": name, "status": "learned", "use": use, "approved": False, "version": 1,
                             "learned_from": f"{', '.join('@' + h for h in handles)} (top {len(rows)} reels by plays, "
                                             f"{time.strftime('%Y-%m-%d')})",
                             "references": [r["url"] for r in rows]})
                pack["pacing"] = {**(pack.get("pacing") or {}), "avg_shot_s": avg,
                                  "measured": "scene changes over 0.32; jump cuts and cuts between shots of similar "
                                              "brightness aren't counted, so real shots can be shorter"}
                errs = _problems(d, pack, catalog)
                if not errs:
                    break
            msgs += [{"role": "assistant", "content": msg.content},
                     {"role": "user", "content": "Fix these and write the whole JSON object again:\n- " + "\n- ".join(errs)}]
        if errs:
            raise LearnError("the pack didn't validate: " + "; ".join(errs[:6]))
        d.mkdir(parents=True, exist_ok=True)
        sheet([r["frames"][0] for r in rows if r["frames"]], d / "preview.jpg")
    (d / "style.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"style learner: wrote styles/{name}/style.json (${spent:.3f}); waiting for Paras's approval")
    return {**pack, "cost": round(spent, 4)}


def approve(styles_root: Path, name: str, value: bool = True) -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", name or ""):
        raise LearnError(f"no style {name!r}")
    f = styles_root / name / "style.json"
    if not f.exists():
        raise LearnError(f"no style {name!r}")
    pack = json.loads(f.read_text(encoding="utf-8"))
    if pack.get("status") != "learned":
        raise LearnError("only learned packs wait for approval")
    pack["approved"] = bool(value)
    f.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pack
