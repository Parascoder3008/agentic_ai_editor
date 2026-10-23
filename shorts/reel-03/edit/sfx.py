"""Reel-03 SFX stem on the master timeline (all synthesized, royalty-free). Every cue sits on its visual event
from gfx/index.html; effects are ducked 6 dB under the voice, whooshes peak >= 0.15 s before the next word.
Writes sfx.wav (48 kHz stereo) and voice.wav (the avatar's lip-synced audio)."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
import score_music as sm  # noqa: E402

ED = Path(__file__).resolve().parent
SR = sm.SR
LEN = 59.6
N = int(LEN * SR)
buf = np.zeros((N, 2), np.float32)
rng = np.random.default_rng(3)
db = lambda d: 10 ** (d / 20)

subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(ED.parent / "avatar.mp4"), "-vn", "-ac", "2", "-ar", str(SR),
                "-c:a", "pcm_s24le", str(ED / "voice.wav")], check=True)


def env(n, a=0.005, r=0.08):
    e = np.ones(n, np.float32); na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na); e[-nr:] *= np.linspace(1, 0, nr)
    return e


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, hi], "band", fs=SR, output="sos"), x).astype(np.float32)


def put(x, t, g, pan=0.5):
    x = x if x.ndim == 2 else np.stack([x * np.sqrt(1 - pan), x * np.sqrt(pan)], 1).astype(np.float32)
    sm.place(buf, x, t, g)


def noise(d):
    return rng.standard_normal(int(d * SR)).astype(np.float32)


def buzz(d=0.36):
    n = int(d * SR); tt = np.arange(n) / SR
    x = signal.square(2 * np.pi * 172 * tt) * 0.5 + np.sin(2 * np.pi * 344 * tt) * 0.3
    return (bp(x.astype(np.float32), 120, 900) * env(n, 0.01, 0.04)).astype(np.float32)


def whoosh(d=0.42, up=True):
    n = int(d * SR); x = noise(d); f = np.linspace(300, 5000, n) if up else np.linspace(5000, 300, n)
    y = np.zeros(n, np.float32)
    for i in range(0, n, 256):
        y[i:i + 256] = bp(x[max(0, i - 2048):i + 256], f[i] * 0.6, min(f[i] * 1.6, 20000))[-len(x[i:i + 256]):]
    return (y * np.sin(np.linspace(0, np.pi, n)) ** 2 / (np.abs(y).max() + 1e-9)).astype(np.float32)


def pop():
    n = int(0.09 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * (900 - 5000 * tt) * tt) * env(n, 0.002, 0.07)).astype(np.float32)


def tick():
    return (bp(noise(0.012), 2500, 7000) * env(int(0.012 * SR), 0.0005, 0.01)).astype(np.float32)


def thud():
    x = signal.sosfilt(signal.butter(2, 220, "low", fs=SR, output="sos"), noise(0.12)) * env(int(0.12 * SR), 0.002, 0.1)
    return (x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def chime(notes, gap=0.08):
    out = np.zeros(int((gap * len(notes) + 1.2) * SR), np.float32)
    for i, m in enumerate(notes):
        x = sm.bell_note(m); x = x[:, 0] if x.ndim == 2 else x
        i0 = int(i * gap * SR); out[i0:i0 + len(x)] += x[: len(out) - i0]
    return out


def typing(t0, t1, g=db(-36)):
    t = t0
    while t < t1:
        put(tick(), t, g * rng.uniform(0.6, 1.0), rng.uniform(0.35, 0.65)); t += rng.uniform(0.05, 0.12)


def whoosh_into(word_t, d=0.42, g=db(-28)):        # peak (centre) 0.2 s before the word
    put(whoosh(d), word_t - 0.2 - d / 2, g)


# ---- hook: Level 1 night (0-2.9), Level 4 morning (2.9-4.9)
put(sm.impact(), 0.0, db(-30))
for t in (0.25, 0.75, 1.55, 2.05):
    put(buzz(), t, db(-30))
typing(1.42, 2.85)
put(whoosh(0.34, up=False), 3.12 - 0.17, db(-32))                 # soft air on the day cut
put(chime([84, 88], 0.06), 3.30, db(-36))                         # one gentle notification
put(whoosh(0.4), 4.75 - 0.2, db(-31))                            # into the face beat (pause 4.68-5.14)

# ---- staircase overview + levels
for k in range(4):
    put(tick(), 7.42 + k * 0.05, db(-30))
put(pop(), 7.6, db(-31))                                          # YOU? lands
for t in (11.50, 21.06, 32.66):                                 # L1 rides the overview ticks (no whoosh on "one")
    whoosh_into(t)
for t in (8.0, 11.86, 21.38, 32.98):
    put(pop(), t, db(-32))
put(pop(), 8.88, db(-32)); put(pop(), 9.74, db(-33))
put(tick(), 10.12, db(-26)); put(thud(), 10.84, db(-27))
put(pop(), 12.30, db(-32))
for t in (13.64, 14.52, 15.28):
    put(thud(), t + 0.1, db(-29))                                 # paper lands at the end of the drop
put(thud(), 16.34, db(-27))
typing(18.45, 20.3, db(-38)); put(chime([79, 84], 0.07), 19.74, db(-35))
put(pop(), 21.82, db(-32))
for t in (22.86, 23.38, 24.16):
    put(tick(), t, db(-24)); put(pop(), t + 0.02, db(-34))
put(pop(), 25.98, db(-33)); typing(26.76, 27.95)
put(pop(), 28.64, db(-32))
put(pop(), 30.25, db(-33)); put(tick(), 31.61, db(-24)); put(chime([76, 79, 84], 0.07), 32.05, db(-33))
put(tick(), 33.5, db(-26)); put(pop(), 33.97, db(-33))
typing(35.09, 38.6, db(-38)); put(tick(), 38.95, db(-24))
for i in range(7):
    put(chime([88], 0.0), 39.75 + i * 0.16, db(-40))
put(thud(), 41.41, db(-29))

# ---- payoff + guide + CTAs
put(whoosh(0.5), 43.05 - 0.25, db(-29))                           # stage grows (pause 42.6-43.15)
for i in range(3):
    put(tick(), 44.0 + i * 0.37, db(-30))                         # YOU climbs
put(sm.impact(), 45.10, db(-27)); put(chime([79, 84, 88], 0.08), 45.18, db(-33))
put(whoosh(0.3, up=False), 46.48 - 0.15, db(-33))
put(pop(), 46.81, db(-32)); put(thud(), 48.99, db(-29))
put(tick(), 51.35, db(-26)); put(pop(), 52.35, db(-30)); put(chime([84, 88], 0.06), 54.25, db(-35))
put(pop(), 55.19, db(-32)); put(tick(), 58.49, db(-26))

# duck every effect 6 dB while he talks
v, vsr = sf.read(ED / "voice.wav"); assert vsr == SR
v = np.abs(v if v.ndim == 1 else v.mean(1)); hop = int(0.01 * SR); F = len(v) // hop
act = 20 * np.log10(np.sqrt((v[:F * hop].reshape(F, hop) ** 2).mean(1)) + 1e-9) > -45
g = np.where(act, db(-6), 1.0); y = np.empty(F); cur = 1.0
for i in range(F):
    a = 0.7 if g[i] < cur else 0.96
    cur = a * cur + (1 - a) * g[i]; y[i] = cur
buf *= np.interp(np.arange(N) / SR, (np.arange(F) + 0.5) * 0.01, y, right=1.0)[:, None].astype(np.float32)
assert np.isfinite(buf).all()
sf.write(ED / "sfx.wav", buf, SR, subtype="PCM_24")
print(f"sfx.wav {N / SR:.2f}s peak {20 * np.log10(np.abs(buf).max() + 1e-9):.1f} dBFS")
