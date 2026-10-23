"""Compose a 9:16 split-screen reel: top = edited (graded + effects), bottom = ORIGINAL take.

Reads a reel.json config:
{
  "source": "<video whose audio track is the clean voice>",
  "ranges": [[start, end], ...],           # source seconds to keep, in order
  "fps": 25,
  "crop_x": 313,                            # x offset of the 1080-wide crop from the 1707x960 scale
  "grade": "<ffmpeg filter for the edited half>",
  "overlays": [                             # output-timeline seconds; files are 1080x1920
     {"file": "x.webm", "start": 0.0},                                  # simple overlay
     {"file": "back.webm", "start": 0.0, "cutout": "cut.webm",          # graphic BEHIND the speaker
      "cutout_filter": "hue=s=0"}],
  "bubble": {"start": 30, "end": 70, "src_cx": 930, "src_cy": 420, "src_size": 520, "x": 760, "y": 640, "d": 260},
  "captions": "captions.ass",
  "labels": {"top": "EDITED BY CLAUDE", "bottom": "ORIGINAL TAKE"},
  "sfx": [{"file": "a.wav", "at": 1.2, "gain_db": -4}],
  "music": {"file": "bed.mp3", "gain_db": -20},
  "out": "reel.mp4"
}

Usage:
  python reel_compose.py reel.json cut      # step 1: cut.mkv (+ cut timing report)
  python reel_compose.py reel.json compose  # step 2: final mp4 (needs overlays/cutouts rendered)
"""
import json
import subprocess
import sys
from pathlib import Path

FADE = 0.03  # 30 ms audio fades at every cut (no pops)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        sys.exit("ffmpeg failed:\n" + " ".join(map(str, cmd))[:600] + "\n" + p.stderr[-2500:])
    return p


def esc(p):  # path inside an ffmpeg filter argument
    return Path(p).resolve().as_posix().replace(":", r"\:").replace("'", r"\'")


def cut(cfg, wd: Path):
    segs, t = [], 0.0
    for i, (s, e) in enumerate(cfg["ranges"]):
        d = e - s
        seg = wd / f"seg_{i:03d}.mkv"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.3f}", "-i", cfg["source"], "-t", f"{d:.3f}",
             "-vf", f"fps={cfg['fps']},scale=1920:1080", "-af",
             f"afade=t=in:st=0:d={FADE},afade=t=out:st={d - FADE:.3f}:d={FADE}",
             "-c:v", "libx264", "-preset", "fast", "-crf", str(cfg.get("crf", 16)), "-pix_fmt", "yuv420p",
             "-c:a", "pcm_s16le", "-ar", "48000", str(seg)])
        segs.append(seg)
        print(f"  seg {i:02d}  src {s:7.2f}-{e:7.2f}  ->  out {t:7.2f}-{t + d:7.2f}")
        t += d
    lst = wd / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(wd / "cut.mkv")])
    print(f"cut.mkv  {t:.2f}s")


def compose(cfg, wd: Path):
    cutf = wd / "cut.mkv"
    cx = cfg.get("crop_x", 313)
    inputs = ["-i", str(cutf)]
    fc = ["[0:v]split=2[full][forbub]",
          f"[full]scale=1707:960,crop=1080:960:{cx}:0,split=2[srcA][srcB]",
          f"[srcA]{cfg.get('grade', 'null')}[top]",
          "[srcB]null[bot]",
          "[top][bot]vstack=2[base]"]
    cur, n = "[base]", 1

    timing = {}

    def add_input(path, offset):
        nonlocal n
        dec = ["-c:v", "libvpx-vp9"] if str(path).lower().endswith(".webm") else []
        inputs.extend([*dec, "-i", str(path)])
        dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).stdout)
        timing[n] = (offset, offset + dur)
        n += 1
        return n - 1

    def over(label_in, idx, x=0, y=0, pre=""):
        t0, t1 = timing[idx]
        out = f"[v{idx}]"
        fc.append(f"[{idx}:v]{pre}format=rgba,setpts=PTS-STARTPTS+{t0:.3f}/TB[o{idx}]")
        fc.append(f"{label_in}[o{idx}]overlay={x}:{y}:eof_action=pass:enable='between(t,{t0:.3f},{t1:.3f})'{out}")
        return out

    for ov in cfg.get("overlays", []):
        idx = add_input(ov["file"], ov["start"])
        cur = over(cur, idx)
        if ov.get("cutout"):  # speaker cut-out on top of the "behind" graphic, same crop as the edited half
            cidx = add_input(ov["cutout"], ov["start"])
            pre = f"scale=1707:960,crop=1080:960:{cx}:0,{ov.get('cutout_filter', 'null')},"
            cur = over(cur, cidx, pre=pre)
        for fr in ov.get("front", []):
            fidx = add_input(fr, ov["start"])
            cur = over(cur, fidx)

    b = cfg.get("bubble")
    if b:  # round webcam bubble cut from the cut timeline itself
        r, ring = b["d"] // 2, 7  # 7 px brand-blue ring (#1A9FD1) around the face
        D = f"hypot(X-{r},Y-{r})"
        fc.append(f"[forbub]crop={b['src_size']}:{b['src_size']}:{b['src_cx'] - b['src_size'] // 2}:{b['src_cy'] - b['src_size'] // 2},"
                  f"scale={b['d']}:{b['d']},{cfg.get('grade', 'null')},format=rgba,"
                  f"geq=r='if(gt({D},{r - ring}),26,r(X,Y))':g='if(gt({D},{r - ring}),159,g(X,Y))':"
                  f"b='if(gt({D},{r - ring}),209,b(X,Y))':a='if(lte({D},{r - 1}),255,if(lte({D},{r}),128,0))'[bub]")
        fc.append(f"{cur}[bub]overlay={b['x']}:{b['y']}:enable='between(t,{b['start']},{b['end']})'[vb]")
        cur = "[vb]"
    else:
        fc.append("[forbub]nullsink")

    lab = cfg.get("labels")
    if lab:
        fonts = esc(cfg["fontfile"])
        for text, y in ((lab.get("top"), lab.get("top_y", 24)), (lab.get("bottom"), lab.get("bottom_y", 984))):
            if not text:
                continue
            fc.append(f"{cur}drawtext=fontfile='{fonts}':text='{text}':x=28:y={y}:fontsize=26:fontcolor=white:"
                      f"box=1:boxcolor=0x0C0E0F@0.72:boxborderw=12[l{y}]")
            cur = f"[l{y}]"
    if cfg.get("captions"):
        fd = f":fontsdir='{esc(cfg['fontsdir'])}'" if cfg.get("fontsdir") else ""
        fc.append(f"{cur}subtitles='{esc(cfg['captions'])}'{fd}[vout]")
    else:
        fc.append(f"{cur}null[vout]")

    # ---- audio: voice + ducked music + SFX
    aud = ["[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[voice][key]"]
    mix = ["[voice]"]
    m = cfg.get("music")
    if m:
        inputs.extend(["-stream_loop", "-1", "-i", m["file"]]); n += 1
        aud.append(f"[{n - 1}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={m['gain_db']}dB[bed]")
        if m.get("sidechain", True):   # off for score_music stems (already automated against the voice)
            aud.append("[bed][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck]")
            mix.append("[duck]")
        else:
            aud.append("[key]anullsink")
            mix.append("[bed]")
    else:
        aud.append("[key]anullsink")
    for i, s in enumerate(cfg.get("sfx", [])):
        inputs.extend(["-i", s["file"]]); n += 1
        ms = int(round(s["at"] * 1000))
        aud.append(f"[{n - 1}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={s.get('gain_db', -6)}dB,adelay={ms}|{ms}[s{i}]")
        mix.append(f"[s{i}]")
    aud.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first[amix]")

    pre = wd / "reel.prenorm.mkv"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc + aud),
         "-map", "[vout]", "-map", "[amix]", "-r", str(cfg["fps"]), "-c:v", "libx264", "-preset", cfg.get("preset", "medium"),
         "-crf", str(cfg.get("out_crf", 18)), "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-shortest", str(pre)])

    # two-pass loudness: -14 LUFS integrated, -1 dBTP (social)
    meas = run(["ffmpeg", "-v", "info", "-i", str(pre), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    j = json.loads(meas[meas.rfind("{"): meas.rfind("}") + 1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
          f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    out = Path(cfg["out"])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(pre), "-c:v", "copy", "-af", ln, "-ar", "48000",
         "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out)])
    print(f"done: {out}  (input loudness {j['input_i']} LUFS)")


if __name__ == "__main__":
    cfg_path = Path(sys.argv[1])
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    wd = cfg_path.parent
    {"cut": cut, "compose": compose}[sys.argv[2]](cfg, wd)
