"""voice.wav (master timeline from both takes; energy-limited room-tone handles crossfade every joint) and sfx.wav
(synthesized, royalty-free; every cue sits on a graphics event of gfx/index.html; ducked 6 dB under the voice).
Usage: python sfx.py"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
import score_music as sm  # noqa: E402

ED = Path(__file__).resolve().parent
TL = json.loads((ED / "timeline.json").read_text())
SR = sm.SR
LEN = TL["length"] + 0.8
N = int(LEN * SR)


def load(path, s, e, h_in=0.0, h_out=0.0):
    """source [s - h_in, e + h_out]; handles carry the fades (tone into tone). Short/no handle -> 15 ms fade inside."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{s - h_in:.3f}", "-t", f"{e - s + h_in + h_out:.3f}", "-i", path, "-vn",
                          "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    for n, rev in ((int(max(h_in, 0.015) * SR), False), (int(max(h_out, 0.015) * SR), True)):
        r = np.sin(np.linspace(0, np.pi / 2, n, dtype=np.float32))[:, None] ** 2
        if rev:
            x[-n:] *= r[::-1]
        else:
            x[:n] *= r
    return x


EDB = {}
for k, f in TL["files"].items():
    xd = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                                      capture_output=True, check=True).stdout, np.float32)
    EDB[k] = 20 * np.log10(np.sqrt(np.convolve(xd ** 2, np.ones(80) / 80, mode="same"))[::80] + 1e-9)     # 5 ms


def handle(k, t, step):
    """extend while in room tone or while the word still decays; stop at any new onset (his restarts aren't in the text)"""
    edb = EDB[k]; h, prev = 0.0, edb[int(t * 200)]
    while h < 0.04:
        cur = edb[int((t + step * (h + 0.005)) * 200)]
        if cur > -45 and cur > prev:
            break
        h += 0.005; prev = cur
    return h


voice = np.zeros((N, 2), np.float32)
prev = None
for p in TL["pieces"]:
    s, e = p["src"]
    joined = prev is not None and prev["file"] == p["file"] and abs(prev["src"][1] - s) < 1e-3 and abs(prev["out"][1] - p["out"][0]) < 1e-3
    h_in = 0.0 if joined else handle(p["file"], s, -1)
    h_out = handle(p["file"], e, +1)
    x = load(TL["files"][p["file"]], s, e, h_in, h_out)
    if joined:                                       # same take continues across a piece boundary: no fade-in at all
        n = int(0.015 * SR); x[:n] /= np.maximum(np.sin(np.linspace(0, np.pi / 2, n, dtype=np.float32))[:, None] ** 2, 1e-3)
    i0 = int(round((p["out"][0] - h_in) * SR))
    if i0 < 0:
        x, i0 = x[-i0:], 0
    voice[i0:i0 + len(x)] += x[:max(0, N - i0)]
    prev = p
sf.write(ED / "voice.wav", voice, SR, subtype="PCM_24")

buf = np.zeros((N, 2), np.float32)
rng = np.random.default_rng(7)
db = lambda d: 10 ** (d / 20)


def env(n, a=0.005, r=0.08):
    e = np.ones(n, np.float32); na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na); e[-nr:] *= np.linspace(1, 0, nr); return e


def bp(x, lo, hi):
    return signal.sosfilt(signal.butter(2, [lo, hi], "band", fs=SR, output="sos"), x).astype(np.float32)


def put(x, t, g, pan=0.5):
    x = x if x.ndim == 2 else np.stack([x * np.sqrt(1 - pan), x * np.sqrt(pan)], 1).astype(np.float32)
    sm.place(buf, x, t, g)


noise = lambda d: rng.standard_normal(int(d * SR)).astype(np.float32)


def whoosh(d=0.4, up=True):
    n = int(d * SR); x = noise(d); f = np.linspace(300, 5000, n) if up else np.linspace(5000, 300, n); y = np.zeros(n, np.float32)
    for i in range(0, n, 256):
        y[i:i + 256] = bp(x[max(0, i - 2048):i + 256], f[i] * 0.6, min(f[i] * 1.6, 20000))[-len(x[i:i + 256]):]
    return (y * np.sin(np.linspace(0, np.pi, n)) ** 2 / (np.abs(y).max() + 1e-9)).astype(np.float32)


def pop():
    n = int(0.09 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * (900 - 5000 * tt) * tt) * env(n, 0.002, 0.07)).astype(np.float32)


def tick(d=0.012, lo=2500, hi=7000):
    return (bp(noise(d), lo, hi) * env(int(d * SR), 0.0005, d * 0.8)).astype(np.float32)


def chime(notes, gap=0.08):
    out = np.zeros(int((gap * len(notes) + 1.2) * SR), np.float32)
    for i, m in enumerate(notes):
        x = sm.bell_note(m); x = x[:, 0] if x.ndim == 2 else x
        i0 = int(i * gap * SR); out[i0:i0 + len(x)] += x[: len(out) - i0]
    return out


def rustle(d=0.35):
    """paper: crackly band-passed noise with random grains"""
    x = bp(noise(d), 1500, 9000) * (rng.random(int(d * SR)) < 0.08).astype(np.float32) * 3 + bp(noise(d), 600, 4000) * 0.35
    return (x * env(int(d * SR), 0.004, d * 0.6) / (np.abs(x).max() + 1e-9)).astype(np.float32)


def pitch_drop(d=0.32, f0=920.0, f1=380.0):
    """the client's punch sound: a tone sliding down ~1.3 octaves (measured on his best reel: ~1 kHz -> 450 Hz in 0.2 s)"""
    n = int(d * SR); tt = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (tt / d)                       # exponential glide
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)
    return (np.tanh(1.6 * x) * env(n, 0.004, d * 0.55) / 1.2).astype(np.float32)


def typing(t0, t1, cps=15):
    t = t0
    while t < t1:
        put(tick(0.010, 1800, 6000), t, db(-40), rng.uniform(0.4, 0.6)); t += rng.uniform(0.6, 1.4) / cps


# ---- hook
put(sm.impact(), 0.0, db(-30)); put(pop(), 0.05, db(-32))
put(whoosh(0.35), 4.37 - 0.22, db(-33)); put(sm.impact(), 4.37, db(-31))
# ---- prompt bar: in, typing, a tick-chime on every executed edit
put(whoosh(0.3, up=False), 5.66 - 0.12, db(-34))
PROMPTS = [(5.75, 7.90, 8.55), (8.90, 11.00, 12.30), (12.70, 14.90, 15.40), (15.90, 17.20, 17.90), (19.85, 22.20, 22.45),
           (23.42, 25.00, 27.40), (27.80, 29.30, 29.95), (30.40, 33.80, 34.40), (34.80, 35.80, 36.06)]
for a, b, d in PROMPTS:
    typing(a, b); put(chime([84, 91], 0.05), d, db(-37))
put(whoosh(0.3), 36.45 - 0.1, db(-36))
# ---- card layout
put(whoosh(0.45, up=False), 7.95, db(-30)); put(whoosh(0.4), 10.45, db(-32)); put(pop(), 10.85, db(-33))
for t in (11.64, 11.88, 12.17):
    put(pop(), t, db(-33))
put(whoosh(0.4), 13.87, db(-31))
# ---- title behind him + cinematic morph
put(sm.impact(), 15.31, db(-29)); put(whoosh(0.5), 15.31 - 0.3, db(-34)); put(chime([67, 74, 79, 86], 0.09), 17.30, db(-34))
# ---- spotlight, graphics out of the watch and back
put(sm.impact(), 22.33, db(-31)); put(chime([88], 0.0), 22.45, db(-36))
for i in range(6):
    put(pop(), 25.04 + i * 0.06, db(-34), 0.35 + i * 0.06)
put(chime([84, 88, 91], 0.05), 25.10, db(-38))
put(whoosh(0.4, up=False), 27.02, db(-33)); put(chime([91], 0.0), 27.30, db(-35))
put(sm.impact(), 27.70, db(-33))
# ---- paper cut (stop-motion clicks), sticker, B-roll
put(rustle(0.4), 29.38, db(-28)); put(pop(), 29.40, db(-33))
t = 29.5
while t < 31.15:
    put(tick(0.008, 900, 3500), t, db(-42)); t += 0.1
put(whoosh(0.35, up=False), 31.19 - 0.05, db(-33)); put(rustle(0.25), 31.40, db(-34))
put(whoosh(0.45), 32.07 - 0.25, db(-31)); put(sm.impact(), 32.07, db(-32))
for t in (33.07, 34.07):
    put(whoosh(0.25), t - 0.12, db(-36))
put(whoosh(0.4), 35.80 - 0.1, db(-32))
put(sm.impact(), 36.86, db(-29)); put(pop(), 36.88, db(-31))
# ---- "aap bhi kar sakte ho"
put(pop(), 38.12, db(-33)); put(chime([84, 88], 0.06), 39.48, db(-37))
# ---- IG tail
put(pop(), 40.54, db(-33)); put(whoosh(0.3), 42.40, db(-37)); put(pop(), 44.70, db(-33)); put(pop(), 45.45, db(-33))
put(sm.impact(), 46.05, db(-28)); put(chime([84, 88], 0.06), 46.73, db(-36)); put(pop(), 47.53, db(-32))
put(pop(), 50.17, db(-33)); put(pop(), 52.20, db(-33)); put(pop(), 53.23, db(-33)); put(pop(), 53.57, db(-33))
put(tick(0.03, 1200, 4000), 54.37, db(-34)); put(pop(), 55.30, db(-33)); put(sm.impact(), 56.06, db(-30))
# ---- YT tail
for t in (58.15, 59.15, 60.31, 61.78, 63.94):
    put(pop(), t, db(-33))
put(sm.impact(), 66.85, db(-29)); put(chime([79, 84], 0.07), 67.20, db(-35))

# pitch-drop hits on the punches (crash zoom in compose_base.py PUNCH + the slammed headlines)
for t in (4.37, 36.86, 46.05, 54.37):
    put(pitch_drop(), t + 0.01, db(-27)); put(whoosh(0.25), t + 0.30, db(-38))

# duck under the voice
v = np.abs(voice.mean(1)); hop = int(0.01 * SR); F = len(v) // hop
act = 20 * np.log10(np.sqrt((v[:F * hop].reshape(F, hop) ** 2).mean(1)) + 1e-9) > -45
g = np.where(act, db(-6), 1.0); y = np.empty(F); cur = 1.0
for i in range(F):
    a = 0.7 if g[i] < cur else 0.96; cur = a * cur + (1 - a) * g[i]; y[i] = cur
buf *= np.interp(np.arange(N) / SR, (np.arange(F) + 0.5) * 0.01, y, right=1.0)[:, None].astype(np.float32)
sf.write(ED / "sfx.wav", buf, SR, subtype="PCM_24")
print(f"voice + sfx {N / SR:.2f}s, sfx peak {20 * np.log10(np.abs(buf).max() + 1e-9):.1f} dBFS")
