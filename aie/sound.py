"""The voice stem, the mix, and one loudness-normalised audio file per variant.

Voice stem (build/voice.wav, 48 kHz stereo on the output timeline):
  from a source   an avatar render: its audio from voice_offset on (reel-05)
  from the cut    every piece from its take; each joint crossfades through a few ms of room tone measured on the take
                  ("handles"), never into a new word (reel-04)
Mix per variant (job.json "mix"):
  {"voice": "avatar", "gain_db": "auto", "voice_lufs": -17, "joint_fade": 0.02, "tail": 0.8}
  gain "auto": the voice alone sets the gain so it reaches the limiter at about voice_lufs; loudnorm then only trims
  (stays linear, no pumping). voice + sfx + music -> gain -> limiter -> the variant's ranges (fades at every joint,
  the last range runs on into the freeze) -> fade out -> two-pass loudnorm to -14 LUFS, true peak -1.5 dBTP.
Ported from reel-05's and reel-04's compose.py and reel-04's sfx.py.
"""
import json
import subprocess
from pathlib import Path

import numpy as np

from .ffmpeg import run

SR = 48000
LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"
LIMITER = "alimiter=limit=0.72:attack=4:release=60:level=disabled"


# ---------------------------------------------------------------- voice stem

def voice_from_source(src: Path, offset: float, out: Path) -> Path:
    run(["ffmpeg", "-y", "-v", "error", "-ss", str(offset), "-i", src, "-vn", "-ac", "2", "-ar", str(SR),
         "-c:a", "pcm_s24le", out])
    return out


def _load(path, s, e, h_in=0.0, h_out=0.0):
    """Source [s - h_in, e + h_out]; the handles carry the fades (tone into tone). No handle -> a 15 ms fade inside."""
    raw = run_bytes(["ffmpeg", "-v", "error", "-ss", f"{s - h_in:.3f}", "-t", f"{e - s + h_in + h_out:.3f}", "-i",
                     str(path), "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"])
    x = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    for n, rev in ((int(max(h_in, 0.015) * SR), False), (int(max(h_out, 0.015) * SR), True)):
        r = np.sin(np.linspace(0, np.pi / 2, n, dtype=np.float32))[:, None] ** 2
        if rev:
            x[-n:] *= r[::-1]
        else:
            x[:n] *= r
    return x


def run_bytes(cmd) -> bytes:
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def _edb(path) -> np.ndarray:
    """5 ms loudness of a take (16 kHz mono), for finding room tone around a joint."""
    xd = np.frombuffer(run_bytes(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f",
                                  "f32le", "-"]), np.float32)
    return 20 * np.log10(np.sqrt(np.convolve(xd ** 2, np.ones(80) / 80, mode="same"))[::80] + 1e-9)


def _handle(edb, t, step):
    """Extend while in room tone or while the word still decays; stop at any new onset (restarts aren't in the text)."""
    at = lambda x: edb[min(max(int(x * 200), 0), len(edb) - 1)]     # clamped: a cut at the very start/end of a take
    h, prev = 0.0, at(t)
    while h < 0.04:
        cur = at(t + step * (h + 0.005))
        if cur > -45 and cur > prev:
            break
        h += 0.005; prev = cur
    return h


def voice_from_pieces(pieces: list, files: dict, length: float, out: Path) -> Path:
    """pieces: [{"src", "in", "out", "out0"}] in output order; files: {src: path}; length: output seconds."""
    import soundfile as sf
    n = int(length * SR)
    edb = {k: _edb(f) for k, f in files.items() if any(p["src"] == k for p in pieces)}
    voice = np.zeros((n, 2), np.float32)
    prev = None
    for p in pieces:
        s, e, o0 = p["in"], p["out"], p["out0"]
        joined = (prev is not None and prev["src"] == p["src"] and abs(prev["out"] - s) < 1e-3
                  and abs(prev["out0"] + prev["out"] - prev["in"] - o0) < 1e-3)
        h_in = 0.0 if joined else _handle(edb[p["src"]], s, -1)
        h_out = _handle(edb[p["src"]], e, +1)
        x = _load(files[p["src"]], s, e, h_in, h_out)
        if joined:                                   # the same take continues across a piece boundary: no fade-in
            k = int(0.015 * SR)
            x[:k] /= np.maximum(np.sin(np.linspace(0, np.pi / 2, k, dtype=np.float32))[:, None] ** 2, 1e-3)
        i0 = int(round((o0 - h_in) * SR))
        if i0 < 0:
            x, i0 = x[-i0:], 0
        voice[i0:i0 + len(x)] += x[:max(0, n - i0)]
        prev = p
    sf.write(out, voice, SR, subtype="PCM_24")
    return out


# ---------------------------------------------------------------- mix

def lufs(path) -> float:
    o = run(["ffmpeg", "-v", "info", "-i", path, "-af", "ebur128", "-f", "null", "-"]).stderr
    return float([ln for ln in o.splitlines() if ln.strip().startswith("I:")][-1].split()[1])


def premix_cmd(voice, sfx, music, dst, end: float, gain_db: float, mute_after: float | None = None) -> list:
    """voice + sfx + music -> gain -> limiter, trimmed at end; mute_after silences the voice from then on (a freeze
    must not leak the next line)."""
    vf = (f"[0:a]volume=0:enable='gte(t,{mute_after:.3f})'[vo];" if mute_after is not None else "[0:a]anull[vo];")
    ins = [x for f in (voice, sfx, music) if f for x in ("-i", f)]
    n = len(ins) // 2
    mixer = "".join(["[vo]"] + [f"[{i}:a]" for i in range(1, n)]) + f"amix=inputs={n}:normalize=0:duration=longest,"
    return ["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex",
            vf + mixer + f"atrim=0:{end:.3f},volume={gain_db:.2f}dB,{LIMITER}", "-ar", str(SR), "-c:a", "pcm_s24le", dst]


def variant_graph(ranges: list, freeze: float, fade: float) -> tuple:
    """The variant's ranges cut from the premix (fades at each joint; the last range runs on into the freeze), then a
    0.5 s fade out. Returns (filter graph, total seconds)."""
    total = sum(b - a for a, b in ranges) + freeze
    parts = "".join(f"[0:a]atrim={a}:{b + (freeze if i == len(ranges) - 1 else 0)},asetpts=PTS-STARTPTS,"
                    f"afade=t=in:st=0:d={fade},afade=t=out:st={b - a + (freeze if i == len(ranges) - 1 else 0) - fade:.3f}"
                    f":d={fade}[a{i}];" for i, (a, b) in enumerate(ranges))
    cat = "".join(f"[a{i}]" for i in range(len(ranges))) + f"concat=n={len(ranges)}:v=0:a=1,afade=t=out:st={total - 0.5:.3f}:d=0.5[a]"
    return parts + cat, total


def loudnorm(src, dst) -> dict:
    """Two-pass: measure, then normalise linearly to -14 LUFS / -1.5 dBTP."""
    o = run(["ffmpeg", "-v", "info", "-i", src, "-af", f"{LOUDNORM}:print_format=json", "-f", "null", "-"]).stderr
    j = json.loads(o[o.rfind("{"): o.rfind("}") + 1])
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af",
         f"{LOUDNORM}:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
         f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true",
         "-ar", str(SR), "-c:a", "pcm_s24le", dst])
    return j


def measure(path) -> dict:
    """Integrated loudness and true peak of a finished file."""
    o = run(["ffmpeg", "-v", "info", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    tail = o[o.rfind("Summary:"):]
    get = lambda key: float(tail.split(key)[1].split()[0])
    return {"lufs": get("I:"), "true_peak": get("Peak:")}

