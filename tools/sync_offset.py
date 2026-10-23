"""Find how far an external audio file is offset from a camera's scratch audio.

Prints OFFSET seconds: positive = external audio starts OFFSET s before the camera,
so camera time t corresponds to external time t + OFFSET.

Usage: python sync_offset.py <camera_video> <external_audio> [--window 90]
"""
import argparse
import subprocess
import sys

import numpy as np

SR = 2000  # envelope rate is plenty for speech-sync


def load(path: str, seconds: float | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-map", "0:a:0", "-ac", "1", "-ar", "8000"]
    if seconds:
        cmd += ["-t", str(seconds)]
    cmd += ["-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    env = np.abs(x[: len(x) // 4 * 4]).reshape(-1, 4).mean(axis=1)  # 8 kHz -> 2 kHz envelope
    env -= env.mean()
    return env / (env.std() + 1e-9)


def offset(cam: np.ndarray, ext: np.ndarray) -> tuple[float, float]:
    n = 1 << int(np.ceil(np.log2(len(cam) + len(ext))))
    c = np.fft.irfft(np.fft.rfft(ext, n) * np.conj(np.fft.rfft(cam, n)), n)
    lag = int(np.argmax(c))
    if lag > n // 2:
        lag -= n
    peak = c.max() / (np.sqrt((cam ** 2).sum() * (ext ** 2).sum()) + 1e-9)
    return lag / SR, float(peak)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("camera")
    ap.add_argument("external")
    ap.add_argument("--window", type=float, default=90.0, help="seconds of camera audio to match")
    a = ap.parse_args()
    cam = load(a.camera, a.window)
    ext = load(a.external)
    off, score = offset(cam, ext)
    print(f"OFFSET {off:.3f}  (correlation {score:.3f})")
    if score < 0.2:
        sys.exit("weak match - verify by ear/waveform before trusting this offset")
