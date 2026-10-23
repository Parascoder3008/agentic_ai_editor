"""Reel-05 final compose. Picture and sound are rendered SEPARATELY and only muxed at the end (mixing both in one
filter graph drifted the Equal ad by up to 0.77 s).
  picture: plan.SEGMENTS -> base_video.mp4 (Flow hook + Flow B-roll full frame | avatar face beat | presenter card under the
           HyperFrames stage), then gfx/render.webm + ASS captions -> video_master.mp4
  sound:   avatar voice + sfx + score -> limiter -> per-variant two-pass loudnorm -14 LUFS / -1.5 dBTP
  variants: plan.VARIANTS (IG ends on comment AGENT + freeze, YT on the WhatsApp channel line)
Usage: python compose.py [--sound-only]"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from plan import END, FPS, OFF, SEGMENTS, VARIANTS

ED = Path(__file__).resolve().parent
JOB = ED.parent
FONTS = r"C:\Users\PARAS ARORA\AI_Editor\fonts"
CARD = (97, 975, 886, 924)                 # x, y, w, h of the presenter card (glass panel, 28 px radius)
CARD_CROP = (840, 876, 540, 50)            # w, h, x, y in the 1920x1080 avatar: head ~y1123, chin ~y1492 on the reel
FACE_CROP = (608, 1080, 656, 0)            # 9:16 window centred on his face for the full-frame beat
esc = lambda p: Path(p).resolve().as_posix().replace(":", r"\:")


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        sys.exit(" ".join(map(str, cmd))[:700] + "\n" + p.stderr[-2500:])
    return p


x, y, w, h = CARD
m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], 28, fill=255); m.save(ED / "card_mask.png")
b = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
ImageDraw.Draw(b).rounded_rectangle([x - 1, y - 1, x + w, y + h], 29, outline=(58, 176, 216, 140), width=3)
b.save(ED / "card_border.png")

vid = ED / "video_master.mp4"
if "--sound-only" not in sys.argv:
    ins, fl = [], []
    n = len(SEGMENTS)
    for i, (t0, t1, lay, src, s_in, sp) in enumerate(SEGMENTS):
        d = t1 - t0
        ins += ["-i", str(JOB / src)]
        trim = f"[{i}:v]trim={s_in}:{s_in + d * sp},setpts=(PTS-STARTPTS)/{sp},fps={FPS},"
        if lay in ("hook", "broll"):
            fl.append(trim + f"scale=1080:1920:flags=lanczos,setsar=1,format=yuv420p[s{i}]")
        elif lay == "face":
            cw, ch, cx, cy = FACE_CROP
            fl.append(trim + f"crop={cw}:{ch}:{cx}:{cy},scale=1080:1920:flags=lanczos,unsharp=5:5:0.5,setsar=1,format=yuv420p[s{i}]")
        else:
            cw, ch, cx, cy = CARD_CROP
            fl.append(trim + f"crop={cw}:{ch}:{cx}:{cy},scale={w}:{h}:flags=lanczos,format=yuva420p[a{i}];"
                      f"[{n}:v]format=gray,trim=0:{d:.3f}[mk{i}];[a{i}][mk{i}]alphamerge[ac{i}];"
                      f"color=c=0x0C0E0F:s=1080x1920:r={FPS}:d={d:.3f}[bg{i}];[bg{i}][ac{i}]overlay={x}:{y}:shortest=1[c{i}];"
                      f"[c{i}][{n + 1}:v]overlay=0:0:shortest=1,setsar=1,format=yuv420p[s{i}]")
    # the masks are looped stills: split them so every split beat gets its own copy
    splits = [i for i, s in enumerate(SEGMENTS) if s[2] == "split"]
    k = len(splits)
    pre = (f"[{n}:v]split={k}" + "".join(f"[m{j}]" for j in range(k)) + ";" +
           f"[{n + 1}:v]split={k}" + "".join(f"[b{j}]" for j in range(k)) + ";")
    for j, i in enumerate(splits):
        fl[i] = fl[i].replace(f"[{n}:v]format=gray", f"[m{j}]format=gray").replace(f"[{n + 1}:v]overlay", f"[b{j}]overlay")
    fc = pre + ";".join(fl) + ";" + "".join(f"[s{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    base = ED / "base_video.mp4"
    run(["ffmpeg", "-y", "-v", "error", *ins, "-loop", "1", "-i", str(ED / "card_mask.png"), "-loop", "1", "-i", str(ED / "card_border.png"),
         "-filter_complex", fc, "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-t", f"{END:.3f}", str(base)])
    if "--base-only" in sys.argv:
        sys.exit("base_video.mp4 done")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(base), "-c:v", "libvpx-vp9", "-i", str(JOB / "gfx" / "render.webm"),
         "-filter_complex", f"[1:v]trim=start={OFF},setpts=PTS-STARTPTS,fps={FPS},tpad=stop_mode=clone:stop_duration=0.5,format=yuva420p[g];[0:v][g]overlay=0:0:format=auto,"
                            f"subtitles='{esc(ED / 'captions.ass')}':fontsdir='{esc(FONTS)}',format=yuv420p[v]",
         "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-r", str(FPS), "-t", f"{END:.3f}", str(vid)])
    print("video_master.mp4 done")

# ---- sound
def premix(dst, mute_after=None):
    """voice + sfx + score; mute_after silences the voice from that time on (an IG freeze must not leak the next line)"""
    vf = f"[0:a]volume=0:enable='gte(t,{mute_after})'[vo];" if mute_after else "[0:a]anull[vo];"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(ED / "voice.wav"), "-i", str(ED / "sfx.wav"), "-i", str(ED / "music_score.wav"),
         "-filter_complex", vf + f"[vo][1:a][2:a]amix=inputs=3:normalize=0:duration=longest,atrim=0:{END + 0.6:.3f},"
                            "volume=12dB,alimiter=limit=0.72:attack=4:release=60:level=disabled",
         "-ar", "48000", "-c:a", "pcm_s24le", str(dst)])


premix(ED / "mix_pre.wav")


def loudnorm(src, dst):
    o = run(["ffmpeg", "-v", "info", "-i", str(src), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    j = json.loads(o[o.rfind("{"): o.rfind("}") + 1])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af",
         f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
         f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true", "-ar", "48000", "-c:a", "pcm_s24le", str(dst)])


# ---- variants (cut picture and sound with the same ranges, then normalise each, then mux)
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
    pre = ED / "mix_pre.wav"
    if vcfg.get("mute_voice_after"):
        pre = ED / f"mix_pre_{name}.wav"; premix(pre, vcfg["mute_voice_after"])
    araw = ED / f"a_{name}_pre.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(pre), "-filter_complex", aparts + acat, "-map", "[a]",
         "-ar", "48000", "-c:a", "pcm_s24le", str(araw)])
    aout = ED / f"a_{name}.wav"
    loudnorm(araw, aout)
    out = JOB / f"REEL05_{name}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(vout), "-i", str(aout), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "256k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)])
    chk = run(["ffmpeg", "-v", "info", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    print(f"-> {out.name} {total:.2f}s |", " ".join(l.strip() for l in chk.splitlines()[-14:] if any(k in l for k in ("I:", "Peak:"))))
