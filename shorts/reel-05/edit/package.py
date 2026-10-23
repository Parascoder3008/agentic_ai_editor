"""Reel-05 publish assets: per-variant SRT captions (from words_master.json and plan.VARIANTS) and cover.jpg
(the hook frame where he turns the phone to camera, with a 4-word title inside the IG safe zone).
Usage: python package.py"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
import captions_ass as ca  # noqa: E402
from plan import VARIANTS  # noqa: E402

ED = Path(__file__).resolve().parent
PUB = ED.parent / "publish"
PUB.mkdir(exist_ok=True)
FONTS = Path(r"C:\Users\PARAS ARORA\AI_Editor\fonts")
words = json.loads((ED / "words_master.json").read_text(encoding="utf-8"))["words"]


def srt_time(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


for name, v in VARIANTS.items():
    out, off = [], 0.0
    for a, b in v["ranges"]:
        ws = [dict(w, start=w["start"] - a + off, end=min(w["end"], b) - a + off) for w in words if a <= w["start"] < b]
        out += ws; off += b - a
    lines = [f"{i}\n{srt_time(c[0]['start'])} --> {srt_time(c[-1]['end'])}\n{' '.join(w['text'] for w in c)}\n"
             for i, c in enumerate(ca.chunks(out), 1)]
    (PUB / f"REEL05_{name}.srt").write_text("\n".join(lines), encoding="utf-8")
    print(f"REEL05_{name}.srt: {len(lines)} cues")

# cover: base frame at 4.6 s (phone turned to camera, closed-mouth smile) + title, all inside x 90-930, y 200-1560
frame = ED / "cover_src.png"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "4.6", "-i", str(ED / "base_video.mp4"), "-frames:v", "1", str(frame)], check=True)
im = Image.open(frame).convert("RGB")
shade = Image.new("L", im.size, 0); ImageDraw.Draw(shade).rectangle([0, 1180, 1080, 1600], fill=150)
im = Image.composite(Image.new("RGB", im.size, (12, 14, 15)), im, shade.filter(ImageFilter.GaussianBlur(60)))
d = ImageDraw.Draw(im)
f1, f2 = ImageFont.truetype(str(FONTS / "Inter-ExtraBold.ttf"), 64), ImageFont.truetype(str(FONTS / "Inter-Black.ttf"), 76)
for text, font, y, fill in (("CLAUDE ka apna", f1, 1250, (255, 255, 255)), ("WhatsApp NUMBER", f2, 1335, (26, 159, 209))):
    w = d.textlength(text, font=font); x = (1080 - w) / 2
    assert 90 <= x and x + w <= 930, (text, x, w)
    d.text((x + 4, y + 6), text, font=font, fill=(0, 0, 0))
    d.text((x, y), text, font=font, fill=fill)
im.save(PUB / "cover.jpg", quality=92)
print("cover.jpg")
