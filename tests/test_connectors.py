"""HeyGen and Higgsfield through their MCP servers, against in-process stand-ins with the real tool names and a local
HTTP server for the files (downloads and the presigned upload). Checks the gates: no render before Paras approved
that exact audio, a running render is polled and never resubmitted, no clip past the credit cap."""
import http.server
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

HAVE = all(importlib.util.find_spec(m) for m in ("mcp", "anthropic", "fastapi", "httpx", "multipart"))


class Files(http.server.ThreadingHTTPServer):
    """Serves files from a folder and keeps what is PUT to it."""

    def __init__(self, root: Path):
        self.root, self.puts = root, {}
        files = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                f = files.root / self.path.lstrip("/").split("?")[0]
                if not f.is_file():
                    self.send_error(404)
                    return
                data = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_PUT(self):
                n = int(self.headers["Content-Length"])
                files.puts[self.path] = (self.headers["Content-Type"], self.rfile.read(n))
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *a):
                pass

        super().__init__(("127.0.0.1", 0), H)
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def url(self, name):
        return f"http://127.0.0.1:{self.server_address[1]}/{name}"


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)


def fake_heygen(files: Files, states: list, calls: list):
    from mcp.server.mcpserver import MCPServer
    s = MCPServer("heygen-stand-in")

    @s.tool()
    def create_speech(text: str, voiceId: str) -> dict:
        calls.append(("create_speech", {"text": text, "voiceId": voiceId}))
        return {"data": {"audio_url": files.url("speech.m4a"), "duration": 1.5}}

    @s.tool()
    def create_asset_upload(filename: str, contentType: str, sizeBytes: int) -> dict:
        calls.append(("create_asset_upload", {"filename": filename, "contentType": contentType, "sizeBytes": sizeBytes}))
        return {"data": {"asset_id": "asset-1", "upload_url": files.url("put/asset-1")}}

    @s.tool()
    def complete_asset_upload(assetId: str) -> dict:
        calls.append(("complete_asset_upload", {"assetId": assetId}))
        return {"data": {"id": assetId, "status": "ready"}}

    @s.tool()
    def create_video_from_avatar(avatarId: str, audioAssetId: str = "", aspectRatio: str = "auto",
                                 resolution: str = "", title: str = "") -> dict:
        calls.append(("create_video_from_avatar", {"avatarId": avatarId, "audioAssetId": audioAssetId}))
        return {"data": {"video_id": "video-1"}}

    @s.tool()
    def get_video(videoId: str) -> dict:
        calls.append(("get_video", {"videoId": videoId}))
        st = states.pop(0) if len(states) > 1 else states[0]
        return {"data": {"id": videoId, "status": st, "retry_after_seconds": 0,
                         **({"video_url": files.url("avatar.mp4")} if st == "completed" else {}),
                         **({"failure_message": "audio too short"} if st == "failed" else {})}}
    return s


def fake_higgsfield(files: Files, cost: float, results: list, calls: list):
    from mcp.server.mcpserver import MCPServer
    s = MCPServer("higgsfield-stand-in")

    @s.tool()
    def generate_video(params: dict, context: str = "") -> dict:
        calls.append(("generate_video", params))
        if params.get("get_cost"):
            return {"cost": {"credits": cost}}
        return {"jobs": [{"index": 0, "job_id": f"job-{len(calls)}"}]}

    @s.tool()
    def jobs_wait(jobs: list, timeout_seconds: int = 15) -> dict:
        calls.append(("jobs_wait", jobs))
        st = results.pop(0) if len(results) > 1 else results[0]
        return {"all_terminal": st != "processing", "poll_after_seconds": 0,
                "jobs": [{"index": 0, "status": st, **({"result_url": files.url("clip.mp4")} if st == "completed" else {})}]}
    return s


@unittest.skipUnless(HAVE and shutil.which("ffmpeg"), "needs mcp, anthropic, fastapi, httpx, python-multipart, ffmpeg")
class HeyGenTest(unittest.TestCase):
    def setUp(self):
        from aie.connectors import mcp
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "srv").mkdir()
        ff("-f", "lavfi", "-i", "sine=frequency=220:duration=1.5", "-c:a", "aac", self.tmp / "srv/speech.m4a")
        ff("-f", "lavfi", "-i", "testsrc=s=1920x1080:r=25:d=2", "-f", "lavfi", "-i", "sine=duration=2", "-shortest",
           "-pix_fmt", "yuv420p", self.tmp / "srv/avatar.mp4")
        self.files = Files(self.tmp / "srv")
        self.calls, self.states = [], ["processing", "completed"]
        self.targets = mock.patch.dict(mcp.TARGETS, {"heygen": fake_heygen(self.files, self.states, self.calls)})
        self.targets.start()
        self.d = self.tmp / "jobs/av"
        (self.d / "raw").mkdir(parents=True)
        (self.d / "brief.json").write_text(json.dumps({"title": "Av", "mode": "avatar", "platforms": ["instagram"]}))
        self.rotation = self.tmp / "rotation.json"
        self.rotation.write_text(json.dumps({"voice_id": "voice-14", "looks": []}))

    def tearDown(self):
        self.targets.stop()
        self.files.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def brief(self):
        return json.loads((self.d / "brief.json").read_text())

    def made(self, tool):
        return [a for n, a in self.calls if n == tool]

    def test_preview_approve_render(self):
        from aie.connectors import heygen
        with self.assertRaisesRegex(heygen.AvatarError, "script_tts.txt"):
            heygen.preview(self.d, self.rotation)
        (self.d / "script_tts.txt").write_text("{Claude|क्लॉड} का अपना number", encoding="utf-8")
        pv = heygen.preview(self.d, self.rotation)
        self.assertEqual(self.made("create_speech"), [{"text": "क्लॉड का अपना number", "voiceId": "voice-14"}])
        self.assertTrue((self.d / "pron/preview.wav").exists())
        self.assertEqual((pv["file"], pv["voice"]), ("pron/preview.wav", "voice-14"))
        self.assertFalse(self.brief()["pron_approved"])

        with self.assertRaisesRegex(heygen.AvatarError, "look"):
            heygen.start_render(self.d)
        b = self.brief()
        b["look"] = {"id": "look-7", "name": "Cleaned Look", "orientation": "landscape"}
        (self.d / "brief.json").write_text(json.dumps(b))
        with self.assertRaisesRegex(heygen.AvatarError, "approve the pronunciation"):
            heygen.start_render(self.d)
        heygen.approve(self.d, True)
        wav = (self.d / "pron/preview.wav").read_bytes()
        (self.d / "pron/preview.wav").write_bytes(wav + b"\0")
        with self.assertRaisesRegex(heygen.AvatarError, "changed since you approved"):
            heygen.render(self.d, poll=0)                     # the approval is for the audio Paras heard, not this
        (self.d / "pron/preview.wav").write_bytes(wav)

        out = heygen.render(self.d, poll=0)
        self.assertEqual(out, self.d / "raw/avatar.mp4")
        self.assertEqual(self.files.puts["/put/asset-1"], ("audio/wav", wav))
        self.assertEqual(self.made("create_asset_upload")[0]["sizeBytes"], len(wav))
        self.assertEqual(self.made("complete_asset_upload"), [{"assetId": "asset-1"}])
        self.assertEqual(self.made("create_video_from_avatar"), [{"avatarId": "look-7", "audioAssetId": "asset-1"}])
        self.assertEqual(len(self.made("get_video")), 2)
        job = json.loads((self.d / "job.json").read_text())
        self.assertEqual(job["sources"]["avatar"]["rights"], "generated")
        self.assertEqual(job["layouts"]["face"]["crop"], [606, 1080, 657, 0])
        self.assertEqual(self.brief()["render"]["status"], "done")
        with self.assertRaisesRegex(heygen.AvatarError, "already rendered"):
            heygen.render(self.d, poll=0)
        b = self.brief()
        heygen.preview(self.d, self.rotation)                 # a new preview withdraws the approval
        self.assertFalse(self.brief()["pron_approved"])
        self.assertNotIn("pron_approved_sha", self.brief())

    def test_a_slow_render_is_polled_again_not_resubmitted(self):
        from aie.connectors import heygen
        (self.d / "script_tts.txt").write_text("namaste", encoding="utf-8")
        heygen.preview(self.d, self.rotation)
        b = self.brief()
        b["look"] = {"id": "look-7", "name": "Cleaned Look"}
        (self.d / "brief.json").write_text(json.dumps(b))
        heygen.approve(self.d, True)
        self.states[:] = ["processing"]
        self.assertIsNone(heygen.render(self.d, poll=0, wait=0))
        self.assertIn("isn't resubmitted", self.brief()["render"]["message"])
        self.states[:] = ["completed"]
        heygen.render(self.d, poll=0)
        self.assertEqual(len(self.made("create_video_from_avatar")), 1)
        self.assertEqual(self.brief()["render"]["status"], "done")

    def test_a_failed_render_says_why(self):
        from aie.connectors import heygen
        (self.d / "script_tts.txt").write_text("namaste", encoding="utf-8")
        heygen.preview(self.d, self.rotation)
        b = self.brief()
        b["look"] = {"id": "look-7", "name": "x"}
        (self.d / "brief.json").write_text(json.dumps(b))
        heygen.approve(self.d, True)
        self.states[:] = ["failed"]
        done = threading.Event()
        heygen.start_render(self.d, on_done=done.set)
        for _ in range(200):
            if (self.brief().get("render") or {}).get("status") == "failed":
                break
            time.sleep(0.02)
        self.assertEqual(self.brief()["render"]["message"], "AvatarError: HeyGen: audio too short")
        self.assertFalse(done.is_set())


@unittest.skipUnless(HAVE and shutil.which("ffmpeg"), "needs mcp, anthropic, fastapi, httpx, python-multipart, ffmpeg")
class HiggsfieldTest(unittest.TestCase):
    def setUp(self):
        from aie.connectors import mcp
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "srv").mkdir()
        ff("-f", "lavfi", "-i", "testsrc=s=1080x1920:r=25:d=1", "-pix_fmt", "yuv420p", self.tmp / "srv/clip.mp4")
        self.files = Files(self.tmp / "srv")
        self.calls, self.results = [], ["processing", "completed"]
        self.targets = mock.patch.dict(mcp.TARGETS, {"higgsfield": fake_higgsfield(self.files, 4, self.results, self.calls)})
        self.targets.start()
        self.d = self.tmp / "job"
        self.d.mkdir()

    def tearDown(self):
        self.targets.stop()
        self.files.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def gen(self, name="sky", **kw):
        from aie.connectors import higgsfield
        return higgsfield.generate(self.d, name, "a calm sky over Mumbai, no text", poll=0, **kw)

    def test_the_credit_cap(self):
        from aie.connectors import higgsfield
        with mock.patch.dict(os.environ, {"HIGGSFIELD_CREDIT_CAP": ""}):
            self.assertIn("hasn't set a credit cap", self.gen())
        self.assertEqual(self.calls, [])
        with mock.patch.dict(os.environ, {"HIGGSFIELD_CREDIT_CAP": "10"}):
            self.assertEqual(self.gen("Bad Name"), "name: 1-40 lowercase letters, digits, - or _")
            first = self.gen("sky")
            self.assertTrue(first.startswith("saved raw/gen_sky.mp4 (4 credits; 6 of the 10 cap left)"), first)
            self.results[:] = ["completed"]
            self.assertIn("2 of the 10 cap left", self.gen("sea"))
            third = self.gen("city")
            self.assertIn("costs 4 credits and 2 of the 10 cap are left", third)
        submits = [p for n, p in self.calls if n == "generate_video" and not p.get("get_cost")]
        self.assertEqual(len(submits), 2)                               # the third was only priced
        self.assertTrue(all(p["use_unlim"] is False and p["model"] == higgsfield.DEFAULT_MODEL for p in submits))
        led = higgsfield.ledger(self.d)
        self.assertEqual((led["spent"], [c["file"] for c in led["clips"]]), (8.0, ["raw/gen_sky.mp4", "raw/gen_sea.mp4"]))

    def test_a_failed_job_is_reported_not_retried(self):
        from aie.connectors import higgsfield
        self.results[:] = ["failed"]
        with mock.patch.dict(os.environ, {"HIGGSFIELD_CREDIT_CAP": "10"}):
            out = self.gen("sky")
        self.assertIn("failed", out)
        self.assertIn("Not retried; tell Paras", out)
        self.assertEqual(len([1 for n, p in self.calls if n == "generate_video" and not p.get("get_cost")]), 1)
        self.assertEqual(higgsfield.ledger(self.d)["spent"], 4.0)          # the charge is on the ledger anyway

    def test_only_the_generator_has_the_tool(self):
        from aie.agents.tools import Toolbox
        from aie.settings import load_settings
        s = load_settings(self.tmp / "none.json")
        names = lambda role: [t.name for t in Toolbox(role, self.d, s).tools()]
        self.assertIn("generate_clip", names("Generator"))
        self.assertNotIn("generate_clip", names("Story Editor"))
        with mock.patch.dict(os.environ, {"HIGGSFIELD_CREDIT_CAP": "10"}):
            out = Toolbox("Generator", self.d, s).generate_clip("sky", "a calm sky")
        self.assertTrue(out.startswith("saved raw/gen_sky.mp4"), out)


@unittest.skipUnless(HAVE and shutil.which("ffmpeg"), "needs mcp, anthropic, fastapi, httpx, python-multipart, ffmpeg")
class AvatarRoutesTest(HeyGenTest):
    """The same flow through the app: preview, approve, render, then transcribe and the storyboard are queued."""

    def test_preview_approve_render(self):
        from fastapi.testclient import TestClient
        from aie.app.server import create_app
        from aie.connectors import mcp
        from aie.settings import load_settings
        repo = self.tmp
        (repo / "settings.json").write_text(json.dumps({"min_free_gb": 0, "avatar_rotation": str(self.rotation)}))
        ran = []
        env = mock.patch.dict(os.environ, {"AIE_SECRETS": str(repo / "secrets.local.json")})
        env.start()
        from aie.connectors import heygen
        fast = mock.patch.object(heygen, "POLL", 0)
        fast.start()
        self.addCleanup(fast.stop)
        app = create_app(repo, repo / "app_data", load_settings(repo / "settings.json"),
                         lambda job, s, stage, force, log: ran.append(stage) or {})
        try:
            c = TestClient(app)
            pid = next(p["id"] for p in c.get("/api/projects").json() if p["path"] == "jobs/av")
            self.assertIsNone(c.get(f"/api/projects/{pid}").json()["connectors"]["heygen"])
            self.assertEqual(c.post(f"/api/projects/{pid}/avatar/approve", json={"value": True}).status_code, 409)
            self.assertEqual(c.post(f"/api/projects/{pid}/brief", json={"pron_approved": True}).status_code, 400)
            (self.d / "script_tts.txt").write_text("namaste", encoding="utf-8")
            r = c.post(f"/api/projects/{pid}/avatar/preview")
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(c.get(f"/media/{pid}/pron/preview.wav").status_code, 200)
            c.post(f"/api/projects/{pid}/brief", json={"look": {"id": "look-7", "name": "Cleaned Look"}})
            self.assertTrue(c.post(f"/api/projects/{pid}/avatar/approve", json={"value": True}).json()["pron_approved"])
            self.assertIn("rendering on HeyGen", c.post(f"/api/projects/{pid}/avatar/render").json()["message"])
            for _ in range(300):
                if ran[-1:] == ["storyboard"]:
                    break
                time.sleep(0.02)
            self.assertEqual(ran, ["transcribe", "storyboard"], self.brief().get("render"))
            p = c.get(f"/api/projects/{pid}").json()
            self.assertEqual((p["brief"]["render"]["status"], p["errors"]), ("done", []))
            with mock.patch.dict(mcp.TARGETS, clear=True):
                r = c.post(f"/api/projects/{pid}/avatar/render")
                self.assertEqual(r.status_code, 409)
                self.assertIn("MCP server URL isn't set", r.json()["detail"])
        finally:
            app.state.worker.stop()
            app.state.db.close()
            env.stop()

    test_a_slow_render_is_polled_again_not_resubmitted = None
    test_a_failed_render_says_why = None


if __name__ == "__main__":
    unittest.main()
