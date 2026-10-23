"""python -m aie <command>

  validate JOB...        check job.json files (a job folder or the file itself); --check-files also checks the
                         footage and other files they point at exist on this machine
  effects                list the effects catalog; --kind overlay|picture|transition|caption|sound, --format 9:16
  doctor                 check this machine: ffmpeg, Node, Python libraries, aie.local.json paths, fonts, catalog
"""
import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

from . import __version__
from .effects import KINDS, Catalog
from .job import JobError, aspect, load_job
from .settings import PATH_KEYS, REPO, SettingsError, load_settings

# Output stays ASCII: a Windows console on cp1252 can't print check marks.
OK, BAD, WARN = "OK  ", "FAIL", "WARN"


def cmd_validate(a) -> int:
    settings = load_settings()
    catalog = Catalog.load(settings.path("effects"))
    bad = 0
    for path in a.jobs:
        try:
            job = load_job(path, settings, catalog, a.check_files)
        except JobError as e:
            print(f"{BAD} {e}")
            bad += 1
            continue
        d = job.data
        n = len(d["timeline"]) if "timeline" in d else len(d["cut"].get("pieces", d["cut"].get("keep", [])))
        ln = f"{job.length:.2f} s" if job.length is not None else "length set by the cutter"
        print(f"{OK} {job.id}: {d['mode']}, {aspect(d['size'])} at {d['fps']} fps, {ln}, {n} segments/pieces, "
              f"variants: {', '.join(d['variants'])}")
    return 1 if bad else 0


def cmd_effects(a) -> int:
    settings = load_settings()
    cat = Catalog.load(settings.path("effects"))
    for e in cat.errors:
        print(f"{BAD} {e}")
    rows = [fx for fx in cat.effects.values()
            if (not a.kind or fx.data["kind"] == a.kind) and (not a.format or a.format in fx.formats)]
    for fx in rows:
        req = [k for k, p in fx.params.items() if p.get("required")]
        brand = "  [Paras only]" if fx.data.get("brand") == "own" else ""
        print(f"{fx.name:14} {fx.data['kind']:10} {','.join(fx.formats):8} {fx.data['title']}{brand}"
              + (f"  (needs: {', '.join(req)})" if req else ""))
    print(f"{len(rows)} effect(s)" + (f" of {len(cat.effects)}" if len(rows) != len(cat.effects) else ""))
    return 1 if cat.errors else 0


def cmd_doctor(a) -> int:
    fails = 0

    def line(status, what, detail=""):
        nonlocal fails
        fails += status == BAD
        print(f"{status} {what}" + (f"  {detail}" if detail else ""))

    line(OK if sys.version_info >= (3, 10) else BAD, f"Python {sys.version.split()[0]}", "(3.10+ needed)")
    for exe, need in (("ffmpeg", True), ("ffprobe", True), ("node", False), ("npx", False)):
        p = shutil.which(exe)
        line(OK if p else (BAD if need else WARN), exe, p or ("not on PATH" + ("" if need else "; needed for graphics")))
    for mod in ("numpy", "scipy", "soundfile", "PIL", "cv2", "faster_whisper", "torch", "torchaudio", "playwright"):
        line(OK if importlib.util.find_spec(mod) else WARN, f"python module {mod}",
             "" if importlib.util.find_spec(mod) else "not installed (needed by later stages)")
    try:
        s = load_settings()
    except SettingsError as e:
        line(BAD, "aie.local.json", str(e))
        return 1
    line(OK if s.source else WARN, "aie.local.json", str(s.source) if s.source else
         f"not found; using defaults (copy {REPO / 'aie.local.example.json'} to {REPO / 'aie.local.json'})")
    for k in PATH_KEYS:
        p = s.path(k)
        if p is not None:
            line(OK if p.exists() else WARN, f"path {k}", str(p) + ("" if p.exists() else " (missing)"))
    for name, root in s.data["roots"].items():
        line(OK if Path(root).exists() else WARN, f"root @{name}", root)
    fonts = s.path("fonts")
    inter = sorted(fonts.glob("Inter-*.ttf")) if fonts and fonts.exists() else []
    line(OK if inter else BAD, "Inter fonts", f"{len(inter)} file(s) in {fonts}")
    cat = Catalog.load(s.path("effects"))
    line(OK if not cat.errors else BAD, "effects catalog", f"{len(cat.effects)} effect(s), {len(cat.errors)} problem(s)")
    for e in cat.errors:
        print(f"     {e}")
    return 1 if fails else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aie", description=f"AI Editor pipeline {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="check job.json files")
    v.add_argument("jobs", nargs="+", help="job folder(s) or job.json file(s)")
    v.add_argument("--check-files", action="store_true", help="also check that footage and other files exist")
    e = sub.add_parser("effects", help="list the effects catalog")
    e.add_argument("--kind", choices=sorted(KINDS))
    e.add_argument("--format", choices=["16:9", "9:16", "1:1"])
    sub.add_parser("doctor", help="check this machine's setup")
    a = ap.parse_args(argv)
    return {"validate": cmd_validate, "effects": cmd_effects, "doctor": cmd_doctor}[a.cmd](a)
