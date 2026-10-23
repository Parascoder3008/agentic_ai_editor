"""Reel-03 final compose. Picture and sound are rendered SEPARATELY and only muxed at the end (mixing both in one
filter graph drifted the Equal ad by up to 0.77 s).
  master timeline 0-59.1 s:  0-4.9 Flow hook | 4.9-7.25 avatar full frame | 7.25-end presenter card (avatar at 82 %
  in a glass card, face clear of IG UI) + HyperFrames gfx (top half; full frame for the payoff) + ASS captions
  audio: avatar voice + sfx + score -> limiter -> two-pass loudnorm -14 LUFS / -1.5 dBTP
  variants: IG = 0-54.88 + 0.6 s freeze (comment LEVEL), YT = 0-50.42 + 54.98-59.1 (WhatsApp channel)
Usage: python compose.py"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ED = Path(__file__).resolve().parent
JOB = ED.parent
FONTS = r"C:\Users\PARAS ARORA\AI_Editor\fonts"
FPS, HOOK, SPLIT, END = 25, 5.0, 7.40, 59.1
CARD = (97, 975, 886, 924)                 # x, y, w, h: avatar scaled to 886 wide, hair ~y1015, chin ~y1549
CROP_Y = 214                               # rows skipped at the top of the scaled avatar
esc = lambda p: Path(p).resolve().as_posix().replace(":", r"\:")


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        sys.exit(" ".join(map(str, cmd))[:700] + "\n" + p.stderr[-2500:])
    return p


# ---- card mask + border (brand glass panel, 28 px radius)
x, y, w, h = CARD
m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], 28, fill=255); m.save(ED / "card_mask.png")
b = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
ImageDraw.Draw(b).rounded_rectangle([x - 1, y - 1, x + w, y + h], 29, outline=(58, 176, 216, 140), width=3)
b.save(ED / "card_border.png")

# ---- picture
base = ED / "base_video.mp4"
av = str(JOB / "avatar.mp4")
fc = (f"[0:v]fps={FPS},setpts=PTS-STARTPTS[hk];"
      f"[1:v]trim={HOOK}:{SPLIT},setpts=PTS-STARTPTS,fps={FPS}[face];"
      f"color=c=0x0C0E0F:s=1080x1920:r={FPS}:d={END - SPLIT:.3f}[bg];"
      f"[2:v]trim={SPLIT}:{END},setpts=PTS-STARTPTS,fps={FPS},scale={w}:-2:flags=lanczos,crop={w}:{h}:0:{CROP_Y}[a];"
      f"[3:v]format=gray[mk];[a][mk]alphamerge[ac];"
      f"[bg][ac]overlay={x}:{y}:shortest=1[c1];[c1][4:v]overlay=0:0[card];"
      f"[hk][face][card]concat=n=3:v=1:a=0,format=yuv420p[v]")
run(["ffmpeg", "-y", "-v", "error", "-i", str(JOB / "hook" / "hook_video_1080.mp4"), "-i", av, "-i", av,
     "-loop", "1", "-i", str(ED / "card_mask.png"), "-loop", "1", "-i", str(ED / "card_border.png"),
     "-filter_complex", fc, "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-t", f"{END:.3f}", str(base)])
vid = ED / "video_master.mp4"
run(["ffmpeg", "-y", "-v", "error", "-i", str(base), "-c:v", "libvpx-vp9", "-i", str(JOB / "gfx" / "render.webm"),
     "-filter_complex", f"[1:v]fps={FPS},format=yuva420p[g];[0:v][g]overlay=0:0:format=auto,"
                        f"subtitles='{esc(ED / 'captions.ass')}':fontsdir='{esc(FONTS)}',format=yuv420p[v]",
     "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-r", str(FPS), "-t", f"{END:.3f}", str(vid)])

# ---- sound
pre = ED / "mix_pre.wav"
run(["ffmpeg", "-y", "-v", "error", "-i", str(ED / "voice.wav"), "-i", str(ED / "sfx.wav"), "-i", str(ED / "music_score.wav"),
     "-filter_complex", f"[0:a][1:a][2:a]amix=inputs=3:normalize=0:duration=longest,atrim=0:{END + 0.6:.3f},"
                        "volume=12dB,alimiter=limit=0.72:attack=4:release=60:level=disabled",
     "-ar", "48000", "-c:a", "pcm_s24le", str(pre)])


def loudnorm(src, dst):
    o = run(["ffmpeg", "-v", "info", "-i", str(src), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    j = json.loads(o[o.rfind("{"): o.rfind("}") + 1])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af",
         f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
         f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true", "-ar", "48000", "-c:a", "pcm_s24le", str(dst)])


# ---- variants (cut picture and sound with the same ranges, then normalise each, then mux)
VARIANTS = {"instagram": {"ranges": [(0.0, 54.88)], "freeze": 0.6},
            "youtube": {"ranges": [(0.0, 50.42), (54.98, END)], "freeze": 0.4}}
for name, vcfg in VARIANTS.items():
    rs, fz = vcfg["ranges"], vcfg["freeze"]
    vparts = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];" for i, (a, b) in enumerate(rs))
    vcat = "".join(f"[v{i}]" for i in range(len(rs))) + f"concat=n={len(rs)}:v=1:a=0,tpad=stop_mode=clone:stop_duration={fz}[v]"
    vout = ED / f"v_{name}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(vid), "-filter_complex", vparts + vcat, "-map", "[v]",
         "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-r", str(FPS), str(vout)])
    total = sum(b - a for a, b in rs) + fz
    aparts = "".join(f"[0:a]atrim={a}:{b + (fz if i == len(rs) - 1 else 0)},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:st=0:d=0.03,afade=t=out:st={b - a + (fz if i == len(rs) - 1 else 0) - 0.03:.3f}:d=0.03[a{i}];"
                     for i, (a, b) in enumerate(rs))
    acat = "".join(f"[a{i}]" for i in range(len(rs))) + f"concat=n={len(rs)}:v=0:a=1,afade=t=out:st={total - 0.5:.3f}:d=0.5[a]"
    araw = ED / f"a_{name}_pre.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(pre), "-filter_complex", aparts + acat, "-map", "[a]",
         "-ar", "48000", "-c:a", "pcm_s24le", str(araw)])
    aout = ED / f"a_{name}.wav"
    loudnorm(araw, aout)
    out = JOB / f"REEL03_{name}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(vout), "-i", str(aout), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "256k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)])
    chk = run(["ffmpeg", "-v", "info", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    print(f"-> {out.name} {total:.2f}s |", " ".join(l.strip() for l in chk.splitlines()[-14:] if any(k in l for k in ("I:", "Peak:"))))
