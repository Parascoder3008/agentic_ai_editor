"""The picture: a base video from the timeline (or the cut), graphics and captions on top, one cut per variant, muxed
with that variant's audio. Picture and sound render separately and only meet in the mux (rendering both in one graph
drifted the Equal ad by up to 0.77 s).

job.json "layouts" (framing measured on each job's footage):
  {"split": {"card": [x, y, w, h], "crop": [w, h, x, y], "radius": 28, "border": "#3AB0D88C"},
                         presenter card: the source cropped, scaled into a rounded glass card on the void background,
                         under the graphics stage (reel-05)
   "face":  {"crop": [w, h, x, y]}       a 9:16 window of the source, full frame (reel-05)
   "camera": {"head": [x, y], "crop": [w, h, x, y]}}
                                         cut jobs: each piece scaled by its zoom about the head point (in output
                                         pixels), cropped to the frame, so a punch-in never moves the face off its mark
                                         (reel-04). "crop" (optional) first cuts a source whose shape differs from the
                                         output, e.g. a 9:16 window of a 16:9 take.
Layouts hook, broll and full fill the frame with the whole source.
job.json "custom": scripts that rework the base in order (reel-04's compose_base.py: frame-by-frame layouts, cut-outs).
Each runs from its own folder with AIE_IN (the base so far), AIE_OUT (where to write), AIE_JOB, AIE_FPS, AIE_SIZE.

Ported from reel-05's compose.py and reel-04's prep.py / compose.py; the ffmpeg commands are the ones they ran.
"""
from pathlib import Path

LAYOUT_KEYS = {"split", "face", "camera"}
FULL = {"hook", "broll", "full"}
FINAL = ["-crf", "16", "-preset", "slow"]
PREVIEW = ["-crf", "23", "-preset", "veryfast"]
BASE = ["-crf", "14", "-preset", "medium"]          # the base is re-encoded once more, so it starts finer


def esc(p) -> str:
    """A path inside an ffmpeg filter argument."""
    return Path(p).resolve().as_posix().replace(":", r"\:").replace("'", r"\'")


def _rgba(c: str) -> tuple:
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) + ((int(c[7:9], 16),) if len(c) == 9 else (255,))


def card_assets(split: dict, size, out_dir: Path) -> tuple:
    """The presenter card's rounded mask and its thin border, as stills for ffmpeg."""
    from PIL import Image, ImageDraw
    x, y, w, h = split["card"]
    r = split.get("radius", 28)
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=255)
    out_dir.mkdir(parents=True, exist_ok=True)
    mask, border = out_dir / "card_mask.png", out_dir / "card_border.png"
    m.save(mask)
    b = Image.new("RGBA", tuple(size), (0, 0, 0, 0))
    ImageDraw.Draw(b).rounded_rectangle([x - 1, y - 1, x + w, y + h], r + 1, outline=_rgba(split.get("border", "#3AB0D88C")),
                                        width=3)
    b.save(border)
    return mask, border


def timeline_base_cmd(segments: list, paths: list, layouts: dict, fps: int, size, end: float, mask, border, out,
                      quality=BASE) -> list:
    """Every segment framed by its layout, joined in one graph (reel-05)."""
    W, H = size
    ins, fl = [], []
    n = len(segments)
    for i, (seg, path) in enumerate(zip(segments, paths)):
        t0, t1 = seg["t"]
        lay, s_in, sp = seg["layout"], seg["in"], seg.get("speed", 1.0)
        d = t1 - t0
        ins += ["-i", str(path)]
        trim = f"[{i}:v]trim={s_in}:{s_in + d * sp},setpts=(PTS-STARTPTS)/{sp},fps={fps},"
        if lay in FULL:
            fl.append(trim + f"scale={W}:{H}:flags=lanczos,setsar=1,format=yuv420p[s{i}]")
        elif lay == "face":
            cw, ch, cx, cy = layouts["face"]["crop"]
            fl.append(trim + f"crop={cw}:{ch}:{cx}:{cy},scale={W}:{H}:flags=lanczos,unsharp=5:5:0.5,setsar=1,format=yuv420p[s{i}]")
        elif lay == "split":
            x, y, w, h = layouts["split"]["card"]
            cw, ch, cx, cy = layouts["split"]["crop"]
            fl.append(trim + f"crop={cw}:{ch}:{cx}:{cy},scale={w}:{h}:flags=lanczos,format=yuva420p[a{i}];"
                      f"[{n}:v]format=gray,trim=0:{d:.3f}[mk{i}];[a{i}][mk{i}]alphamerge[ac{i}];"
                      f"color=c=0x0C0E0F:s={W}x{H}:r={fps}:d={d:.3f}[bg{i}];[bg{i}][ac{i}]overlay={x}:{y}:shortest=1[c{i}];"
                      f"[c{i}][{n + 1}:v]overlay=0:0:shortest=1,setsar=1,format=yuv420p[s{i}]")
        else:
            raise ValueError(f"layout {lay!r} has no picture yet")
    splits = [i for i, s in enumerate(segments) if s["layout"] == "split"]
    k = len(splits)
    pre = ""
    if k:   # the masks are looped stills: split them so every split beat gets its own copy
        pre = (f"[{n}:v]split={k}" + "".join(f"[m{j}]" for j in range(k)) + ";" +
               f"[{n + 1}:v]split={k}" + "".join(f"[b{j}]" for j in range(k)) + ";")
        for j, i in enumerate(splits):
            fl[i] = fl[i].replace(f"[{n}:v]format=gray", f"[m{j}]format=gray").replace(f"[{n + 1}:v]overlay", f"[b{j}]overlay")
    fc = pre + ";".join(fl) + ";" + "".join(f"[s{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    extra = ["-loop", "1", "-i", str(mask), "-loop", "1", "-i", str(border)] if k else []
    return ["ffmpeg", "-y", "-v", "error", *ins, *extra, "-filter_complex", fc, "-map", "[v]", "-an", "-c:v", "libx264",
            *quality, "-t", f"{end:.3f}", str(out)]


def face_piece_cmds(pieces: list, files: dict, head, fps: int, size, seg_dir: Path, crop=None) -> list:
    """Each piece from its take, scaled by its zoom about the head point and cropped to the frame (reel-04).
    Returns [(cmd, output file)]; a piece whose file already exists can be skipped (its name holds its settings)."""
    W0, H0 = size
    hx, hy = head
    pre = f"crop={crop[0]}:{crop[1]}:{crop[2]}:{crop[3]}," if crop else ""
    out = []
    for i, p in enumerate(pieces):
        s, e, z = p["in"], p["out"], p.get("zoom", 1.0)
        W, H = int(W0 * z) // 2 * 2, int(H0 * z) // 2 * 2
        x0, y0 = int(hx * z - hx), int(hy * z - hy)
        f = seg_dir / f"f{i:02d}_{p['src']}_{s:.3f}_{z}.mkv"
        out.append((["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.4f}", "-i", str(files[p["src"]]), "-t", f"{e - s:.4f}",
                     "-vf", f"fps={fps},{pre}scale={W}:{H}:flags=lanczos,crop={W0}:{H0}:{x0}:{y0},setsar=1,format=yuv420p",
                     "-an", "-c:v", "libx264", "-crf", "12", "-preset", "medium", str(f)], f))
    return out


def concat_cmd(files: list, list_file: Path, out) -> list:
    list_file.write_text("".join(f"file '{Path(p).as_posix()}'\n" for p in files))
    return ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)]


def master_cmd(base, fps: int, end: float, out, gfx=None, gfx_offset: float = 0.0, gfx_pad: float = 0.0, ass=None,
               fonts=None, quality=FINAL, effects=()) -> list:
    """Graphics (a transparent webm), effects (transparent webms placed at their times) and burned-in captions over
    the base, in that order from the bottom."""
    ins, chain = ["-i", str(base)], ""
    pre = ""
    if gfx:
        ins += ["-c:v", "libvpx-vp9", "-i", str(gfx)]                  # libvpx keeps the webm's alpha
        g = ""
        if gfx_offset:
            g += f"trim=start={gfx_offset},setpts=PTS-STARTPTS,"
        g += f"fps={fps},"
        if gfx_pad:
            g += f"tpad=stop_mode=clone:stop_duration={gfx_pad},"
        pre = f"[1:v]{g}format=yuva420p[g];"
        chain = "[0:v][g]overlay=0:0:format=auto,"
    for j, e in enumerate(effects):
        ins += ["-c:v", "libvpx-vp9", "-i", str(e["path"])]
        k = 1 + bool(gfx) + j                            # its input number: the base, the graphics, earlier effects
        pre += f"[{k}:v]fps={fps},format=yuva420p,setpts=PTS-STARTPTS+{e['at']}/TB[e{j}];"   # shifted, never seeked
        prev = "[0:v]"
        if chain:
            chain, prev = chain[:-1] + f"[c{j}];", f"[c{j}]"
        chain += f"{prev}[e{j}]overlay=0:0:format=auto:eof_action=pass,"
    chain = chain or "[0:v]"
    if ass:
        chain += f"subtitles='{esc(ass)}':fontsdir='{esc(fonts)}',"
    graph = pre + chain + "format=yuv420p[v]"
    return ["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", graph, "-map", "[v]", "-an", "-c:v", "libx264",
            *quality, "-r", str(fps), "-t", f"{end:.3f}", str(out)]


def variant_video_cmd(master, ranges: list, freeze: float, fps: int, out, quality=FINAL) -> list:
    """The variant's ranges cut from the master; the last frame held for the freeze."""
    parts = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];" for i, (a, b) in enumerate(ranges))
    cat = "".join(f"[v{i}]" for i in range(len(ranges))) + f"concat=n={len(ranges)}:v=1:a=0,tpad=stop_mode=clone:stop_duration={freeze}[v]"
    return ["ffmpeg", "-y", "-v", "error", "-i", str(master), "-filter_complex", parts + cat, "-map", "[v]",
            "-c:v", "libx264", *quality, "-r", str(fps), str(out)]


def mux_cmd(video, audio, total: float, out) -> list:
    return ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "256k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)]


def check_layouts(cfg, data: dict) -> list:
    if not isinstance(cfg, dict):
        return ["layouts: must be an object"]
    errs = [f"layouts: unknown key {k!r} (allowed: {', '.join(sorted(LAYOUT_KEYS))})" for k in sorted(set(cfg) - LAYOUT_KEYS)]
    four = lambda v: isinstance(v, list) and len(v) == 4 and all(isinstance(n, int) and n >= 0 for n in v)
    s = cfg.get("split")
    if s is not None and not (isinstance(s, dict) and four(s.get("card")) and four(s.get("crop"))):
        errs.append("layouts.split: needs \"card\": [x, y, w, h] and \"crop\": [w, h, x, y] in pixels")
    f = cfg.get("face")
    if f is not None and not (isinstance(f, dict) and four(f.get("crop"))):
        errs.append("layouts.face: needs \"crop\": [w, h, x, y] in source pixels")
    c = cfg.get("camera")
    if c is not None and not (isinstance(c, dict) and isinstance(c.get("head"), list) and len(c["head"]) == 2
                              and set(c) <= {"head", "crop"} and ("crop" not in c or four(c["crop"]))):
        errs.append("layouts.camera: needs \"head\": [x, y], the head centre in the output frame, and optionally "
                    "\"crop\": [w, h, x, y] in source pixels")
    used = {s.get("layout") for s in data.get("timeline", []) if isinstance(s, dict)}
    for lay in ("split", "face"):
        if lay in used and lay not in cfg:
            errs.append(f"layouts.{lay}: the timeline uses the {lay} layout, so its framing is needed here")
    return errs
