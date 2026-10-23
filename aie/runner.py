"""Run one stage of a job: python -m aie run <job> <stage> [--force].

Outputs go to <job>/build/ (git-ignored). Each output records a key made from the stage's inputs, so a stage whose
inputs haven't changed is skipped; --force runs it anyway.

  transcribe -> build/words_<source>.json   every spoken word with its time (Whisper, on the PC)
  cut      -> build/pieces.json   frame-exact pieces in output order
  verify   -> build/piece_tx.json, build/joints.txt   every kept piece transcribed alone, every joint reviewed
  captions -> build/words.json, build/captions.ass    words on the output timeline, styled word-by-word captions
  storyboard -> build/storyboard.html  every beat: words, layout, a framed still with every planned box; Paras approves
                                       it (gates.storyboard_approved) before the picture renders
  package  -> build/publish/<PREFIX>_<variant>.srt, cover.jpg
  voice, sfx, music -> build/voice.wav, sfx.wav, music.wav
  mix      -> build/audio_<variant>.wav   one -14 LUFS file per variant
  graphics -> build/graphics.webm      the HyperFrames composition, transparent (or graphics.render, used as is)
  effects  -> build/effects/<n>/render.webm   each catalog effect placed in job.json, transparent
  base     -> build/base.mp4           the footage framed by layout (timeline jobs) or cut piece by piece (cut jobs),
                                       then the job's "custom" scripts in order
  picture  -> build/picture.mp4        graphics, effects and burned-in captions over the base
  deliver  -> build/publish/<PREFIX>_<variant>[_PREVIEW].mp4   each variant cut from the picture, muxed with its audio
  qa       -> build/qa/qa.json, contact sheets   the 9.5 audit (aie/qa.py); "all" runs every stage through qa
  otio     -> build/nle/<id>.otio, <id>.xml, *.srt   the edit for finishing in Resolve or Premiere (aie/nle.py)

A stage brings the stages it reads up to date first (captions runs the cut if it changed). Renders are PREVIEW quality
and named _PREVIEW until gates.final_approved is true. One render runs at a time on a machine.
"""
import contextlib
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .job import Job
from .settings import Settings

# Stages import their modules when they run (numpy, Whisper), so validate and doctor work on a bare machine.

SPAN_PARAMS = ("gap", "pad_in", "pad_out", "silence_db", "speech_db", "min_island")


class StageError(RuntimeError):
    pass


def _key(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _stamp(path) -> list:
    """Size and modification time: enough to notice a replaced source without hashing gigabytes of footage."""
    st = path.stat()
    return [st.st_size, int(st.st_mtime)]


def _read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _source(job: Job, settings: Settings, name: str):
    p = job.source(name, settings)
    if not p.exists():
        raise StageError(f"source {name!r} not found: {p} (check \"sources\" in job.json and \"roots\" in aie.local.json)")
    return p


HINGLISH_PROMPT = ("Umm, toh basically, matlab, haan, achha, uh, dekho, you know, "
                   "toh main aapko bataata hoon, so yeh AI tool hai, na, theek hai.")
FILLER_PROMPT = "Umm, uh, so, like, you know, I mean, hmm. Okay, uh, so basically, um."


def _spoken_sources(job: Job) -> list:
    d = job.data
    cut = d.get("cut") or {}
    if cut.get("mode") == "spans":
        return [cut["source"]]
    if cut.get("mode") == "pieces":
        return sorted({p["src"] for p in cut["pieces"]})
    return [n for n, s in d["sources"].items() if "voice_offset" in s] or list(d["sources"])[:1]


def stage_transcribe(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    """build/words_<source>.json: every spoken word with its time (Whisper, word timestamps, fillers kept so they can
    be cut). Hinglish jobs come out in Roman script, as tools/transcribe_local.py --hinglish wrote them. A first pass:
    names are fixed from qa.words and the Proofreader corrects the rest before captions are final."""
    lang, model = job.data.get("language", "hi"), settings.data["whisper_model"]
    names = job.data.get("qa", {}).get("words", [])
    prompt = (HINGLISH_PROMPT if lang == "hi" else FILLER_PROMPT) + (" " + ", ".join(names) + "." if names else "")
    made, ran = {}, False
    for name in _spoken_sources(job):
        src = _source(job, settings, name)
        out = job.dir / "build" / f"words_{name}.json"
        key = _key("transcribe", model, lang, prompt, _stamp(src))
        old = _read(out)
        if old and old.get("key") == key and not force:
            made[name] = old
            continue
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise StageError("transcribe needs faster-whisper and its model (pip install faster-whisper; the model "
                             "downloads from huggingface.co on first use). Run it on the PC.") from None
        log(f"transcribe: {src.name} with {model} ...")
        m = WhisperModel(model, device="cpu", compute_type="int8")
        segs, info = m.transcribe(str(src), language="en" if lang == "hi" else lang, word_timestamps=True,
                                  vad_filter=False, condition_on_previous_text=False, initial_prompt=prompt, beam_size=5)
        words = [{"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3), "p": round(w.probability, 3)}
                 for sg in segs for w in (sg.words or []) if w.word.strip()]
        made[name] = {"key": key, "language": info.language, "words": words}
        _write(out, made[name])
        ran = True
        log(f"transcribe: {len(words)} words -> {out}")
    if not ran:
        log("transcribe: up to date (" + ", ".join(f"{n} {len(v['words'])} words" for n, v in made.items()) + ")")
    return made


def stage_cut(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    from . import audio, cuts
    cut = job.data.get("cut")
    if not cut:
        raise StageError("this job has no \"cut\": its timeline is written by hand, so there is nothing to cut")
    fps, out = job.data["fps"], job.dir / "build" / "pieces.json"
    if cut["mode"] == "pieces":
        key = _key("cut", cut, fps)
    else:
        src = _source(job, settings, cut["source"])
        key = _key("cut", cut, fps, _stamp(src))
    old = _read(out)
    if old and old.get("key") == key and not force:
        log(f"cut: up to date ({len(old['pieces'])} pieces, {old['length']:.2f} s)")
        return old
    if cut["mode"] == "pieces":
        pieces = cuts.layout_pieces(cut["pieces"])
    else:
        log(f"cut: measuring {src.name} ...")
        env = audio.Envelope.of(src)
        pieces = cuts.build_spans(env, cut["keep"], cut.get("drop", []), fps, cut["source"],
                                  **{k: cut[k] for k in SPAN_PARAMS if k in cut})
    res = {"key": key, "fps": fps, "length": round(cuts.total(pieces), 4), "pieces": pieces}
    _write(out, res)
    log(f"cut: {len(pieces)} pieces, {res['length']:.2f} s ({res['length'] / 60:.1f} min) -> {out}")
    for sec, a, b in cuts.sections(pieces):
        if sec:
            log(f"  {sec:10s} out {a:7.2f}-{b:7.2f}  ({b - a:5.1f}s)")
    return res


def stage_verify(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    from . import audio, verify
    built = _read(job.dir / "build" / "pieces.json")
    if not built:
        raise StageError("no build/pieces.json yet: run the cut stage first")
    pieces = built["pieces"]
    lang, model = job.data.get("language", "hi"), settings.data["whisper_model"]
    out = job.dir / "build" / "piece_tx.json"
    key = _key("verify", built["key"], lang, model)
    old = _read(out)
    if old and old.get("key") == key and not force:
        items = old["pieces"]
        log("verify: transcripts up to date")
    else:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            raise StageError("verify needs faster-whisper and its model (pip install faster-whisper; the model "
                             "downloads from huggingface.co on first use). Run it on the PC.") from None
        sounds = {name: audio.load(_source(job, settings, name)) for name in sorted({p["src"] for p in pieces})}
        log(f"verify: transcribing {len(pieces)} pieces with {model} ({lang}) ...")
        items = verify.transcribe_pieces(pieces, sounds, model, lang, (old or {}).get("pieces"))
        _write(out, {"key": key, "pieces": items})
    js = verify.joints(items)
    lines = verify.format_joints(js)
    (job.dir / "build" / "joints.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    flagged = sum(j["repeat"] or j["lone"] for j in js)
    for line in lines:
        log(line)
    log(f"verify: {len(js)} joints, {flagged} flagged ('<<' repeat, '!!' lone short piece). "
        "Read every line, not just the flags.")
    return {"joints": len(js), "flagged": flagged}


def _dep(log):
    """Log for a prerequisite stage: silent when it was already up to date, so a run only reports work it did."""
    return lambda s: None if s.split(" (")[0].endswith(": up to date") else log(s)


def _built_cut(job: Job, settings: Settings, log) -> dict | None:
    """The cut, brought up to date first, or None for a job whose timeline is written by hand."""
    return stage_cut(job, settings, False, _dep(log)) if "cut" in job.data else None


def _length(job: Job, built: dict | None) -> float:
    return built["length"] if built else job.length


def stage_captions(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    from . import captions
    cap = job.data.get("captions") or {}
    if "words" not in cap:
        raise StageError('this job has no "captions.words": nothing to caption from')
    built = _built_cut(job, settings, log)
    w = cap["words"]
    files = [w["file"], w.get("display")] if w["from"] == "aligned" else list(w["aligned"].values())
    stamps = []
    for f in filter(None, files):
        p = job.dir / f
        if not p.exists():
            raise StageError(f"captions: {f} not found in {job.dir}")
        stamps.append([f, _stamp(p)])
    key = _key("captions", cap, job.data.get("timeline"), job.data["size"], job.data["sources"],
               built and built["key"], stamps)
    out = job.dir / "build" / "words.json"
    old = _read(out)
    if old and old.get("key") == key and (job.dir / "build" / "captions.ass").exists() and not force:
        log(f"captions: up to date ({len(old['words'])} words)")
        return old
    pieces = built["pieces"] if built else None
    try:
        words = captions.caption_words(job.dir, job.data, pieces)
    except ValueError as e:
        raise StageError(f"captions: {e}") from None
    ass = captions.build_ass(job.data, words, pieces, _length(job, built))
    (job.dir / "build").mkdir(exist_ok=True)
    (job.dir / "build" / "captions.ass").write_text(ass, encoding="utf-8")
    res = {"key": key, "words": words}
    _write(out, res)
    n = ass.count("\nDialogue:")
    log(f"captions: {len(words)} words, {n} caption events -> {job.dir / 'build' / 'captions.ass'}")
    return res


def stage_package(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    from . import captions, package
    cap, pkg = job.data.get("captions") or {}, job.data.get("package", {})
    if "words" not in cap and not pkg.get("cover"):
        raise StageError('nothing to package: no "captions.words" for subtitles and no "package.cover"')
    words = stage_captions(job, settings, False, _dep(log))["words"] if "words" in cap else None
    built = _built_cut(job, settings, lambda *_: None)
    prefix = pkg.get("prefix", job.id.upper().replace("-", ""))
    pub = job.dir / "build" / "publish"
    pub.mkdir(parents=True, exist_ok=True)
    made, length = [], _length(job, built)
    chunk = cap.get("chunk")
    for name, v in job.data["variants"].items() if words is not None else ():
        f = pub / f"{prefix}_{name}.srt"
        f.write_text(captions.build_srt(words, v.get("ranges", [[0.0, length]]), chunk), encoding="utf-8")
        made.append(f)
    cov = pkg.get("cover")
    if cov:
        if "frame" in cov:
            frame = job.dir / cov["frame"]
        else:
            picture = job.dir / "build" / "picture.mp4"
            if not picture.exists():
                raise StageError("package: the cover needs the composed picture (run the picture stage) or a "
                                 "\"frame\" image")
            frame = package.grab_frame(picture, cov["at"], job.dir / "build" / "cover_src.png")
        if not frame.exists():
            raise StageError(f"package: cover frame {frame} not found")
        try:
            made.append(package.cover(frame, cov, settings.path("fonts"), pub / "cover.jpg"))
        except ValueError as e:
            raise StageError(f"package: {e}") from None
    for f in made:
        log(f"package: {f}")
    return {"files": [str(f) for f in made]}


def _mix(job: Job) -> dict:
    return {"gain_db": "auto", "voice_lufs": -17.0, "joint_fade": 0.02, "tail": 0.8, **job.data.get("mix", {})}


def _voice_source(job: Job) -> str | None:
    """The source whose own audio is the voice (an avatar render), or None when the voice comes from the cut."""
    m = job.data.get("mix", {})
    if "voice" in m:
        return m["voice"]
    if "cut" in job.data:
        return None
    named = [n for n, s in job.data["sources"].items() if "voice_offset" in s]
    if not named:
        raise StageError('no voice: give "mix": {"voice": <source>} or a "cut"')
    return named[0]


def stage_voice(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    from . import sound
    built = _built_cut(job, settings, log)
    name, out = _voice_source(job), job.dir / "build" / "voice.wav"
    if name:
        src = _source(job, settings, name)
        key = _key("voice", name, job.data["sources"][name], _stamp(src))
    else:
        files = {n: _source(job, settings, n) for n in sorted({p["src"] for p in built["pieces"]})}
        key = _key("voice", built["key"], _mix(job)["tail"], [[n, _stamp(f)] for n, f in files.items()])
    stamp = job.dir / "build" / "voice.key"
    if out.exists() and stamp.exists() and stamp.read_text() == key and not force:
        log("voice: up to date")
        return {"key": key, "path": out}
    out.parent.mkdir(parents=True, exist_ok=True)
    if name:
        sound.voice_from_source(src, job.data["sources"][name].get("voice_offset", 0.0), out)
        log(f"voice: {name} from {job.data['sources'][name].get('voice_offset', 0.0)} s -> {out}")
    else:
        sound.voice_from_pieces(built["pieces"], files, built["length"] + _mix(job)["tail"], out)
        log(f"voice: {len(built['pieces'])} pieces, room-tone crossfade at every joint -> {out}")
    stamp.write_text(key)
    return {"key": key, "path": out}


def _stem(job, settings, force, log, kind, cfg, render):
    """Shared shape of the sfx and music stages: brought up to date against the voice and their own settings."""
    import soundfile as sf
    voice = stage_voice(job, settings, False, _dep(log))
    out, stamp = job.dir / "build" / f"{kind}.wav", job.dir / "build" / f"{kind}.key"
    key = _key(kind, cfg, voice["key"], job.length)
    if out.exists() and stamp.exists() and stamp.read_text() == key and not force:
        log(f"{kind}: up to date")
        return {"key": key, "path": out}
    x = render(voice["path"])
    sf.write(out, x, 48000, subtype="PCM_24")
    stamp.write_text(key)
    log(f"{kind}: {len(x) / 48000:.2f} s, peak {20 * math.log10(float(abs(x).max()) + 1e-12):.1f} dBFS -> {out}")
    return {"key": key, "path": out}


def stage_sfx(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    from . import sfx
    cfg = job.data.get("sfx")
    if not cfg or not cfg.get("cues"):
        raise StageError("this job has no \"sfx\" cues")
    built = _built_cut(job, settings, lambda *_: None)

    def render(voice_path):
        import soundfile as sf
        v, _ = sf.read(voice_path)
        return sfx.render(cfg, _length(job, built) + _mix(job)["tail"], v)
    return _stem(job, settings, force, log, "sfx", cfg, render)


def stage_music(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    from . import music
    cfg = job.data.get("music")
    if not cfg:
        raise StageError("this job has no \"music\" score")

    def render(voice_path):
        return music.render(cfg["score"], music.read_stereo(voice_path), cfg.get("voice_gain", []), log)
    return _stem(job, settings, force, log, "music", cfg, render)


def stage_mix(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    from . import sound
    built = _built_cut(job, settings, lambda *_: None)
    voice = stage_voice(job, settings, False, _dep(log))
    fx = stage_sfx(job, settings, False, _dep(log)) if job.data.get("sfx") else None
    mu = stage_music(job, settings, False, _dep(log)) if job.data.get("music") else None
    stems = [fx and fx["path"], mu and mu["path"]]
    m, length = _mix(job), _length(job, built)
    key = _key("mix", m, job.data["variants"], length, voice["key"], fx and fx["key"], mu and mu["key"])
    report_file = job.dir / "build" / "mix.json"
    old = _read(report_file)
    if old and old.get("key") == key and not force and all(Path(v["path"]).exists() for v in old["variants"].values()):
        log("mix: up to date")
        return old
    gain = m["gain_db"] if m["gain_db"] != "auto" else m["voice_lufs"] - sound.lufs(voice["path"])
    report = {"key": key, "gain_db": round(gain, 2), "variants": {}}
    b = job.dir / "build"
    for name, v in job.data["variants"].items():
        pre = b / f"mix_{name}.wav"
        sound.run(sound.premix_cmd(voice["path"], stems[0], stems[1], pre, length + m["tail"], gain,
                                   v.get("mute_voice_after")))
        graph, total = sound.variant_graph(v.get("ranges", [[0.0, length]]), v.get("freeze", 0.0), m["joint_fade"])
        raw = b / f"audio_{name}_pre.wav"
        sound.run(["ffmpeg", "-y", "-v", "error", "-i", pre, "-filter_complex", graph, "-map", "[a]",
                   "-ar", "48000", "-c:a", "pcm_s24le", raw])
        out = b / f"audio_{name}.wav"
        sound.loudnorm(raw, out)
        meas = sound.measure(out)
        report["variants"][name] = {"path": str(out), "seconds": round(total, 3), **meas}
        log(f"mix: {name} {total:.2f} s, {meas['lufs']:.1f} LUFS, true peak {meas['true_peak']:.1f} dBTP -> {out}")
    _write(report_file, report)
    return report


# ---------------------------------------------------------------- picture

LOCK_FILE = Path(tempfile.gettempdir()) / "aie-render.lock"
GSAP_CDN = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
_lock = {"depth": 0, "file": None}


def _flock(f, on: bool):
    if os.name == "nt":
        import msvcrt
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK if on else msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(f, (fcntl.LOCK_EX | fcntl.LOCK_NB) if on else fcntl.LOCK_UN)


@contextlib.contextmanager
def render_lock():
    """One render at a time on this machine (CLAUDE.md render safety). Re-entrant within one run; the OS drops the lock
    when the process ends, so a crash never leaves it stuck."""
    if not _lock["depth"]:
        f = open(LOCK_FILE, "a+")
        try:
            _flock(f, True)
        except OSError:
            f.close()
            raise StageError("another render is running on this machine (one render at a time); "
                             "wait for it to finish") from None
        _lock["file"] = f
    _lock["depth"] += 1
    try:
        yield
    finally:
        _lock["depth"] -= 1
        if not _lock["depth"]:
            _flock(_lock["file"], False)
            _lock["file"].close()
            _lock["file"] = None


def _render(job: Job, settings: Settings, cmd: list):
    """An ffmpeg render: refused when the disk is nearly full, so a long render can't die near the end."""
    from .ffmpeg import FFmpegError, run as ff
    free = shutil.disk_usage(job.dir).free / 1e9
    if free < settings.data["min_free_gb"]:
        raise StageError(f"only {free:.1f} GB free on the job's disk; renders need {settings.data['min_free_gb']} GB "
                         "(free some space, or lower min_free_gb in aie.local.json)")
    try:
        return ff(cmd)
    except FFmpegError as e:
        raise StageError(str(e)) from None


def _quality(job: Job):
    """(final?, x264 settings): preview quality until Paras approves the final."""
    from . import picture
    final = job.data.get("gates", {}).get("final_approved", False)
    return final, (picture.FINAL if final else picture.PREVIEW)


def _tree(folder: Path, skip=()) -> list:
    """Every file of a composition folder (path, size, time), so editing any of them re-renders it."""
    out = []
    for f in sorted(folder.rglob("*")):
        rel = f.relative_to(folder).as_posix()
        if f.is_file() and not rel.startswith(("node_modules/", ".hyperframes/", "renders/", "build/")) and rel not in skip \
                and f.suffix != ".log":
            out.append([rel, *_stamp(f)])
    return out


def _hyperframes(settings: Settings, folder: Path, fps: int, out: Path):
    npx = shutil.which("npx")
    if not npx:
        raise StageError("graphics need Node.js (npx on PATH) to render HyperFrames compositions")
    env = dict(os.environ)
    if settings.data.get("chrome"):
        env["PRODUCER_HEADLESS_SHELL_PATH"] = str(settings.path("chrome"))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.webm")
    r = subprocess.run([npx, "--yes", settings.data["hyperframes"], "render", ".", "--format", "webm", "--fps", str(fps),
                        "--workers", "1", "--quality", "looks", "-o", str(tmp.resolve())],
                       cwd=folder, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode or not tmp.exists():
        tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-8:])
        raise StageError(f"HyperFrames render of {folder} failed:\n{tail}")
    tmp.replace(out)


def _check_overlay(job: Job, path: Path, what: str):
    from . import ffmpeg
    info = ffmpeg.video_info(path)
    if info["size"] != list(job.data["size"]):
        raise StageError(f"{what}: {path.name} is {info['size'][0]}x{info['size'][1]}, the job is "
                         f"{job.data['size'][0]}x{job.data['size'][1]} (the composition's data-width/height must match)")


def stage_graphics(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    g = job.data.get("graphics")
    if not g:
        raise StageError('this job has no "graphics"')
    if "render" in g:
        p = job.dir / g["render"]
        if not p.exists():
            raise StageError(f"graphics: {g['render']} not found in {job.dir} (render the composition, or drop "
                             "\"render\" so this stage renders it)")
        log(f"graphics: up to date ({g['render']}, rendered outside the pipeline)")
        return {"key": _key("graphics", g, _stamp(p)), "path": p}
    folder = (job.dir / g["composition"]).parent
    out, stamp = job.dir / "build" / "graphics.webm", job.dir / "build" / "graphics.key"
    key = _key("graphics", g, job.data["fps"], settings.data["hyperframes"], _tree(folder, ("render.webm",)))
    if out.exists() and stamp.exists() and stamp.read_text() == key and not force:
        log("graphics: up to date")
        return {"key": key, "path": out}
    with render_lock():
        log(f"graphics: rendering {g['composition']} with HyperFrames (takes minutes) ...")
        _hyperframes(settings, folder, job.data["fps"], out)
    _check_overlay(job, out, "graphics")
    stamp.write_text(key)
    log(f"graphics: -> {out}")
    return {"key": key, "path": out}


def stage_effects(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    """Every catalog effect placed in job.json, rendered on its own (cached by its filled HTML)."""
    from .effects import Catalog
    places = job.data.get("effects", [])
    if not places:
        raise StageError('this job places no "effects"')
    cat = Catalog.load(settings.path("effects"))
    base, root = settings.path("hyperframes_base"), job.dir / "build" / "effects"
    items, keys, made = [], [], 0
    for i, p in enumerate(places):
        fx = cat.get(p["effect"])
        if fx.data["kind"] != "overlay" or fx.data["engine"] != "hyperframes-template":
            raise StageError(f"effects[{i}]: {fx.name} is a {fx.data['kind']} / {fx.data['engine']} effect; the "
                             "pipeline renders hyperframes-template overlays so far")
        dur = p.get("dur", fx.data.get("duration", {}).get("default"))
        try:
            html = fx.html(p.get("params", {}), dur, settings.path("templates"))
        except (ValueError, KeyError) as e:
            raise StageError(f"effects[{i}]: {e}") from None
        d = root / f"{i:02d}_{p.get('id', fx.name)}"
        d.mkdir(parents=True, exist_ok=True)
        for f in ("package.json", "hyperframes.json", "meta.json"):
            if not (d / f).exists():
                shutil.copy(base / f, d / f)
        if settings.data.get("gsap"):                   # offline: GSAP from a local copy instead of the CDN
            shutil.copy(settings.path("gsap"), d / "gsap.min.js")
            html = html.replace(GSAP_CDN, "gsap.min.js")
        (d / "index.html").write_text(html, encoding="utf-8")
        copies = {}         # shared files (reel.css) and file parameters (logos, from the job folder)
        for name, src in fx.files(p.get("params", {}), settings.path("templates")).items():
            path = src if isinstance(src, Path) else settings.resolve(src, job.dir)
            if not path.exists():
                raise StageError(f"effects[{i}]: {fx.name} needs {path}, which isn't there")
            copies[name] = path
            shutil.copy(path, d / name)
        k = _key("effect", html, job.data["fps"], settings.data["hyperframes"],
                 [[n, hashlib.sha1(f.read_bytes()).hexdigest()] for n, f in sorted(copies.items())])
        out, stamp = d / "render.webm", d / ".rendered"
        if not (out.exists() and stamp.exists() and stamp.read_text() == k and not force):
            log(f"effects: rendering {d.name} ({fx.name}, {dur} s) ...")
            with render_lock():
                _hyperframes(settings, d, job.data["fps"], out)
            _check_overlay(job, out, f"effects[{i}]")
            stamp.write_text(k)
            made += 1
        items.append({"path": str(out), "at": p["at"], "variants": p.get("variants")})
        keys.append(k)
    log(f"effects: {made} rendered, {len(items)} in all" if made else f"effects: up to date ({len(items)})")
    return {"key": _key("effects", keys, places), "items": items}


def _scripts(job: Job) -> list:
    out = []
    for s in job.data.get("custom", []):
        p = job.dir / s
        if not p.exists():
            raise StageError(f"custom script {s} not found in {job.dir}")
        out.append([s, hashlib.sha1(p.read_bytes()).hexdigest()[:12]])
    return out


def stage_base(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    from . import picture
    d, b = job.data, job.dir / "build"
    fps, size, lay = d["fps"], d["size"], d.get("layouts", {})
    out, stamp = b / "base.mp4", b / "base.key"
    built = _built_cut(job, settings, log)
    if "timeline" in d:
        names = sorted({s["src"] for s in d["timeline"]})
        what = d["timeline"]
    else:
        if "camera" not in lay:
            raise StageError('a cut job needs "layouts": {"camera": {"head": [x, y]}} to frame its pieces '
                             "(the long-form's picture is still built by tools/longform_compose.py)")
        names = sorted({p["src"] for p in built["pieces"]})
        what = built["key"]
    files = {n: _source(job, settings, n) for n in names}
    key = _key("base", what, lay, fps, size, [[n, _stamp(f)] for n, f in files.items()], _scripts(job))
    if out.exists() and stamp.exists() and stamp.read_text() == key and not force:
        log("base: up to date")
        return {"key": key, "path": out}
    custom = d.get("custom", [])
    first = b / "base_footage.mp4" if custom else out
    with render_lock():
        if "timeline" in d:
            mask = border = None
            if any(s["layout"] == "split" for s in d["timeline"]):
                mask, border = picture.card_assets(lay["split"], size, b)
            log(f"base: {len(d['timeline'])} segments ...")
            _render(job, settings, picture.timeline_base_cmd(d["timeline"], [files[s["src"]] for s in d["timeline"]], lay,
                                                             fps, size, job.length, mask, border, first))
        else:
            cam = lay["camera"]
            segs = b / "segs"
            seg_key = _key(fps, size, cam, [[n, _stamp(f)] for n, f in files.items()])
            if (segs / ".key").exists() and (segs / ".key").read_text() != seg_key:
                shutil.rmtree(segs)
            segs.mkdir(parents=True, exist_ok=True)
            (segs / ".key").write_text(seg_key)
            cmds = picture.face_piece_cmds(built["pieces"], files, cam["head"], fps, size, segs, cam.get("crop"))
            for f in segs.glob("*.mkv"):
                if f not in {o for _, o in cmds}:
                    f.unlink()
            for i, (cmd, f) in enumerate(cmds):
                if not f.exists() or force:       # a piece's file name holds its source, in point and zoom
                    log(f"base: piece {i + 1}/{len(cmds)} ...")
                    _render(job, settings, cmd)
            _render(job, settings, picture.concat_cmd([f for _, f in cmds], b / "segs.txt", first))
        src = first
        for i, s in enumerate(custom):
            dst = out if i == len(custom) - 1 else b / f"base_custom{i + 1}.mp4"
            log(f"base: custom {s} ...")
            env = {**os.environ, "AIE_JOB": str(job.dir.resolve()), "AIE_IN": str(src.resolve()),
                   "AIE_OUT": str(dst.resolve()), "AIE_FPS": str(fps), "AIE_SIZE": f"{size[0]}x{size[1]}"}
            script = (job.dir / s).resolve()
            dst.unlink(missing_ok=True)
            r = subprocess.run([sys.executable, str(script)], cwd=script.parent, env=env, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            if r.returncode or not dst.exists():
                tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-10:])
                raise StageError(f"custom {s} failed (it must read AIE_IN and write AIE_OUT):\n{tail}")
            src = dst
    stamp.write_text(key)
    log(f"base: -> {out}")
    return {"key": key, "path": out}


def _overlays(job: Job, settings: Settings, log) -> tuple:
    """(graphics, captions, effects) for the picture, each brought up to date."""
    gfx = stage_graphics(job, settings, False, _dep(log)) if job.data.get("graphics") else None
    cap = job.data.get("captions") or {}
    ass = stage_captions(job, settings, False, _dep(log)) if "words" in cap and cap.get("burn", True) else None
    fx = stage_effects(job, settings, False, _dep(log)) if job.data.get("effects") else None
    return gfx, ass, fx


def stage_storyboard(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    """build/storyboard.html + storyboard.json: every beat with its words, layout, a framed still and the planned boxes."""
    from . import storyboard as sb
    from .effects import Catalog
    d, b = job.data, job.dir / "build"
    built = _built_cut(job, settings, lambda *_: None)
    words = stage_captions(job, settings, False, _dep(log))["words"] if "words" in (d.get("captions") or {}) else []
    cat = Catalog.load(settings.path("effects"))
    folder = b / "storyboard"
    folder.mkdir(parents=True, exist_ok=True)
    rows, lay = [], d.get("layouts", {})
    for n, beat in enumerate(sb.beats(d, built and built["pieces"]), 1):
        t0, t1 = beat["t"]
        src = _source(job, settings, beat["src"])
        mid = beat["in"] + (t1 - t0) / 2 * beat["speed"]
        still = sb.frame_for(beat["layout"], lay, sb.grab(src, mid), d["size"], beat["zoom"])
        items = sb.boxes(d, beat, cat)
        name = f"beat_{n:02d}.jpg"
        sb.draw(still, items, d["size"], 360 if d["size"][1] > d["size"][0] else 640, settings.path("fonts")).save(
            folder / name, quality=86)
        rows.append({"n": n, "t": [t0, t1], "layout": beat["layout"], "src": beat["src"], "in": beat["in"],
                     "words": " ".join(w["text"] for w in words if t0 <= w["start"] < t1),
                     "on_screen": [label for label, _, _ in items],
                     "sfx": [c for c in (d.get("sfx") or {}).get("cues", []) if "t" in c and t0 <= c["t"] < t1],
                     "note": beat["note"], "still": f"storyboard/{name}"})
    sb.write(b / "storyboard.json", rows)
    (b / "storyboard.html").write_text(sb.page(d, rows), encoding="utf-8")
    state = "approved" if d.get("gates", {}).get("storyboard_approved") else "waiting for approval"
    log(f"storyboard: {len(rows)} beats -> {b / 'storyboard.html'} ({state})")
    return {"beats": rows}


def _storyboard_gate(job: Job):
    if not job.data.get("gates", {}).get("storyboard_approved", False):
        raise StageError("the storyboard isn't approved yet: review build/storyboard.html (python -m aie run "
                         f"{job.dir.name} storyboard), then set gates.storyboard_approved to true in job.json")


def stage_picture(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    """The master picture: build/picture.mp4, plus build/picture_<variant>.mp4 for a variant whose effects differ."""
    from . import picture
    _storyboard_gate(job)
    base = stage_base(job, settings, False, _dep(log))
    gfx, ass, fx = _overlays(job, settings, log)
    built = _built_cut(job, settings, lambda *_: None)
    final, q = _quality(job)
    g = job.data.get("graphics", {})
    fonts = settings.path("fonts")
    key = _key("picture", base["key"], gfx and gfx["key"], ass and ass["key"], fx and fx["key"], g.get("offset"),
               g.get("pad"), q, str(fonts), _length(job, built))
    b = job.dir / "build"
    sets = {}                       # the effects each variant shows -> the variants sharing that master
    for name in job.data["variants"]:
        mine = tuple(i for i, e in enumerate(fx["items"] if fx else []) if not e["variants"] or name in e["variants"])
        sets.setdefault(mine, []).append(name)
    masters = {mine: b / ("picture.mp4" if i == 0 else f"picture_{names[0]}.mp4")    # the first variant's is the
               for i, (mine, names) in enumerate(sets.items())}                       # cover's picture.mp4
    report_file = b / "picture.json"
    old = _read(report_file)
    if old and old.get("key") == key and not force and all(Path(p).exists() for p in old["variants"].values()):
        log("picture: up to date")
        return old
    report = {"key": key, "final": final, "variants": {}}
    with render_lock():
        for mine, names in sets.items():
            out = masters[mine]
            log(f"picture: {'final' if final else 'preview'} quality, {len(mine)} effect(s)"
                + (f" for {', '.join(names)}" if len(sets) > 1 else "") + " ...")
            _render(job, settings, picture.master_cmd(
                base["path"], job.data["fps"], _length(job, built), out, gfx and gfx["path"], g.get("offset", 0.0),
                g.get("pad", 0.0), ass and b / "captions.ass", fonts, q, [fx["items"][i] for i in mine]))
            for n in names:
                report["variants"][n] = str(out)
            log(f"picture: -> {out}")
    _write(report_file, report)
    return report


def stage_deliver(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    from . import ffmpeg, picture, sound
    pic = stage_picture(job, settings, False, _dep(log))
    mix = stage_mix(job, settings, False, _dep(log))
    if "words" in (job.data.get("captions") or {}) or job.data.get("package", {}).get("cover"):
        stage_package(job, settings, False, _dep(log))
    built = _built_cut(job, settings, lambda *_: None)
    final, q = _quality(job)
    pkg = job.data.get("package", {})
    prefix = pkg.get("prefix", job.id.upper().replace("-", ""))
    b, pub = job.dir / "build", job.dir / "build" / "publish"
    pub.mkdir(parents=True, exist_ok=True)
    key = _key("deliver", pic["key"], mix["key"], job.data["variants"], q, prefix)
    old = _read(b / "deliver.json")
    if old and old.get("key") == key and not force and all(Path(v["path"]).exists() for v in old["variants"].values()):
        log("deliver: up to date")
        return old
    report = {"key": key, "final": final, "variants": {}}
    fps, length = job.data["fps"], _length(job, built)
    with render_lock():
        for name, v in job.data["variants"].items():
            ranges, freeze = v.get("ranges", [[0.0, length]]), v.get("freeze", 0.0)
            total = sum(e - s for s, e in ranges) + freeze
            vout = b / f"video_{name}.mp4"
            _render(job, settings, picture.variant_video_cmd(pic["variants"][name], ranges, freeze, fps, vout, q))
            out = pub / f"{prefix}_{name}{'' if final else '_PREVIEW'}.mp4"
            _render(job, settings, picture.mux_cmd(vout, mix["variants"][name]["path"], total, out))
            meas, dur = sound.measure(out), ffmpeg.duration(out)
            if abs(dur - total) > 1.5 / fps:
                raise StageError(f"deliver: {out.name} runs {dur:.3f} s, expected {total:.3f} s")
            report["variants"][name] = {"path": str(out), "seconds": round(dur, 3), **meas}
            log(f"deliver: {out.name} {dur:.2f} s, {meas['lufs']:.1f} LUFS, true peak {meas['true_peak']:.1f} dBTP")
    if not final:
        log("deliver: PREVIEW quality. Set gates.final_approved to true in job.json after Paras approves, then rerun.")
    _write(b / "deliver.json", report)
    return report


def stage_qa(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    """The 9.5 audit of the delivered files (see aie/qa.py) -> build/qa/qa.json and contact sheets."""
    from . import qa
    from .effects import Catalog
    dl = stage_deliver(job, settings, False, _dep(log))
    d, b = job.data, job.dir / "build"
    built = _built_cut(job, settings, lambda *_: None)
    pieces = built["pieces"] if built else None
    length, fps, size = _length(job, built), d["fps"], d["size"]
    out = b / "qa"
    out.mkdir(parents=True, exist_ok=True)
    cap = d.get("captions") or {}
    words = (_read(b / "words.json") or {}).get("words", []) if "words" in cap else []
    voice = qa._pcm(b / "voice.wav")
    C = {}

    exp = {n: sum(e - s for s, e in v.get("ranges", [[0.0, length]])) + v.get("freeze", 0.0) for n, v in d["variants"].items()}
    bad = [f"{n} {v['seconds']:.2f} s (expected {exp[n]:.2f})" for n, v in dl["variants"].items()
           if abs(v["seconds"] - exp[n]) > 1.5 / fps]
    C["length"] = qa.check("FAIL" if bad else "OK", "length", "; ".join(bad) or
                           ", ".join(f"{n} {v['seconds']:.2f} s" for n, v in dl["variants"].items()))
    bad = [f"{n} {v['lufs']:.1f} LUFS / {v['true_peak']:.1f} dBTP" for n, v in dl["variants"].items()
           if abs(v["lufs"] + 14) > 0.5 or v["true_peak"] > -1.5]
    C["loudness"] = qa.check("FAIL" if bad else "OK", "loudness", "; ".join(bad) or
                             ", ".join(f"{n} {v['lufs']:.1f} LUFS, {v['true_peak']:.1f} dBTP" for n, v in dl["variants"].items()))

    finals, rows, heard, sheets = {}, {}, {}, []
    for n, v in d["variants"].items():
        ranges = v.get("ranges", [[0.0, length]])
        finals[n] = qa._pcm(dl["variants"][n]["path"])
        items = qa.stretches(d, pieces, ranges, length)
        rows[n] = qa.sync(finals[n], voice, items)
        heard[n] = qa.heard(finals[n], voice, items, settings.data["whisper_model"], d.get("language", "hi"))
        video = Path(dl["variants"][n]["path"])
        at = qa.cuts(d, pieces, ranges)
        sheets.append(qa.joints_sheet(video, at, size, out / f"{n}_joints.jpg"))
        f = qa.out_map(ranges)
        marks = sorted({round(o, 2) for o in [f(e["at"] + 0.4) for e in d.get("effects", [])] +
                        [f((s["t"][0] + s["t"][1]) / 2) for s in d.get("timeline", [])] if o is not None})
        sheets.append(qa.zones_sheet(video, marks or [exp[n] * k / 8 for k in range(8)], size, out / f"{n}_sheet.jpg"))
    lags = [abs(r["lag_ms"]) for rs in rows.values() for r in rs]
    worst = max(lags) if lags else None
    C["sync"] = qa.check("FAIL" if worst is not None and worst > 10 else ("OK" if lags else "WARN"), "sync",
                         f"max |lag| {worst} ms over {len(lags)} stretches" if lags else "no voiced stretch to line up",
                         rows=rows)

    if pieces:
        hs = qa.holes(voice, [p["out0"] for p in pieces[1:]])
        C["joints"] = qa.check("FAIL" if hs else "OK", "joints", f"{len(hs)} hole(s) in the room tone at a cut" if hs
                               else f"{len(pieces) - 1} audio joints, no hole", holes=hs)
    if any(h is None for h in heard.values()):
        C["words"] = qa.check("NOT RUN", "words", "needs faster-whisper (run QA on the PC)")
    else:
        lost = [(n, r) for n, rs in heard.items() for r in rs if r["lost"]]
        C["words"] = qa.check("FAIL" if lost else "OK", "words", f"{len(lost)} stretch(es) lose words in the mix" if lost
                              else "every word the voice says is heard in the final mix", heard=heard)

    canon = list((cap.get("text") or {}).get("replace", {}).values()) + d.get("qa", {}).get("words", [])
    sp = qa.spelling(words, canon)
    C["spelling"] = qa.check("FAIL" if sp else "OK", "spelling", "; ".join(
        f"'{f['found']}' at {f['at']:.2f} s should be {f['want']}" for f in sp[:4]) + (f" (+{len(sp) - 4} more)" if len(sp) > 4 else "")
        if sp else
                             f"{len(words)} caption words against {len(set(canon))} name{'' if len(set(canon)) == 1 else 's'} on the "
                             "word list", findings=sp)

    zone = []
    if size[1] > size[0]:
        if cap.get("burn", True):
            zone += [f"caption style {z['style']} box {z['box']}" for z in qa.caption_zone(cap, size)]
        cat = Catalog.load(settings.path("effects"))
        for i, p in enumerate(d.get("effects", [])):
            fx = cat.get(p["effect"])
            webm = next(iter(sorted((b / "effects").glob(f"{i:02d}_*/render.webm"))), None)
            if fx and webm and fx.data.get("zone"):
                dur = p.get("dur", fx.data.get("duration", {}).get("default", 1.0))
                zone += [f"effects[{i}] {fx.name}: {m}" for m in
                         qa.effect_zone(fx.data["zone"], qa.alpha_box(webm, [dur * k for k in (0.2, 0.5, 0.85)], size))]
    C["safe_zone"] = qa.check("FAIL" if zone else "OK", "safe_zone", "; ".join(zone) or
                              "captions and effects inside x 90-930, y 200-1560" if size[1] > size[0] else "16:9: n/a")

    ow = qa.on_word(d.get("effects", []), words)
    off = [r for r in ow if r["off"] is None or not -0.15 <= r["off"] <= 0.2]
    C["on_word"] = qa.check("FAIL" if off else "OK", "on_word",
                            "; ".join(f"effects[{r['effect']}] '{r['word']}' " + ("not heard within 2 s" if r["off"] is None
                                      else f"{r['off']:+.2f} s off") for r in off) or (f"{len(ow)} effect{'' if len(ow) == 1 else 's'} on {'its' if len(ow) == 1 else 'their'} word" if ow
                                      else "no effect is tied to a word"),
                            rows=ow)

    if d["mode"] == "client":
        bad = [n for n, s in d["sources"].items() if s.get("rights") not in ("client", "generated", "licensed")]
        C["rights"] = qa.check("FAIL" if bad else "OK", "rights", f"rights not client/generated/licensed: {', '.join(bad)}"
                               if bad else "every source is the client's, generated or licensed")

    texts = [("title", d.get("title", "")), ("captions", " ".join(w["text"] for w in words))]
    if d.get("script") and (job.dir / d["script"]).exists():
        texts.append(("script", (job.dir / d["script"]).read_text(encoding="utf-8")))
    for i, p in enumerate(d.get("effects", [])):
        texts += [(f"effects[{i}].{k}", json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v)
                  for k, v in p.get("params", {}).items()]
    hits = qa.claims(texts, d.get("qa", {}).get("cleared", []))
    C["compliance"] = qa.check("FAIL" if hits else "OK", "compliance",
                               "; ".join(f"{h['where']}: \"{h['phrase']}\"" for h in hits) + " (blocked: Paras reviews; "
                               "a phrase he clears goes in qa.cleared)" if hits else "no income, return or guarantee claims",
                               hits=hits)

    first = [e["at"] for e in d.get("effects", [])] + ([0.0] if d.get("graphics") else []) + \
            ([w["start"] for w in words[:1]] if cap.get("burn", True) and words else [])
    C["hook"] = qa.check("OK" if first and min(first) <= 1.0 else "WARN", "hook",
                         f"first text or graphic at {min(first):.2f} s" if first else "nothing on screen in the first second")
    still = {n: qa.still_spans(Path(v["path"]), size) for n, v in dl["variants"].items()}
    ends = {n: exp[n] - d["variants"][n].get("freeze", 0.0) for n in d["variants"]}      # the end freeze is meant
    long_ = [f"{n} {a:.1f}-{min(b_, ends[n]):.1f} s" for n, spans in still.items() for a, b_ in spans
             if min(b_, ends[n]) - a >= 3.0]
    C["static"] = qa.check("WARN" if long_ else "OK", "static", ("picture held still: " + "; ".join(long_)) if long_
                           else "no picture held still for over 3 s")

    if "timeline" in d:
        an = qa.anchors(d["timeline"], words) if words else []
        C["anchors"] = qa.check("WARN" if an else "OK", "anchors", "; ".join(
            f"cut {a['cut']:.2f} s: next word '{a['next_word']}' {a['off']:+.2f} s" for a in an) or
            ("every cut on a spoken word" if words else "no words to check against"))
        ru = qa.reused(d["timeline"])
        C["footage"] = qa.check("WARN" if ru else "OK", "footage", "; ".join(
            f"{r['src']} {r['window'][0]}-{r['window'][1]} s shown at {r['at'][0]:.2f} and {r['at'][1]:.2f} s" for r in ru)
            or "no B-roll window shown twice")

    sc, ok = qa.score(C)
    rep = {"score": sc, "passed": ok, "final": dl["final"], "checks": C, "sheets": [str(x) for x in sheets]}
    qa.write(out / "qa.json", rep)
    for line in qa.report_lines(rep):
        log(line)
    log(f"qa: -> {out / 'qa.json'} (look at the contact sheets too: {', '.join(x.name for x in sheets)})")
    return rep


def stage_otio(job: Job, settings: Settings, force: bool = False, log=print) -> dict:
    """build/nle/<id>.otio (Resolve) and <id>.xml (Premiere): the edit for finishing in an NLE (aie/nle.py)."""
    from . import nle, storyboard as sb
    d, b = job.data, job.dir / "build"
    built = _built_cut(job, settings, lambda *_: None)
    base = stage_base(job, settings, False, _dep(log))
    gfx = stage_graphics(job, settings, False, _dep(log)) if d.get("graphics") else None
    fx = stage_effects(job, settings, False, _dep(log)) if d.get("effects") else None
    voice = stage_voice(job, settings, False, _dep(log))
    sfx = stage_sfx(job, settings, False, _dep(log)) if (d.get("sfx") or {}).get("cues") else None
    mus = stage_music(job, settings, False, _dep(log)) if d.get("music") else None
    pkg = stage_package(job, settings, False, _dep(log)) if "words" in (d.get("captions") or {}) else None
    beats = sb.beats(d, built and built["pieces"])
    length = _length(job, built)
    key = _key("otio", base["key"], gfx and gfx["key"], fx and fx["key"], voice["key"], sfx and sfx["key"],
               mus and mus["key"], pkg and [[f, os.path.getmtime(f)] for f in pkg["files"]], beats, d["variants"], length)
    out, report_file = b / "nle", b / "nle" / "nle.json"
    old = _read(report_file)
    if old and old.get("key") == key and not force and Path(old["otio"]).exists():
        log("otio: up to date")
        return old
    tl = nle.timeline(job.id, d["fps"], length, Path(base["path"]), beats,
                      {n: _source(job, settings, n) for n in {bt["src"] for bt in beats}},
                      gfx and (Path(gfx["path"]), d["graphics"].get("offset", 0.0)),
                      [(Path(e["path"]), e["at"], Path(e["path"]).parent.name) for e in fx["items"]] if fx else [],
                      {"voice": Path(voice["path"]), "sfx": sfx and Path(sfx["path"]), "music": mus and Path(mus["path"])},
                      d["variants"])
    report = {"key": key, **nle.write(tl, out, job.id), "srt": []}
    for f in sorted((b / "publish").glob("*.srt")):
        shutil.copy2(f, out / f.name)
        report["srt"].append(str(out / f.name))
    report["tracks"] = [t.name for t in tl.tracks]
    _write(report_file, report)
    log(f"otio: {len(report['tracks'])} tracks -> {report['otio']}" + (f" and {Path(report['xml']).name}" if report["xml"]
                                                                       else f" (no FCP XML: {report['xml_error']})"))
    return report


STAGES = {"transcribe": stage_transcribe, "cut": stage_cut, "verify": stage_verify, "captions": stage_captions, "storyboard": stage_storyboard,
          "package": stage_package,
          "voice": stage_voice, "sfx": stage_sfx, "music": stage_music, "mix": stage_mix,
          "graphics": stage_graphics, "effects": stage_effects, "base": stage_base, "picture": stage_picture,
          "otio": stage_otio,
          "deliver": stage_deliver, "qa": stage_qa, "all": stage_qa}


def run(job: Job, settings: Settings, stage: str, force: bool = False, log=print):
    if stage not in STAGES:
        raise StageError(f"unknown stage {stage!r}; available: {', '.join(STAGES)}")
    return STAGES[stage](job, settings, force, log)
