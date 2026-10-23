"""Find the real gap between two words near master time t: prints the 10 ms RMS dB curve in [t-0.3, t+0.3]
(one char per 10 ms: '#' speech > -40 dB, '+' > -55, '.' quieter) and the deepest valley.
Usage: python wordgap.py t1 [t2 ...]
"""
import subprocess
import sys

import numpy as np

WAV = r"D:\october videos\ai editor\ai editor.wav"
x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", WAV, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                                 capture_output=True, check=True).stdout, np.float32)
db = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(160) / 160, mode="same"))[::160] + 1e-9)
for t in map(float, sys.argv[1:]):
    a, b = int((t - 0.3) * 100), int((t + 0.3) * 100)
    seg = db[a:b]
    bar = "".join("#" if v > -40 else "+" if v > -55 else "." for v in seg)
    v = a + int(np.argmin(seg))
    print(f"{t:8.2f}: {bar[:30]}|{bar[30:]}   deepest {v / 100:.2f}s ({db[v]:.0f} dB)")
