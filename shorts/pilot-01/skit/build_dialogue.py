"""Gated TTS lines -> one 8.06 s dialogue track, each line inside its shot (cuts from scene detection).
A line longer than its window is sped up (atempo, at most 1.15x) rather than spilling into the next shot.

Usage: python build_dialogue.py  -> dialogue.wav + dialogue.json (placements)
"""
import json
import subprocess

import numpy as np
import soundfile as sf

SR, LEN = 48000, 8.064
SHOTS = [(0.0, 3.0), (3.0, 4.75), (4.75, 6.5), (6.5, LEN)]          # two-shot, MAN, FRIEND, MAN
ORDER = [("friend", 0, 0), ("man", 0, 1), ("friend", 1, 2), ("man", 1, 3)]  # (speaker, line idx, shot)
LEAD, TAIL = 0.12, 0.06                                                # start after the cut / clear the next one


def load(p):
    return np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                        capture_output=True, check=True).stdout, np.float32).copy()


def lines(x):
    """split on the >= 0.6 s pause the TTS break left between the two lines."""
    e = np.convolve(x ** 2, np.ones(480) / 480, mode="same")[::480]       # 10 ms
    on = 10 * np.log10(e + 1e-12) > -45
    idx = np.flatnonzero(on)
    gaps = [(a, b) for a, b in zip(idx, idx[1:]) if b - a > 60]
    cut = (gaps[0][0] + gaps[0][1]) // 2
    segs = [(idx[0], cut), (cut, idx[-1] + 1)]
    out = []
    for a, b in segs:
        part = idx[(idx >= a) & (idx < b)]
        out.append(x[max(0, part[0] * 480 - 480): (part[-1] + 2) * 480])
    return out


def tighten(x, keep=0.15):
    """shorten internal pauses (> keep) to keep seconds, cutting at the quietest 10 ms frames."""
    e = 10 * np.log10(np.convolve(x ** 2, np.ones(480) / 480, mode="same")[::480] + 1e-12) > -45
    out, i, n = [], 0, len(e)
    while i < n:
        if not e[i]:
            j = i
            while j < n and not e[j]:
                j += 1
            k = int(keep * 100)
            out.append(x[i * 480: (i + min(j - i, k)) * 480])
            i = j
        else:
            j = i
            while j < n and e[j]:
                j += 1
            out.append(x[i * 480: j * 480])
            i = j
    return np.concatenate(out)


src = {s: [tighten(l) for l in lines(load(f"{s}.wav"))] for s in ("man", "friend")}
track, info = np.zeros(int(LEN * SR), np.float32), []
for spk, li, sh in ORDER:
    seg = src[spk][li]
    a, b = SHOTS[sh]
    room = (b - TAIL) - (a + LEAD)
    d = len(seg) / SR
    if d > room:
        tempo = min(1.15, d / room)
        p = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                            "-af", f"atempo={tempo:.4f}", "-f", "f32le", "-"], input=seg.tobytes(), capture_output=True, check=True)
        seg = np.frombuffer(p.stdout, np.float32)
    else:
        tempo = 1.0
    i = int((a + LEAD) * SR)
    seg = seg[: len(track) - i]
    track[i: i + len(seg)] += seg
    info.append({"speaker": spk, "line": li, "shot": sh, "start": round(a + LEAD, 3), "end": round(a + LEAD + len(seg) / SR, 3),
                 "tempo": round(tempo, 3), "fits": a + LEAD + len(seg) / SR <= b})
track = track / max(1e-6, np.abs(track).max()) * 10 ** (-3 / 20)
sf.write("dialogue.wav", np.stack([track, track], 1), SR, subtype="PCM_16")
json.dump(info, open("dialogue.json", "w"), indent=1)
for r in info:
    print(r)
