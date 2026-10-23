"""Verbatim romanized transcript via greedy CTC on torchaudio MMS_FA — no language model, so false starts,
stutters and repeated words survive (Whisper tends to delete them). Words = letter runs split on >= GAP of blank.

Usage: python verbatim_ctc.py <audio> <out.json> [--start s --end s]
out: {"words": [[start, end, "text"], ...]}  (seconds in the input file's timeline)
"""
import json
import subprocess
import sys

import numpy as np
import torch
from torchaudio.pipelines import MMS_FA as bundle

SR = bundle.sample_rate            # 16 kHz, emissions at 50 Hz
GAP = 0.10                         # blank run that separates words
CHUNK, CTX = 20.0, 1.0


def load(path, start=None, end=None):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", str(start)] if start else []) + (["-to", str(end)] if end else [])
    cmd += ["-i", path, "-map", "0:a", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).copy()


def greedy(model, labels, x):
    """[(time, char)] for every non-blank emission, chunked with context so chunk edges don't clip words."""
    out, n, step = [], len(x), int(CHUNK * SR)
    for a in range(0, n, step):
        lo, hi = max(0, a - int(CTX * SR)), min(n, a + step + int(CTX * SR))
        with torch.inference_mode():
            em, _ = model(torch.from_numpy(x[lo:hi])[None])
        ids = em[0].argmax(-1).numpy()
        fr = lo / SR + np.arange(len(ids)) * (hi - lo) / SR / len(ids)
        prev = 0
        for t, i in zip(fr, ids):
            if i != prev and i != 0 and a / SR <= t < (a + step) / SR and labels[i] != "*":
                out.append((float(t), labels[i]))
            prev = i
    return out


def words(chars):
    ws, cur = [], []
    for t, c in chars:
        if cur and t - cur[-1][0] > GAP:
            ws.append([round(cur[0][0], 2), round(cur[-1][0] + 0.02, 2), "".join(ch for _, ch in cur)])
            cur = []
        cur.append((t, c))
    if cur:
        ws.append([round(cur[0][0], 2), round(cur[-1][0] + 0.02, 2), "".join(ch for _, ch in cur)])
    return ws


if __name__ == "__main__":
    a = sys.argv
    start = float(a[a.index("--start") + 1]) if "--start" in a else None
    end = float(a[a.index("--end") + 1]) if "--end" in a else None
    model, labels = bundle.get_model(with_star=False).eval(), bundle.get_labels(star=None)
    ws = words(greedy(model, labels, load(a[1], start, end)))
    if start:
        ws = [[round(s + start, 2), round(e + start, 2), w] for s, e, w in ws]
    json.dump({"words": ws}, open(a[2], "w"), ensure_ascii=False)
    print(f"{len(ws)} words -> {a[2]}")
