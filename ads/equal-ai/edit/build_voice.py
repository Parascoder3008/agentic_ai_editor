"""Voice stem on the output timeline: intro lines placed over the AI shots, body ranges concatenated from
intro_end. 15 ms fades at every edge. Writes voice.wav (48 kHz mono) and fa_lines.json for force_align.py."""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ED = Path(__file__).resolve().parent
E = json.loads((ED / "edl.json").read_text(encoding="utf-8"))
x, sr = sf.read(r"C:\Users\PARAS ARORA\Desktop\equal ai\equal ai.wav")
x = x.mean(1) if x.ndim > 1 else x
SR = 48000
x = resample_poly(x, SR, sr).astype(np.float32)
FADE = int(0.015 * SR)

out = np.zeros(int((E["length"] + 1) * SR), np.float32)
lines = []


def put(lav, at, sid, text, gain=1.0):
    a, b = int(lav[0] * SR), int(lav[1] * SR)
    seg = x[a:b].copy() * gain
    r = np.linspace(0, 1, FADE)
    seg[:FADE] *= r; seg[-FADE:] *= r[::-1]
    i = int(round(at * SR))
    out[i:i + len(seg)] += seg
    lines.append({"id": sid, "win": [round(at, 3), round(at + len(seg) / SR, 3)], "text": text})


for v in E["intro"]:
    put(v["lav"], v["at"], v["id"], v["text"])
for s in E["body"]:
    put(s["lav"], s["out"][0], s["id"], s["text"])

sf.write(ED / "voice.wav", out, SR, subtype="PCM_24")
(ED / "fa_lines.json").write_text(json.dumps(lines, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"voice.wav {len(out) / SR:.2f}s, {len(lines)} lines")
