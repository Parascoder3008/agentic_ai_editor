"""Synthesized sound effects on the output timeline, ducked under the voice. Nothing is sampled, so the stem is
royalty-free by construction. Ported from reel-05's sfx.py (its library is the canonical one; the stem is reproduced
sample for sample), plus the extra sounds of reel-04 (rustle, pitch-drop, steady typing), the Genjutsu reel (glitch)
and the Equal ad (beds).

job.json "sfx":
  {"seed": 3, "length": 58.7, "voice": "avatar",
   "duck": {"db": -6, "threshold": -45},              effects drop 6 dB while the voice is above -45 dBFS
   "cues": [{"kind": "whoosh", "t": 1.15, "db": -34, "d": 0.3}, ...]}
Cue times are output seconds. Every cue has "kind" and "db" (or the sound's default level); the rest are the sound's
own settings (schema.SFX_KINDS). Cues play in list order from one seeded random stream, so the same list always gives
the same stem.
"""
import numpy as np

from . import music as sm
from .schema import CUE_KEYS
from .schema import SFX_KINDS as KINDS

SR = sm.SR


def db(d):
    return 10 ** (d / 20)


class Renderer:
    def __init__(self, length: float, seed: int):
        self.n = int(length * SR)
        self.buf = np.zeros((self.n, 2), np.float32)
        self.rng = np.random.default_rng(seed)
        sm.reset()                        # impact() and the bells draw from the score's own stream: start it fresh

    # ---- primitives (as in reel-05)
    def env(self, n, a=0.005, r=0.08):
        e = np.ones(n, np.float32); na, nr = int(a * SR), int(r * SR)
        e[:na] = np.linspace(0, 1, na); e[-nr:] *= np.linspace(1, 0, nr)
        return e

    def bp(self, x, lo, hi, order=2):
        from scipy import signal
        return signal.sosfilt(signal.butter(order, [lo, hi], "band", fs=SR, output="sos"), x).astype(np.float32)

    def noise(self, d):
        return self.rng.standard_normal(int(d * SR)).astype(np.float32)

    def put(self, x, t, g, pan=0.5):
        x = x if x.ndim == 2 else np.stack([x * np.sqrt(1 - pan), x * np.sqrt(pan)], 1).astype(np.float32)
        sm.place(self.buf, x, t, g)

    # ---- sounds
    def buzz(self, d=0.36):
        from scipy import signal
        n = int(d * SR); tt = np.arange(n) / SR
        x = signal.square(2 * np.pi * 172 * tt) * 0.5 + np.sin(2 * np.pi * 344 * tt) * 0.3
        return (self.bp(x.astype(np.float32), 120, 900) * self.env(n, 0.01, 0.04)).astype(np.float32)

    def whoosh(self, d=0.42, up=True):
        n = int(d * SR); x = self.noise(d); f = np.linspace(300, 5000, n) if up else np.linspace(5000, 300, n)
        y = np.zeros(n, np.float32)
        for i in range(0, n, 256):
            y[i:i + 256] = self.bp(x[max(0, i - 2048):i + 256], f[i] * 0.6, min(f[i] * 1.6, 20000))[-len(x[i:i + 256]):]
        return (y * np.sin(np.linspace(0, np.pi, n)) ** 2 / (np.abs(y).max() + 1e-9)).astype(np.float32)

    def pop(self):
        n = int(0.09 * SR); tt = np.arange(n) / SR
        return (np.sin(2 * np.pi * (900 - 5000 * tt) * tt) * self.env(n, 0.002, 0.07)).astype(np.float32)

    def tick(self, d=0.012, lo=2500, hi=7000, release=0.01):
        return (self.bp(self.noise(d), lo, hi) * self.env(int(d * SR), 0.0005, release)).astype(np.float32)

    def thud(self):
        from scipy import signal
        x = signal.sosfilt(signal.butter(2, 220, "low", fs=SR, output="sos"), self.noise(0.12)) \
            * self.env(int(0.12 * SR), 0.002, 0.1)
        return (x / (np.abs(x).max() + 1e-9)).astype(np.float32)

    def chime(self, notes, gap=0.08):
        out = np.zeros(int((gap * len(notes) + 1.2) * SR), np.float32)
        for i, m in enumerate(notes):
            x = sm.bell_note(m); x = x[:, 0] if x.ndim == 2 else x
            i0 = int(i * gap * SR); out[i0:i0 + len(x)] += x[: len(out) - i0]
        return out

    def rustle(self, d=0.35):
        """paper: crackly band-passed noise with random grains (reel-04)"""
        x = self.bp(self.noise(d), 1500, 9000) * (self.rng.random(int(d * SR)) < 0.08).astype(np.float32) * 3 \
            + self.bp(self.noise(d), 600, 4000) * 0.35
        return (x * self.env(int(d * SR), 0.004, d * 0.6) / (np.abs(x).max() + 1e-9)).astype(np.float32)

    def pitch_drop(self, d=0.32, f0=920.0, f1=380.0):
        """a tone sliding down ~1.3 octaves: the @venomstech punch sound, measured on his best reel (reel-04)"""
        n = int(d * SR); tt = np.arange(n) / SR
        ph = 2 * np.pi * np.cumsum(f0 * (f1 / f0) ** (tt / d)) / SR
        x = np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)
        return (np.tanh(1.6 * x) * self.env(n, 0.004, d * 0.55) / 1.2).astype(np.float32)

    def glitch(self, d=0.3):
        """gated noise burst (Genjutsu reel)"""
        from scipy import signal
        x = self.noise(d) * (signal.square(2 * np.pi * 37 * np.arange(int(d * SR)) / SR) > 0)
        return (self.bp(x.astype(np.float32), 800, 6000) * self.env(int(d * SR), 0.003, 0.05)).astype(np.float32)

    def bed_sound(self, kind, d):
        """ambience loops (Equal ad): room tone, office murmur, a treadmill belt"""
        if kind == "office":
            return self.bp(self.noise(3), 120, 2500) * 0.25
        if kind == "belt":
            t = np.arange(int(d * SR)) / SR
            return (self.bp(self.noise(d), 200, 1400) * 0.4
                    + 0.25 * np.sin(2 * np.pi * 62 * t) * (1 + 0.3 * np.sin(2 * np.pi * 2.7 * t))).astype(np.float32)
        return self.bp(self.noise(5), 80, 900) * 0.2

    # ---- cues
    def play(self, cue: dict):
        k = cue["kind"]
        s = {**KINDS[k], **{x: v for x, v in cue.items() if x not in CUE_KEYS}}
        g, pan, t = db(cue.get("db", KINDS[k].get("db", -30))), cue.get("pan", 0.5), cue.get("t")
        if k == "typing":
            if s["cps"]:                                      # reel-04: steady rate, quiet, narrow pan
                while t < s["until"]:
                    self.put(self.tick(0.010, 1800, 6000, 0.008), t, g, self.rng.uniform(0.4, 0.6))
                    t += self.rng.uniform(0.6, 1.4) / s["cps"]
            else:                                             # reel-05: uneven bursts, wider pan
                while t < s["until"]:
                    self.put(self.tick(), t, g * self.rng.uniform(0.6, 1.0), self.rng.uniform(0.35, 0.65))
                    t += self.rng.uniform(0.05, 0.12)
            return
        if k == "whoosh_into":
            self.put(self.whoosh(s["d"]), s["word"] - 0.2 - s["d"] / 2, g, pan)
            return
        if k == "bed":
            n = int((s["until"] - t) * SR)
            x = np.resize(self.bed_sound(s["sound"], s["until"] - t), n) * self.env(n, 0.25, 0.25)
            self.put(x.astype(np.float32), t, g, pan)
            return
        x = {"impact": lambda: sm.impact(), "buzz": lambda: self.buzz(s["d"]),
             "chime": lambda: self.chime(s["notes"], s["gap"]), "whoosh": lambda: self.whoosh(s["d"], s["up"]),
             "pop": self.pop, "tick": lambda: self.tick(s["d"], s["lo"], s["hi"], s["release"]), "thud": self.thud,
             "rustle": lambda: self.rustle(s["d"]), "pitch_drop": lambda: self.pitch_drop(s["d"], s["f0"], s["f1"]),
             "glitch": lambda: self.glitch(s["d"]), "riser": lambda: sm.riser(s["d"]), "crash": sm.crash}[k]()
        self.put(x, t, g, pan)

    def duck(self, voice: np.ndarray, gain_db: float = -6.0, threshold: float = -45.0):
        """Every effect drops gain_db while the voice is above threshold (10 ms frames), easing in and out."""
        v = np.abs(voice if voice.ndim == 1 else voice.mean(1))
        hop = int(0.01 * SR); f = len(v) // hop
        act = 20 * np.log10(np.sqrt((v[:f * hop].reshape(f, hop) ** 2).mean(1)) + 1e-9) > threshold
        g = np.where(act, db(gain_db), 1.0); y = np.empty(f); cur = 1.0
        for i in range(f):
            a = 0.7 if g[i] < cur else 0.96
            cur = a * cur + (1 - a) * g[i]; y[i] = cur
        self.buf *= np.interp(np.arange(self.n) / SR, (np.arange(f) + 0.5) * 0.01, y, right=1.0)[:, None].astype(np.float32)


def render(cfg: dict, length: float, voice: np.ndarray | None = None) -> np.ndarray:
    """The SFX stem: every cue in order, then ducked under the voice (float64 or float32, mono or stereo, at SR)."""
    r = Renderer(cfg.get("length", length), cfg.get("seed", 3))
    for cue in cfg.get("cues", []):
        r.play(cue)
    if voice is not None:
        d = cfg.get("duck", {})
        r.duck(voice, d.get("db", -6.0), d.get("threshold", -45.0))
    assert np.isfinite(r.buf).all()
    return r.buf

