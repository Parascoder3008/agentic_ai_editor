"""The agent team without the API: a stand-in plays scripted model turns while the real tools run, so the guards
(ownership, gates, compliance, validation), the budget, the lanes' waves, the note round trip and the QA re-route are
tested the way they will run on the PC."""
import importlib.util
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HAVE = all(importlib.util.find_spec(m) for m in ("anthropic", "fastapi", "httpx", "multipart"))


class FakeRunner:
    """Yields scripted assistant turns; after each one, runs its tool calls through the real tools (as the SDK does)."""

    def __init__(self, turns, tools, api):
        self.turns, self.tools, self.api = turns, {t.name: t for t in tools}, api

    def __iter__(self):
        for i, turn in enumerate(self.turns):
            if isinstance(turn, Exception):
                raise turn
            calls = turn.get("calls", [])
            content = ([SimpleNamespace(type="text", text=turn["say"])] if turn.get("say") else []) + \
                      [SimpleNamespace(type="tool_use", id=f"t{i}{j}", name=n, input=a) for j, (n, a) in enumerate(calls)]
            yield SimpleNamespace(content=content, model=self.api.model, stop_reason=turn.get(
                "stop", "tool_use" if calls else "end_turn"), usage={"input_tokens": 1000, "output_tokens": 100})
            for n, a in calls:
                self.api.results.append((n, self.tools[n].call(a)))

    def close(self):
        self.api.closed += 1


class FakeAPI:
    def __init__(self, scripts=None, model=None):
        self.scripts, self.model, self.requests, self.results, self.closed = scripts or {}, model, [], [], 0
        self.beta = SimpleNamespace(messages=SimpleNamespace(tool_runner=self.tool_runner))

    def tool_runner(self, **kw):
        self.requests.append(kw)
        role = kw["system"][1]["text"].split(".")[0].removeprefix("You are the ")
        return FakeRunner(self.scripts[role].pop(0), kw["tools"], self)


_DEMO = {}


def demo(tmp: Path) -> Path:
    """A copy of the demo job in tmp (its media is made once per run: ffmpeg takes a few seconds)."""
    if "dir" not in _DEMO:
        from aie.app.demo import create_demo
        base = Path(tempfile.mkdtemp())
        _DEMO["dir"] = base / create_demo(base)
    d = tmp / "demo-reel"
    shutil.copytree(_DEMO["dir"], d)
    return d


class Base:
    def setUp(self):
        from aie.settings import load_settings
        self.tmp = Path(tempfile.mkdtemp())
        self.dir = demo(self.tmp)
        self.settings = load_settings(self.tmp / "none.json")
        self.flags = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def box(self, role):
        from aie.agents.tools import Toolbox
        return Toolbox(role, self.dir, self.settings, on_flag=lambda *a: self.flags.append(a))

    def job(self):
        return json.loads((self.dir / "job.json").read_text(encoding="utf-8"))


@unittest.skipUnless(HAVE, "needs anthropic, fastapi, httpx and python-multipart")
class ToolboxTest(Base, unittest.TestCase):
    def test_patch_job_guards(self):
        before = self.job()
        pr, md = self.box("Proofreader"), self.box("Motion Designer")
        self.assertIn("isn't Proofreader's", pr.patch_job([{"op": "replace", "path": "/effects/0/dur", "value": 3}], "x"))
        self.assertIn("gates are Paras's", md.patch_job([{"op": "replace", "path": "/gates/final_approved",
                                                           "value": True}], "x"))
        self.assertIn("must start with /", md.patch_job([{"op": "replace", "path": "effects/0/dur", "value": 3}], "x"))
        self.assertIn("doesn't exist", md.patch_job([{"op": "replace", "path": "/effects/0/nope", "value": 3}], "x"))
        bad = md.patch_job([{"op": "replace", "path": "/effects/0/dur", "value": -1}], "shorter")
        self.assertTrue(bad.startswith("rejected, job.json unchanged"), bad)
        claim = md.patch_job([{"op": "replace", "path": "/effects/0/params/LINE2", "value": "Guaranteed 10% returns"}],
                             "punchier hook")
        self.assertTrue(claim.startswith("blocked:"), claim)
        self.assertEqual(self.flags[0][0], "Motion Designer")
        self.assertEqual(self.job(), before)                                   # nothing above wrote anything
        self.assertFalse((self.dir / "build/agent_changes.jsonl").exists())
        shutil.rmtree(self.dir / "build", ignore_errors=True)                 # a fresh job has no build folder yet

        ok = pr.patch_job([{"op": "add", "path": "/captions/text", "value": {"replace": {"clod": "Claude"}}}], "name")
        self.assertTrue(ok.startswith("applied 1 change"), ok)
        self.assertEqual(self.job()["captions"]["text"], {"replace": {"clod": "Claude"}})
        log = [json.loads(x) for x in (self.dir / "build/agent_changes.jsonl").read_text().splitlines()]
        self.assertEqual((log[0]["role"], log[0]["why"]), ("Proofreader", "name"))
        self.assertEqual(pr.changes, 1)

    def test_cleared_phrases_pass(self):
        data = self.job()
        data["qa"]["cleared"] = ["guaranteed"]
        (self.dir / "job.json").write_text(json.dumps(data))
        out = self.box("Motion Designer").patch_job(
            [{"op": "replace", "path": "/effects/0/params/LINE2", "value": "guaranteed"}], "Paras cleared it")
        self.assertTrue(out.startswith("applied"), out)

    def test_reads(self):
        b = self.box("Story Editor")
        self.assertIn("no caption words yet", b.read_words())               # before the job has a build folder
        (self.dir / "build").mkdir()
        (self.dir / "build/words_a.json").write_text(json.dumps({"words": [
            {"text": "Claude", "start": 1.0, "end": 1.4}, {"text": "edits", "start": 1.5, "end": 1.9}]}))
        self.assertIn("transcripts: a", b.read_words())
        self.assertEqual(b.read_words(1.2, 9, "a"), "edits@1.50")
        self.assertIn("reel-hook", b.list_effects("9:16"))
        self.assertIn("reports:", b.read_report("nope"))
        self.assertEqual(b.read_report("qa"), "qa: not built yet")
        self.assertIn("no style", b.get_style("nope"))
        self.assertEqual(b.mark_note(1, "fixed", "x"), "no notes in this run")


@unittest.skipUnless(HAVE, "needs anthropic, fastapi, httpx and python-multipart")
class RunAgentTest(Base, unittest.TestCase):
    def run_role(self, role, turns, budget=None, model=None):
        from aie.agents.run import run_agent
        api = FakeAPI({role: [turns]}, model)
        box = self.box(role)
        return run_agent(role, "fix it", box, api, budget), api

    def test_request_settings(self):
        from aie.agents.roster import HAIKU, OPUS, ROLES
        from aie.agents.run import PRIMER, request
        kw = request("Story Editor")
        self.assertEqual((kw["model"], kw["output_config"], kw["fallbacks"]), (OPUS, {"effort": "high"}, "default"))
        self.assertEqual(kw["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(kw["system"][0], {"type": "text", "text": PRIMER, "cache_control": {"type": "ephemeral"}})
        self.assertNotIn("thinking", kw)
        with mock.patch.dict(ROLES, {"Publisher": {**ROLES["Proofreader"], "model": HAIKU}}):
            self.assertNotIn("fallbacks", request("Publisher"))              # Haiku has no server-side fallback

    def test_a_turn_that_fixes_and_reports(self):
        out, api = self.run_role("Proofreader", [
            {"calls": [("read_job", {}), ("patch_job", {"ops": [{"op": "add", "path": "/captions/text",
                                                               "value": {"replace": {"clod": "Claude"}}}], "why": "name"})]},
            {"say": "Captions now spell Claude."}])
        self.assertEqual((out["status"], out["changes"], out["turns"]), ("done", 1, 2))
        self.assertEqual(out["text"], "Captions now spell Claude.")
        self.assertAlmostEqual(out["cost"], 2 * (1000 * 2.0 + 100 * 10.0) / 1e6)   # Sonnet prices, two turns
        self.assertEqual([n for n, _ in api.results], ["read_job", "patch_job"])
        self.assertEqual(api.closed, 1)

    def test_budget_stops_before_the_tools_run(self):
        from aie.agents.run import Budget
        before = self.job()
        budget = Budget(0.001)
        out, api = self.run_role("Proofreader", [
            {"calls": [("patch_job", {"ops": [{"op": "add", "path": "/captions/text", "value": {}}], "why": "x"})]}],
            budget)
        self.assertEqual(out["status"], "over budget")
        self.assertEqual((api.results, self.job()), ([], before))
        self.assertFalse(budget.left())
        again, api2 = self.run_role("Proofreader", [{"say": "x"}], budget)
        self.assertEqual((again["status"], api2.requests), ("over budget", []))   # a spent budget starts nothing

    def test_refusal_cap_and_errors(self):
        import anthropic
        import httpx
        out, _ = self.run_role("Proofreader", [{"say": "", "stop": "refusal"}])
        self.assertEqual(out["status"], "refused")
        out, _ = self.run_role("Proofreader", [{"calls": [("read_job", {})]}])      # the runner hit its turn cap
        self.assertEqual(out["status"], "turn cap")
        out, _ = self.run_role("Proofreader", [anthropic.APIConnectionError(request=httpx.Request("POST", "https://x"))])
        self.assertEqual(out["status"], "error")
        self.assertIn("APIConnectionError", out["text"])
        out, _ = self.run_role("Proofreader", [{"say": "x"}], model="some-new-model")
        self.assertAlmostEqual(out["cost"], (1000 * 4.0 + 100 * 20.0) / 1e6)       # unknown models priced as Opus


@unittest.skipUnless(HAVE, "needs anthropic, fastapi, httpx and python-multipart")
class PublisherTest(Base, unittest.TestCase):
    def api(self, text):
        sent = []
        msg = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)],
                              usage={"input_tokens": 900, "output_tokens": 300})
        return SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: sent.append(kw) or msg)), sent

    def test_post_copy(self):
        from aie.agents import publisher
        from aie.agents.roster import HAIKU
        api, sent = self.api("## Instagram\n**Caption:** Claude ab reply karta hai.\nComment AGENT.\n"
                             "**First comment:** #ai #claude")
        with self.assertRaisesRegex(publisher.PublishError, "nothing to write from"):
            publisher.write(self.dir, self.job(), api)
        (self.dir / "build").mkdir()
        (self.dir / "build/words.json").write_text(json.dumps({"words": [{"text": "Claude", "start": 0, "end": 1},
                                                                         {"text": "agent", "start": 1, "end": 2}]}))
        out = publisher.write(self.dir, self.job(), api)
        self.assertEqual(Path(out["file"]).name, "DEMO_post.md")
        self.assertTrue(Path(out["file"]).read_text().startswith("## Instagram"))
        kw = sent[0]
        self.assertEqual((kw["model"], kw["output_config"]), (HAIKU, {"effort": "low"}))
        ask = kw["messages"][0]["content"]
        self.assertIn("Claude agent", ask)
        self.assertIn("comment the keyword AGENT", ask)                          # the brief's CTA keyword
        self.assertIn("## YouTube", ask)                                         # both variants asked for
        bad, _ = self.api("Is system se aap 50,000 per month kama sakte ho. Guaranteed!")
        Path(out["file"]).unlink()
        with self.assertRaisesRegex(publisher.PublishError, "income/return claim"):
            publisher.write(self.dir, self.job(), bad)
        self.assertFalse(Path(out["file"]).exists())                             # nothing saved


class PlanningTest(unittest.TestCase):
    def test_waves_never_share_a_part(self):
        from aie.agents.dispatch import PARALLEL, waves
        from aie.agents.roster import ROLES
        w = waves(list(ROLES))
        self.assertEqual(w, [["Story Editor"], ["Proofreader", "Sound Designer", "Motion Designer", "Compositor"],
                             ["Cut Surgeon"], ["Generator"]])
        for wave in w:
            owned = [k for r in wave for k in ROLES[r]["owns"]]
            self.assertEqual(len(owned), len(set(owned)))
            self.assertLessEqual(len(wave), PARALLEL)

    def test_variant_time_to_master(self):
        from aie.agents.dispatch import to_master
        self.assertEqual(to_master(12.0, [[0, 10], [20, 30]]), 22.0)
        self.assertEqual(to_master(5.0, [[0, 10], [20, 30]]), 5.0)
        self.assertEqual(to_master(99.0, [[0, 10]]), 10.0)
        self.assertIsNone(to_master(None, [[0, 10]]))
        self.assertEqual(to_master(3.0, None), 3.0)


@unittest.skipUnless(HAVE and shutil.which("ffmpeg"), "needs anthropic, fastapi, httpx, python-multipart and ffmpeg")
class DispatchTest(unittest.TestCase):
    """Notes from the review player -> lanes -> render -> QA -> failures back to their owners, through the app's API."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from aie.agents import dispatch
        from aie.app.server import create_app
        from aie.settings import load_settings
        self.repo = Path(tempfile.mkdtemp()).resolve()
        (self.repo / "settings.json").write_text(json.dumps({"min_free_gb": 0, "agent_budget_usd": 1.0}))
        self.env = mock.patch.dict(os.environ, {"AIE_SECRETS": str(self.repo / "secrets.local.json")})
        self.env.start()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.calls, self.qa = [], []

        def fake_run(job, settings, stage, force, log):
            self.calls.append(stage)
            if stage == "all":
                (job.dir / "build/qa").mkdir(parents=True, exist_ok=True)
                (job.dir / "build/qa/qa.json").write_text(json.dumps(self.qa.pop(0)))
            return {"ok": True}

        self.api = FakeAPI()
        self.patches = [mock.patch.object(dispatch, "make_client", lambda key: self.api),
                        mock.patch.object(dispatch, "POLL", 0.01)]
        for p in self.patches:
            p.start()
        self.app = create_app(self.repo, self.repo / "app_data", load_settings(self.repo / "settings.json"), fake_run)
        self.c = TestClient(self.app)
        self.pid = self.c.post("/api/demo").json()["id"]
        self.dir = self.repo / "jobs/demo-reel"

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.app.state.worker.stop()
        self.app.state.worker.thread.join(timeout=5)
        self.app.state.db.close()
        self.env.stop()
        shutil.rmtree(self.repo, ignore_errors=True)

    def note(self, text, **kw):
        return self.c.post(f"/api/projects/{self.pid}/notes", json={"text": text, **kw}).json()

    def settle(self):
        for _ in range(500):
            a = self.c.get(f"/api/projects/{self.pid}/agents").json()
            if not a["running"]:
                return a
            time.sleep(0.02)
        self.fail("the dispatch never finished")

    def notes(self):
        return {n["id"]: n for n in self.c.get(f"/api/projects/{self.pid}/notes").json()}

    def test_notes_round_trip_before_the_storyboard_is_approved(self):
        cap = self.note("caption galat hai: clod", t=3.0, variant="instagram")
        mus = self.note("music too loud here", t=5.0)
        self.assertEqual((cap["owner"], mus["owner"]), ("Proofreader", "Sound Designer"))
        r = self.c.post(f"/api/projects/{self.pid}/notes/send")
        self.assertEqual(r.status_code, 409)                                  # no key: the notes wait, routed
        self.assertFalse(self.c.get(f"/api/projects/{self.pid}/agents").json()["ready"])

        self.api.scripts = {
            "Proofreader": [[
                {"calls": [("patch_job", {"ops": [{"op": "add", "path": "/captions/text",
                                                   "value": {"replace": {"clod": "Claude"}}}], "why": "name"})]},
                {"calls": [("mark_note", {"note_id": cap["id"], "status": "fixed", "reply": "clod -> Claude"}),
                           ("mark_note", {"note_id": mus["id"], "status": "fixed", "reply": "not mine"})]},
                {"say": "Fixed the spelling."}]],
            "Sound Designer": [[{"say": "Looked at the mix; leaving it for Paras."}]]}
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            sent = self.c.post(f"/api/projects/{self.pid}/notes/send").json()
            self.assertEqual(sent["message"], "sent 2 note(s) to Proofreader, Sound Designer")
            a = self.settle()
        d = a["dispatches"][0]
        self.assertEqual(d["status"], "done", d["message"])
        self.assertIn("storyboard is rebuilt", d["message"])
        self.assertEqual(self.calls, ["storyboard"])                          # the gate holds: no picture yet
        self.assertEqual(sorted(r["role"] for r in d["runs"]), ["Proofreader", "Sound Designer"])
        self.assertGreater(d["spent"], 0)
        n = self.notes()
        self.assertEqual((n[cap["id"]]["status"], n[cap["id"]]["agent_reply"]), ("fixed", "Proofreader: clod -> Claude"))
        self.assertEqual(n[mus["id"]]["status"], "open")                      # not the Proofreader's to close
        self.assertIn("Sound Designer didn't close this (done)", n[mus["id"]]["agent_reply"])
        self.assertIn("note 1 at 00:03.00 of the instagram cut", self.api.requests[0]["messages"][0]["content"])
        self.assertIn("patch_job", [r for r in d["runs"] if r["role"] == "Proofreader"][0]["log"])
        job = json.loads((self.dir / "job.json").read_text())
        self.assertEqual(job["captions"]["text"], {"replace": {"clod": "Claude"}})
        self.assertFalse(job["gates"]["storyboard_approved"])

    def test_qa_failures_go_back_to_their_owners(self):
        self.c.post(f"/api/projects/{self.pid}/gates", json={"storyboard_approved": True})
        fx = self.note("the hook text graphic needs to be punchier", t=1.0)
        self.assertEqual(fx["owner"], "Motion Designer")
        fail = {"score": 9.0, "passed": False, "checks": {
            "loudness": {"status": "FAIL", "owner": "Sound Designer", "summary": "-12.1 LUFS", "lufs": -12.1},
            "rights": {"status": "FAIL", "owner": "Producer", "summary": "a downloaded clip in a client job"}}}
        self.qa = [fail, {"score": 9.9, "passed": True, "checks": {}}]
        self.api.scripts = {
            "Motion Designer": [[
                {"calls": [("patch_job", {"ops": [{"op": "replace", "path": "/effects/0/params/LINE2",
                                                   "value": "Guaranteed returns"}], "why": "punchier"})]},
                {"calls": [("patch_job", {"ops": [{"op": "replace", "path": "/effects/0/params/LINE2",
                                                   "value": "POORA REEL, ZERO TOUCH"}], "why": "punchier"}),
                           ("mark_note", {"note_id": fx["id"], "status": "fixed", "reply": "new LINE2"})]},
                {"say": "Hook line two is punchier."}]],
            "Sound Designer": [[
                {"calls": [("patch_job", {"ops": [{"op": "add", "path": "/mix/voice_lufs", "value": -18}],
                                          "why": "QA loudness"})]},
                {"say": "Voice target down 1 dB."}]]}
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            self.c.post(f"/api/projects/{self.pid}/notes/send")
            d = self.settle()["dispatches"][0]
        self.assertEqual(d["status"], "done", d["message"])
        self.assertIn("QA 9.9 PASS", d["message"])
        self.assertTrue(d["message"].endswith("PASS. 1 compliance flag for Paras"), d["message"])
        self.assertEqual(self.calls, ["all", "all"])
        self.assertEqual([(r["role"], r["round"]) for r in d["runs"]], [("Motion Designer", 1), ("Sound Designer", 2)])
        self.assertIn("loudness: -12.1 LUFS", self.api.requests[1]["messages"][0]["content"])
        paras = [n for n in self.notes().values() if n["owner"] == "Paras"]
        self.assertEqual(sorted(n["reason"] for n in paras), ["compliance block", "qa rights"])
        job = json.loads((self.dir / "job.json").read_text())
        self.assertEqual(job["effects"][0]["params"]["LINE2"], "POORA REEL, ZERO TOUCH")
        self.assertEqual(job["mix"]["voice_lufs"], -18)
        self.assertEqual(self.notes()[fx["id"]]["status"], "fixed")

    def test_budget_pauses_and_one_dispatch_at_a_time(self):
        self.note("caption typo", t=1.0)
        self.c.app.state.settings.data["agent_budget_usd"] = 0.0001
        self.api.scripts = {"Proofreader": [[{"calls": [("read_job", {})]}, {"say": "x"}]]}
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            self.c.post(f"/api/projects/{self.pid}/notes/send")
            d = self.settle()["dispatches"][0]
        self.assertEqual(d["status"], "paused")
        self.assertIn("budget is spent", d["message"])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.api.results, [])                               # the turn's tool call never ran
        db = self.app.state.db
        db.x("insert into dispatches (project, kind, status, budget, started) values (?, 'notes', 'running', 1, 0)",
             (self.pid,))
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            self.assertTrue(self.c.post(f"/api/projects/{self.pid}/notes/send").json()["busy"])
            self.assertTrue(self.c.post(f"/api/projects/{self.pid}/agents/plan").json()["busy"])
        from aie.agents.dispatch import recover
        recover(db)                                                          # an app restart ends what it cut off
        self.assertFalse(self.c.get(f"/api/projects/{self.pid}/agents").json()["running"])

    def test_missing_package_says_what_to_install(self):
        from aie.agents import dispatch, run
        self.note("caption typo", t=1.0)
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}), \
                mock.patch.object(dispatch, "make_client", run.client), mock.patch.dict("sys.modules", {"anthropic": None}):
            r = self.c.post(f"/api/projects/{self.pid}/notes/send").json()
            self.assertIn('pip install "anthropic>=2.2"', r["message"])
            r = self.c.post(f"/api/projects/{self.pid}/publish/copy")
            self.assertEqual(r.status_code, 409)
            self.assertIn("pip install", r.json()["detail"])
        self.assertFalse(self.c.get(f"/api/projects/{self.pid}/agents").json()["dispatches"])

    def test_plan_from_the_transcript(self):
        (self.dir / "build").mkdir(exist_ok=True)
        (self.dir / "build/words_presenter.json").write_text(json.dumps({"words": [
            {"text": "AI", "start": 0.2, "end": 0.4}, {"text": "edits", "start": 0.5, "end": 0.9}]}))
        self.api.scripts = {"Story Editor": [[
            {"calls": [("read_words", {"source": "presenter"}), ("patch_job", {"ops": [
                {"op": "add", "path": "/sfx/cues/-", "value": {"kind": "whoosh", "t": 2.0, "db": -34}}], "why": "cut"})]},
            {"say": "Hook: AI edits. Beats: 3. Decide: CTA keyword."}]]}
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            r = self.c.post(f"/api/projects/{self.pid}/agents/plan").json()
            self.assertIn("Story Editor is planning", r["message"])
            d = self.settle()["dispatches"][0]
        self.assertEqual(d["status"], "done", d["message"])
        self.assertIn("storyboard is ready", d["message"])
        self.assertEqual(self.calls, ["storyboard"])
        self.assertEqual(self.api.results[0], ("read_words", "AI@0.20 edits@0.50"))
        self.assertIn("source = one of: presenter", self.api.requests[0]["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main()
