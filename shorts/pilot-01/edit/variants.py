"""Instagram + YouTube Shorts exports from one composed reel (REEL_v2_full.mp4) and the skit hook.

IG = skit + body[line 4 -> end of line 14]          ("follow + comment META, link in DM")
YT = skit + body[line 4 -> end of line 12] + body[line 15 -> end]   ("channel description -> WhatsApp channel")
Cuts sit in the pause between lines (line_times.json, force-aligned). Every joint gets a 30 ms audio
crossfade plus a whoosh; each export gets its own two-pass -14 LUFS / -1.5 dBTP.

Usage: python variants.py <skit.mp4>
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

SKIT, FULL = Path(sys.argv[1]), JOB / "REEL_v2_full.mp4"
FONTS = r"C:\Users\PARAS ARORA\AI_Editor\fonts"
LINES = json.loads((ED / "line_times.json").read_text())
gap = lambda a, b: round((LINES[str(a)][1] + LINES[str(b)][0]) / 2, 3)     # middle of the pause a|b
BODY_IN = max(gap(3, 4), 7.68)          # S3 (GitHub) starts at 7.678: no flash of the previous scene
SKIT_TEXT = [("Yaar,", "yaar"), ("agency", "agency"), ("ne", "ne"), ("phir", "phir"), ("report", "report"),
             ("bheji...", "bheji"), ("ads", "ads"), ("phir", "phir"), ("flop.", "flop"), ("Agency", "agency"),
             ("ki", "ki"), ("chhutti", "chhutti"), ("kar", "kar"), ("do.", "do"), ("Huh?", "hain"), ("Toh", "toh"),
             ("ads", "ads"), ("kaun", "kaun"), ("dekhega?", "dekhega"), ("Claude.", "klod"), ("Dikhata", "dikhata"),
             ("hoon", "hoon"), ("kaise.", "kaise")]
A = ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "25",
     "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        sys.exit(" ".join(map(str, cmd))[:400] + "\n" + p.stderr[-2000:])
    return p


def dur(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout)


esc = lambda p: Path(p).resolve().as_posix().replace(":", r"\:")

# 1. skit part: captions from force-aligned known dialogue, trimmed after the last word
sk = dur(SKIT)
(ED / "skit_lines.json").write_text(json.dumps([{"id": "S", "win": [0.0, round(sk, 3)],
                                                  "text": " ".join(s for _, s in SKIT_TEXT)}]), encoding="utf-8")
run([sys.executable, str(TOOLS / "force_align.py"), str(SKIT), str(ED / "skit_lines.json"), str(ED / "skit_fa.json")])
fa = json.loads((ED / "skit_fa.json").read_text(encoding="utf-8"))["S"]
words = [{"text": shown, "start": w["start"], "end": w["end"]} for (shown, _), w in zip(SKIT_TEXT, fa)]
end = min(sk, words[-1]["end"] + 0.3)
(ED / "skit_words.json").write_text(json.dumps({"words": words}, ensure_ascii=False), encoding="utf-8")
run([sys.executable, str(TOOLS / "captions_ass.py"), str(ED / "skit_words.json"), str(ED / "skit_captions.ass"), "--y", "1430"])
run(["ffmpeg", "-y", "-v", "error", "-i", str(SKIT), "-t", f"{end:.3f}", "-vf",
     "delogo=x=334:y=830:w=66:h=24:enable='lt(t,3.0)',"           # faint laptop brand mark the model drew in shot 1
     f"fps=25,scale=1080:1920:flags=lanczos,subtitles='{esc(ED / 'skit_captions.ass')}':fontsdir='{esc(FONTS)}'",
     "-af", "loudnorm=I=-15:TP=-2:LRA=11", *A, str(ED / "v_skit.mkv")])


def seg(name, a, b, hold_from=None):
    """FULL[a:b]; hold_from: freeze the picture from this (absolute) time on, audio keeps running to b."""
    out = ED / f"v_{name}.mkv"
    vf = (f"trim=end={hold_from - a:.3f},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={b - hold_from:.3f}"
          if hold_from else "null")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-i", str(FULL), "-t", f"{b - a:.3f}", "-vf", vf,
         "-af", f"afade=t=in:d=0.03,afade=t=out:st={b - a - 0.03:.3f}:d=0.03", *A, str(out)])
    return out


def export(name, parts, tail=0.0, first_word=()):
    """first_word[i] = seconds from joint i to the first word after it (whoosh must peak >= 0.15 s before)."""
    lst = ED / f"join_{name}.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    joints, t = [], 0.0
    for p in parts[:-1]:
        t += dur(p); joints.append(t)
    total = t + dur(parts[-1])
    buf = np.zeros((int((total + tail + 2) * sm.SR), 2), np.float32)
    w = sm.riser(0.45)
    w[int(0.33 * sm.SR):] *= np.exp(-np.arange(len(w) - int(0.33 * sm.SR)) / (0.04 * sm.SR))[:, None]
    for i, j in enumerate(joints):
        peak = min(j, j + first_word[i] - 0.15) if i < len(first_word) else j
        sm.place(buf, w, peak - 0.33, 10 ** (-17 / 20))
        if i == 0:                                                   # skit -> body: the music drops in
            sm.place(buf, sm.impact(), peak, 10 ** (-30 / 20))
    sf.write(ED / f"sfx_{name}.wav", buf, sm.SR, subtype="PCM_24")
    pre = ED / f"pre_{name}.mkv"
    vf = f"tpad=stop_mode=clone:stop_duration={tail}" if tail else "null"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(ED / f"sfx_{name}.wav"),
         "-filter_complex", f"[0:v]{vf}[v];[0:a]apad=pad_dur={tail}[va];[va][1:a]amix=inputs=2:normalize=0:duration=first[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
         "-c:a", "pcm_s16le", str(pre)])
    meas = run(["ffmpeg", "-v", "info", "-i", str(pre), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                "-f", "null", "-"]).stderr
    j = json.loads(meas[meas.rfind("{"): meas.rfind("}") + 1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
          f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    out = JOB / f"REEL_pilot01_{name}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(pre), "-c:v", "copy", "-af", ln, "-ar", "48000", "-c:a", "aac",
         "-b:a", "256k", "-movflags", "+faststart", str(out)])
    print(f"{name}: {dur(out):.2f}s  joints at {[round(x, 2) for x in joints]}  -> {out.name}")
    return joints


skit = ED / "v_skit.mkv"
fw = lambda line, cut: LINES[str(line)][0] - cut                     # joint -> first word of the next part
S11_LEAVE = 43.637                       # DM card starts fading out here (gfx/top leave("#s11")): Instagram's end
ig = export("instagram", [skit, seg("ig_body", BODY_IN, gap(14, 15), hold_from=S11_LEAVE - 0.04)], tail=0.4,
            first_word=[fw(4, BODY_IN)])
yt = export("youtube", [skit, seg("yt_a", BODY_IN, gap(12, 13)), seg("yt_b", gap(14, 15), dur(FULL))],
            first_word=[fw(4, BODY_IN), fw(15, gap(14, 15))])
json.dump({"skit_end": end, "body_in": BODY_IN, "ig_joints": ig, "yt_joints": yt,
           "cuts": {"12|13": gap(12, 13), "14|15": gap(14, 15)}}, open(ED / "variants.json", "w"), indent=1)
print("skit words:", " ".join(f"{w['text']}@{w['start']:.2f}" for w in words))
