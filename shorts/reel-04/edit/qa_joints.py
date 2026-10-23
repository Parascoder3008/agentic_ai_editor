"""Joint-level QA on the final cuts.
  1. verbatim CTC (no language model, keeps restarts/repeats) on every piece of voice.wav -> qa/verbatim.txt
  2. room tone across each audio joint: quietest 10 ms within +-60 ms of the cut vs the tone just outside (a dip = gated cut)
  3. frame pairs (last frame before | first frame after) for every cut -> qa/<name>_joints.jpg
Usage: python qa_joints.py"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
import verbatim_ctc as vc  # noqa: E402

ED = Path(__file__).resolve().parent
JOB = ED.parent
TL = json.loads((ED / "timeline.json").read_text())
v, sr = sf.read(ED / "voice.wav", dtype="float32"); v = v.mean(1)
rms = lambda a, b: 20 * np.log10(np.sqrt((v[int(a * sr): int(b * sr)] ** 2).mean()) + 1e-9)

# 1. verbatim per piece
pieces = TL["pieces"]
model, labels = vc.bundle.get_model(with_star=False).eval(), vc.bundle.get_labels(star=None)
lines = []
for p in pieces:
    s, e = p["out"]
    words = vc.words(vc.greedy(model, labels, vc.load(str(ED / "voice.wav"), s, e)))
    lines.append(f'{p["tag"]:6s} {s:6.2f}-{e:6.2f} | ' + " ".join(w[2] for w in words))
(JOB / "qa" / "verbatim.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))

# 2. room tone at joints: quietest 10 ms within +-30 ms of each cut vs the quietest 10 ms just outside it (50-150 ms
#    either side). Much quieter at the cut than around it = the joint gates to silence (a hole under the music).
print("\njoint   at-cut  around  (hole if at-cut < around - 10 dB)")
for p in TL["pieces"]:
    c = p["out"][0]
    lo = min(rms(t, t + 0.01) for t in np.arange(c - 0.03, c + 0.03, 0.005))
    ar = min(rms(t, t + 0.01) for t in [*np.arange(c - 0.15, c - 0.05, 0.005), *np.arange(c + 0.05, c + 0.15, 0.005)])
    print(f"  {c:6.2f}  {lo:6.1f}  {ar:6.1f}{'  <-- HOLE' if lo < ar - 10 else ''}")

# 3. frame pairs at every cut of each final file
for name, key, fz in (("instagram", "ig", 0.6), ("youtube", "yt", 0.4)):
    cuts, t = [], 0.0
    for a, b in TL[key]["ranges"]:
        for p in pieces:
            s, e = p["out"]
            if a - 0.01 <= s < b and s > 0.01:
                cuts.append(round(t + s - a, 2))
        if t > 0:
            cuts.append(round(t, 2))
        t += b - a
    cuts = sorted(set(cuts))
    W, H = 216, 384
    sheet = Image.new("RGB", (W * 2 * 4 + 30, (H + 20) * -(-len(cuts) // 4)), "white")
    for i, c in enumerate(cuts):
        x0, y0 = i % 4 * (W * 2 + 8), i // 4 * (H + 20)
        for j, tt in enumerate((c - 0.04, c + 0.001)):
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{tt:.3f}", "-i", str(JOB / f"REEL04_{name}.mp4"), "-frames:v", "1",
                                  "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
            sheet.paste(Image.frombytes("RGB", (W, H), raw), (x0 + j * W, y0 + 20))
        ImageDraw.Draw(sheet).text((x0 + 4, y0 + 4), f"cut {c:.2f}s", fill="black")
    out = JOB / "qa" / f"{name}_joints.jpg"; sheet.save(out, quality=88); print(out, len(cuts), "cuts")
