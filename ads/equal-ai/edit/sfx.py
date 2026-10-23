"""SFX + ambience stem for the Equal ad (all synthesized, royalty-free). Levels are set relative to the voice and
checked afterwards (effects <= +3 dB over the voice where they overlap speech). Writes sfx.wav (48 kHz stereo)."""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
import score_music as sm  # noqa: E402

ED = Path(__file__).resolve().parent
E = json.loads((ED / "edl.json").read_text(encoding="utf-8"))
T = json.loads((ED / "gfx_times.json").read_text())
SEG = {s["id"]: s for s in E["body"]}
SR = sm.SR
N = int((E["length"] + 1.0) * SR)
buf = np.zeros((N, 2), np.float32)
rng = np.random.default_rng(3)
db = lambda d: 10 ** (d / 20)


def env(n, a=0.005, r=0.08):
    e = np.ones(n, np.float32)
    na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na); e[-nr:] *= np.linspace(1, 0, nr)
    return e


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, hi], "band", fs=SR, output="sos"), x).astype(np.float32)


def st(x, pan=0.5):
    return np.stack([x * np.sqrt(1 - pan), x * np.sqrt(pan)], 1).astype(np.float32)


def put(x, t, g, pan=0.5):
    sm.place(buf, x if x.ndim == 2 else st(x, pan), t, g)


def noise(d):
    return rng.standard_normal(int(d * SR)).astype(np.float32)


def bed(t0, t1, x, g):
    n = int((t1 - t0) * SR); x = np.resize(x, n) * env(n, 0.25, 0.25)
    put(x, t0, g)


# ---------- intro ambience ----------
office = bp(noise(3), 120, 2500) * 0.25
bed(0.0, 2.55, office, db(-30))
t = np.arange(int(2.6 * SR)) / SR
belt = bp(noise(2.6), 200, 1400) * 0.4 + 0.25 * np.sin(2 * np.pi * 62 * t) * (1 + 0.3 * np.sin(2 * np.pi * 2.7 * t))
bed(2.55, 5.10, belt.astype(np.float32), db(-30))
for k in range(7):                                                    # footfalls ~162 spm
    thump = signal.sosfilt(signal.butter(2, 180, "low", fs=SR, output="sos"), noise(0.09)) * env(int(0.09 * SR), 0.002, 0.07)
    put(thump.astype(np.float32), 2.62 + k * 0.37, db(-22))
room = bp(noise(5), 80, 900) * 0.2
bed(5.10, E["intro_end"], room, db(-34))
tc = 5.12
while tc < 6.30:                                                      # typing until he reacts
    click = bp(noise(0.03), 1800, 6000) * env(int(0.03 * SR), 0.001, 0.025)
    put(click, tc, db(-35) * rng.uniform(0.6, 1.0), rng.uniform(0.35, 0.65)); tc += rng.uniform(0.07, 0.19)


# ---------- phone + Equal cues ----------
def buzz(d=0.38):
    n = int(d * SR); tt = np.arange(n) / SR
    x = signal.square(2 * np.pi * 172 * tt) * 0.5 + np.sin(2 * np.pi * 344 * tt) * 0.3
    x = signal.sosfilt(signal.butter(2, [120, 900], "band", fs=SR, output="sos"), x) * env(n, 0.01, 0.04)
    return x.astype(np.float32)


def chime(notes, gap=0.09, g=1.0):
    out = np.zeros(int((gap * len(notes) + 1.2) * SR), np.float32)
    for i, m in enumerate(notes):
        x = sm.bell_note(m); x = x[:, 0] if x.ndim == 2 else x
        i0 = int(i * gap * SR); out[i0:i0 + len(x)] += x[: len(out) - i0] * g
    return out


def whoosh(d=0.42, up=True):
    n = int(d * SR); x = noise(d); f = np.linspace(300, 5000, n) if up else np.linspace(5000, 300, n)
    y = np.zeros(n, np.float32); s = 0.0
    for i in range(0, n, 256):                                         # swept band-pass, block-wise
        y[i:i + 256] = bp(x[max(0, i - 2048):i + 256], f[i] * 0.6, min(f[i] * 1.6, 20000))[-len(x[i:i + 256]):]
    e = np.sin(np.linspace(0, np.pi, n)) ** 2
    return (y * e / (np.abs(y).max() + 1e-9)).astype(np.float32)


def pop():
    n = int(0.09 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * (900 - 5000 * tt) * tt) * env(n, 0.002, 0.07)).astype(np.float32)


def tick():
    return (bp(noise(0.012), 2500, 7000) * env(int(0.012 * SR), 0.0005, 0.01)).astype(np.float32)


for on in (T["c1_in"], T["c2_in"], T["c3_in"]):                    # closing gag uses the ringtone instead
    put(buzz(), on, db(-27)); put(buzz(), on + 0.5, db(-30))
for eq in (T["c1_eq"], T["c2_eq"], T["c3_eq"], T["r_eq"]):
    put(chime([72, 76, 79], 0.07), eq, db(-31))                       # "Equal is on it" (C-E-G up)
put(pop(), T["c3_msg"], db(-31))

# ringtone for the closing gag: an original 4-note marimba phrase, twice
ring = chime([79, 76, 72, 76], 0.12, 1.0)[: int(0.85 * SR)]
ring *= np.r_[np.ones(len(ring) - int(0.25 * SR)), np.linspace(1, 0, int(0.25 * SR))].astype(np.float32)   # tail out before "phir"
RING_AT = SEG["s14"]["out"][1] - 0.02                                # in the gap before "Arre yaar"
put(ring, RING_AT, db(-23))

# ---------- body ----------
for t0 in (18.40, 23.80, 28.76, 42.45, 47.30):                        # into app UI (peak just before the cut)
    put(whoosh(0.42), t0 - 0.30, db(-27))
for t0 in (19.99, 26.50):                                              # UI -> UI swipe
    put(whoosh(0.30, up=False), t0 - 0.20, db(-30))
for t0 in (56.40, 66.05):                                              # back to the assistant shots
    put(whoosh(0.36), t0 - 0.26, db(-29))
put(pop(), T["logo"], db(-28)); put(chime([84, 88], 0.06), T["logo"] + 0.05, db(-33))
put(whoosh(0.25, up=False), T["salary_x"] - 0.05, db(-31))
put(pop(), T["ai_in"] - 0.10, db(-32))
put(pop(), T["ins_in"], db(-31))
tc = T["ins_type"]
while tc < T["ins_type"] + 1.9:
    put(tick(), tc, db(-37), rng.uniform(0.4, 0.6)); tc += rng.uniform(0.05, 0.11)
put(pop(), T["cnt_in"], db(-31))
for k in range(10):
    put(tick(), T["cnt_in"] + 0.15 + 0.9 * (1 - (1 - k / 9) ** 2), db(-37))
put(chime([84], 0.0), T["cnt_in"] + 1.08, db(-34))
put(pop(), T["pa_in"], db(-31))
put(pop(), T["play"], db(-31)); put(pop(), T["apple"], db(-31))
imp = sm.impact(); put(imp, T["end"], db(-24))
put(chime([79, 84, 88], 0.08), T["end"] + 0.1, db(-26))

# duck every effect 6 dB while he talks (voice envelope, 30 ms attack / 250 ms release)
v, vsr = sf.read(ED / "voice.wav"); assert vsr == SR
v = np.abs(v if v.ndim == 1 else v.mean(1)); hop = int(0.01 * SR); F = len(v) // hop
act = 20 * np.log10(np.sqrt((v[:F * hop].reshape(F, hop) ** 2).mean(1)) + 1e-9) > -45
g = np.where(act, db(-6), 1.0); y = np.empty(F); cur = 1.0
for i in range(F):
    a = 0.7 if g[i] < cur else 0.96
    cur = a * cur + (1 - a) * g[i]; y[i] = cur
gain = np.interp(np.arange(N) / SR, (np.arange(F) + 0.5) * 0.01, y)
buf *= gain[:, None].astype(np.float32)
assert np.isfinite(buf).all()
sf.write(ED / "sfx.wav", buf, SR, subtype="PCM_24")
print(f"sfx.wav {N / SR:.2f}s peak {20 * np.log10(np.abs(buf).max() + 1e-9):.1f} dBFS")
