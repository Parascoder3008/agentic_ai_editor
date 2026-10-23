"""Face centre per camera timestamp (for punch-in framing). Samples single frames by fast input-seek,
detects the most confident face with OpenCV YuNet (OpenCV 5 dropped Haar cascades), returns centre
and face width in 1920x1080 space.

Usage: python face_track.py <camera> <out.json> --times 41.2,47.9,...   (camera-time seconds)
       python face_track.py <camera> <out.json> --every 2 --until 1160
"""
import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

MODEL = Path(__file__).parent / "models" / "face_detection_yunet_2023mar.onnx"
W, H = 960, 540

ap = argparse.ArgumentParser()
ap.add_argument("cam")
ap.add_argument("out")
ap.add_argument("--times")
ap.add_argument("--every", type=float)
ap.add_argument("--until", type=float)
a = ap.parse_args()
times = [float(t) for t in a.times.split(",")] if a.times else [i * a.every for i in range(int(a.until / a.every))]
det = cv2.FaceDetectorYN_create(str(MODEL), "", (W, H), 0.7, 0.3, 5)
res = {}
for t in times:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", a.cam, "-frames:v", "1", "-vf", f"scale={W}:{H}",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    if len(raw) < W * H * 3:
        continue
    img = np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 3)
    _, faces = det.detect(img)
    if faces is not None and len(faces):
        x, y, w, h = max(faces, key=lambda f: f[-1])[:4]
        res[f"{t:.2f}"] = [round(float(x + w / 2) * 2), round(float(y + h / 2) * 2), round(float(w) * 2)]
json.dump(res, open(a.out, "w"), indent=0)
print(f"{len(res)}/{len(times)} frames with a face")
