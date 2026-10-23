"""voice.wav (master timeline: raw dialogue 0-15.36 + DJI pieces, 30 ms fades at every cut) and sfx.wav
(synthesized, royalty-free; cues on the gfx events; ducked 6 dB under the voice; whooshes peak >= 0.15 s before a word)."""
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
RAW = r"C:\Users\PARAS ARORA\Downloads\New Reel Raw Footage .mp4"
DJI = r"C:\Users\PARAS ARORA\Downloads\DJI_20261019154130_0355_D.MP4"
FADE = 0.03


def load(path, s, e):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", path, "-vn", "-ac", "2",
                          "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    n = int(FADE * SR); r = np.linspace(0, 1, n, dtype=np.float32)[:, None]
    x[:n] *= r; x[-n:] *= r[::-1]
    return x


# ---- voice master (DJI talking head is ~+3 dB hotter than the raw clip; matched by measurement below)
voice = np.zeros((N, 2), np.float32)
seg = load(RAW, 0.0, TL["split"]); voice[:len(seg)] += seg
for p in TL["pieces"]:
    x = load(DJI, *p["src"]); i0 = int(round(p["out"][0] * SR)); n = min(len(x), int(round((p["out"][1] - p["out"][0]) * SR)))
    voice[i0:i0 + n] += x[:n]
rms = lambda a: 20 * np.log10(np.sqrt((a ** 2).mean()) + 1e-12)
g_raw, g_dji = rms(voice[:int(TL["split"] * SR)]), rms(voice[int(TL["split"] * SR):int(TL["length"] * SR)])
voice[int(TL["split"] * SR):] *= 10 ** ((g_raw - g_dji) / 20)              # level-match the two sources
sf.write(ED / "voice.wav", voice, SR, subtype="PCM_24")
print(f"voice: raw {g_raw:.1f} dBFS, dji {g_dji:.1f} dBFS -> matched")

buf = np.zeros((N, 2), np.float32)
rng = np.random.default_rng(5)
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


def tick():
    return (bp(noise(0.012), 2500, 7000) * env(int(0.012 * SR), 0.0005, 0.01)).astype(np.float32)


def glitch(d=0.3):
    x = noise(d) * (signal.square(2 * np.pi * 37 * np.arange(int(d * SR)) / SR) > 0)
    return (bp(x.astype(np.float32), 800, 6000) * env(int(d * SR), 0.003, 0.05)).astype(np.float32)


def chime(notes, gap=0.08):
    out = np.zeros(int((gap * len(notes) + 1.2) * SR), np.float32)
    for i, m in enumerate(notes):
        x = sm.bell_note(m); x = x[:, 0] if x.ndim == 2 else x
        i0 = int(i * gap * SR); out[i0:i0 + len(x)] += x[: len(out) - i0]
    return out


# split
put(sm.impact(), 0.0, db(-30)); put(pop(), 0.10, db(-32)); put(pop(), 0.18, db(-33))
for t in (5.11, 8.76, 12.91):
    put(chime([84, 88], 0.06), t, db(-36))                               # claim chips
put(glitch(0.32), 14.86, db(-30)); put(glitch(0.28), 14.94, db(-31))       # REAL/FAKE flip (pause after "na")
put(whoosh(0.45), 15.36 - 0.25, db(-28))                                  # into the how-to (peak 0.1 s before cut)
# steps
for t in (15.70, 16.00, 20.39, 21.00, 22.03, 24.58, 26.98, 29.40, 32.42, 36.28, 40.30, 46.38):
    put(pop(), t, db(-33))
put(chime([79, 84], 0.07), 23.61, db(-34)); put(chime([76, 79, 84], 0.07), 28.37, db(-35))
t = 29.54
while t < 31.05:
    put(tick(), t, db(-38), rng.uniform(0.4, 0.6)); t += rng.uniform(0.05, 0.11)
put(chime([84], 0.0), 32.42, db(-34))
for t0, t1 in ((33.24, 36.28), (47.68, 52.24), (60.92, 63.12)):          # layout changes: soft swoosh, peak before the cut
    put(whoosh(0.3, up=False), t0 - 0.2, db(-32)); put(whoosh(0.3), t1 - 0.2, db(-34))
put(sm.impact(), 43.22, db(-34)); put(sm.impact(), 44.10, db(-34)); put(chime([79, 84, 88], 0.08), 44.87, db(-33))
put(sm.impact(), 48.30, db(-29)); put(chime([84, 88], 0.06), 48.73, db(-35)); put(pop(), 50.44, db(-32))
put(pop(), 56.63, db(-33)); put(pop(), 59.68, db(-33)); put(chime([79, 84], 0.07), 62.26, db(-33))

# duck under the voice
v = np.abs(voice.mean(1)); hop = int(0.01 * SR); F = len(v) // hop
act = 20 * np.log10(np.sqrt((v[:F * hop].reshape(F, hop) ** 2).mean(1)) + 1e-9) > -45
g = np.where(act, db(-6), 1.0); y = np.empty(F); cur = 1.0
for i in range(F):
    a = 0.7 if g[i] < cur else 0.96; cur = a * cur + (1 - a) * g[i]; y[i] = cur
buf *= np.interp(np.arange(N) / SR, (np.arange(F) + 0.5) * 0.01, y, right=1.0)[:, None].astype(np.float32)
sf.write(ED / "sfx.wav", buf, SR, subtype="PCM_24")
print(f"sfx {N / SR:.2f}s peak {20 * np.log10(np.abs(buf).max() + 1e-9):.1f} dBFS")
