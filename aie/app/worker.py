"""The render queue: stage runs wait in order and one worker runs them, one at a time (renders on this PC only, and the
runner's render lock agrees). Each run's log is kept; a finished deliver or qa becomes a numbered version whose files
are kept under build/versions/v<n>/, so v1 and v2 can be compared in the review player.
"""
import json
import os
import queue
import shutil
import threading
import traceback
from pathlib import Path

from .. import runner
from ..effects import Catalog
from ..ffmpeg import FFmpegError
from ..job import JobError, load_job
from ..settings import REPO, SettingsError
from .db import DB, dumps, now


class Worker:
    def __init__(self, db: DB, settings, repo: Path = REPO, run=None):
        self.db, self.settings, self.repo = db, settings, repo
        self.run_stage = run or runner.run          # tests stand in a fake runner here
        self.q = queue.Queue()
        self.current = None
        for r in db.q("select id from runs where status in ('queued', 'running') order by id"):
            db.x("update runs set status='queued', started=null where id=?", (r["id"],))   # an app restart re-queues
            self.q.put(r["id"])
        self.thread = threading.Thread(target=self._loop, daemon=True, name="aie-worker")
        self.thread.start()

    def submit(self, project: int, stage: str, force: bool = False) -> int:
        if stage not in runner.STAGES:
            raise ValueError(f"unknown stage {stage!r}")
        rid = self.db.x("insert into runs (project, stage, force, status, queued) values (?, ?, ?, 'queued', ?)",
                        (project, stage, int(force), now()))
        self.q.put(rid)
        return rid

    def _log(self, rid: int, line: str):
        with self.db.lock:
            self.db.con.execute("update runs set log = log || ? where id=?", (line.rstrip() + "\n", rid))
            self.db.con.commit()

    def _loop(self):
        while True:
            rid = self.q.get()
            if rid is None:
                return
            self.current = rid
            try:
                self._run(rid)
            finally:
                self.current = None

    def _run(self, rid: int):
        r = self.db.one("select * from runs where id=?", (rid,))
        if not r or r["status"] != "queued":
            return
        p = self.db.one("select * from projects where id=?", (r["project"],))
        self.db.x("update runs set status='running', started=? where id=?", (now(), rid))
        status, result = "failed", None
        try:
            job = load_job(self.repo / p["path"], self.settings, Catalog.load(self.settings.path("effects")))
            result = self.run_stage(job, self.settings, r["stage"], bool(r["force"]), lambda s: self._log(rid, s))
            status = "done"
            if r["stage"] in ("deliver", "qa", "all"):
                self._version(p, rid)
        except (JobError, runner.StageError, SettingsError, FFmpegError, ValueError) as e:
            self._log(rid, f"FAIL {e}")
        except ImportError as e:
            self._log(rid, f"FAIL {r['stage']} needs the Python module {e.name!r} (python -m aie doctor)")
        except Exception:                                  # keep the worker alive; the log shows what broke
            self._log(rid, "FAIL unexpected error:\n" + traceback.format_exc()[-1500:])
        self.db.x("update runs set status=?, ended=?, result=? where id=?",
                  (status, now(), dumps(_small(result)), rid))

    def _version(self, p: dict, rid: int):
        d = self.repo / p["path"]
        dl = _read(d / "build/deliver.json")
        if not dl:
            return
        last = self.db.one("select * from versions where project=? order by n desc limit 1", (p["id"],))
        files = {n: v["path"] for n, v in dl["variants"].items()}
        qa = _read(d / "build/qa/qa.json")
        stamp = {n: os.path.getmtime(f) for n, f in files.items() if os.path.exists(f)}
        if last and json.loads(last["files"]).get("_stamp") == stamp:     # same files: refresh the QA score only
            if qa:
                self.db.x("update versions set qa_score=?, qa_passed=? where id=?", (qa["score"], int(qa["passed"]), last["id"]))
            return
        n = (last["n"] if last else 0) + 1
        keep = d / "build" / "versions" / f"v{n}"
        keep.mkdir(parents=True, exist_ok=True)
        kept = {}
        for name, f in files.items():
            dst = keep / Path(f).name
            try:
                os.link(f, dst)                     # no extra disk when the drive allows it
            except OSError:
                shutil.copy2(f, dst)
            kept[name] = str(dst)
        kept["_stamp"] = stamp
        self.db.x("insert into versions (project, n, created, final, files, qa_score, qa_passed, run) values (?,?,?,?,?,?,?,?)",
                  (p["id"], n, now(), int(dl.get("final", False)), dumps(kept), qa and qa["score"],
                   qa and int(qa["passed"]), rid))
        self.db.x("update notes set fixed_in=? where project=? and status='fixed' and fixed_in is null", (n, p["id"]))

    def stop(self):
        self.q.put(None)


def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _small(x):
    """A run result small enough to keep: drop word lists and stems."""
    if isinstance(x, dict):
        return {k: _small(v) for k, v in x.items() if k not in ("words", "pieces", "beats", "items")}
    if isinstance(x, (list, tuple)):
        return [_small(v) for v in x[:50]]
    return x if isinstance(x, (str, int, float, bool, type(None))) else str(x)
