"""Skit-hook version: Seedance skit (full-screen 9:16, its own dialogue + captions) -> hard cut -> the
composed reel from avatar t=BODY_IN ("Plugin ka naam hai Claude Ads"). One whoosh+impact on the cut,
then a two-pass -14 LUFS / -1.5 dBTP pass over the whole thing.

Usage: python skit_join.py   (expects ../skit/skit.mp4 and ../REEL_pilot01.mp4)
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ED = Path(__file__).resolve().parent
JOB = ED.parent
TOOLS = Path(r"C:\Users\PARAS ARORA\AI_Editor\tools")
sys.path.insert(0, str(TOOLS))
import score_music as sm  # noqa: E402

SKIT, REEL, OUT = JOB / "skit" / "skit.mp4", JOB / "REEL_pilot01.mp4", JOB / "REEL_pilot01_skit.mp4"
BODY_IN = 8.85
LINES = "Yaar, agency ne phir report bheji... ads phir flop. Agency ki chhutti kar do. Huh? Toh ads kaun dekhega? Claude. Dikhata hoon kaise."
FONTS = r"C:\Users\PARAS ARORA\AI_Editor\fonts"


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        sys.exit(" ".join(map(str, cmd))[:400] + "\n" + p.stderr[-2000:])
    return p


def dur(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout)


def esc(p):
    return Path(p).resolve().as_posix().replace(":", r"\:")


# 1. word times for the skit captions (known text, force-aligned over the whole clip)
sk = dur(SKIT)
(ED / "skit_lines.json").write_text(json.dumps([{"id": "S", "win": [0.0, round(sk, 3)], "text": LINES}]), encoding="utf-8")
run([sys.executable, str(TOOLS / "force_align.py"), str(SKIT), str(ED / "skit_lines.json"), str(ED / "skit_fa.json")])
words = json.loads((ED / "skit_fa.json").read_text(encoding="utf-8"))["S"]
end = min(sk, words[-1]["end"] + 0.35)                         # trim dead air after "kaise"
(ED / "skit_words.json").write_text(json.dumps({"words": words}, ensure_ascii=False), encoding="utf-8")
run([sys.executable, str(TOOLS / "captions_ass.py"), str(ED / "skit_words.json"), str(ED / "skit_captions.ass"), "--y", "1430"])

# 2. both parts to identical streams (1080x1920 25 fps, 48 kHz stereo)
A = ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]
run(["ffmpeg", "-y", "-v", "error", "-i", str(SKIT), "-t", f"{end:.3f}", "-vf",
     f"fps=25,scale=1080:1920:flags=lanczos,subtitles='{esc(ED / 'skit_captions.ass')}':fontsdir='{esc(FONTS)}'",
     "-af", "loudnorm=I=-15:TP=-2:LRA=11", *A, str(ED / "part_skit.mkv")])
run(["ffmpeg", "-y", "-v", "error", "-i", str(REEL), "-ss", f"{BODY_IN:.3f}", *A, str(ED / "part_body.mkv")])

# 3. cut SFX stem (whoosh into the cut, impact on it)
n = int((end + dur(ED / "part_body.mkv") + 1) * sm.SR)
buf = np.zeros((n, 2), np.float32)
w = sm.riser(0.45)
w[int(0.33 * sm.SR):] *= np.exp(-np.arange(len(w) - int(0.33 * sm.SR)) / (0.04 * sm.SR))[:, None]
sm.place(buf, w, end - 0.33, 10 ** (-17 / 20))
sm.place(buf, sm.impact(), end, 10 ** (-26 / 20))
sf.write(ED / "cut_sfx.wav", buf, sm.SR, subtype="PCM_24")

# 4. join + mix the cut SFX, then two-pass loudness
lst = ED / "join.txt"
lst.write_text(f"file '{(ED / 'part_skit.mkv').as_posix()}'\nfile '{(ED / 'part_body.mkv').as_posix()}'\n", encoding="utf-8")
run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(ED / "cut_sfx.wav"),
     "-filter_complex", "[0:a][1:a]amix=inputs=2:normalize=0:duration=first[a]", "-map", "0:v", "-map", "[a]",
     "-c:v", "copy", "-c:a", "pcm_s16le", str(ED / "skit_prenorm.mkv")])
meas = run(["ffmpeg", "-v", "info", "-i", str(ED / "skit_prenorm.mkv"), "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
j = json.loads(meas[meas.rfind("{"): meas.rfind("}") + 1])
ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
      f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
run(["ffmpeg", "-y", "-v", "error", "-i", str(ED / "skit_prenorm.mkv"), "-c:v", "copy", "-af", ln, "-ar", "48000",
     "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(OUT)])
print(f"skit {end:.2f}s + body {dur(ED / 'part_body.mkv'):.2f}s -> {OUT}  ({dur(OUT):.2f}s)")
print("skit words:", " ".join(f"{w['text']}@{w['start']:.2f}" for w in words))
