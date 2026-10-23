"""Face proxy on the master timeline: every piece decoded from the 4K camera file, zoomed about the head
(so a punch-in never moves the face off its mark), 1080x1920 @30, concatenated -> base_face.mp4 (video only).
Usage: python prep.py"""
import json
import subprocess
import sys
from pathlib import Path

ED = Path(__file__).resolve().parent
TL = json.loads((ED / "timeline.json").read_text())
HX, HY = 440, 760                       # head centre in 1080x1920 (measured on the frames)
SEG = ED / "segs"; SEG.mkdir(exist_ok=True)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        sys.exit(p.stderr[-2000:])


lst = []
for i, p in enumerate(TL["pieces"]):
    s, e = p["src"]; z = p["zoom"]
    W, H = int(1080 * z) // 2 * 2, int(1920 * z) // 2 * 2
    x0, y0 = int(HX * z - HX), int(HY * z - HY)
    out = SEG / f"f{i:02d}_{p['file']}_{s:.3f}_{z}.mkv"
    lst.append(out)
    if not out.exists():
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.4f}", "-i", TL["files"][p["file"]], "-t", f"{e - s:.4f}",
             "-vf", f"fps=30,scale={W}:{H}:flags=lanczos,crop=1080:1920:{x0}:{y0},setsar=1,format=yuv420p",
             "-an", "-c:v", "libx264", "-crf", "12", "-preset", "medium", str(out)])
    print("seg", out.name)
(ED / "face_concat.txt").write_text("".join(f"file '{p.as_posix()}'\n" for p in lst))
run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(ED / "face_concat.txt"), "-c", "copy", str(ED / "base_face.mp4")])
d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ED / "base_face.mp4")],
                   capture_output=True, text=True).stdout.strip()
print("base_face.mp4", d, "s vs timeline", TL["length"])
