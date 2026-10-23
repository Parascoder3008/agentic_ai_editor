"""Pilot-01 SFX stem: every hit synthesized here (score_music's synth voices + a whoosh and a pop),
placed on the force-aligned word times, mixed to one 48 kHz stereo WAV so the compose gets one input."""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
import score_music as sm  # noqa: E402

import json  # noqa: E402

ED = Path(__file__).resolve().parent
TM = json.loads((ED / "timemap.json").read_text()) if (ED / "timemap.json").exists() else None
M = (lambda t: float(np.interp(t, TM["old"], TM["new"]))) if TM else (lambda t: t)   # cues authored on the v1 take
SR, LEN = sm.SR, M(49.84)
OUT = ED / "sfx.wav"


def whoosh(d=0.42):
    """noise swept up then away; loudest at 70 % of its length (= the cut)."""
    n = int(d * SR); t = sm.tsec(n)
    y = sm.riser(d)[:, 0]
    env = np.where(t < 0.7 * d, (t / (0.7 * d)) ** 1.5, np.exp(-(t - 0.7 * d) / 0.05))
    return sm.oneshot(y * env, fade=0.02)


def pop():
    n = int(0.09 * SR); t = sm.tsec(n)
    f = 900 * np.exp(-t / 0.03) + 420
    return sm.oneshot(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.025), fade=0.01)


buf = np.zeros((int((LEN + 3) * SR), 2), np.float32)


def put(x, t, db, pan=0.5):
    sm.place(buf, x, M(t), 10 ** (db / 20), pan)


W = whoosh()
ONSETS = [w["start"] for w in json.loads((ED / "words.json").read_text(encoding="utf-8"))["words"]]


def clear_peak(p, guard=0.15):
    """a whoosh peaking on a word onset swallows its first consonant ('Plugin' heard as 'lagin'):
    keep the peak >= guard before the next onset."""
    nxt = min((o for o in ONSETS if o >= p - 0.05), default=1e9)
    return min(p, nxt - guard)


for cut in (3.05, 8.85, 14.15, 19.35, 28.55, 31.95, 35.2, 39.95, 43.95, 45.95):
    p = clear_peak(M(cut))
    sm.place(buf, W, p - 0.7 * 0.42, 10 ** (-18 / 20))
for t in (3.72, 4.85, 5.71, 6.59, 7.66, 9.79, 11.44, 12.7, 14.24, 15.3, 16.65, 17.63, 18.75,
          27.98, 30.56, 31.57, 40.3, 42.26, 42.64, 48.23):
    put(pop(), t, -22)
put(sm.impact(), 1.95, -27)           # "= 1 FREE CLAUDE PLUGIN" slam on "chhutti"
put(sm.impact(), 25.06, -13)          # "Boom!" audit card
put(sm.kick("house"), 34.3, -21)      # NO APPROVAL = NO CHANGE banner
put(sm.crash(), 25.06, -28)
for t0, t1 in ((19.5, 20.05), (20.1, 20.7), (22.38, 24.45)):   # typing ticks under the typed lines
    for i, t in enumerate(np.arange(t0, t1, 0.075)):
        put(sm.rim(), float(t), -34 + (i % 3), pan=0.45 + 0.1 * (i % 2))

y = buf[: int(LEN * SR)]
assert np.abs(y).max() < 1.0
sf.write(OUT, y, SR, subtype="PCM_24")
print(f"sfx -> {OUT}  peak {20 * np.log10(np.abs(y).max()):.1f} dBFS")
