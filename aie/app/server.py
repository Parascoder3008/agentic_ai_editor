"""The local API and the web app: python -m aie app (http://127.0.0.1:8765).

/api/...   JSON for the screens          /media/<project id>/<path>   files inside a project (video with range requests)
/fx/<name>/preview.jpg   effect previews  /fonts/<file>   the Inter fonts   /   the single-page app (static/)
Nothing here posts or uploads anywhere: Publish stays with Paras.
"""
import contextlib
import json
import shutil
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .. import runner
from ..agents import dispatch
from ..connectors import heygen, mcp
from ..effects import Catalog
from ..job import JobError, dumps as job_dumps, validate
from ..settings import REPO, load_settings
from . import connections, notes as notes_mod, projects
from .db import DB, dumps, now
from .demo import create_demo
from .worker import Worker

STATIC = Path(__file__).parent / "static"
PIPELINE = ["transcribe", "cut", "captions", "storyboard", "voice", "sfx", "music", "mix", "graphics", "effects", "base",
            "picture", "deliver", "qa"]


def create_app(repo: Path = REPO, data_dir: Path | None = None, settings=None, worker_run=None) -> FastAPI:
    settings = settings or load_settings()
    data_dir = Path(data_dir or repo / "app_data")
    db = DB(data_dir / "app.db")
    worker = Worker(db, settings, repo, worker_run)
    dispatch.recover(db)
    @contextlib.asynccontextmanager
    async def lifespan(_app):
        yield
        worker.stop()

    app = FastAPI(title="AI Editor", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
    app.state.db, app.state.worker, app.state.settings, app.state.repo = db, worker, settings, repo

    def catalog():
        return Catalog.load(settings.path("effects"))

    def sync_projects():
        known = {r["path"] for r in db.q("select path from projects")}
        for rel in projects.discover(repo):
            if rel not in known:
                db.x("insert into projects (path, created) values (?, ?)", (rel, now()))
        return db.q("select * from projects order by id")

    def project(pid: int) -> dict:
        p = db.one("select * from projects where id=?", (pid,))
        if not p or not (repo / p["path"]).exists():
            raise HTTPException(404, "no such project")
        return p

    def summary(p: dict, cat) -> dict:
        st = projects.state(repo, p["path"], settings, cat)
        last = db.one("select id, stage, status, started, ended from runs where project=? order by id desc limit 1", (p["id"],))
        open_notes = db.one("select count(*) n from notes where project=? and status!='fixed'", (p["id"],))["n"]
        version = db.one("select n, final from versions where project=? order by n desc limit 1", (p["id"],))
        return {"id": p["id"], **{k: st[k] for k in ("path", "title", "mode", "next", "qa", "stages", "errors", "has_job")},
                "last_run": last, "open_notes": open_notes, "version": version}

    # ---------------------------------------------------------------- overview
    @app.get("/api/health")
    def health():
        items = connections.listing(_tests(db))
        return {"ok": True, "placeholder": connections.placeholder_summary(items), "worker": worker.current,
                "queued": worker.q.qsize()}

    @app.get("/api/projects")
    def list_projects():
        cat = catalog()
        return [summary(p, cat) for p in sync_projects()]

    @app.post("/api/projects")
    async def new_project(brief: str = Form(...), files: list[UploadFile] = File(default=[])):
        try:
            b = json.loads(brief)
        except ValueError:
            raise HTTPException(400, "brief must be JSON")
        tmp = Path(tempfile.mkdtemp(dir=data_dir))
        ups = []
        for f in files:
            dst = tmp / Path(f.filename or "upload").name
            with dst.open("wb") as out:
                shutil.copyfileobj(f.file, out, 1 << 20)
            ups.append({"name": dst.name, "path": dst})
        try:
            rel = projects.create(repo, b, ups)
        except ValueError as e:
            raise HTTPException(400, str(e))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        sync_projects()
        return {"id": db.one("select id from projects where path=?", (rel,))["id"], "path": rel}

    @app.post("/api/demo")
    def new_demo():
        rel = create_demo(repo)
        sync_projects()
        return {"id": db.one("select id from projects where path=?", (rel,))["id"], "path": rel}

    @app.get("/api/projects/{pid}")
    def get_project(pid: int):
        p = project(pid)
        d = repo / p["path"]
        st = projects.state(repo, p["path"], settings, catalog())
        read = lambda f: projects._read(d / f)
        return {**summary(p, catalog()), "job": st["job"], "brief": st["brief"], "deliveries": st["deliveries"],
                "storyboard": read("build/storyboard.json"), "qa_report": read("build/qa/qa.json"),
                "picture": read("build/picture.json"), "mix": read("build/mix.json"),
                "publish": sorted(f.name for f in (d / "build/publish").glob("*")) if (d / "build/publish").exists() else [],
                "script": (d / "script.txt").read_text(encoding="utf-8") if (d / "script.txt").exists() else None,
                "connectors": {n: mcp.missing(n) for n in mcp.SERVERS},
                "nle": read("build/nle/nle.json"),
                "versions": [{**v, "files": json.loads(v["files"])} for v in
                             db.q("select * from versions where project=? order by n", (pid,))]}

    @app.put("/api/projects/{pid}/job")
    def put_job(pid: int, body: dict):
        p = project(pid)
        errs = validate(body, catalog(), repo / p["path"], settings)
        if errs:
            raise HTTPException(422, {"errors": errs})
        (repo / p["path"] / "job.json").write_text(job_dumps(body) + "\n", encoding="utf-8")
        return {"ok": True}

    @app.put("/api/projects/{pid}/script")
    def put_script(pid: int, body: dict):
        p = project(pid)
        name = body.get("file", "script.txt")
        if name not in ("script.txt", "script_tts.txt"):
            raise HTTPException(400, "file: script.txt or script_tts.txt")
        (repo / p["path"] / name).write_text(body["text"].rstrip() + "\n", encoding="utf-8")
        return {"ok": True}

    @app.get("/api/projects/{pid}/script/{name}")
    def get_script(pid: int, name: str):
        if name not in ("script.txt", "script_tts.txt"):
            raise HTTPException(400, "script.txt or script_tts.txt")
        f = repo / project(pid)["path"] / name
        return {"text": f.read_text(encoding="utf-8") if f.exists() else ""}

    @app.post("/api/projects/{pid}/brief")
    def patch_brief(pid: int, body: dict):
        """Small brief updates from the avatar studio (pronunciation approved, ...)."""
        f = repo / project(pid)["path"] / "brief.json"
        b = projects._read(f) or {}
        allowed = {"topic", "cta", "style", "notes", "look", "voice"}
        if set(body) - allowed:
            raise HTTPException(400, f"brief fields: {sorted(allowed)}")
        b.update(body)
        f.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
        return b

    @app.post("/api/projects/{pid}/gates")
    def set_gate(pid: int, body: dict):
        """Paras's two approvals. Approving the final re-renders at final quality on the next deliver."""
        p = project(pid)
        f = repo / p["path"] / "job.json"
        data = json.loads(f.read_text(encoding="utf-8"))
        for k in ("storyboard_approved", "final_approved"):
            if k in body:
                data.setdefault("gates", {})[k] = bool(body[k])
        f.write_text(job_dumps(data) + "\n", encoding="utf-8")
        return data["gates"]

    # ---------------------------------------------------------------- runs
    @app.post("/api/projects/{pid}/run")
    def run(pid: int, body: dict):
        project(pid)
        stage = body.get("stage", "all")
        if stage not in runner.STAGES:
            raise HTTPException(400, f"unknown stage {stage}")
        return {"run": worker.submit(pid, stage, bool(body.get("force")))}

    @app.get("/api/runs")
    def runs(project: int | None = None, limit: int = 30):
        sql = "select id, project, stage, force, status, queued, started, ended from runs"
        args = ()
        if project is not None:
            sql, args = sql + " where project=?", (project,)
        return db.q(sql + " order by id desc limit ?", (*args, limit))

    @app.get("/api/runs/{rid}")
    def get_run(rid: int):
        r = db.one("select * from runs where id=?", (rid,))
        if not r:
            raise HTTPException(404, "no such run")
        r["result"] = json.loads(r["result"]) if r["result"] else None
        return r

    # ---------------------------------------------------------------- notes
    @app.get("/api/projects/{pid}/notes")
    def get_notes(pid: int):
        project(pid)
        return db.q("select * from notes where project=? order by coalesce(t, beat, 0), id", (pid,))

    @app.post("/api/projects/{pid}/notes")
    def add_note(pid: int, body: dict):
        project(pid)
        text = (body.get("text") or "").strip()
        if not text:
            raise HTTPException(400, "a note needs text")
        owner, reason = notes_mod.route(text)
        nid = db.x("insert into notes (project, variant, t, beat, text, owner, reason, created) values (?,?,?,?,?,?,?,?)",
                   (pid, body.get("variant"), body.get("t"), body.get("beat"), text, owner, reason, now()))
        return db.one("select * from notes where id=?", (nid,))

    @app.patch("/api/notes/{nid}")
    def edit_note(nid: int, body: dict):
        n = db.one("select * from notes where id=?", (nid,))
        if not n:
            raise HTTPException(404, "no such note")
        status = body.get("status", n["status"])
        if status not in ("open", "sent", "fixed", "wontfix"):
            raise HTTPException(400, "status: open, sent, fixed or wontfix")
        fixed_in = body.get("fixed_in", n["fixed_in"])
        if status == "fixed" and fixed_in is None:
            v = db.one("select n from versions where project=? order by n desc limit 1", (n["project"],))
            fixed_in = v and v["n"]
        db.x("update notes set status=?, owner=?, fixed_in=? where id=?", (status, body.get("owner", n["owner"]), fixed_in, nid))
        return db.one("select * from notes where id=?", (nid,))

    @app.delete("/api/notes/{nid}")
    def del_note(nid: int):
        db.x("delete from notes where id=?", (nid,))
        return {"ok": True}

    @app.post("/api/projects/{pid}/notes/send")
    def send_notes(pid: int):
        """Open notes to the agent team. Placeholder until the Claude API key is set: the notes wait, routed."""
        project(pid)
        open_ = db.q("select id from notes where project=? and status='open'", (pid,))
        if not connections.get("ANTHROPIC_API_KEY"):
            raise HTTPException(409, "the agent team needs the Claude API key (Connections); the notes wait, routed to "
                                     "their owners")
        return dispatch.notes(repo, db, worker, project(pid), [n["id"] for n in open_])

    # ---------------------------------------------------------------- the agent team
    @app.get("/api/projects/{pid}/agents")
    def agents(pid: int):
        project(pid)
        return {**dispatch.status(db, pid), "ready": bool(connections.get("ANTHROPIC_API_KEY")),
                "budget": settings.data["agent_budget_usd"]}

    @app.post("/api/projects/{pid}/agents/plan")
    def agents_plan(pid: int):
        """The Story Editor drafts the edit from the brief and the transcript; the storyboard follows."""
        p = project(pid)
        if not connections.get("ANTHROPIC_API_KEY"):
            raise HTTPException(409, "the agent team needs the Claude API key (Connections)")
        return dispatch.plan(repo, db, worker, p)

    # ---------------------------------------------------------------- deliveries
    @app.post("/api/projects/{pid}/drive")
    def to_drive(pid: int):
        """Copy the approved deliveries into the Drive folder (Drive for desktop syncs it). Only after both approvals
        and a passing QA: this is the one step that leaves the PC."""
        p = project(pid)
        d = repo / p["path"]
        data = json.loads((d / "job.json").read_text(encoding="utf-8"))
        qa = projects._read(d / "build/qa/qa.json")
        if not data.get("gates", {}).get("final_approved"):
            raise HTTPException(409, "approve the final first")
        if not qa or not qa["passed"]:
            raise HTTPException(409, "QA hasn't passed on these files")
        folder = connections.get("DRIVE_FOLDER")
        if not folder or not Path(folder).is_dir():
            raise HTTPException(409, "set the Google Drive folder in Connections")
        dst = Path(folder) / d.name
        dst.mkdir(parents=True, exist_ok=True)
        copied = []
        for f in sorted((d / "build/publish").glob("*")):
            if "_PREVIEW" not in f.name:
                shutil.copy2(f, dst / f.name)
                copied.append(f.name)
        return {"folder": str(dst), "files": copied}

    @app.post("/api/projects/{pid}/publish/copy")
    def post_copy(pid: int):
        """The Publisher writes the post copy (it never posts); copy with a claim is not saved."""
        d = repo / project(pid)["path"]
        key = connections.get("ANTHROPIC_API_KEY")
        if not key:
            raise HTTPException(409, "the Publisher needs the Claude API key (Connections)")
        from ..agents import publisher
        try:
            return publisher.write(d, json.loads((d / "job.json").read_text(encoding="utf-8")),
                                   dispatch.make_client(key))
        except (publisher.PublishError, RuntimeError) as e:
            raise HTTPException(409, str(e))

    @app.post("/api/projects/{pid}/nle/resolve")
    def to_resolve(pid: int):
        """Import the exported timeline into the open Resolve project (tools/resolve_import.py)."""
        d = repo / project(pid)["path"]
        rep = projects._read(d / "build/nle/nle.json")
        if not rep or not Path(rep["otio"]).exists():
            raise HTTPException(409, "export the timeline first")
        exe = connections.get("RESOLVE_PATH")
        if not exe:
            raise HTTPException(409, "set the Resolve path in Connections")
        return {"message": _tool(REPO / "tools/resolve_import.py", rep["otio"], "--resolve", exe).strip()}

    # ---------------------------------------------------------------- avatar studio
    def _tool(*args) -> str:
        import subprocess
        import sys
        r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=repo)
        if r.returncode:
            raise HTTPException(400, (r.stderr or r.stdout).strip()[-800:])
        return r.stdout

    @app.post("/api/projects/{pid}/avatar/tts")
    def avatar_tts(pid: int):
        """The exact text HeyGen reads (pronunciation gate step 2: tools/pron_check.py --tts)."""
        d = repo / project(pid)["path"]
        if not (d / "script_tts.txt").exists():
            raise HTTPException(400, "write script_tts.txt first (Hindi in Devanagari, English in Latin, {Shown|बोला} pins)")
        return {"text": _tool(REPO / "tools/pron_check.py", d / "script_tts.txt", "--tts")}

    @app.post("/api/projects/{pid}/avatar/look")
    def avatar_look(pid: int):
        """The next look in the rotation (never the previous one), recorded in shorts/avatar_rotation.json."""
        p = project(pid)
        look = json.loads(_tool(REPO / "tools/pick_avatar.py", Path(p["path"]).name))
        f = repo / p["path"] / "brief.json"
        b = projects._read(f) or {}
        b["look"] = look
        f.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
        return look

    def _heygen(pid: int) -> Path:
        d = repo / project(pid)["path"]
        why = mcp.missing("heygen")
        if why:
            raise HTTPException(409, f"HeyGen isn't connected: {why} (Connections)")
        return d

    @app.post("/api/projects/{pid}/avatar/preview")
    def avatar_preview(pid: int):
        """Pronunciation gate step 2: HeyGen reads the exact TTS text in the approved voice; the report flags drift."""
        d = _heygen(pid)
        try:
            return heygen.preview(d, settings.path("avatar_rotation"))
        except (heygen.AvatarError, mcp.MCPError) as e:
            raise HTTPException(400, str(e))

    @app.post("/api/projects/{pid}/avatar/approve")
    def avatar_approve(pid: int, body: dict):
        """Paras listened: the approval is tied to this preview's exact audio."""
        try:
            return heygen.approve(repo / project(pid)["path"], bool(body.get("value", True)))
        except heygen.AvatarError as e:
            raise HTTPException(409, str(e))

    @app.post("/api/projects/{pid}/avatar/render")
    def avatar_render(pid: int):
        d = _heygen(pid)
        try:
            return heygen.start_render(d, on_done=lambda: (worker.submit(pid, "transcribe"),
                                                           worker.submit(pid, "storyboard")))
        except heygen.AvatarError as e:
            raise HTTPException(409, str(e))

    # ---------------------------------------------------------------- library
    @app.get("/api/effects")
    def effects():
        cat = catalog()
        return {"effects": [{"name": n, **{k: fx.data.get(k) for k in ("title", "description", "kind", "zone", "formats",
                                                                         "brand", "tags", "origin", "duration")},
                             "params": {k: {kk: vv for kk, vv in v.items()} for k, v in fx.params.items()},
                             "preview": f"/fx/{n}/preview.jpg" if (fx.dir / "preview.jpg").exists() else None}
                            for n, fx in sorted(cat.effects.items())], "errors": cat.errors}

    learning = {}                                     # style name -> the Style Learner's latest word on it

    @app.get("/api/styles")
    def styles():
        from ..styles import library
        return {**library(settings), "learning": learning}

    @app.post("/api/styles/learn")
    def learn_style(body: dict):
        """The Style Learner, on a thread: Apify scrapes the profiles, the pack waits for Paras's approval."""
        from ..agents import learner
        name = (body.get("name") or "").strip()
        if not connections.get("APIFY_TOKEN"):
            raise HTTPException(409, "the Style Learner needs the Apify token (Connections) to read the profiles")
        key = connections.get("ANTHROPIC_API_KEY")
        if not key:
            raise HTTPException(409, "the Style Learner needs the Claude API key (Connections)")
        if (learning.get(name) or {}).get("status") == "running":
            return {"message": f"already learning {name}"}
        try:
            api = dispatch.make_client(key)
        except RuntimeError as e:
            raise HTTPException(409, str(e))

        def go():
            try:
                pack = learner.learn(name, body.get("handles") or [], body.get("use", "any"), settings.path("styles"),
                                     settings, api, log=lambda m: learning.update({name: {"status": "running", "message": m}}))
                learning[name] = {"status": "done", "message": f"learned from {pack['learned_from']}: approve it to use it"}
            except Exception as e:                    # the library shows what broke
                learning[name] = {"status": "failed", "message": f"{type(e).__name__}: {e}"}
        learning[name] = {"status": "running", "message": "starting"}
        threading.Thread(target=go, daemon=True, name=f"aie-learn-{name}").start()
        return {"message": f"learning {name} from {', '.join(body.get('handles') or [])}"}

    @app.post("/api/styles/{name}/approve")
    def approve_style(name: str, body: dict):
        from ..agents import learner
        try:
            return learner.approve(settings.path("styles"), name, bool(body.get("value", True)))
        except learner.LearnError as e:
            raise HTTPException(409, str(e))

    @app.get("/api/avatars")
    def avatars():
        f = settings.path("avatar_rotation")
        return projects._read(f) if f and f.exists() else {"looks": []}

    # ---------------------------------------------------------------- connections
    @app.get("/api/connections")
    def get_connections():
        items = connections.listing(_tests(db))
        return {"items": items, "summary": connections.placeholder_summary(items)}

    @app.put("/api/connections/{cid}")
    def put_connection(cid: str, body: dict):
        try:
            connections.update(cid, body.get("values", {}))
        except KeyError:
            raise HTTPException(404, "no such connection")
        except ValueError as e:
            raise HTTPException(400, str(e))
        db.x("delete from connection_tests where id=?", (cid,))
        return {"ok": True}

    @app.post("/api/connections/{cid}/test")
    def test_connection(cid: str):
        try:
            ok, msg = connections.test(cid)
        except KeyError:
            raise HTTPException(404, "no such connection")
        db.x("insert or replace into connection_tests (id, ok, message, at) values (?,?,?,?)", (cid, int(ok), msg, now()))
        return {"ok": ok, "message": msg}

    # ---------------------------------------------------------------- files
    @app.api_route("/media/{pid}/{path:path}", methods=["GET", "HEAD"])
    def media(pid: int, path: str):
        base = (repo / project(pid)["path"]).resolve()
        f = (base / path).resolve()
        if base not in f.parents or not f.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(f)

    @app.get("/fx/{name}/preview.jpg")
    def fx_preview(name: str):
        fx = catalog().get(name)
        if not fx or not (fx.dir / "preview.jpg").exists():
            raise HTTPException(404, "no preview")
        return FileResponse(fx.dir / "preview.jpg")

    @app.get("/styles/{name}/preview.jpg")
    def style_preview(name: str):
        f = (settings.path("styles") or REPO / "styles") / Path(name).name / "preview.jpg"
        if not f.exists():
            raise HTTPException(404, "no preview")
        return FileResponse(f)

    @app.get("/fonts/{name}")
    def font(name: str):
        f = (settings.path("fonts") / Path(name).name)
        if not f.exists() or f.suffix != ".ttf":
            raise HTTPException(404, "no such font")
        return FileResponse(f)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (STATIC / "index.html").read_text(encoding="utf-8")

    return app


def _tests(db: DB) -> dict:
    return {r["id"]: {"ok": bool(r["ok"]), "message": r["message"], "at": r["at"]} for r in db.q("select * from connection_tests")}
