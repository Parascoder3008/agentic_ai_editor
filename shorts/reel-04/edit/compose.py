"""Final reel-04 compose. Picture and sound rendered SEPARATELY, muxed at the end.
  picture: base_video.mp4 (compose_base.py) + gfx/render.webm (alpha, incl. kinetic captions) -> video_master.mp4
  sound:   voice + sfx + score, mixed per variant with the voice muted after the variant's last word (the freeze can't
           leak the next section), gain set from a measurement, limiter, then two-pass loudnorm -14 LUFS / -1.5 dBTP
  variants: IG = shared + IG tail + 0.6 s freeze; YT = shared + YT tail + 0.4 s freeze
Usage: python compose.py"""
import json
import subprocess
import sys
from pathlib import Path

ED = Path(__file__).resolve().parent
JOB = ED.parent
TL = json.loads((ED / "timeline.json").read_text())
FONTS = r"C:\Users\PARAS ARORA\AI_Editor\fonts"
FPS, END = 30, TL["length"]
esc = lambda p: Path(p).resolve().as_posix().replace(":", r"\:")


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        sys.exit(" ".join(map(str, cmd))[:800] + "\n" + p.stderr[-2500:])
    return p


vid = ED / "video_master.mp4"
if not vid.exists() or vid.stat().st_mtime < max((ED / f).stat().st_mtime for f in ("base_video.mp4", "captions.ass")) \
        or vid.stat().st_mtime < (JOB / "gfx" / "render.webm").stat().st_mtime:
    run(["ffmpeg", "-y", "-v", "error", "-i", str(ED / "base_video.mp4"), "-c:v", "libvpx-vp9", "-i", str(JOB / "gfx" / "render.webm"),
         "-filter_complex", f"[1:v]fps={FPS},format=yuva420p[g];[0:v][g]overlay=0:0:format=auto,format=yuv420p[v]",   # captions live in the gfx
         "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-r", str(FPS), "-t", f"{END:.3f}", str(vid)])
    print("video_master.mp4 done")


def lufs(path):
    o = run(["ffmpeg", "-v", "info", "-i", str(path), "-af", "ebur128", "-f", "null", "-"]).stderr
    return float([l for l in o.splitlines() if l.strip().startswith("I:")][-1].split()[1])


def mix(dst, voice_end, gain_db):
    run(["ffmpeg", "-y", "-v", "error", "-i", str(ED / "voice.wav"), "-i", str(ED / "sfx.wav"), "-i", str(ED / "music_score.wav"),
         "-filter_complex", f"[0:a]volume=0:enable='gte(t,{voice_end:.3f})'[vo];[vo][1:a][2:a]amix=inputs=3:normalize=0:duration=longest,"
                            f"atrim=0:{END + 0.8:.3f},volume={gain_db:.2f}dB,alimiter=limit=0.72:attack=4:release=60:level=disabled",
         "-ar", "48000", "-c:a", "pcm_s24le", str(dst)])


def loudnorm(src, dst):
    o = run(["ffmpeg", "-v", "info", "-i", str(src), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    j = json.loads(o[o.rfind("{"): o.rfind("}") + 1])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af",
         f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
         f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true", "-ar", "48000", "-c:a", "pcm_s24le", str(dst)])


# the voice alone sets the gain: ~-17 LUFS into the limiter, so loudnorm only trims (stays linear, no pumping)
GAIN = -17 - lufs(ED / "voice.wav")
VARIANTS = {"instagram": (TL["ig"]["ranges"], 0.6), "youtube": (TL["yt"]["ranges"], 0.4)}
for name, (rs, fz) in VARIANTS.items():
    vparts = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];" for i, (a, b) in enumerate(rs))
    vcat = "".join(f"[v{i}]" for i in range(len(rs))) + f"concat=n={len(rs)}:v=1:a=0,tpad=stop_mode=clone:stop_duration={fz}[v]"
    vout = ED / f"v_{name}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(vid), "-filter_complex", vparts + vcat, "-map", "[v]",
         "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-r", str(FPS), str(vout)])
    total = sum(b - a for a, b in rs) + fz
    pre = ED / f"mix_{name}.wav"; mix(pre, rs[-1][1], GAIN)
    aparts = "".join(f"[0:a]atrim={a}:{b + (fz if i == len(rs) - 1 else 0)},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.02,"
                     f"afade=t=out:st={b - a + (fz if i == len(rs) - 1 else 0) - 0.02:.3f}:d=0.02[a{i}];" for i, (a, b) in enumerate(rs))
    acat = "".join(f"[a{i}]" for i in range(len(rs))) + f"concat=n={len(rs)}:v=0:a=1,afade=t=out:st={total - 0.5:.3f}:d=0.5[a]"
    araw = ED / f"a_{name}_pre.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(pre), "-filter_complex", aparts + acat, "-map", "[a]", "-ar", "48000", "-c:a", "pcm_s24le", str(araw)])
    aout = ED / f"a_{name}.wav"
    loudnorm(araw, aout)
    out = JOB / f"REEL04_{name}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(vout), "-i", str(aout), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "256k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)])
    chk = run(["ffmpeg", "-v", "info", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    print(f"-> {out.name} {total:.2f}s |", " ".join(l.strip() for l in chk.splitlines()[-14:] if any(k in l for k in ("I:", "Peak:"))))
