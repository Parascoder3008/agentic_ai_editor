"""Publish assets: an SRT per variant and the cover image (ported from reel-05's package.py).

job.json "package":
  prefix   file name prefix, e.g. "REEL05" -> REEL05_instagram.srt
  cover    {"frame": "edit/cover_src.png" | "at": 4.6,           a still, or a time in the composed picture
            "shade": {"y": [1180, 1600], "amount": 150, "blur": 60, "color": "#0C0E0F"},
            "lines": [{"text", "font": "Inter-ExtraBold", "size", "y", "color"}],
            "shadow": [4, 6], "safe": [90, 930]}                  every title line must fit inside safe x
"""
import subprocess
from pathlib import Path

PACKAGE_KEYS = {"prefix", "cover"}
COVER_KEYS = {"frame", "at", "shade", "lines", "shadow", "safe"}
LINE_KEYS = {"text", "font", "size", "y", "color"}
SAFE = [90, 930]                                     # Instagram UI covers the rest (measured on the Equal ad)


def _rgb(c: str) -> tuple:
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def cover(frame: Path, cfg: dict, fonts: Path, out: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont     # only the cover needs Pillow

    im = Image.open(frame).convert("RGB")
    sh = cfg.get("shade")
    if sh:
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).rectangle([0, sh["y"][0], im.size[0], sh["y"][1]], fill=sh.get("amount", 150))
        im = Image.composite(Image.new("RGB", im.size, _rgb(sh.get("color", "#0C0E0F"))), im,
                             mask.filter(ImageFilter.GaussianBlur(sh.get("blur", 60))))
    d = ImageDraw.Draw(im)
    dx, dy = cfg.get("shadow", [4, 6])
    lo, hi = cfg.get("safe", SAFE)
    for ln in cfg["lines"]:
        font = ImageFont.truetype(str(fonts / f"{ln['font']}.ttf"), ln["size"])
        w = d.textlength(ln["text"], font=font)
        x = (im.size[0] - w) / 2
        if not (lo <= x and x + w <= hi):
            raise ValueError(f"cover line {ln['text']!r} is {w:.0f} px wide and doesn't fit inside x {lo}-{hi} "
                             "(Instagram covers the rest); shorten it or lower its size")
        d.text((x + dx, ln["y"] + dy), ln["text"], font=font, fill=(0, 0, 0))
        d.text((x, ln["y"]), ln["text"], font=font, fill=_rgb(ln.get("color", "#FFFFFF")))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=92)
    return out


def grab_frame(video: Path, at: float, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-i", str(video), "-frames:v", "1", str(out)],
                   check=True)
    return out


def check(pkg, data: dict) -> list:
    if not isinstance(pkg, dict):
        return ["package: must be an object"]
    errs = [f"package: unknown key {k!r}" for k in sorted(set(pkg) - PACKAGE_KEYS)]
    if "prefix" in pkg and not (isinstance(pkg["prefix"], str) and pkg["prefix"]):
        errs.append("package.prefix: file name prefix, e.g. \"REEL06\"")
    c = pkg.get("cover")
    if c is None:
        return errs
    if not isinstance(c, dict):
        return errs + ["package.cover: must be an object"]
    errs += [f"package.cover: unknown key {k!r}" for k in sorted(set(c) - COVER_KEYS)]
    if "frame" not in c and "at" not in c:
        errs.append("package.cover: give \"at\" (seconds into the picture) or \"frame\" (a still image)")
    lines = c.get("lines")
    if not isinstance(lines, list) or not lines:
        errs.append("package.cover.lines: at least one title line")
        lines = []
    for i, ln in enumerate(lines):
        p = f"package.cover.lines[{i}]"
        if not isinstance(ln, dict):
            errs.append(f"{p}: must be an object")
            continue
        errs += [f"{p}: unknown key {k!r}" for k in sorted(set(ln) - LINE_KEYS)]
        for k, t in (("text", str), ("font", str), ("size", int), ("y", int)):
            if not isinstance(ln.get(k), t):
                errs.append(f"{p}.{k}: required")
    return errs
