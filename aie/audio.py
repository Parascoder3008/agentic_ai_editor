"""Loudness on a 10 ms grid, measured from the audio itself, for placing cuts.

Ported from the long-form's body_edl.py / wordgap.py; the arithmetic is kept exactly as it was, because cut edges
are compared to the shipped edit to the millisecond.
"""
import subprocess

import numpy as np

SR = 16000
HOP = SR // 100                      # 10 ms


def load(path, sr: int = SR) -> np.ndarray:
    """Mono float audio via ffmpeg, as 16-bit samples scaled to [-1, 1) (what the cutter measured on)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


class Envelope:
    """RMS loudness of 10 ms frames. Frame k covers time k/100 s."""

    def __init__(self, x: np.ndarray):
        self.env = np.sqrt(np.convolve(x ** 2, np.ones(HOP) / HOP, mode="same"))[::HOP]
        self.db = 20 * np.log10(self.env + 1e-9)

    @classmethod
    def of(cls, path) -> "Envelope":
        return cls(load(path))

    def quiet(self, t0: float, t1: float) -> float:
        """Start of the quietest 10 ms frame in [t0, t1] (a cut placed here doesn't click or clip a word)."""
        a, b = int(max(0, t0) * 100), int(t1 * 100) + 1
        return (a + int(np.argmin(self.env[a:b]))) / 100 if b > a else t0

    def onset(self, t: float, lim: float, fwd: bool = True, speech_db: float = -45.0):
        """First (fwd) / last (back) 10 ms frame of clear speech within lim s of t, else None."""
        a, b = (int(t * 100), int((t + lim) * 100)) if fwd else (int((t - lim) * 100), int(t * 100))
        idx = np.flatnonzero(self.db[a:b] > speech_db)
        return None if not len(idx) else (a + (idx[0] if fwd else idx[-1])) / 100

    def islands(self, m0: float, m1: float, silence_db: float = -55.0, gap: float = 0.40) -> list:
        """Split [m0, m1] into stretches of sound at every silence of at least gap seconds."""
        a, b = int(m0 * 100), int(m1 * 100)
        loud = self.db[a:b] > silence_db
        islands, start, last_loud = [], None, None
        for i, lv in enumerate(loud):
            t = (a + i) / 100
            if lv:
                if start is None:
                    start = t
                elif t - last_loud >= gap:
                    islands.append((start, last_loud + 0.01))
                    start = t
                last_loud = t
        if start is not None:
            islands.append((start, last_loud + 0.01))
        return islands

    def bar(self, t: float, half: float = 0.3) -> str:
        """One character per 10 ms around t: '#' speech > -40 dB, '+' > -55 dB, '.' quieter; '|' marks t.
        Followed by the deepest valley, the place a cut between two words belongs."""
        a, b = int((t - half) * 100), int((t + half) * 100)
        seg = self.db[a:b]
        s = "".join("#" if v > -40 else "+" if v > -55 else "." for v in seg)
        v = a + int(np.argmin(seg))
        mid = int(half * 100)
        return f"{t:8.2f}: {s[:mid]}|{s[mid:]}   deepest {v / 100:.2f}s ({self.db[v]:.0f} dB)"
