"""Condensed 16:9 side-by-side intro built from the finished reel.

Left half  = edited (graded + effects), right half = ORIGINAL, both a 960x1080 crop of the reel cut.
Blocks of the reel's OUTPUT timeline (frame-exact, cut in silences):
  A  hook + bad-takes timeline      reel [0 .. end of W4]
  B  logo -> glass break            reel [W6 start .. W9 end]
  C  reels hit + documentary        reel [W19 start .. W23 end]

Usage:
  python build_intro.py gfx            # write + lint + render the overlay slots (cached)
  python build_intro.py compose [final]
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

R = Path(r"C:\Users\PARAS ARORA\Desktop\edit\edit")            # the reel job
I = Path(r"C:\Users\PARAS ARORA\AI_Editor\inbox\longform-ai-editor\edit\intro")
BASE = R / "animations" / "_base"
FPS, X0 = 25, 450          # left/right halves = crop x 450..1410 of the 1920x1080 reel cut
HF = "npx --yes hyperframes@0.8.111"
GRADE = "eq=contrast=1.08:saturation=1.06:brightness=0.01,colorbalance=rs=-0.01:bs=0.04:rm=0.035:gm=-0.012:bm=-0.02,vignette=angle=0.42"

words = json.load(open(R / "words_out.json", encoding="utf-8"))["words"]


def fr(t):  # snap to frame
    return round(round(t * FPS) / FPS, 3)


def first(line):
    return next(w for w in words if w["line"] == line)


def last(line):
    return [w for w in words if w["line"] == line][-1]


BLOCKS = [  # reel output time
    (0.0, fr(last("W4")["end"] + 0.14)),
    (fr(first("W6")["start"] - 0.10), fr(last("W9")["end"] + 0.18)),
    (fr(first("W19")["start"] - 0.10), fr(last("W23")["end"] + 0.30)),
]


def to_intro(t):
    acc = 0.0
    for a, b in BLOCKS:
        if a - 1e-6 <= t <= b + 1e-6:
            return round(acc + (t - a), 3)
        acc += b - a
    return None


INTRO_LEN = round(sum(b - a for a, b in BLOCKS), 3)

# overlay slots: template, reel start time, substitutions (positions converted from the reel's top-half coords)
SLOTS = {
    "hook": ("hook.html", 0.0, {"DUR": 3.2, "T_SLAM": 1.86, "WORDS": json.dumps(
        [["Bhai,", "i", 0.05], ["maine", "i", 0.29], ["kar", "i", 0.65], ["diya", "i", 0.85], ["apne", "i", 1.0],
         ["video", "b", 1.26], ["editor", "b", 1.54], ["ki", "i", 1.88]])}),
    "timeline": ("timeline.html", 7.55, {}),
    "glass": ("glass.html", 16.70, {"DUR": 9.6, "T_APPEAR": 0.27, "T_SPIN": 1.68, "T_GROW": 3.29, "T_ZOOM": 5.51,
                                    "T_BREAK": 6.33, "T_FALL": 7.43, "PALM_X": 645, "PALM_Y": 658, "CX": 480, "CY": 520}),
    "reels": ("reels.html", 52.70, {"DUR": 10.8, "T_IN": 0.36, "T_CLICK": 6.49, "T_HIT": 8.36, "T_HIT2": 9.43,
                                    "CX": 480, "CY": 596, "HX": 484, "HY": 242, "H2X": 1455, "H2Y": 262,
                                    "B1X": 600, "B1Y": 120, "B2X": 1570, "B2Y": 140}),
    "doc_back": ("doc_back.html", 67.72, {"DUR": 2.8}),
    "doc_front": ("doc_front.html", 67.72, {"DUR": 2.8}),
}


def sh(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=isinstance(cmd, str))


def gfx():
    for name, (tpl, _, subs) in SLOTS.items():
        d = I / "slots" / name
        d.mkdir(parents=True, exist_ok=True)
        for f in ("package.json", "hyperframes.json", "meta.json"):
            shutil.copy(BASE / f, d / f)
        html = (I / "tpl" / tpl).read_text(encoding="utf-8")
        for k, v in subs.items():
            html = html.replace("{{" + k + "}}", str(v))
        assert "{{" not in html, f"{name}: unfilled placeholder"
        if name == "reels" and not (d / "img").exists():
            shutil.copytree(R / "animations" / "slot_reels" / "img", d / "img")
        old = (d / "index.html").read_text(encoding="utf-8") if (d / "index.html").exists() else None
        (d / "index.html").write_text(html, encoding="utf-8")
        lint = sh(f"{HF} lint", d)
        bad = [l for l in (lint.stdout + lint.stderr).splitlines() if l.strip().startswith("✗")]
        if bad:
            sys.exit(f"{name} lint:\n" + "\n".join(bad))
        if old == html and (d / "render.webm").exists():
            print(f"{name}: cached"); continue
        r = sh(f"{HF} render . --format webm --fps {FPS} --workers 1 --quality looks -o render.webm", d)
        print(f"{name}: {'rendered' if (d / 'render.webm').exists() and r.returncode == 0 else 'FAILED ' + r.stderr[-300:]}", flush=True)


def esc(p):
    return Path(p).resolve().as_posix().replace(":", r"\:").replace("'", r"\'")


def ass_time(t):
    h, r = divmod(max(0, t), 3600); m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def captions(path, hide):
    """Word-by-word captions on the EDITED half only (centred at x=480)."""
    sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
    from captions_ass import chunks
    ws = []
    for w in words:
        a = to_intro(w["start"]); b = to_intro(w["end"])
        if a is not None and b is not None:
            ws.append({**w, "start": a, "end": b})
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Cap,Inter,52,&H00FFFFFF,&H00FFFFFF,&H000F0E0C,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,2,40,1000,70,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    BLUE = r"{\c&HD19F1A&\fscx112\fscy112\t(0,90,\fscx100\fscy100)}"
    lines = []
    for ch in chunks(ws):
        for j, w in enumerate(ch):
            a = w["start"]; b = ch[j + 1]["start"] if j + 1 < len(ch) else w["end"] + 0.12
            if any(a < h1 and b > h0 for h0, h1 in hide):
                continue
            txt = " ".join((BLUE + x["text"] + r"{\c&HFFFFFF&}") if k == j else x["text"] for k, x in enumerate(ch))
            lines.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Cap,,0,0,0,,{txt}")
    Path(path).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def compose(final=False):
    cut = R / ("cut_final.mkv" if final else "cut.mkv")
    wd = I / "build"; wd.mkdir(exist_ok=True)
    # 1. cut the three blocks out of the reel cut (frame-exact, 30 ms audio fades)
    segs = []
    for i, (a, b) in enumerate(BLOCKS):
        d = round(b - a, 3); seg = wd / f"blk{i}.mkv"
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-i", str(cut), "-t", f"{d:.3f}", "-vf", f"fps={FPS}",
            "-af", f"afade=t=in:st=0:d=0.03,afade=t=out:st={d - 0.03:.3f}:d=0.03", "-c:v", "libx264", "-preset", "fast",
            "-crf", "14" if final else "18", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-ar", "48000", str(seg)])
        segs.append(seg)
    (wd / "blocks.txt").write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    base = wd / "intro_base.mkv"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(wd / "blocks.txt"), "-c", "copy", str(base)])

    # 2. overlays (+ cut-outs from the reel job) in intro time
    hook_cut, doc_cut = R / "cutouts" / "hook_cut.webm", R / "cutouts" / "doc_cut.webm"
    S = {n: I / "slots" / n / "render.webm" for n in SLOTS}
    ov = [  # (file, intro start, pre-filter, is cut-out)
        (S["hook"], to_intro(0.0), "", False),
        (hook_cut, to_intro(0.0), f"crop=960:1080:{X0}:0,", "grade"),
        (S["timeline"], to_intro(7.55), "", False),
        (S["glass"], to_intro(16.70), "", False),
        (S["reels"], to_intro(52.70), "", False),
        (S["doc_back"], to_intro(67.72), "", False),
        (doc_cut, to_intro(67.72), f"crop=960:1080:{X0}:0,format=rgba,hue=s=0,", True),
        (S["doc_front"], to_intro(67.72), "", False),
    ]
    missing = [str(o[0]) for o in ov if o[1] is None or not Path(o[0]).exists()]
    if missing:
        sys.exit("missing overlays: " + ", ".join(missing))
    inputs = ["-i", str(base)]
    fc = ["[0:v]split=2[a][b]", f"[a]crop=960:1080:{X0}:0,{GRADE}[L]", f"[b]crop=960:1080:{X0}:0[Rr]",
          "[L][Rr]hstack=2,drawbox=x=958:y=0:w=4:h=1080:color=0x1A9FD1@1:t=fill[base]"]
    cur = "[base]"
    for k, (f, t0, pre, is_cut) in enumerate(ov, start=1):
        inputs += ["-c:v", "libvpx-vp9", "-i", str(f)]
        dur = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)]).stdout)
        if is_cut == "grade":   # colour filters drop alpha: grade RGB, then put the cut-out's own alpha back
            fc.append(f"[{k}:v]{pre}format=rgba,split=2[c{k}][m{k}]")
            fc.append(f"[c{k}]{GRADE},format=rgba[g{k}]")
            fc.append(f"[m{k}]alphaextract[a{k}]")
            fc.append(f"[g{k}][a{k}]alphamerge,setpts=PTS-STARTPTS+{t0:.3f}/TB[o{k}]")
        else:
            fc.append(f"[{k}:v]{pre}format=rgba,setpts=PTS-STARTPTS+{t0:.3f}/TB[o{k}]")
        fc.append(f"{cur}[o{k}]overlay=0:0:eof_action=pass:enable='between(t,{t0:.3f},{t0 + dur:.3f})'[v{k}]")
        cur = f"[v{k}]"
    font = esc(r"C:\Users\PARAS ARORA\AI_Editor\fonts\Inter-Bold.ttf")
    for text, x in (("EDITED BY CLAUDE", 28), ("ORIGINAL TAKE", 988)):
        fc.append(f"{cur}drawtext=fontfile='{font}':text='{text}':x={x}:y=24:fontsize=24:fontcolor=white:"
                  f"box=1:boxcolor=0x0C0E0F@0.72:boxborderw=12[l{x}]")
        cur = f"[l{x}]"
    hook_end, doc0 = to_intro(3.2), to_intro(67.72)
    tl0 = to_intro(7.55)
    n_caps = captions(wd / "intro.ass", [[0, hook_end], [tl0, tl0 + 5.6], [doc0, doc0 + 2.8]])
    fc.append(f"{cur}subtitles='{esc(wd / 'intro.ass')}':fontsdir='{esc(r'C:/Users/PARAS ARORA/AI_Editor/fonts')}'[vout]")

    # 3. audio: voice + the reel's SFX that fall inside the blocks
    cfg = json.load(open(R / "reel.json"))
    sfx = [(s["file"], to_intro(s["at"]), s["gain_db"]) for s in cfg["sfx"]]
    sfx = [s for s in sfx if s[1] is not None]
    aud = ["[0:a]aformat=sample_rates=48000:channel_layouts=stereo[voice]"]
    mix = ["[voice]"]
    n = len(ov) + 1
    for j, (f, at, g) in enumerate(sfx):
        inputs += ["-i", f]
        ms = int(at * 1000)
        aud.append(f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={g}dB,adelay={ms}|{ms}[s{j}]")
        mix.append(f"[s{j}]"); n += 1
    aud.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first[aout]")
    out = I / ("intro_final.mkv" if final else "intro_preview.mkv")
    r = sh(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc + aud), "-map", "[vout]", "-map", "[aout]",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "medium" if final else "veryfast", "-crf", "16" if final else "20",
            "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(out)])
    if r.returncode:
        sys.exit(r.stderr[-2000:])
    print(f"intro: {out}  {INTRO_LEN:.2f}s, {len(ov)} overlays, {len(sfx)} sfx, {n_caps} caption events")
    print("blocks (reel time):", BLOCKS)


if __name__ == "__main__":
    if sys.argv[1] == "gfx":
        gfx()
    else:
        compose(final=len(sys.argv) > 2 and sys.argv[2] == "final")
