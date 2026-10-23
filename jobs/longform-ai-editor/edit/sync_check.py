"""Verify sync offsets at several points (drift check) for camera->wav and screen->wav."""
import subprocess
import sys

import numpy as np

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
from sync_offset import offset  # noqa: E402

D = r"D:\october videos\ai editor"
W = D + r"\ai editor.wav"


def seg(path, ss, t, track=0):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(max(0, ss)), "-t", str(t), "-i", path, "-map", f"0:a:{track}",
                          "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    e = np.abs(x[: len(x) // 4 * 4]).reshape(-1, 4).mean(1)
    e -= e.mean()
    return e / (e.std() + 1e-9)


def drift(name, src, coarse, points, track=0):
    # coarse: src time t <-> wav time t + coarse
    print(f"--- {name} (coarse {coarse:+.3f})")
    for t in points:
        w0 = t + coarse - 15
        o, sc = offset(seg(src, t, 40, track), seg(W, w0, 70))
        print(f"  src {t:6.0f}s -> offset {w0 - t + o:+.3f}  corr {sc:.2f}")


if __name__ == "__main__":
    which = sys.argv[1]
    if which == "camera":
        drift("camera", D + r"\C7443.MP4", -36.165, [60, 300, 600, 900, 1120])
    else:
        # screen recording: find coarse offset first over the whole file
        a = seg(D + r"\2026-10-06 21-27-13.mp4", 0, 866)
        b = seg(W, 0, 1104)
        o, sc = offset(a, b)
        print(f"screen coarse offset {o:+.3f} corr {sc:.3f}")
        drift("screen", D + r"\2026-10-06 21-27-13.mp4", o, [30, 200, 400, 600, 840])
