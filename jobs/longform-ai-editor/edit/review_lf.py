"""Self-review of the long-form preview: labelled frame sheets at every graphic + every screen shot +
evenly spaced camera samples, plus audio QA (LUFS / true peak / effects-over-voice per graphic)."""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

E = Path(r"C:\Users\PARAS ARORA\AI_Editor\inbox\longform-ai-editor\edit")
cfg = json.load(open(E / "lf.json"))
video = Path(sys.argv[1]) if len(sys.argv) > 1 else E / "longform_preview.mp4"
out = E / "review_lf"; out.mkdir(exist_ok=True)
for f in out.glob("*.jpg"):
    f.unlink()

marks = []   # (time, label)
for ov in cfg["overlays"]:
    marks.append((ov["start"] + 1.0, Path(ov["file"]).parent.name))
t = 42.40
for s in cfg["segments"][1:]:
    d = s["m1"] - s["m0"]
    if s["type"] == "scr":
        marks.append((t + d / 2, "scr " + "x".join(map(str, s["crop"][2:]))))
    t += d
for k in range(0, int(t), 45):
    marks.append((k + 3.0, "sample"))
marks.sort()


def grab(tt):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{tt:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=480:270",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return Image.frombytes("RGB", (480, 270), raw) if len(raw) == 480 * 270 * 3 else Image.new("RGB", (480, 270))


ims = []
for tt, lab in marks:
    im = grab(tt); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 230, 15], fill=(0, 0, 0)); d.text((3, 2), f"{int(tt // 60)}:{tt % 60:05.2f} {lab}", fill=(255, 255, 0))
    ims.append(im)
cols, per = 5, 25
for p in range(0, len(ims), per):
    grp = ims[p:p + per]; rows = (len(grp) + cols - 1) // cols
    S = Image.new("RGB", (cols * 480, rows * 270))
    for k, im in enumerate(grp):
        S.paste(im, ((k % cols) * 480, (k // cols) * 270))
    S.save(out / f"sheet_{p // per:02d}.jpg", quality=82)
print(f"{len(ims)} review frames -> {out}")

# ---- audio QA
r = subprocess.run(["ffmpeg", "-i", str(video), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
summ = r[r.rfind("Summary:"):]
print(" ".join(l.strip() for l in summ.splitlines() if l.strip().startswith(("I:", "LRA:", "Peak:"))))
