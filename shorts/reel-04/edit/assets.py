"""Static plates for the base compositor (brand: void #0C0E0F, blue #1A9FD1, bright #3AB0D8, navy #11324C).
  bg_pip.png    dark studio plate behind the card layout (blue glow + faint grid)
  paper_bg.png  paper-cut world: navy craft paper with fibres, two torn lighter sheets, soft shadows
Usage: python assets.py"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ED = Path(__file__).resolve().parent
OUT = ED.parent / "assets"; OUT.mkdir(exist_ok=True)
W, H = 1080, 1920
rng = np.random.default_rng(4)

# ---- card-layout backdrop: Clauditing navy, faint stars, a soft coral glow (client style, not the AI-OS blue)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
glow = np.exp(-(((xx - 760) / 620) ** 2 + ((yy - 1150) / 760) ** 2)) * 0.30
base = np.array([21, 19, 43], np.float32)
coral = np.array([242, 162, 126], np.float32)
img = base + glow[..., None] * (coral - base) * 0.35
stars = rng.random((H, W)) > 0.9985
img[stars] = np.array([200, 190, 220], np.float32) * rng.uniform(0.35, 0.9, (stars.sum(), 1))
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)).save(OUT / "bg_pip.png")
# cream "UI" plate with a dot grid (product panels)
cream = np.ones((H, W, 3), np.float32) * np.array([244, 239, 232], np.float32)
dots = ((xx % 34) < 2.2) & ((yy % 34) < 2.2)
cream[dots] -= 18
Image.fromarray(np.clip(cream, 0, 255).astype(np.uint8)).save(OUT / "cream_bg.png")


# ---- paper world
def fibres(h, w, strength):
    n = rng.standard_normal((h // 4, w // 4)).astype(np.float32)
    n = np.array(Image.fromarray(((n * 40) + 128).clip(0, 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) - 128
    streak = rng.standard_normal((h, 1)).astype(np.float32) * 0.6 + rng.standard_normal((1, w)).astype(np.float32) * 0.3
    return (n * 0.5 + streak * 6) * strength


def torn(poly_pts, jag=9):
    """jagged polygon edge = torn paper"""
    out = []
    for (x0, y0), (x1, y1) in zip(poly_pts, poly_pts[1:] + poly_pts[:1]):
        n = max(2, int(np.hypot(x1 - x0, y1 - y0) / 14))
        for k in range(n):
            f = k / n
            out.append((x0 + (x1 - x0) * f + rng.uniform(-jag, jag), y0 + (y1 - y0) * f + rng.uniform(-jag, jag)))
    return out


paper = np.array([243, 237, 228], np.float32)[None, None, :] + fibres(H, W, 0.35)[..., None]
canvas = Image.fromarray(np.clip(paper, 0, 255).astype(np.uint8)).convert("RGBA")
for pts, col in (([(-40, 1180), (1120, 980), (1120, 2000), (-40, 2000)], (242, 162, 126)),     # coral
                 ([(-40, 1460), (1120, 1380), (1120, 2000), (-40, 2000)], (240, 106, 140)),    # pink
                 ([(-40, -40), (1120, -40), (1120, 300), (-40, 420)], (43, 30, 54))):           # plum
    sheet = Image.new("L", (W, H), 0); ImageDraw.Draw(sheet).polygon(torn(pts), fill=255)
    shadow = sheet.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.55))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sh.putalpha(shadow)
    canvas = Image.alpha_composite(canvas, sh.transform((W, H), Image.AFFINE, (1, 0, -6, 0, 1, -12)))
    tex = np.clip(np.array(col, np.float32)[None, None, :] + fibres(H, W, 0.3)[..., None], 0, 255).astype(np.uint8)
    layer = Image.fromarray(tex).convert("RGBA"); layer.putalpha(sheet)
    canvas = Image.alpha_composite(canvas, layer)
canvas.convert("RGB").save(OUT / "paper_bg.png")
print("assets ->", OUT)
