"""Final compose. Picture and sound rendered SEPARATELY, muxed at the end (one A/V graph drifted before).
  base: split 0-15.36 (AI top 1080x606 @y330, original inset 840x472 @(120,1040), rounded) | how-to pieces: presenter in a
        rounded card (882x940 @(99,960), punch-in alternates 1.00/1.08 to hide jump cuts) or full frame on the FF beats
  then: HyperFrames gfx (alpha webm) + ASS captions | audio: voice + sfx + score -> limiter -> loudnorm -14 LUFS / -1.5 dBTP
  variants: IG = shared + IG tail + 0.6 s freeze (comment FLEX), YT = shared + YT tail + 0.4 s (WhatsApp + subscribe)
Usage: python compose.py"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ED = Path(__file__).resolve().parent
JOB = ED.parent
TL = json.loads((ED / "timeline.json").read_text())
FONTS = r"C:\Users\PARAS ARORA\AI_Editor\fonts"
GEN = r"C:\Users\PARAS ARORA\Documents\ChatGPT\Higgsfield API\.local-data\genjutsu-plan\output\genjutsu-white-cullinan-mansion-original.mp4"
RAW = r"C:\Users\PARAS ARORA\Downloads\New Reel Raw Footage .mp4"
DJI = r"C:\Users\PARAS ARORA\Downloads\DJI_20261019154130_0355_D.MP4"
FPS, END = 25, TL["length"]
FF = [tuple(x) for x in TL["ff"]]                           # full-frame presenter beats (written by retime.py)
CARD = (99, 960, 882, 940)
HEAD_TOP = 533 / 1920                       # head top as a fraction of DJI frame height (measured)
esc = lambda p: Path(p).resolve().as_posix().replace(":", r"\:")
SEG = ED / "segs"; SEG.mkdir(exist_ok=True)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        sys.exit(" ".join(map(str, cmd))[:800] + "\n" + p.stderr[-2500:])
    return p


def mask(w, h, r, path):
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=255); m.save(path)


mask(840, 472, 24, ED / "mask_inset.png"); mask(CARD[2], CARD[3], 28, ED / "mask_card.png")
ENC = ["-an", "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS)]

# ---- split
split = SEG / "s00_split.mkv"
if not split.exists():
    run(["ffmpeg", "-y", "-v", "error", "-i", GEN, "-i", RAW, "-loop", "1", "-i", str(ED / "mask_inset.png"),
         "-filter_complex",
         f"color=c=black:s=1080x1920:r={FPS}:d={TL['split']}[bg];"
         f"[0:v]fps={FPS},scale=1080:606:flags=lanczos,setsar=1[top];"
         f"[1:v]fps={FPS},scale=840:472:flags=lanczos,setsar=1,format=yuva420p[ins];[2:v]format=gray[mk];[ins][mk]alphamerge[insr];"
         f"[bg][top]overlay=0:330:shortest=1[b1];[b1][insr]overlay=120:1040,format=yuv420p[v]",
         "-map", "[v]", "-t", f"{TL['split']:.3f}", *ENC, str(split)])

# ---- how-to pieces
segs = [split]
for i, p in enumerate(TL["pieces"]):
    s, e = p["src"]; d = e - s
    full = any(a - 0.02 <= p["out"][0] < b - 0.02 for a, b in FF)       # every piece inside a full-frame beat
    out = SEG / f"s{i + 1:02d}_{'full' if full else 'card'}_{s:.2f}.mkv"
    segs.append(out)
    if out.exists():
        continue
    if full:
        z = 1.14 if i % 2 else 1.04                 # alternate punch-in here too (CTA has two takes back to back)
        W, H = int(1080 * z) // 2 * 2, int(1920 * z) // 2 * 2
        vf = f"[0:v]fps={FPS},scale={W}:{H}:flags=lanczos,crop=1080:1920:{(W - 1080) // 2}:{int(H * HEAD_TOP - 1920 * HEAD_TOP)},setsar=1,format=yuv420p[v]"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.3f}", "-i", DJI, "-filter_complex", vf, "-map", "[v]", "-t", f"{d:.3f}", *ENC, str(out)])
    else:
        z = 1.08 if i % 2 else 1.0                  # alternate punch-in hides the jump cut between takes
        x, y, w, h = CARD
        W = int(w * z) // 2 * 2; H = int(W * 3072 / 1728) // 2 * 2
        y0 = max(0, int(H * HEAD_TOP - 40 * z)); x0 = (W - w) // 2
        vf = (f"color=c=black:s=1080x1920:r={FPS}:d={d:.3f}[bg];"
              f"[0:v]fps={FPS},scale={W}:{H}:flags=lanczos,crop={w}:{h}:{x0}:{y0},setsar=1,format=yuva420p[a];"
              f"[1:v]format=gray[mk];[a][mk]alphamerge[ac];[bg][ac]overlay={x}:{y}:shortest=1,format=yuv420p[v]")
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.3f}", "-i", DJI, "-loop", "1", "-i", str(ED / "mask_card.png"),
             "-filter_complex", vf, "-map", "[v]", "-t", f"{d:.3f}", *ENC, str(out)])
    print("  seg", out.name, f"{d:.2f}s")

lst = ED / "concat.txt"
lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
base = ED / "base_video.mkv"
run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(base)])
vid = ED / "video_master.mp4"
run(["ffmpeg", "-y", "-v", "error", "-i", str(base), "-c:v", "libvpx-vp9", "-i", str(JOB / "gfx" / "render.webm"),
     "-filter_complex", f"[1:v]fps={FPS},format=yuva420p[g];[0:v][g]overlay=0:0:format=auto,"
                        f"subtitles='{esc(ED / 'captions.ass')}':fontsdir='{esc(FONTS)}',format=yuv420p[v]",
     "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-r", str(FPS), "-t", f"{END:.3f}", str(vid)])

# ---- sound (mixed per variant: the voice is muted after the variant's last word, so the end freeze can't play the
#      next section of the master — the IG freeze used to leak the start of the YT CTA, "hamara WhatsApp")
def mix(dst, voice_end):
    run(["ffmpeg", "-y", "-v", "error", "-i", str(ED / "voice.wav"), "-i", str(ED / "sfx.wav"), "-i", str(ED / "music_score.wav"),
         "-filter_complex", f"[0:a]volume=0:enable='gte(t,{voice_end:.3f})'[vo];[vo][1:a][2:a]amix=inputs=3:normalize=0:duration=longest,"
                            f"atrim=0:{END + 0.8:.3f},volume=14dB,alimiter=limit=0.72:attack=4:release=60:level=disabled",
         "-ar", "48000", "-c:a", "pcm_s24le", str(dst)])


def loudnorm(src, dst):
    o = run(["ffmpeg", "-v", "info", "-i", str(src), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    j = json.loads(o[o.rfind("{"): o.rfind("}") + 1])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af",
         f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
         f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true", "-ar", "48000", "-c:a", "pcm_s24le", str(dst)])


VARIANTS = {"instagram": (TL["ig"]["ranges"], 0.6), "youtube": (TL["yt"]["ranges"], 0.4)}
for name, (rs, fz) in VARIANTS.items():
    vparts = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];" for i, (a, b) in enumerate(rs))
    vcat = "".join(f"[v{i}]" for i in range(len(rs))) + f"concat=n={len(rs)}:v=1:a=0,tpad=stop_mode=clone:stop_duration={fz}[v]"
    vout = ED / f"v_{name}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(vid), "-filter_complex", vparts + vcat, "-map", "[v]",
         "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-r", str(FPS), str(vout)])
    total = sum(b - a for a, b in rs) + fz
    aparts = "".join(f"[0:a]atrim={a}:{b + (fz if i == len(rs) - 1 else 0)},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.03,"
                     f"afade=t=out:st={b - a + (fz if i == len(rs) - 1 else 0) - 0.03:.3f}:d=0.03[a{i}];" for i, (a, b) in enumerate(rs))
    acat = "".join(f"[a{i}]" for i in range(len(rs))) + f"concat=n={len(rs)}:v=0:a=1,afade=t=out:st={total - 0.5:.3f}:d=0.5[a]"
    pre = ED / f"mix_{name}.wav"; mix(pre, rs[-1][1])
    araw = ED / f"a_{name}_pre.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(pre), "-filter_complex", aparts + acat, "-map", "[a]", "-ar", "48000", "-c:a", "pcm_s24le", str(araw)])
    aout = ED / f"a_{name}.wav"
    loudnorm(araw, aout)
    out = JOB / f"GENJUTSU_REEL_{name}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(vout), "-i", str(aout), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "256k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)])
    chk = run(["ffmpeg", "-v", "info", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    print(f"-> {out.name} {total:.2f}s |", " ".join(l.strip() for l in chk.splitlines()[-14:] if any(k in l for k in ("I:", "Peak:"))))
