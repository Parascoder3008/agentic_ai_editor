"""preview.jpg for the built style packs (styles/<name>/preview.jpg): a strip of the pack's catalog effects when they
have previews, otherwise a spec card (its palette, title and look in Inter). Learned packs get their preview from
the Style Learner (frames of the reference reels) and are left alone.

Usage: python tools/style_preview.py [name ...]      (no names: every built pack)
"""
import json
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
W, H = 1280, 560
VOID = (12, 14, 15)
SHOWCASE = ("reel-hook", "reel-chat", "reel-code", "reel-cta-comment")     # shown first when a pack has them


def rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def font(size: int, bold: bool = True):
    return ImageFont.truetype(str(REPO / "fonts" / ("Inter-Bold.ttf" if bold else "Inter-Regular.ttf")), size)


def palette_bar(im: Image.Image, colors: list, y: int, h: int):
    d = ImageDraw.Draw(im)
    w = W / max(1, len(colors))
    for i, c in enumerate(colors):
        d.rectangle([round(i * w), y, round((i + 1) * w), y + h], fill=rgb(c))


def strip(pack: dict, previews: list) -> Image.Image:
    """The last frame of each effect's preview sheet (the effect fully built), four across."""
    im = Image.new("RGB", (W, H), VOID)
    shots = []
    for f in previews[:4]:
        sheet = Image.open(f).convert("RGB")
        third = sheet.width // 3
        shots.append(sheet.crop((sheet.width - third, 0, sheet.width, sheet.height)))
    fh = H - 40 - 32
    fw = round(shots[0].width * fh / shots[0].height)
    gap = (W - len(shots) * fw) // (len(shots) + 1)
    for i, shot in enumerate(shots):
        im.paste(shot.resize((fw, fh)), (gap + i * (fw + gap), 16))
    palette_bar(im, pack["palette"], H - 28, 28)
    return im


def card(pack: dict) -> Image.Image:
    im = Image.new("RGB", (W, H), VOID)
    d = ImageDraw.Draw(im)
    pal = pack["palette"]
    sw = 120
    for i, c in enumerate(pal[:6]):
        x = 64 + i * (sw + 18)
        d.rounded_rectangle([x, 300, x + sw, 300 + sw], radius=28, fill=rgb(c), outline=(58, 176, 216), width=2)
        d.text((x, 300 + sw + 14), c.upper(), font=font(22, False), fill=(223, 221, 223))
    d.text((64, 70), pack["title"], font=font(76), fill=(255, 255, 255))
    for k, line in enumerate(textwrap.wrap(pack["look"], 70)[:2]):
        d.text((64, 176 + k * 40), line, font=font(30, False), fill=(223, 221, 223))
    d.text((W - 64, 70), "spec", font=font(24), fill=(58, 176, 216), anchor="ra")
    return im


def make(d: Path) -> Path | None:
    pack = json.loads((d / "style.json").read_text(encoding="utf-8"))
    if pack["status"] != "built":
        return None
    fx = pack.get("effects", [])
    fx = [e for e in SHOWCASE if e in fx] + [e for e in fx if e not in SHOWCASE]
    previews = [REPO / "effects" / e / "preview.jpg" for e in fx]
    previews = [p for p in previews if p.exists()]
    im = strip(pack, previews) if previews else card(pack)
    out = d / "preview.jpg"
    im.save(out, quality=86)
    return out


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(p.parent.name for p in (REPO / "styles").glob("*/style.json"))
    for n in names:
        out = make(REPO / "styles" / n)
        if out:
            print(f"{n}: {out.relative_to(REPO)}")
