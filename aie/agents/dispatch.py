"""The Producer and the QA Auditor, as code. Paras's review notes go to the lane that owns each one (aie/app/notes.py
routed them when he wrote them). Lanes whose parts of job.json don't overlap run side by side; the rest wait for the
next wave. Then the job is rendered again and audited, and each failed QA check goes back to its owner, at most twice.

A dispatch never approves a gate, publishes or spends past its budget (aie.local.json "agent_budget_usd"). A change
that reads as an income or return claim is blocked and becomes a note to Paras (Constitution sections 4 and 5).
"""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..app.db import now
from ..app.notes import timecode
from .roster import ROLES
from .run import Budget, client, run_agent
from .tools import Toolbox

QA_ROUNDS = 2
PARALLEL = 4
POLL = 2.0
make_client = client                  # tests stand a fake API in here


def recover(db):
    """Close what an app restart cut off: its dispatch stopped, its notes open again."""
    for d in db.q("select id from dispatches where status='running'"):
        db.x("update dispatches set status='stopped', ended=?, message='the app stopped while it ran' where id=?",
             (now(), d["id"]))
        db.x("update agent_runs set status='stopped', ended=? where dispatch=? and status='running'", (now(), d["id"]))
    db.x("update notes set status='open' where status='sent'")


def waves(roles) -> list:
    """The roles in waves whose owned parts of job.json don't overlap, so two lanes never edit one thing at once."""
    out = []
    for r in roles:
        keys = set(ROLES[r]["owns"])
        for w in out:
            if len(w) < PARALLEL and not keys & {k for x in w for k in ROLES[x]["owns"]}:
                w.append(r)
                break
        else:
            out.append([r])
    return out


def to_master(t: float, ranges: list | None) -> float:
    """A time on a variant's own clock -> the master timeline (variants are master ranges played back to back)."""
    if t is None or not ranges:
        return t
    o = 0.0
    for a, b in ranges:
        if t <= o + (b - a):
            return round(a + (t - o), 3)
        o += b - a
    return round(ranges[-1][1], 3)


def busy(db, pid: int):
    return db.one("select * from dispatches where project=? and status='running'", (pid,))


def notes(repo: Path, db, worker, p: dict, note_ids: list) -> dict:
    """Send these open notes to their owners; returns at once, the work runs on a thread."""
    rows = [n for n in (db.one("select * from notes where id=? and project=?", (i, p["id"])) for i in note_ids)
            if n and n["status"] == "open"]
    if not rows:
        return {"message": "no open notes to send"}
    to_paras = [n for n in rows if n["owner"] not in ROLES]
    rows = [n for n in rows if n["owner"] in ROLES]
    if not rows:
        return {"message": "these notes are for Paras, not the agents"}
    d = _start(repo, db, worker, p, "notes")
    if isinstance(d, dict):
        return d
    for n in rows:
        db.x("update notes set status='sent' where id=?", (n["id"],))
    lanes = sorted({n["owner"] for n in rows}, key=list(ROLES).index)
    threading.Thread(target=d.run_notes, args=(rows,), daemon=True, name=f"aie-dispatch-{d.id}").start()
    msg = f"sent {len(rows)} note(s) to {', '.join(lanes)}"
    return {"message": msg + (f"; {len(to_paras)} stay with Paras" if to_paras else ""), "dispatch": d.id}


def plan(repo: Path, db, worker, p: dict) -> dict:
    """The Story Editor drafts the edit (cut, effects, SFX, caption fixes) from the brief and the transcript, then the
    storyboard is built for Paras to approve."""
    d = _start(repo, db, worker, p, "plan")
    if isinstance(d, dict):
        return d
    threading.Thread(target=d.run_plan, daemon=True, name=f"aie-dispatch-{d.id}").start()
    return {"message": "the Story Editor is planning the edit; the storyboard follows", "dispatch": d.id}


def _start(repo, db, worker, p, kind):
    if busy(db, p["id"]):
        return {"message": "the agents are already working on this project", "busy": True}
    from ..app import connections
    try:
        api = make_client(connections.get("ANTHROPIC_API_KEY"))
    except RuntimeError as e:
        return {"message": str(e)}
    return Dispatch(repo, db, worker, p, kind, api)


class Dispatch:
    def __init__(self, repo: Path, db, worker, p: dict, kind: str, api):
        self.db, self.worker, self.p, self.api = db, worker, p, api
        self.dir = Path(repo) / p["path"]
        self.settings = worker.settings
        self.budget = Budget(self.settings.data.get("agent_budget_usd", 3.0))
        self.id = db.x("insert into dispatches (project, kind, status, budget, started) values (?, ?, 'running', ?, ?)",
                       (p["id"], kind, self.budget.limit, now()))
        self.flags = 0

    # ------------------------------------------------------------ flows
    def run_notes(self, rows: list):
        try:
            job = self._job()
            groups = {}
            for n in rows:
                groups.setdefault(n["owner"], []).append(n)
            tasks = {role: (self._notes_task(role, ns, job), [n["id"] for n in ns]) for role, ns in groups.items()}
            self._finish(*self._loop(tasks))
        except Exception as e:                               # the dispatch says what broke; the app keeps running
            self._finish("failed", f"{type(e).__name__}: {e}")
        finally:
            self.db.x("update notes set status='open' where id in (%s) and status='sent'" % ",".join("?" * len(rows)),
                      [n["id"] for n in rows])

    def run_plan(self):
        try:
            if not list((self.dir / "build").glob("words_*.json")):
                if not self._render("transcribe"):
                    return self._finish("failed", "transcribe didn't finish; see its run log")
            job = self._job()
            role = "Story Editor"
            out = self._lane(role, self._plan_task(job), [], 1)
            if out["status"] not in ("done", "turn cap"):
                return self._finish("stopped", f"{role}: {out['status']}. {out['text'][:300]}")
            ok = self._render("storyboard")
            self._finish("done", f"{role} planned the edit ({_n(out['changes'], 'change')}); "
                         + ("the storyboard is ready for your approval" if ok else "the storyboard didn't build: see its run"))
        except Exception as e:
            self._finish("failed", f"{type(e).__name__}: {e}")

    def _loop(self, tasks: dict) -> tuple:
        """Run the lanes; render; audit; send failed checks back to their owners. (status, message)"""
        said = []
        for rnd in range(1, QA_ROUNDS + 2):
            results = self._round(tasks, rnd)
            changed = sum(r["changes"] for r in results)
            stopped = [r for r in results if r["status"] in ("over budget", "refused", "error")]
            said.append(f"round {rnd}: " + ", ".join(f"{r['role']} {r['status']} ({_n(r['changes'], 'change')})"
                                                    for r in results))
            if stopped and any(r["status"] == "over budget" for r in stopped):
                return "paused", "; ".join(said) + f". The ${self.budget.limit:.2f} budget is spent: Paras decides " \
                                                   "whether to send the rest"
            if not changed:
                return "done", "; ".join(said) + ". Nothing changed, so nothing was rendered"
            gated = not self._job().get("gates", {}).get("storyboard_approved")
            stage = "storyboard" if gated else "all"
            if not self._render(stage):
                return "failed", "; ".join(said) + f". The {stage} run failed: see its log"
            if gated:
                return "done", "; ".join(said) + ". The storyboard is rebuilt; approve it to render the picture"
            qa = _read(self.dir / "build/qa/qa.json") or {}
            if qa.get("passed"):
                return "done", "; ".join(said) + f". Re-rendered; QA {qa['score']:.1f} PASS"
            fails = {n: c for n, c in qa.get("checks", {}).items() if c["status"] == "FAIL"}
            tasks = {}
            for name, c in fails.items():
                owner = c["owner"] if c["owner"] in ROLES else "Story Editor" if name == "length" else None
                if owner is None:
                    self._note_for_paras(f"QA {name} failed: {c['summary']}", f"qa {name}")
                    continue
                tasks.setdefault(owner, []).append((name, c))
            if not tasks or rnd > QA_ROUNDS:
                return "done", "; ".join(said) + f". QA {qa.get('score', 0):.1f} still fails " \
                                                 f"({', '.join(fails)}): over to Paras"
            tasks = {role: (self._qa_task(role, items, qa), []) for role, items in tasks.items()}
        return "done", "; ".join(said)

    def _round(self, tasks: dict, rnd: int) -> list:
        results = []
        for wave in waves([r for r in ROLES if r in tasks]):
            with ThreadPoolExecutor(max_workers=len(wave)) as ex:
                results += list(ex.map(lambda r: self._lane(r, tasks[r][0], tasks[r][1], rnd), wave))
        return results

    # ------------------------------------------------------------ one lane
    def _lane(self, role: str, task: str, note_ids: list, rnd: int) -> dict:
        rid = self.db.x("insert into agent_runs (project, dispatch, role, round, status, task, started) "
                        "values (?, ?, ?, ?, 'running', ?, ?)", (self.p["id"], self.id, role, rnd, task, now()))

        def mark(note_id, status, reply):
            if note_id not in note_ids:
                return f"note {note_id} isn't one of yours in this run"
            self.db.x("update notes set status=?, agent_reply=? where id=?", (status, reply, note_id))
            return f"note {note_id}: {status}"

        def log(line):
            with self.db.lock:
                self.db.con.execute("update agent_runs set log = log || ? where id=?", (line.rstrip() + "\n", rid))
                self.db.con.commit()

        box = Toolbox(role, self.dir, self.settings, notes=mark, on_flag=self._flag)
        try:
            out = run_agent(role, task, box, self.api, self.budget, log)
        except Exception as e:                               # a tool or the SDK broke: this lane stops, the rest go on
            out = {"role": role, "status": "error", "text": f"{type(e).__name__}: {e}", "cost": 0.0,
                   "changes": box.changes}
        for i in note_ids:                                   # a note the agent didn't close goes back to Paras, explained
            n = self.db.one("select status from notes where id=?", (i,))
            if n and n["status"] == "sent":
                self.db.x("update notes set status='open', agent_reply=? where id=?",
                          (f"{role} didn't close this ({out['status']}): {out['text'][:300]}".strip(), i))
        self.db.x("update agent_runs set status=?, reply=?, cost=?, changes=?, ended=? where id=?",
                  (out["status"], out["text"][:4000], out["cost"], out["changes"], now(), rid))
        self.db.x("update dispatches set spent=? where id=?", (round(self.budget.spent, 4), self.id))
        return out

    def _flag(self, role: str, hits: list, why: str):
        self.flags += 1
        what = "; ".join(f"{h['where']}: \"{h['phrase']}\"" for h in hits)
        self._note_for_paras(f"{role} tried to add {what} (for: {why}). Blocked as an income/return claim "
                             "(Constitution section 4). Clear the phrase in qa.cleared only if it is education.",
                             "compliance block")

    def _note_for_paras(self, text: str, reason: str):
        self.db.x("insert into notes (project, text, owner, reason, status, created) values (?, ?, 'Paras', ?, 'open', ?)",
                  (self.p["id"], text, reason, now()))

    # ------------------------------------------------------------ the render worker
    def _render(self, stage: str) -> bool:
        rid = self.worker.submit(self.p["id"], stage)
        while True:
            r = self.db.one("select status from runs where id=?", (rid,))
            if r["status"] in ("done", "failed"):
                return r["status"] == "done"
            time.sleep(POLL)

    def _finish(self, status: str, message: str):
        if self.flags:
            message = message.rstrip(".") + f". {_n(self.flags, 'compliance flag')} for Paras"
        self.db.x("update dispatches set status=?, message=?, spent=?, ended=? where id=?",
                  (status, message,
                   round(self.budget.spent, 4), now(), self.id))

    def _job(self) -> dict:
        return json.loads((self.dir / "job.json").read_text(encoding="utf-8"))

    # ------------------------------------------------------------ what each agent is asked
    def _head(self, job: dict) -> str:
        b = _read(self.dir / "brief.json") or {}
        return (f"Job {self.p['path']}: mode {job.get('mode', 'footage')}, {job.get('fps')} fps, size {job.get('size')}."
                + (f"\nBrief: {json.dumps(b, ensure_ascii=False)[:1500]}" if b else ""))

    def _notes_task(self, role: str, ns: list, job: dict) -> str:
        variants = job.get("variants", {})
        lines = []
        for n in ns:
            ranges = (variants.get(n["variant"]) or {}).get("ranges") if n["variant"] else None
            m = to_master(n["t"], ranges)
            where = []
            if n["t"] is not None:
                where.append(f"at {timecode(n['t'])} of the {n['variant'] or 'master'} cut"
                             + (f" (master {m:.2f} s)" if ranges and m != n["t"] else f" ({n['t']:.2f} s)"))
            if n["beat"] is not None:
                where.append(f"storyboard beat {n['beat']}")
            lines.append(f"- note {n['id']}" + (f" {', '.join(where)}" if where else "") + f": \"{n['text']}\"")
        return (self._head(job) + "\n\nParas's review notes for you:\n" + "\n".join(lines) +
                "\n\nRead the job and whatever reports you need, fix each note by changing only your parts of job.json "
                "with patch_job, then close every note with mark_note (fixed, with one line on what changed, or "
                "wontfix, with why).")

    def _qa_task(self, role: str, items: list, qa: dict) -> str:
        lines = [f"- {name}: {c['summary']}\n  detail: {json.dumps({k: v for k, v in c.items() if k not in ('status', 'owner', 'summary')}, ensure_ascii=False)[:1500]}"
                 for name, c in items]
        return (self._head(self._job()) + f"\n\nQA scored the latest render {qa.get('score', 0):.1f}/10 (the gate is "
                "9.5 with no failed check). These failed checks are yours:\n" + "\n".join(lines) +
                "\n\nFix what job.json can fix with patch_job. There are no notes to close; finish with one line on "
                "what you changed, or why it can't be fixed from job.json.")

    def _plan_task(self, job: dict) -> str:
        srcs = sorted(p.stem[6:] for p in (self.dir / "build").glob("words_*.json"))
        return (self._head(job) + f"\n\nThe raw takes are transcribed (read_words with source = one of: "
                f"{', '.join(srcs)}). Plan the edit in job.json: keep the best take of each line and drop false starts, "
                "repeats and dead air (cut); put catalog effects on the words they illustrate (list_effects for this "
                "format; the hook text within the first second, nothing static over ~3 s, the CTA at the end); add SFX "
                "cues (whoosh into cuts, pop on cards); fix misheard names in captions.text.replace. Check every spoken "
                "claim against the house rules. The storyboard is built from your plan for Paras to approve; finish "
                "with three lines: the hook, the beats, anything Paras should decide.")


def status(db, pid: int, limit: int = 8) -> dict:
    ds = db.q("select * from dispatches where project=? order by id desc limit ?", (pid, limit))
    ids = [d["id"] for d in ds]
    runs = db.q("select * from agent_runs where dispatch in (%s) order by id" % ",".join("?" * len(ids)), ids) if ids else []
    for d in ds:
        d["runs"] = [r for r in runs if r["dispatch"] == d["id"]]
    return {"dispatches": ds, "running": bool(ds and ds[0]["status"] == "running")}


def _n(k: int, word: str) -> str:
    return f"{k} {word}{'' if k == 1 else 's'}"


def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
