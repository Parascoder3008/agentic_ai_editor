"""Final Equal ad. Audio and picture are rendered SEPARATELY and only muxed at the end: mixing both in one
filter graph left 0.26 s pts gaps at the AI-shot cuts (voice drifted up to -0.77 s by the end).
  audio: voice + sfx + music -> +17 dB -> limiter -> two-pass loudnorm -14 LUFS / -1.5 dBTP   (wav)
  video: base picture + gfx (alpha webm) + captions                                             (h264)
Usage: python compose.py [out.mp4]"""
import json
import subprocess
import sys
from pathlib import Path

ED = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ED.parent / "EQUAL_AI_Paras.mp4"
FONTS = r"C:\Users\PARAS ARORA\AI_Editor\fonts"
L = json.loads((ED / "edl.json").read_text(encoding="utf-8"))["length"]
esc = lambda p: Path(p).resolve().as_posix().replace(":", r"\:")


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        sys.exit(" ".join(map(str, cmd))[:600] + "\n" + p.stderr[-2500:])
    return p


# ---- audio
mix = ED / "mix_pre.wav"
run(["ffmpeg", "-y", "-v", "error", "-i", str(ED / "voice.wav"), "-i", str(ED / "sfx.wav"), "-i", str(ED / "music.wav"),
     "-filter_complex", f"[0:a][1:a][2:a]amix=inputs=3:normalize=0:duration=longest,atrim=0:{L:.3f},"
                        "volume=17dB,alimiter=limit=0.72:attack=4:release=60:level=disabled",
     "-ar", "48000", "-c:a", "pcm_s24le", str(mix)])
m = run(["ffmpeg", "-v", "info", "-i", str(mix), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
j = json.loads(m[m.rfind("{"): m.rfind("}") + 1])
ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
      f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
aud = ED / "mix_final.wav"
run(["ffmpeg", "-y", "-v", "error", "-i", str(mix), "-af", ln, "-ar", "48000", "-c:a", "pcm_s24le", str(aud)])

# ---- picture
vid = ED / "video_final.mp4"
run(["ffmpeg", "-y", "-v", "error", "-i", str(ED / "base_video.mkv"), "-c:v", "libvpx-vp9", "-i", str(ED / "gfx" / "gfx.webm"),
     "-filter_complex", f"[1:v]fps=25,format=yuva420p[g];[0:v][g]overlay=0:0:format=auto,"
                        f"subtitles='{esc(ED / 'captions.ass')}':fontsdir='{esc(FONTS)}',format=yuv420p[v]",
     "-map", "[v]", "-t", f"{L:.3f}", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
     "-r", "25", str(vid)])

# ---- mux
run(["ffmpeg", "-y", "-v", "error", "-i", str(vid), "-i", str(aud), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
     "-c:a", "aac", "-b:a", "256k", "-t", f"{L:.3f}", "-movflags", "+faststart", str(OUT)])
chk = run(["ffmpeg", "-v", "info", "-i", str(OUT), "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
print("->", OUT)
print("\n".join(l for l in chk.splitlines()[-14:] if any(k in l for k in ("I:", "LRA:", "Peak:"))))
