"""Reel-05 SFX stem on the master timeline (all synthesized, royalty-free). Every cue sits on its visual event
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
LEN = 58.7
N = int(LEN * SR)
buf = np.zeros((N, 2), np.float32)
rng = np.random.default_rng(3)
db = lambda d: 10 ** (d / 20)

subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "0.24", "-i", str(ED.parent / "avatar.mp4"), "-vn", "-ac", "2", "-ar", str(SR),
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


# ---- hook (0 - 5.40): the phone lights up, he picks it up, turns it to camera
put(sm.impact(), 0.0, db(-31))
put(buzz(), 0.22, db(-31)); put(chime([84, 88], 0.06), 0.27, db(-34))     # notification as the screen lights
put(whoosh(0.3), 1.15, db(-34))                                            # peak 1.30, 'ka' at 1.52
put(whoosh(0.3, up=False), 2.98, db(-33)); put(thud(), 3.10, db(-29))   # label swap on 'Aur'
put(whoosh(0.34, up=False), 5.08, db(-32))                                 # into the 2 AM bedroom: peak 5.25, 'Socho' 5.44

# everything below is written in aligned (pre-trim) time; the voice starts 0.24 s earlier on the master
_put = put
put = lambda x, t, g, pan=0.5: _put(x, t - 0.24, g, pan)

# ---- 2 AM customer
typing(5.64, 6.70, db(-38))                                                 # starts on the cut (5.40)
put(tick(), 6.80, db(-27)); put(tick(), 6.92, db(-30))                      # the 2:04 clock
put(pop(), 8.16, db(-31)); put(chime([88], 0.0), 8.18, db(-37))             # her message

# ---- chat: the agent replies
whoosh_into(9.48)
put(pop(), 9.36, db(-33)); put(tick(), 9.74, db(-30))
put(pop(), 10.02, db(-31)); put(pop(), 10.92, db(-33)); put(pop(), 11.14, db(-33))
put(tick(), 11.46, db(-24)); put(pop(), 11.56, db(-33)); put(chime([79, 84, 88], 0.07), 11.80, db(-33))
put(pop(), 12.18, db(-32))                                                   # BOOKED on the salon shot

# ---- free tool reveal + API + free plan
whoosh_into(13.45)
put(pop(), 13.61, db(-32)); put(pop(), 13.90, db(-33))
for i in range(5):
    put(tick(), 14.40 + i * 0.12, db(-33))
put(sm.impact(), 15.40, db(-29)); put(chime([79, 84], 0.07), 15.45, db(-35))
put(pop(), 16.59, db(-32)); put(pop(), 17.09, db(-32))
put(tick(), 17.79, db(-30)); put(pop(), 18.37, db(-31))
for t in (18.55, 18.95, 19.15):
    put(tick(), t, db(-29))
put(pop(), 19.74, db(-32))
for i in range(9):
    put(tick(), 20.42 + i * 0.07, db(-33))
put(thud(), 21.05, db(-28)); put(pop(), 21.53, db(-33))

# ---- face beat + steps
whoosh_into(22.29); put(pop(), 22.91, db(-31))
whoosh_into(24.19); put(pop(), 24.45, db(-33))
put(tick(), 25.61, db(-24)); typing(26.93, 27.50); put(chime([84, 88], 0.06), 27.57, db(-34))
whoosh_into(28.43, 0.36); put(pop(), 28.60, db(-33))
typing(29.25, 30.80)
for i in range(4):
    put(tick(), 30.95 + i * 0.14, db(-28))
put(thud(), 31.73, db(-28))
whoosh_into(33.01, 0.36); put(pop(), 33.40, db(-33))
typing(34.81, 37.00, db(-38)); put(tick(), 37.25, db(-24)); put(whoosh(0.3), 37.30, db(-35))
put(pop(), 37.78, db(-33)); typing(37.85, 39.20, db(-40)); put(thud(), 39.29, db(-28))

# ---- 24 hours (sleeping owner)
put(whoosh(0.4, up=False), 39.43, db(-33))                                # peak 39.63, 'Aur' at 39.83
put(chime([88], 0.0), 40.30, db(-40)); put(chime([88], 0.0), 40.85, db(-40))   # his phone glows again
put(sm.impact(), 41.08, db(-28))

# ---- rule, guide, CTAs
whoosh_into(42.80)
put(thud(), 43.45, db(-27)); put(pop(), 44.55, db(-32))
put(tick(), 45.20, db(-25)); put(chime([84, 88], 0.06), 45.24, db(-34))
put(pop(), 46.34, db(-32))
for i in range(4):
    put(tick(), 46.70 + i * 0.22, db(-31))
put(thud(), 48.00, db(-28))
put(pop(), 49.80, db(-32)); put(tick(), 50.10, db(-26)); put(pop(), 50.72, db(-33))
put(pop(), 51.16, db(-30)); put(sm.impact(), 51.22, db(-31)); put(pop(), 52.40, db(-32)); put(chime([84, 88], 0.06), 53.44, db(-35))
put(pop(), 54.34, db(-32)); put(pop(), 54.80, db(-34)); put(tick(), 57.44, db(-26))

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
