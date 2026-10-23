"""Contact sheet of a final cut with IG UI zones drawn. Usage: python qa_sheet.py <instagram|youtube> t1 t2 ..."""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

JOB = Path(__file__).resolve().parent.parent
name, ts = sys.argv[1], [float(t) for t in sys.argv[2:]]
W, H, COLS = 270, 480, 8
sheet = Image.new("RGB", (W * COLS, (H + 22) * -(-len(ts) // COLS)), "white")
for i, t in enumerate(ts):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(JOB / f"GENJUTSU_REEL_{name}.mp4"), "-frames:v", "1",
                          "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    im = Image.frombytes("RGB", (W, H), raw); d = ImageDraw.Draw(im); k = W / 1080
    d.line([(0, 200 * k), (W, 200 * k)], fill="red"); d.line([(0, 1560 * k), (W, 1560 * k)], fill="red")
    d.rectangle([930 * k, 1000 * k, W - 1, 1700 * k], outline="red")
    x, y = i % COLS * W, i // COLS * (H + 22)
    sheet.paste(im, (x, y + 22)); ImageDraw.Draw(sheet).text((x + 4, y + 4), f"{t:.2f}s", fill="black")
out = JOB / "qa" / f"{name}_sheet.jpg"
sheet.save(out, quality=88); print(out)
