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


def _built_cut(job: Job, settings: Settings, log) -> dict | None:
    """The cut, brought up to date first, or None for a job whose timeline is written by hand."""
    return stage_cut(job, settings, False, log) if "cut" in job.data else None


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
    words = stage_captions(job, settings, False, log)["words"]
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


STAGES = {"cut": stage_cut, "verify": stage_verify, "captions": stage_captions, "package": stage_package}


def run(job: Job, settings: Settings, stage: str, force: bool = False, log=print):
    if stage not in STAGES:
        raise StageError(f"unknown stage {stage!r}; available so far: {', '.join(STAGES)}")
    return STAGES[stage](job, settings, force, log)
