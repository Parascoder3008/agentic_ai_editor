"""Run one stage of a job: python -m aie run <job> <stage> [--force].

Outputs go to <job>/build/ (git-ignored). Each output records a key made from the stage's inputs, so a stage whose
inputs haven't changed is skipped; --force runs it anyway.

  cut      -> build/pieces.json   frame-exact pieces in output order
  verify   -> build/piece_tx.json, build/joints.txt   every kept piece transcribed alone, every joint reviewed
  captions -> build/words.json, build/captions.ass    words on the output timeline, styled word-by-word captions
  package  -> build/publish/<PREFIX>_<variant>.srt, cover.jpg

A stage brings the stages it reads up to date first (captions runs the cut if it changed).
"""
import hashlib
import json
import math
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
    words = stage_captions(job, settings, False, _dep(log))["words"]
    built = _built_cut(job, settings, lambda *_: None)
    pkg = job.data.get("package", {})
    prefix = pkg.get("prefix", job.id.upper().replace("-", ""))
    pub = job.dir / "build" / "publish"
    pub.mkdir(parents=True, exist_ok=True)
    made, length = [], _length(job, built)
    chunk = (job.data.get("captions") or {}).get("chunk")
    for name, v in job.data["variants"].items():
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


STAGES = {"cut": stage_cut, "verify": stage_verify, "captions": stage_captions, "package": stage_package,
          "voice": stage_voice, "sfx": stage_sfx, "music": stage_music, "mix": stage_mix}


def run(job: Job, settings: Settings, stage: str, force: bool = False, log=print):
    if stage not in STAGES:
        raise StageError(f"unknown stage {stage!r}; available so far: {', '.join(STAGES)}")
    return STAGES[stage](job, settings, force, log)
