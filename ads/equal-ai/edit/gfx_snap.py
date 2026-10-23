"""QA stills: seek the gfx timeline (emulating HyperFrames clip visibility) and composite over base_video frames.
Usage: python gfx_snap.py t1,t2,...  -> qa/gfx_<t>.jpg + qa/gfx_sheet.jpg"""
import subprocess
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ED = Path(__file__).resolve().parent
QA = ED / "qa"; QA.mkdir(exist_ok=True)
times = [float(t) for t in sys.argv[1].split(",")]
SEEK = """t => { document.querySelectorAll('.clip').forEach(el => { const s = +el.dataset.start, d = +el.dataset.duration;
  el.style.visibility = (t >= s && t < s + d) ? 'visible' : 'hidden'; }); window.__timelines.main.seek(t, false); }"""
tiles = []
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 1080, "height": 1920})
    pg.goto((ED / "gfx" / "index.html").as_uri(), wait_until="networkidle")
    pg.evaluate("document.fonts.ready")
    for t in times:
        pg.evaluate(SEEK, t)
        pg.wait_for_timeout(60)
        png = QA / f"_g{t:.2f}.png"
        pg.screenshot(path=str(png), omit_background=True)
        fr = QA / f"_f{t:.2f}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(ED / "base_video.mkv"), "-frames:v", "1", str(fr)], check=True)
        im = Image.open(fr).convert("RGBA"); im.alpha_composite(Image.open(png).convert("RGBA"))
        im = im.convert("RGB"); im.save(QA / f"gfx_{t:.2f}.jpg", quality=88)
        tiles.append(im.resize((360, 640)))
    b.close()
cols = min(6, len(tiles)); rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 360, rows * 640))
for i, im in enumerate(tiles):
    sheet.paste(im, ((i % cols) * 360, (i // cols) * 640))
sheet.save(QA / "gfx_sheet.jpg", quality=85)
print("sheet:", QA / "gfx_sheet.jpg")
