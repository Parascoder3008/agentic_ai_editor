"""Reel-03 hook: Flow shot A (Level 1, night) -> shot B (Level 4, morning smirk), 1080x1920 @25, under VO line 1.
Video and audio are rendered separately, then muxed (never one graph). Usage: python build_hook.py [src_suffix]
src_suffix: '' uses shotA_flow.mp4/shotB_flow.mp4 (720p); '_1080' uses the Flow 1080p upscales."""
import subprocess
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
SUF = sys.argv[1] if len(sys.argv) > 1 else ""
FONT = "C\\:/Users/PARAS ARORA/AI_Editor/fonts/Inter-Black.ttf"
# (source, in, out, speed, label, colour): B's mouth moves at 6.0-6.2 and 7.6-8.0 s, so only 8.2-10.0 is used
SEGS = [("A", 0.15, 1.55, 1.0, "LEVEL 1", "white", 250),
        ("A", 5.30, 7.02, 1.0, "LEVEL 1", "white", 250),
        ("B", 8.20, 9.89, 0.9, "LEVEL 4", "0x3AB0D8", 210)]       # B's face sits higher: keep text off the hair
LEN = sum((b - a) / s for _, a, b, s, *_ in SEGS)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        sys.exit(p.stderr[-2000:])


ins, fl, t = [], [], 0.0
for i, (src, a, b, sp, label, col, y) in enumerate(SEGS):
    ins += ["-i", str(H / f"shot{src}_flow{SUF}.mp4")]
    d = (b - a) / sp
    fl.append(f"[{i}:v]trim={a}:{b},setpts=(PTS-STARTPTS)/{sp},fps=25,scale=1080:1920:flags=lanczos,setsar=1,"
              f"drawtext=fontfile='{FONT}':text='{label}':fontsize=150:fontcolor={col}:x=(w-tw)/2:y={y}:"
              f"borderw=6:bordercolor=black@0.55:shadowx=0:shadowy=6:shadowcolor=black@0.5[v{i}]")
    t += d
fl.append("".join(f"[v{i}]" for i in range(len(SEGS))) + f"concat=n={len(SEGS)}:v=1:a=0,format=yuv420p[v]")
vid = H / f"hook_video{SUF}.mp4"
run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fl), "-map", "[v]", "-an",
     "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-r", "25", str(vid)])
# draft preview: VO line 1 only (final mix adds SFX + score in the reel compose)
out = H / f"hook_preview{SUF}.mp4"
run(["ffmpeg", "-y", "-v", "error", "-i", str(vid), "-i", str(H.parent / "pron" / "preview_v1.wav"),
     "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{LEN:.3f}", str(out)])
print(f"{out.name}: {LEN:.2f}s")
assert abs(LEN - 5.0) < 0.01, LEN   # cuts on spoken anchors: 1.40 "hain", 3.12 "owners", 5.00 just before "Aap" (5.16)
