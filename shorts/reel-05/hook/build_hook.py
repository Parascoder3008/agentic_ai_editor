"""Reel-05 hook: one Flow shot of Paras ("Me" avatar, black tee, night) cut into three moments under VO line 1,
1080x1920 @25, video only (labels come from gfx/index.html; audio is mixed in compose.py).
Usage: python build_hook.py"""
import subprocess
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
SRC = H / "hook_flow_1080.mp4"
# (in, out) in the Flow clip: phone lights up on the desk | picks it up, surprised | turns it to camera, smiling
SEGS = [(1.75, 3.15), (4.40, 6.20), (6.90, 9.10)]
LEN = sum(b - a for a, b in SEGS)

fl = [f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,fps=25,scale=1080:1920:flags=lanczos,setsar=1[v{i}]" for i, (a, b) in enumerate(SEGS)]
fl.append("".join(f"[v{i}]" for i in range(len(SEGS))) + f"concat=n={len(SEGS)}:v=1:a=0,format=yuv420p[v]")
p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(SRC), "-filter_complex", ";".join(fl), "-map", "[v]", "-an",
                    "-c:v", "libx264", "-crf", "15", "-preset", "slow", "-r", "25", str(H / "hook_video.mp4")],
                   capture_output=True, text=True)
if p.returncode:
    sys.exit(p.stderr[-2000:])
assert abs(LEN - 5.40) < 0.01, LEN      # cuts: 1.40 (between "khud" and "ka"), 3.20 (before "Aur" 3.34), 5.40 (before "Socho" 5.68)
print(f"hook_video.mp4 {LEN:.2f}s")
