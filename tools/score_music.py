"""Original score for an edit: composed and synthesized to picture. No samples or third-party audio are used
anywhere, so the track is royalty-free by construction (nothing for Content ID to match).

cfg["music"]["score"] (written by the job's planner, e.g. make_longform.py):
  blocks: [{t0, t1, cue, level, start: hit|drop|fade|none, end: riser|tapestop|cut|ring,
            drums_in (bars), level_at [[t, level]], riser (bars), build: noise|roll, ring (s)}]
          every block is its own bar grid with the downbeat on t0 (a cut, a card or a punchline)
  events: [{type: bell, t, note} | {type: dip, t0, t1} | {type: lift, t0, t1, db}]
  duck:   [{t0, t1, speech, gap}]  music loudness relative to the voice (LU) while he talks / in pauses
Writes cfg["music"]["file"]: the music stem, already level-automated against the voice (mix at 0 dB, no sidechain).
Usage: python score_music.py <lf.json> [--raw]   (--raw also writes <file>_raw.wav: the score before automation)
"""
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

SR = 48000
RNG = np.random.default_rng(7)
REF = -20.0                                   # each block is normalised to REF + LEVEL_DB[level], then automated
LEVEL_DB = {0: -6.0, 1: -2.5, 2: -1.5, 3: -0.8, 4: 0.0, 5: 0.5}
TAIL = 3.0

# ---------------- harmony: everything in C major / A minor so cues hand over cleanly ----------------
QUAL = {"maj7": (0, 4, 7, 11), "maj9": (0, 4, 7, 11, 14), "add9": (0, 4, 7, 14), "6": (0, 4, 7, 9),
        "m7": (0, 3, 7, 10), "m9": (0, 3, 7, 10, 14), "13": (0, 4, 10, 14, 21)}
C, D, E, F, G, A = 48, 50, 52, 53, 55, 57


def voicings(prog, lo=57, hi=77):
    """close voicings (root left to the bass), each chord placed nearest the previous one."""
    out, prev = [], None
    for root, q in prog:
        pcs = {(root + i) % 12 for i in QUAL[q][1:]}
        best = None
        for base in range(lo, hi):
            v = sorted(base + (pc - base) % 12 for pc in pcs)
            if v[-1] > hi:
                continue
            cost = abs(sum(v) / len(v) - 66) if prev is None else sum(min(abs(a - p) for p in prev) for a in v)
            if best is None or cost < best[0]:
                best = (cost, v)
        out.append(best[1])
        prev = best[1]
    return out


# ---------------- arrangement vocabulary ----------------
def pat(s, length=1.0, vel=None):
    return [(i, length, vel[i] if vel else (1.0 if c == "x" else 0.55), 0) for i, c in enumerate(s) if c in "xo"]


ACC16 = [1.0, 0.45, 0.7, 0.45] * 4
PATTERNS = {   # name: (instrument, [(16th step, length in 16ths, velocity, interval above the root)])
    "kick4": ("kick", pat("x...x...x...x...")),
    "kick2": ("kick", pat("x.......x.......")),
    "kick_bb": ("kick", pat("x......x..x.....")),
    "kick_half": ("kick", pat("x.........x.....")),
    "clap": ("clap", pat("....x.......x...")),
    "snare": ("snare", pat("....x.......x...")),
    "rim": ("rim", pat("....x.......x...")),
    "brush": ("brush", pat("........x.......")),
    "hat16": ("chat", pat("x" * 16, vel=ACC16)),
    "hat8": ("chat", pat("x.x.x.x.x.x.x.x.", vel=[1.0, 0, 0.55, 0] * 4)),
    "hatoff": ("chat", pat("..x...x...x...x.")),
    "ohat": ("ohat", pat("..x...x...x...x.")),
    "shaker": ("shaker", pat("x" * 16, vel=[0.5, 0.8, 0.6, 1.0] * 4)),
    "bass_off": ("bass", pat("..x...x...x...x.", 1.6)),
    "bass8": ("bass", pat("x.x.x.x.x.x.x.x.", 1.7)),
    "bass_sync": ("bass", [(0, 2.5, 1.0, 0), (3, 2.5, 0.8, 0), (6, 3, 0.9, 0), (10, 2.5, 0.85, 0), (13, 2.5, 0.75, 7)]),
    "bass_long": ("bass", [(0, 15, 1.0, 0)]),
    "bass_lofi": ("bass", [(0, 9, 1.0, 0), (10, 3, 0.8, 0), (14, 2, 0.7, 7)]),
    "ep_lofi": ("ep", [(0, 6, 0.85, 0), (7, 2, 0.5, 0), (10, 5, 0.7, 0)]),
    "ep_long": ("ep", [(0, 15, 0.8, 0)]),
    "ep_stab": ("ep", [(0, 2, 0.9, 0), (3, 2, 0.6, 0), (6, 3, 0.75, 0), (10, 4, 0.7, 0)]),
    "pad": ("pad", [(0, 16, 1.0, 0)]),
    "arp8": ("arp", [(i, 2, 1.0 if i % 4 == 0 else 0.7, 0) for i in range(0, 16, 2)]),
    "arp16": ("arp", [(i, 1, ACC16[i], 0) for i in range(16)]),
    "bells": ("bell", [(0, 4, 0.8, 0), (10, 4, 0.6, 0)]),
}
CUES = {
    # house: four on the floor, offbeat bass, pumping pad, pluck arp
    "hook": {"bpm": 118, "swing": 0.5, "kick": "house", "ir": 1.3, "pump": 0.55, "carve": -2.0, "fill": "roll",
             "roll": "clap", "bright": 0.6, "prog": [(F, "maj7"), (G, "6"), (E, "m7"), (A, "m9")],
             "levels": {0: ["pad"],
                        3: ["kick4", "clap", "hat16", "ohat", "bass_off", "pad", "arp8"],
                        4: ["kick4", "clap", "hat16", "ohat", "bass_off", "pad", "arp16", "crash8"]}},
    # lo-fi: swung boom-bap, FM electric piano, round sub bass
    "story": {"bpm": 88, "swing": 0.58, "kick": "soft", "ir": 1.8, "pump": 0.12, "carve": -3.5, "fill": "break",
              "roll": "snare", "bright": 0.45, "breathe": True, "prog": [(A, "m9"), (D, "m9"), (G, "13"), (C, "maj9")],
              "levels": {1: ["kick_bb", "rim", "hat8", "ep_lofi", "bass_lofi"],
                         2: ["kick_bb", "rim", "hat8", "ep_lofi", "bass_lofi", "pad"],
                         3: ["kick_bb", "snare", "hat8", "shaker", "ep_lofi", "bass_lofi", "pad"]}},
    # tech-pop: builds a layer per step, so the music climbs with the tutorial
    "build": {"bpm": 110, "swing": 0.5, "kick": "house", "ir": 1.5, "pump": 0.45, "carve": -3.5, "fill": "roll",
              "roll": "clap", "bright": 0.55, "breathe": True, "prog": [(F, "maj9"), (G, "6"), (A, "m9"), (E, "m7")],
              "levels": {1: ["kick2", "shaker", "bass8", "pad"],
                         2: ["kick4", "shaker", "hatoff", "bass8", "pad"],
                         3: ["kick4", "shaker", "hatoff", "bass8", "pad", "arp8"],
                         4: ["kick4", "clap", "shaker", "hatoff", "bass8", "pad", "arp16"],
                         5: ["kick4", "clap", "shaker", "hatoff", "bass8", "pad", "arp16", "bells", "crash8"]}},
    # half-time and warm for the "my rule" reflection
    "reflect": {"bpm": 80, "swing": 0.56, "kick": "soft", "ir": 2.2, "pump": 0.0, "carve": -3.5, "fill": "break",
                "roll": "snare", "bright": 0.4, "prog": [(D, "m9"), (G, "13"), (C, "maj9"), (A, "m9")],
                "levels": {1: ["kick_half", "brush", "ep_long", "pad", "bass_long"],
                           2: ["kick_half", "brush", "hat8", "ep_long", "pad", "bass_long"]}},
    # driving pop for the numbers / payoff
    "numbers": {"bpm": 104, "swing": 0.5, "kick": "house", "ir": 1.4, "pump": 0.35, "carve": -3.5, "fill": "roll",
                "roll": "clap", "bright": 0.55, "prog": [(A, "m9"), (F, "maj9"), (C, "add9"), (G, "6")],
                "levels": {3: ["kick4", "clap", "hat16", "bass_sync", "ep_stab", "pad"],
                           4: ["kick4", "clap", "hat16", "bass_sync", "ep_stab", "pad", "arp8", "crash8"]}},
}
CUES["outro"] = CUES["hook"]
DRUMS = {"kick", "clap", "snare", "rim", "brush", "chat", "ohat", "shaker"}
GAIN = {"kick": 0.3, "clap": 0.54, "snare": 0.59, "rim": 0.63, "brush": 0.39, "chat": 0.19, "ohat": 0.089,
        "shaker": 0.10, "crash": 0.08, "impact": 0.4, "riser": 0.125, "bass": 0.42, "ep": 0.22, "pad": 0.12,
        "arp": 0.12, "bell": 0.14}           # drum kit balanced by solo loudness; bus levels are set per cue by MIX
SEND = {"clap": 0.25, "snare": 0.22, "rim": 0.15, "brush": 0.2, "chat": 0.05, "ohat": 0.06, "shaker": 0.06,
        "crash": 0.15, "impact": 0.2, "riser": 0.2, "ep": 0.3, "pad": 0.45, "arp": 0.35, "bell": 0.5}
PAN = {"clap": 0.5, "snare": 0.52, "rim": 0.6, "brush": 0.45, "chat": 0.62, "ohat": 0.4, "shaker": 0.36}
MIX = {   # bus loudness relative to the drum bus (LU), applied per block: the "faders"
    "hook": {"bass": -3, "keys": -4.5, "lead": -7}, "story": {"bass": -1.5, "keys": 1.5, "lead": -7},
    "build": {"bass": -3, "keys": -3.5, "lead": -7}, "reflect": {"bass": -2, "keys": 3, "lead": -7},
    "numbers": {"bass": -3, "keys": -2, "lead": -7}}
MIX["outro"] = MIX["hook"]
FILL = {"roll": (12, {"kick", "clap", "snare", "chat", "ohat"}), "break": (8, {"kick", "snare", "rim", "brush"})}


# ---------------- synthesis ----------------
def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tsec(n):
    return np.arange(n) / SR


@lru_cache(None)
def _sos(kind, f, order):
    return signal.butter(order, f, btype=kind, fs=SR, output="sos")


def filt(x, kind, f, order=2):
    return signal.sosfilt(_sos(kind, f, order), x, axis=0)


def norm(x):
    return x / (np.abs(x).max() + 1e-12)


def oneshot(x, fade=0.04):
    k = int(fade * SR)
    x = x.copy()
    x[-k:] *= np.cos(np.linspace(0, np.pi / 2, k)) ** 2
    return norm(x).astype(np.float32)


def saw(f, n):
    """PolyBLEP band-limited sawtooth."""
    dt = f / SR
    ph = (RNG.uniform() + dt * np.arange(n)) % 1.0
    y = 2 * ph - 1
    a = ph < dt
    x = ph[a] / dt
    y[a] -= 2 * x - x * x - 1
    b = ph > 1 - dt
    x = (ph[b] - 1) / dt
    y[b] -= x * x + 2 * x + 1
    return y


METAL = (205.3, 304.4, 369.6, 522.7, 540.0, 800.0)     # the 808 cymbal oscillator bank


@lru_cache(None)
def kick(kind):
    n = int(0.5 * SR); t = tsec(n); hard = kind == "house"
    f = 45 + (120 if hard else 85) * np.exp(-t / 0.03)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (0.28 if hard else 0.2))
    click = filt(RNG.standard_normal(n), "highpass", 1800) * np.exp(-t / 0.0025) * (0.35 if hard else 0.12)
    return oneshot(np.tanh(1.8 * (body + click)))


@lru_cache(None)
def clap():
    n = int(0.4 * SR); t = tsec(n)
    env = sum(np.where(t >= d, np.exp(-(t - d) / 0.007), 0.0) for d in (0.0, 0.010, 0.021))
    env = env + 0.7 * np.where(t >= 0.03, np.exp(-(t - 0.03) / 0.12), 0.0)
    return oneshot(filt(RNG.standard_normal(n), "bandpass", (900, 4200)) * env)


@lru_cache(None)
def snare():
    n = int(0.35 * SR); t = tsec(n)
    body = np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.05)
    nz = filt(RNG.standard_normal(n), "bandpass", (1200, 7500)) * np.exp(-t / 0.11)
    return oneshot(0.7 * norm(body) + norm(nz))


@lru_cache(None)
def rim():
    n = int(0.12 * SR); t = tsec(n)
    return oneshot(np.sin(2 * np.pi * 820 * t) * np.exp(-t / 0.012)
                   + 0.5 * filt(RNG.standard_normal(n), "bandpass", (1500, 4500)) * np.exp(-t / 0.006), fade=0.01)


@lru_cache(None)
def brush():
    n = int(0.3 * SR); t = tsec(n)
    return oneshot(filt(RNG.standard_normal(n), "bandpass", (1800, 9000)) * (1 - np.exp(-t / 0.012)) * np.exp(-t / 0.09))


@lru_cache(None)
def hat(open_):
    d = 0.2 if open_ else 0.032
    n = int(6 * d * SR); t = tsec(n)
    x = RNG.standard_normal(n) + 0.8 * sum(signal.square(2 * np.pi * f * t) for f in METAL) / 6
    return oneshot(filt(x, "highpass", 7000, 4) * np.exp(-t / d), fade=0.01)


@lru_cache(None)
def shaker():
    n = int(0.15 * SR); t = tsec(n)
    return oneshot(filt(RNG.standard_normal(n), "bandpass", (4500, 11000)) * (1 - np.exp(-t / 0.008)) * np.exp(-t / 0.035),
                   fade=0.01)


@lru_cache(None)
def crash():
    n = int(2.8 * SR); t = tsec(n)
    x = RNG.standard_normal(n) + 0.7 * sum(signal.square(2 * np.pi * f * 1.37 * t) for f in METAL) / 6
    return oneshot(filt(x, "highpass", 4000, 4) * np.exp(-t / 0.85) * (1 - np.exp(-t / 0.002)), fade=0.3)


@lru_cache(None)
def impact():
    n = int(2.2 * SR); t = tsec(n)
    f = 32 + 48 * np.exp(-t / 0.22)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.8)
    boom = norm(filt(RNG.standard_normal(n), "lowpass", 350)) * np.exp(-t / 0.3)
    return oneshot(np.tanh(1.6 * (sub + 0.5 * boom)), fade=0.3)


def riser(dur):
    """band-passed noise sweeping 250 Hz -> 9 kHz, swelling into its end."""
    n = int(dur * SR); t = tsec(n)
    fr, tt, Z = signal.stft(RNG.standard_normal(n + 4096), SR, nperseg=2048)
    fc = 250 * (9000 / 250) ** np.clip(tt / dur, 0, 1)
    Z = Z * np.exp(-0.5 * (np.log2((fr[:, None] + 1) / fc[None, :]) / 0.55) ** 2)
    y = norm(signal.istft(Z, SR, nperseg=2048)[1][:n]) * (t / dur) ** 2.2
    return np.stack([y, np.r_[np.zeros(240), y[:-240]]], 1).astype(np.float32)     # 5 ms Haas width


@lru_cache(None)
def ep_note(m, dq, vq):
    """FM electric piano (1:1 operator pair with decaying index + a short tine)."""
    dur, vel = dq / 50, vq / 10
    f = mtof(m); n = int((dur + 0.3) * SR); t = tsec(n)
    idx = (0.6 + 1.6 * vel) * np.exp(-t / 0.45) + 0.25
    x = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t))
    x += 0.10 * vel * np.sin(2 * np.pi * min(14 * f, 9000) * t) * np.exp(-t / 0.012)
    env = np.exp(-t / (1.9 if f < 330 else 1.3)) * np.clip(1 - (t - dur) / 0.25, 0, 1) * (1 - np.exp(-t / 0.002))
    return (x * env * (0.45 + 0.55 * vel)).astype(np.float32)


@lru_cache(None)
def pad_note(m, dq, bq):
    """three detuned saws, low-passed, slow attack; stereo."""
    dur, bright = dq / 50, bq / 10
    f = mtof(m); n = int((dur + 0.9) * SR); t = tsec(n)
    c = saw(f, n)
    x = np.stack([saw(f * 2 ** (-0.09 / 12), n) + 0.6 * c, saw(f * 2 ** (0.09 / 12), n) + 0.6 * c], 1)
    x = filt(x, "lowpass", 700 + 2200 * bright)
    env = np.minimum(t / 0.3, 1) * np.clip(1 - (t - dur) / 0.8, 0, 1)
    return (x * env[:, None] * 0.4).astype(np.float32)


@lru_cache(None)
def bass_note(m, dq, kind):
    dur = dq / 50
    f = mtof(m); n = int((dur + 0.08) * SR); t = tsec(n)
    x = np.sin(2 * np.pi * f * t) + 0.2 * np.sin(4 * np.pi * f * t)
    if kind == "house":
        x = x + 0.3 * filt(saw(f, n), "lowpass", 800)
    env = np.minimum(t / 0.005, 1) * np.clip(1 - (t - dur) / 0.06, 0, 1)
    return (np.tanh(1.3 * x) * env).astype(np.float32)


@lru_cache(None)
def pluck_note(m, vq):
    """additive pluck: higher harmonics die faster, like a plucked string."""
    f = mtof(m); n = int(0.8 * SR); t = tsec(n)
    x = np.zeros(n)
    for k in range(1, max(2, min(24, int(10000 / f))) + 1):
        x += np.sin(2 * np.pi * k * f * t + RNG.uniform(0, 2 * np.pi)) * np.exp(-t * (4 + 6 * k)) / k
    return (norm(x * (1 - np.exp(-t / 0.0015))) * vq / 10).astype(np.float32)


@lru_cache(None)
def bell_note(m):
    """glockenspiel: inharmonic bar partials."""
    f = mtof(m); n = int(2.6 * SR); t = tsec(n)
    x = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t / d)
            for r, a, d in ((1, 1, 1.3), (2.76, .4, .5), (5.4, .2, .22), (8.93, .08, .1)) if f * r < 18000)
    return norm(x * (1 - np.exp(-t / 0.001))).astype(np.float32)


@lru_cache(None)
def ir(t60):
    """synthetic stereo hall: decorrelated noise, highs decaying faster than lows."""
    n = int((t60 + 0.02) * SR); t = tsec(n); pre = int(0.02 * SR)
    out = np.zeros((n, 2))
    for c in range(2):
        nz = RNG.standard_normal(n)
        out[:, c] = (filt(nz, "lowpass", 3500) * np.exp(-6.9 * t / t60)
                     + 0.4 * filt(nz, "highpass", 3500) * np.exp(-6.9 * t / (0.35 * t60)))
        out[:pre, c] = 0
    return (out / np.sqrt((out ** 2).sum(0))).astype(np.float32)


def peaking(f0, db, q):
    a = 10 ** (db / 40); w = 2 * np.pi * f0 / SR; al = np.sin(w) / (2 * q)
    return signal.tf2sos([1 + al * a, -2 * np.cos(w), 1 - al * a], [1 + al / a, -2 * np.cos(w), 1 - al / a])


KSOS = np.vstack([signal.tf2sos([1.53512485958697, -2.69169618940638, 1.19839281085285],
                                [1.0, -1.69065929318241, 0.73248077421585]),
                  signal.tf2sos([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])])   # BS.1770 @48k


def lufs(x):
    y = signal.sosfilt(KSOS, x, axis=0).astype(np.float64)
    return -0.691 + 10 * np.log10((y ** 2).mean(0).sum() + 1e-15)


def place(buf, x, t, gain, pan=0.5):
    i = int(round(t * SR))
    if gain == 0 or i >= len(buf):
        return
    if x.ndim == 1:
        x = x[:, None] * (np.array([np.cos(pan * np.pi / 2), np.sin(pan * np.pi / 2)], np.float32) * 1.4142)
    if i < 0:
        x, i = x[-i:], 0
    j = min(len(buf), i + len(x))
    buf[i:j] += gain * x[: j - i]


def pump(times, n, depth):
    """kick-keyed sidechain envelope."""
    env = np.ones(n, np.float32)
    if depth <= 0 or not times:
        return env
    idx = np.sort(np.clip((np.array(times) * SR).astype(np.int64), 0, n - 1))
    mark = np.full(n, -1, np.int64)
    mark[idx] = idx
    last = np.maximum.accumulate(mark)
    tau = (np.arange(n) - last) / SR
    e = 1 - depth * (1 - np.exp(-tau / 0.004)) * np.exp(-tau / 0.13)
    e[last < 0] = 1
    return e.astype(np.float32)


def tape_stop(x, end_i, dur):
    n = min(int(dur * SR), end_i)
    s = end_i - n
    pos = s + np.cumsum((1 - np.arange(n) / n) ** 1.5)
    src = np.arange(len(x))
    for c in range(2):
        x[s:end_i, c] = np.interp(pos, src, x[:, c])
    x[end_i:] = 0
    k = int(0.01 * SR)
    x[end_i - k:end_i] *= np.linspace(1, 0, k)[:, None]


def dip(x, t0, t1, fc=420):
    """DJ-style low-pass dip over [t0, t1] with 0.25 s ramps."""
    r = int(0.25 * SR); i0, i1 = int(t0 * SR), int(t1 * SR)
    a, b = max(0, i0 - r), min(len(x), i1 + r)
    seg = x[a:b].copy()
    lo = signal.sosfiltfilt(_sos("lowpass", fc, 4), seg, axis=0) * 1.4
    tt = np.arange(a, b)
    w = np.clip(np.minimum((tt - (i0 - r)) / r, ((i1 + r) - tt) / r), 0, 1)[:, None]
    x[a:b] = seg * (1 - w) + lo * w


# ---------------- one block = one cue on its own bar grid ----------------
def level_at(b, t):
    lev = b["level"]
    for tt, lv in b.get("level_at", []):
        if t >= tt - 1e-6:
            lev = lv
    return lev


def render_block(b):
    cue = CUES[b["cue"]]
    beat = 60.0 / cue["bpm"]; st = beat / 4; bar = 4 * beat
    T = b["t1"] - b["t0"]; n = int((T + TAIL) * SR); i1 = int(T * SR)
    bus = {k: np.zeros((n, 2), np.float32) for k in ("drums", "bass", "keys", "lead", "fx")}
    sends = {k: np.zeros((n, 2), np.float32) for k in ("drums", "keys", "lead", "fx")}
    voic = voicings(cue["prog"])
    end, start = b.get("end", "cut"), b.get("start", "none")
    rb = min(b.get("riser", 1.0) * bar, 0.95 * T) if end == "riser" else 0.0
    drum_until = np.floor((T - rb) / beat + 1e-6) * beat if end == "riser" else T
    tonal_until = T - 0.6 * beat if end == "riser" else T
    hit = T - b.get("ring", 0.7)
    if end == "ring":
        drum_until = tonal_until = hit
    drums_in = b.get("drums_in", 0) * bar
    sw = (cue["swing"] - 0.5) * 2 * st
    human = cue["swing"] > 0.5
    kicks = []

    def drum(name, t, vel):
        x = {"kick": lambda: kick(cue["kick"]), "clap": clap, "snare": snare, "rim": rim, "brush": brush,
             "chat": lambda: hat(False), "ohat": lambda: hat(True), "shaker": shaker}[name]()
        if human:
            t += RNG.normal(0, 0.003)
            vel *= 1 + RNG.normal(0, 0.06)
        place(bus["drums"], x, t, GAIN[name] * vel, PAN.get(name, 0.5))
        place(sends["drums"], x, t, GAIN[name] * vel * SEND.get(name, 0), PAN.get(name, 0.5))
        if name == "kick":
            kicks.append(t)

    def tone(inst, x, t, vel=1.0, pan=0.5):
        k = "bass" if inst == "bass" else "keys" if inst in ("ep", "pad") else "lead"
        place(bus[k], x, t, GAIN[inst] * vel, pan)
        if k != "bass":
            place(sends[k], x, t, GAIN[inst] * vel * SEND.get(inst, 0), pan)

    def fx(x, t, g, send=0.2):
        place(bus["fx"], x, t, g)
        place(sends["fx"], x, t, g * send)

    if start == "hit":
        fx(impact(), 0, GAIN["impact"]); fx(crash(), 0, GAIN["crash"], 0.15)
    elif start == "drop":
        fx(crash(), 0, 0.7 * GAIN["crash"], 0.15)

    for bi in range(int(np.ceil(T / bar))):
        t_bar = bi * bar
        lev = level_at(b, b["t0"] + t_bar)
        ks = [k for k in cue["levels"] if k <= lev]
        names = cue["levels"][max(ks) if ks else min(cue["levels"])]
        if cue.get("breathe") and (bi // 8) % 4 == 3:
            names = [nm for nm in names if not nm.startswith("hat")]         # a breather phrase every 32 bars
        v = voic[bi % len(voic)]
        root = 36 + (cue["prog"][bi % len(voic)][0] - 36) % 12
        fill = bi % 8 == 7 and t_bar + bar < drum_until - 1e-6
        if "crash8" in names and bi % 8 == 0 and 0 < t_bar < drum_until and t_bar >= drums_in:
            fx(crash(), t_bar, 0.5 * GAIN["crash"], 0.15)
        for nm in names:
            if nm == "crash8":
                continue
            inst, steps = PATTERNS[nm]
            for s, ln, vel, iv in steps:
                t = t_bar + s * st + (sw if s % 2 else 0.0)
                if inst in DRUMS:
                    if t < drums_in - 1e-6 or t >= drum_until - 1e-6:
                        continue
                    if fill and s >= FILL[cue["fill"]][0] and inst in FILL[cue["fill"]][1]:
                        continue
                    drum(inst, t, vel)
                    continue
                if t >= tonal_until - 1e-6:
                    continue
                dq = int(round(ln * st * 50))
                if inst == "bass":
                    tone("bass", bass_note(root + iv, dq, "house" if cue["kick"] == "house" else "sub"), t, vel)
                elif inst == "ep":
                    for k, m in enumerate(v):
                        tone("ep", ep_note(m, dq, int(round(vel * 10))), t + k * (0.012 if human else 0.004), 1.0, 0.38 + 0.08 * k)
                elif inst == "pad":
                    br = 0.25 if lev == 0 else cue["bright"]
                    for m in v:
                        tone("pad", pad_note(m, dq, int(round(br * 10))), t)
                elif inst == "arp":
                    seq = v + [v[0] + 12]
                    seq = seq + seq[-2:0:-1]                                   # up-down
                    k = (bi * 16 + s) // (2 if nm == "arp8" else 1)
                    tone("arp", pluck_note(seq[k % len(seq)] + 12, int(round(vel * 10))), t, 1.0, 0.35 if k % 2 else 0.65)
                elif inst == "bell" and bi % 2 == 0:
                    tone("bell", bell_note((v[-1] if s == 0 else v[-2]) + 12), t, vel)
        if fill:
            if cue["fill"] == "roll":
                for s, vel in zip(range(12, 16), (0.35, 0.5, 0.7, 0.95)):
                    drum(cue["roll"], t_bar + s * st, vel)
            else:
                drum("ohat", t_bar + 14 * st, 0.7)

    if end == "riser":
        roll = b.get("build") == "roll"
        fx(riser(rb), T - rb, GAIN["riser"] * (0.6 if roll else 1.0))
        L = min(rb, 1.6)
        fx(crash()[: int(L * SR)][::-1] * np.minimum(1, np.arange(int(L * SR)) / (0.01 * SR)), T - L, 0.6 * GAIN["crash"], 0.15)
        if roll:
            for k in range(int(np.ceil((T - rb) / st)), int(np.ceil(T / st - 1e-6))):
                drum(cue["roll"], k * st, 0.2 + 0.8 * ((k * st - (T - rb)) / rb) ** 1.5)
    if end == "ring":                                                      # final hit, then let it ring out
        fx(impact(), hit, GAIN["impact"]); fx(crash(), hit, GAIN["crash"], 0.15)
        fv = voicings([(C, "maj9")])[0]
        for k, m in enumerate(fv):
            tone("pad", pad_note(m, 80, 6), hit)
            tone("arp", pluck_note(m + 12, 9), hit + 0.015 * k, 1.0, 0.3 + 0.13 * k)
        tone("bell", bell_note(84), hit, 0.8)

    # gate at the block end (the next block's downbeat), keep reverb tails, sidechain-pump the tonal buses
    g = np.ones(n, np.float32)
    if end == "ring":
        a = int((hit + 0.3) * SR)
        g[a:i1] = np.linspace(1, 0, max(0, i1 - a)) ** 1.5
        g[i1:] = 0
    else:
        k = int(0.015 * SR)
        g[i1:i1 + k] = np.linspace(1, 0, len(g[i1:i1 + k]))
        g[i1 + k:] = 0
    # faders: each bus to its MIX level vs. the drums (fx ride with the drums, or the keys when there are none)
    loud = {k: lufs(v[:i1]) for k, v in bus.items() if k != "fx" and np.abs(v[:i1]).max() > 0}
    ref = loud.get("drums", loud.get("keys", -30.0))
    fad = {k: 10 ** (((0 if k == "drums" else MIX[b["cue"]][k]) + ref - l) / 20) for k, l in loud.items()}
    fad["fx"] = fad.get("drums", fad.get("keys", 1.0))
    env = pump(kicks, n, cue["pump"])
    dry = sum(bus[k] * fad.get(k, 0) * (env[:, None] if k in ("bass", "keys", "lead") else 1) for k in bus) * g[:, None]
    h = ir(cue["ir"])
    wet = np.zeros((n, 2), np.float32)
    for k, sv in sends.items():
        if fad.get(k) and np.abs(sv).max() > 0:
            sv = sv * g[:, None] * fad[k]
            wet += np.stack([signal.oaconvolve(sv[:, c], h[:, c])[:n] for c in range(2)], 1).astype(np.float32)
    if end == "ring":
        wet *= g[:, None]
    out = dry + wet
    out = signal.sosfilt(_sos("highpass", 30, 2), out, axis=0)
    out = signal.sosfilt(peaking(2800, cue["carve"], 0.9), out, axis=0)      # carve room for the voice
    pk = np.abs(out).max() + 1e-9
    out = np.tanh(1.2 * out / pk) / np.tanh(1.2) * pk                         # gentle glue on the peaks
    if end == "tapestop":
        tape_stop(out, i1, 0.5)
    gain = 10 ** ((REF + LEVEL_DB[b["level"]] - lufs(out[:i1])) / 20)
    stats = {k: round(float(20 * np.log10(f)), 1) for k, f in fad.items()}
    return (out * gain).astype(np.float32), stats


# ---------------- level automation against the voice ----------------
def automation(cfg, cfg_path, sc, N):
    base = cfg_path.parent / Path(cfg["out"]).stem / "base.mkv"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(base), "-map", "0:a", "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    v = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    for t0, t1, db in cfg.get("voice_gain", []):                 # the mix trims the voice the same way
        v[int(t0 * SR):int(t1 * SR)] *= 10 ** (db / 20)
    hop = int(0.02 * SR); F = len(v) // hop
    ms = (v[: F * hop].astype(np.float64) ** 2).mean(1).reshape(F, hop).mean(1)
    act = 10 * np.log10(ms + 1e-15) > -52
    edges = np.flatnonzero(np.diff(np.r_[0, (~act).astype(np.int8), 0]))
    for s, e in zip(edges[::2], edges[1::2]):                # pauses < 0.6 s are not gaps; pre-duck 0.1 s
        if (e - s) * 0.02 < 0.6:
            act[s:e] = True
        act[max(s, e - 5):e] = True
    kp = (signal.sosfilt(KSOS, v, axis=0).astype(np.float64) ** 2).sum(1)
    kpf = kp[: F * hop].reshape(F, hop).mean(1)
    ft = (np.arange(F) + 0.5) * 0.02
    rel, vf = np.zeros(F), np.full(F, np.nan)
    for r in sc["duck"]:
        m = (ft >= r["t0"]) & (ft < r["t1"])
        vr = -0.691 + 10 * np.log10(kpf[m & act].mean())
        vf[m] = vr
        rel[m] = np.where(act[m], r["speech"], r["gap"])
        print(f"  duck {r['t0']:7.2f}-{min(r['t1'], ft[-1]):7.2f}: voice {vr:6.1f} LUFS, voice/SFX in {act[m].mean() * 100:3.0f}% of frames")
    assert not np.isnan(vf).any(), "duck regions must cover the whole timeline"
    for e in sc.get("events", []):
        if e["type"] == "lift":
            rel[(ft >= e["t0"]) & (ft < e["t1"])] += e["db"]
    rel = np.minimum(rel, -4.0)
    a_dn, a_up = np.exp(-0.02 / 0.08), np.exp(-0.02 / 0.45)          # duck fast, recover slow
    y, cur = np.empty(F), rel[0]
    for i in range(F):
        a = a_dn if rel[i] < cur else a_up
        cur = a * cur + (1 - a) * rel[i]
        y[i] = cur
    return (10 ** (np.interp((np.arange(N) + 0.5) / SR, ft, vf + y - REF) / 20)).astype(np.float32)


if __name__ == "__main__":
    cfg_path = Path(sys.argv[1])
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    sc = cfg["music"]["score"]
    N = int((sc["length"] + 1.0) * SR)
    mus = np.zeros((N, 2), np.float32)
    for b in sc["blocks"]:
        out, stats = render_block(b)
        i0 = int(round(b["t0"] * SR)); j = min(N, i0 + len(out))
        mus[i0:j] += out[: j - i0]
        print(f"{b['t0']:7.2f}-{b['t1']:7.2f} {b['cue']:8s} L{b['level']} {b.get('start', 'none'):4s}>{b.get('end', 'cut'):8s} buses(LU): {stats}", flush=True)
    for e in sc.get("events", []):
        if e["type"] == "dip":
            dip(mus, e["t0"], e["t1"])
        elif e["type"] == "bell":
            x = bell_note(e["note"])
            wet = np.stack([signal.oaconvolve(x, ir(2.2)[:, c]) for c in range(2)], 1)
            place(mus, x, e["t"], 10 ** ((REF - 6) / 20) * 2.5)
            place(mus, wet.astype(np.float32), e["t"], 10 ** ((REF - 6) / 20) * 2.5 * 0.45)
    out = Path(cfg["music"]["file"])
    if "--raw" in sys.argv:
        sf.write(out.with_name(out.stem + "_raw.wav"), mus, SR, subtype="PCM_24")
    mus *= automation(cfg, cfg_path, sc, N)[:, None]
    assert np.isfinite(mus).all() and np.abs(mus).max() < 1.0
    sf.write(out, mus, SR, subtype="PCM_24")
    print(f"score -> {out}  ({N / SR:.2f}s, peak {20 * np.log10(np.abs(mus).max()):.1f} dBFS)")
