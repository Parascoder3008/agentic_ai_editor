"""Track the watch face (white dial) on base_face.mp4 between two master times by template matching, frame by frame.
Writes watch_track.json [[t, x, y, score], ...] in 1080x1920 space. Usage: python track_watch.py t0 t1 tref x y"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ED = Path(__file__).resolve().parent
t0, t1, tref = map(float, sys.argv[1:4])
raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-i", str(ED / "base_face.mp4"), "-t", f"{t1 - t0:.3f}",
                      "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
F = np.frombuffer(raw, np.uint8).reshape(-1, 1920, 1080)
ref = F[int(round((tref - t0) * 30))]
cx, cy = int(sys.argv[4]), int(sys.argv[5])            # dial centre at tref, read off a gridded frame
T = ref[cy - 70:cy + 70, cx - 70:cx + 70]
res = {}
k0 = int(round((tref - t0) * 30))
for order in (range(k0, len(F)), range(k0, -1, -1)):
  px, py = cx, cy
  for i in order:
    f = F[i]
    x0, y0 = max(0, px - 170), max(0, py - 170)
    win = f[y0:py + 170, x0:px + 170]
    r = cv2.matchTemplate(win, T, cv2.TM_CCOEFF_NORMED); _, sc, _, loc = cv2.minMaxLoc(r)
    if sc > 0.45:
        px, py = x0 + loc[0] + 70, y0 + loc[1] + 70
    res[i] = [round(t0 + i / 30, 3), int(px), int(py), round(float(sc), 2)]
out = [res[i] for i in sorted(res)]
(ED / "watch_track.json").write_text(json.dumps(out))
print("ref dial", cx, cy)
for r in out[::6]:
    print(r)
