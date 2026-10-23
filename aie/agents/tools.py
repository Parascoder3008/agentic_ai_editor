"""The tools agents act through. Nothing here gives an agent the filesystem or a shell: it reads the job and its
reports, and it changes job.json only with patch_job, which (1) lets a role touch only the top-level keys it owns,
(2) validates the result the way the runner does, (3) screens new text for income/return claims (Constitution
section 4: blocked, and Paras is flagged), (4) never touches the approval gates, and (5) logs every change to
build/agent_changes.jsonl. Edits to one job are serialised, so lanes working at the same time can't lose each other's.
"""
import copy
import json
import threading
import time
from pathlib import Path

from ..effects import Catalog
from ..job import dumps as job_dumps, validate
from ..qa import claims
from .roster import ROLES

_locks: dict = {}
_locks_guard = threading.Lock()


def job_lock(path: Path) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(str(path.resolve()), threading.Lock())


def _ptr(path: str) -> list:
    if not path.startswith("/"):
        raise ValueError(f"path {path!r} must start with /, e.g. /effects/0/at")
    return [p.replace("~1", "/").replace("~0", "~") for p in path[1:].split("/")]


def apply_ops(data: dict, ops: list) -> dict:
    """JSON-patch style ops (replace, add, remove) on a copy of data."""
    out = copy.deepcopy(data)
    for op in ops:
        kind, parts = op.get("op"), _ptr(op.get("path", ""))
        if kind not in ("replace", "add", "remove"):
            raise ValueError(f"op must be replace, add or remove, not {kind!r}")
        parent = out
        for p in parts[:-1]:
            parent = parent[int(p)] if isinstance(parent, list) else parent[p]
        last = parts[-1]
        if isinstance(parent, list):
            i = len(parent) if last == "-" else int(last)
            if kind == "add":
                parent.insert(i, op["value"])
            elif kind == "remove":
                del parent[i]
            else:
                parent[i] = op["value"]
        else:
            if kind == "remove":
                del parent[last]
            elif kind == "replace" and last not in parent:
                raise ValueError(f"{op['path']} doesn't exist (use add)")
            else:
                parent[last] = op["value"]
    return out


def _texts(x, where="") -> list:
    if isinstance(x, str):
        return [(where, x)]
    if isinstance(x, dict):
        return [t for k, v in x.items() for t in _texts(v, f"{where}/{k}")]
    if isinstance(x, list):
        return [t for i, v in enumerate(x) for t in _texts(v, f"{where}/{i}")]
    return []


class Toolbox:
    """The tools for one role working on one job. `notes` hands mark_note its writes; `on_flag` gets compliance flags."""

    def __init__(self, role: str, job_dir: Path, settings, notes=None, on_flag=None):
        self.role, self.dir, self.settings = role, Path(job_dir), settings
        self.owns = ROLES[role]["owns"]
        self.notes, self.on_flag = notes, on_flag or (lambda *a: None)
        self.changes = 0

    # ---------------------------------------------------------------- reads
    def read_job(self) -> str:
        return (self.dir / "job.json").read_text(encoding="utf-8")

    def read_words(self, t0: float = 0.0, t1: float = 1e9, source: str = "") -> str:
        """Words as text@start. Without a source: the caption words on the output timeline (build/words.json). With
        one: that source's own transcript (build/words_<source>.json, source seconds), which is what a cut is planned on."""
        f = self.dir / "build" / (f"words_{source}.json" if source else "words.json")
        if not f.exists():
            made = sorted(p.stem[6:] for p in (self.dir / "build").glob("words_*.json"))
            return (f"no transcript for source {source!r}" if source else
                    "no caption words yet (the captions stage hasn't run)") + \
                   (f"; transcripts: {', '.join(made)} (pass source=...)" if made else "")
        words = json.loads(f.read_text(encoding="utf-8"))["words"]
        sel = [w for w in words if t0 <= w["start"] < t1]
        return " ".join(f"{w['text']}@{w['start']:.2f}" for w in sel[:1500]) or "no words in that window"

    def read_report(self, name: str) -> str:
        files = {"qa": "build/qa/qa.json", "storyboard": "build/storyboard.json", "mix": "build/mix.json",
                 "deliver": "build/deliver.json", "pieces": "build/pieces.json", "joints": "build/joints.txt"}
        if name not in files:
            return f"reports: {', '.join(files)}"
        f = self.dir / files[name]
        return f.read_text(encoding="utf-8")[:20000] if f.exists() else f"{name}: not built yet"

    def list_effects(self, fmt: str = "") -> str:
        cat = Catalog.load(self.settings.path("effects"))
        rows = []
        for n, fx in sorted(cat.effects.items()):
            if fmt and fmt not in fx.formats:
                continue
            p = ", ".join(f"{k}{'*' if v.get('required') else ''}" + (f"({v['type']})" if v.get("type") else "")
                          for k, v in fx.params.items())
            d = fx.data.get("duration", {})
            rows.append(f"{n} [{','.join(fx.formats)}, {fx.data.get('zone', '')}, {d.get('min', '')}-{d.get('max', '')} s]: "
                        f"{fx.data['title']}. params: {p}")
        return "\n".join(rows)

    def get_style(self, name: str) -> str:
        f = (self.settings.path("styles") or self.dir) / name / "style.json"
        return f.read_text(encoding="utf-8") if f.exists() else f"no style {name!r}"

    # ---------------------------------------------------------------- writes
    def patch_job(self, ops: list, why: str) -> str:
        if not self.owns:
            return f"rejected: {self.role} changes nothing itself"
        for op in ops:
            try:
                top = _ptr(op.get("path", "/"))[0]
            except ValueError as e:
                return f"rejected: {e}"
            if top == "gates":
                return "rejected: the gates are Paras's approvals; agents never change them"
            if top not in self.owns:
                return f"rejected: {top} isn't {self.role}'s ({', '.join(self.owns)}); leave a note for its owner"
        f = self.dir / "job.json"
        with job_lock(f):
            data = json.loads(f.read_text(encoding="utf-8"))
            try:
                new = apply_ops(data, ops)
            except (KeyError, IndexError, ValueError, TypeError) as e:
                return f"rejected: {e}"
            added = [t for op in ops if op.get("op") != "remove" for t in _texts(op.get("value"), op.get("path", ""))]
            hits = claims(added, new.get("qa", {}).get("cleared", []))
            if hits:
                self.on_flag(self.role, hits, why)
                return ("blocked: " + "; ".join(f"{h['where']}: \"{h['phrase']}\"" for h in hits) +
                        " reads as an income/return claim (Constitution section 4). Paras is flagged; don't retry it.")
            errs = validate(new, Catalog.load(self.settings.path("effects")), self.dir, self.settings)
            if errs:
                return "rejected, job.json unchanged:\n" + "\n".join(errs[:12])
            (self.dir / "build").mkdir(exist_ok=True)
            with (self.dir / "build/agent_changes.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps({"t": round(time.time(), 2), "role": self.role, "why": why, "ops": ops},
                                     ensure_ascii=False) + "\n")
            f.write_text(job_dumps(new) + "\n", encoding="utf-8")
            self.changes += 1
        return f"applied {len(ops)} change(s); job.json is valid"

    def generate_clip(self, name: str, prompt: str, seconds: int = 5, aspect: str = "9:16", model: str = "") -> str:
        from ..connectors import higgsfield, mcp
        try:
            return higgsfield.generate(self.dir, name, prompt, seconds, aspect, model or higgsfield.DEFAULT_MODEL)
        except mcp.MCPError as e:
            return f"not generated: {e}"

    def mark_note(self, note_id: int, status: str, reply: str) -> str:
        if status not in ("fixed", "wontfix"):
            return "status: fixed or wontfix"
        if self.notes is None:
            return "no notes in this run"
        return self.notes(note_id, status, f"{self.role}: {reply}")

    # ---------------------------------------------------------------- for the API
    def tools(self) -> list:
        """The role's tools as SDK function tools (the Tool Runner calls them)."""
        from anthropic import beta_tool
        tb = self

        @beta_tool
        def read_job() -> str:
            """The job's job.json, as it is now."""
            return tb.read_job()

        @beta_tool
        def read_words(t0: float = 0.0, t1: float = 1e9, source: str = "") -> str:
            """Spoken words as text@start-seconds between t0 and t1.

            Leave source empty for the caption words on the output timeline (master seconds); name a source (e.g. "a")
            for its raw transcript in source seconds, which is what cut keeps and drops are written in.

            Args:
                t0: window start in seconds.
                t1: window end in seconds.
                source: a name from job.json sources, or empty.
            """
            return tb.read_words(t0, t1, source)

        @beta_tool
        def read_report(name: str) -> str:
            """A build report: qa, storyboard, mix, deliver, pieces or joints.

            Args:
                name: which report.
            """
            return tb.read_report(name)

        @beta_tool
        def list_effects(fmt: str = "") -> str:
            """The effects catalog: name, formats, zone, duration range, title, parameters (* = required).

            Args:
                fmt: only effects built for this format, e.g. "9:16".
            """
            return tb.list_effects(fmt)

        @beta_tool
        def get_style(name: str) -> str:
            """A style pack (palette, type, captions block, effects, pacing).

            Args:
                name: the pack's name, e.g. ai-os-blue.
            """
            return tb.get_style(name)

        @beta_tool(input_schema={
            "type": "object", "required": ["ops", "why"], "additionalProperties": False,
            "properties": {
                "ops": {"type": "array", "minItems": 1, "items": {
                    "type": "object", "required": ["op", "path"], "properties": {
                        "op": {"type": "string", "enum": ["replace", "add", "remove"]},
                        "path": {"type": "string", "description": "JSON pointer, e.g. /effects/0/at or /sfx/cues/-"},
                        "value": {"description": "the new value (not for remove)"}}}},
                "why": {"type": "string", "description": "one line: what this fixes"}}})
        def patch_job(ops: list, why: str) -> str:
            """Change job.json with replace / add / remove operations at JSON pointers.

            Only the parts your role owns; the result must validate. Returns "applied ..." or why it was rejected.
            """
            return tb.patch_job(ops, why)

        @beta_tool
        def mark_note(note_id: int, status: str, reply: str) -> str:
            """Close a review note you were given.

            Args:
                note_id: the note's id.
                status: fixed or wontfix.
                reply: one line for Paras: what changed, or why not.
            """
            return tb.mark_note(note_id, status, reply)

        out = [read_job, read_words, read_report, list_effects, get_style, patch_job, mark_note]
        if self.role == "Generator":
            @beta_tool
            def generate_clip(name: str, prompt: str, seconds: int = 5, aspect: str = "9:16", model: str = "") -> str:
                """Generate one shot on Higgsfield into raw/gen_<name>.mp4, within Paras's credit cap.

                It is priced first and refused past the cap; a failed job is reported, never retried.

                Args:
                    name: file name part, lowercase letters, digits, - or _.
                    prompt: what the shot shows; no logos, no text, no real people unless Paras asked.
                    seconds: length in seconds.
                    aspect: "9:16" for reels, "16:9" for long-form.
                    model: a Higgsfield model id; empty for the default (Seedance).
                """
                return tb.generate_clip(name, prompt, seconds, aspect, model)
            out.append(generate_clip)
        return out
