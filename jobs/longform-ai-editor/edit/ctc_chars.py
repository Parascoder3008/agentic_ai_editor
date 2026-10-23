"""Letter-level CTC timeline (20 ms frames) for short master windows: prints char@time, '|' marks gaps >= 60 ms.
Usage: python ctc_chars.py t0:t1 [t0:t1 ...]"""
import subprocess, sys
import numpy as np, torch
from torchaudio.pipelines import MMS_FA as bundle
SR = 16000
model, labels = bundle.get_model(with_star=False).eval(), bundle.get_labels(star=None)
WAV = r"D:\october videos\ai editor\ai editor.wav"
for arg in sys.argv[1:]:
    a, b = map(float, arg.split(":")); lo = a - 1.0
    x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-ss", str(lo), "-to", str(b + 1.0), "-i", WAV, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout, np.float32).copy()
    with torch.inference_mode():
        em, _ = model(torch.from_numpy(x)[None])
    lp = em[0].log_softmax(-1); ids = lp.argmax(-1).numpy(); step = len(x) / SR / len(ids)
    out, prev, last_t = [], 0, None
    for k, i in enumerate(ids):
        t = lo + k * step
        if i != prev and i != 0 and a <= t <= b:
            if last_t is not None and t - last_t >= 0.06: out.append("|")
            out.append(f"{labels[i]}{t:.2f}"); last_t = t
        prev = i
    print(f"{a:.2f}-{b:.2f}: " + " ".join(out))
