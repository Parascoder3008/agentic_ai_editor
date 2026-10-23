"""The local web app's API: projects from briefs, the render queue, notes routed to their owners, the two gates,
connections with secrets never shown, media served safely, Drive delivery held until it's approved and passes QA."""
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HAVE = all(importlib.util.find_spec(m) for m in ("fastapi", "httpx", "multipart", "numpy", "PIL"))


def clip(path: Path, size="1920x1080", seconds=2):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=s={size}:r=25:d={seconds}", "-f", "lavfi",
                    "-i", f"sine=frequency=300:duration={seconds}", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)],
                   check=True)


@unittest.skipUnless(HAVE and shutil.which("ffmpeg"), "needs fastapi, httpx, python-multipart and ffmpeg")
class AppTest(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from aie.app.server import create_app
        from aie.settings import load_settings
        self.repo = Path(tempfile.mkdtemp()).resolve()
        (self.repo / "settings.json").write_text(json.dumps({"min_free_gb": 0}))
        self.env = mock.patch.dict(os.environ, {"AIE_SECRETS": str(self.repo / "secrets.local.json")})
        self.env.start()
        self.calls = []

        def fake_run(job, settings, stage, force, log):        # the render queue with a stand-in runner
            self.calls.append((job.id, stage, force))
            log(f"{stage}: pretend")
            if stage in ("deliver", "all"):
                pub = job.dir / "build/publish"
                pub.mkdir(parents=True, exist_ok=True)
                (pub / "X_instagram.mp4").write_bytes(b"mp4")
                (job.dir / "build/deliver.json").write_text(json.dumps(
                    {"final": job.data["gates"].get("final_approved", False),
                     "variants": {"instagram": {"path": str(pub / "X_instagram.mp4"), "seconds": 2.0, "lufs": -14.0,
                                                "true_peak": -2.0}}}))
            return {"ok": True}

        self.app = create_app(self.repo, self.repo / "app_data", load_settings(self.repo / "settings.json"), fake_run)
        self.c = TestClient(self.app)

    def tearDown(self):
        self.app.state.worker.stop()
        self.app.state.worker.thread.join(timeout=5)
        self.app.state.db.close()
        self.env.stop()

    def brief(self, files=(), **b):
        body = {"mode": "footage", "title": "Test reel", "platforms": ["instagram", "youtube"], **b}
        up = [("files", (Path(f).name, open(f, "rb"), "video/mp4")) for f in files]
        r = self.c.post("/api/projects", data={"brief": json.dumps(body)}, files=up or None)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def wait(self, rid):
        for _ in range(100):
            r = self.c.get(f"/api/runs/{rid}").json()
            if r["status"] in ("done", "failed"):
                return r
            time.sleep(0.05)
        self.fail("the run never finished")

    def test_footage_brief_becomes_a_runnable_job(self):
        clip(self.repo / "take.mp4")
        made = self.brief([self.repo / "take.mp4"], cta="AGENT")
        p = self.c.get(f"/api/projects/{made['id']}").json()
        self.assertEqual(p["errors"], [])
        job = p["job"]
        self.assertEqual((job["fps"], job["size"]), (25, [1080, 1920]))
        self.assertEqual(job["layouts"]["camera"]["crop"], [606, 1080, 657, 0])       # a 9:16 window of the 16:9 take
        self.assertEqual(job["sources"]["a"], {"path": "raw/take.mp4", "rights": "own"})
        self.assertEqual(job["cut"]["keep"][0][:2], [0.0, 2.0])
        self.assertEqual(set(job["variants"]), {"instagram", "youtube"})
        self.assertEqual(p["next"], "storyboard")
        self.assertIn("transcribe", [s["stage"] for s in p["stages"]])

    def test_client_brief_marks_footage_as_the_clients(self):
        clip(self.repo / "c.mp4", "1080x1920")
        made = self.brief([self.repo / "c.mp4"], mode="client", client="Venom Tech")
        job = self.c.get(f"/api/projects/{made['id']}").json()["job"]
        self.assertTrue(made["path"].startswith("clients/"))
        self.assertEqual(job["sources"]["a"]["rights"], "client")
        self.assertNotIn("crop", job["layouts"]["camera"])                            # already 9:16

    def test_avatar_brief_waits_for_its_script(self):
        made = self.brief(mode="avatar", topic="Kapso", script="Claude ko ab apna WhatsApp number mil sakta hai.")
        p = self.c.get(f"/api/projects/{made['id']}").json()
        self.assertFalse(p["has_job"])
        self.assertEqual(p["next"], "avatar")                       # the script is in: next is the avatar studio
        self.assertIn("WhatsApp", p["script"])
        bare = self.brief(mode="avatar", topic="Kapso")
        self.assertEqual(self.c.get(f"/api/projects/{bare['id']}").json()["next"], "script")

    def test_runs_versions_and_gates(self):
        clip(self.repo / "take.mp4")
        pid = self.brief([self.repo / "take.mp4"])["id"]
        r = self.wait(self.c.post(f"/api/projects/{pid}/run", json={"stage": "storyboard"}).json()["run"])
        self.assertEqual((r["status"], r["log"]), ("done", "storyboard: pretend\n"))
        self.assertEqual(self.c.post(f"/api/projects/{pid}/run", json={"stage": "publish"}).status_code, 400)
        self.assertEqual(self.c.post(f"/api/projects/{pid}/gates", json={"storyboard_approved": True}).json(),
                         {"storyboard_approved": True, "final_approved": False})
        self.wait(self.c.post(f"/api/projects/{pid}/run", json={"stage": "all"}).json()["run"])
        p = self.c.get(f"/api/projects/{pid}").json()
        self.assertEqual([v["n"] for v in p["versions"]], [1])
        kept = Path(p["versions"][0]["files"]["instagram"])
        self.assertTrue(kept.exists() and "versions/v1" in kept.as_posix())
        self.wait(self.c.post(f"/api/projects/{pid}/run", json={"stage": "qa"}).json()["run"])
        self.assertEqual(len(self.c.get(f"/api/projects/{pid}").json()["versions"]), 1)      # same files: no new version
        self.assertEqual([c[1] for c in self.calls], ["storyboard", "all", "qa"])

    def test_notes_route_to_their_owners(self):
        clip(self.repo / "take.mp4")
        pid = self.brief([self.repo / "take.mp4"])["id"]
        cases = {"caption galat hai: 'clod' should be Claude": "Proofreader", "music too loud under the hook": "Sound Designer",
                 "cut the repeat here": "Cut Surgeon", "make this beat full screen": "Compositor",
                 "the chip text overlaps": "Motion Designer", "feels slow": "Story Editor"}
        for text, owner in cases.items():
            n = self.c.post(f"/api/projects/{pid}/notes", json={"t": 12.4, "variant": "instagram", "text": text}).json()
            self.assertEqual(n["owner"], owner, text)
        notes = self.c.get(f"/api/projects/{pid}/notes").json()
        fixed = self.c.patch(f"/api/notes/{notes[0]['id']}", json={"status": "fixed"}).json()
        self.assertEqual(fixed["status"], "fixed")
        r = self.c.post(f"/api/projects/{pid}/notes/send")
        self.assertEqual(r.status_code, 409)                                  # placeholder mode: no Claude key
        self.assertIn("Claude API key", r.json()["detail"])
        self.assertEqual(self.c.post(f"/api/projects/{pid}/notes", json={"text": "  "}).status_code, 400)

    def test_job_edits_are_validated(self):
        clip(self.repo / "take.mp4")
        pid = self.brief([self.repo / "take.mp4"])["id"]
        job = self.c.get(f"/api/projects/{pid}").json()["job"]
        job["fps"] = 23
        r = self.c.put(f"/api/projects/{pid}/job", json=job)
        self.assertEqual(r.status_code, 422)
        self.assertTrue(any("fps" in e for e in r.json()["detail"]["errors"]))
        job["fps"] = 25
        self.assertEqual(self.c.put(f"/api/projects/{pid}/job", json=job).status_code, 200)

    def test_connections_keep_secrets(self):
        r = self.c.get("/api/connections").json()
        self.assertEqual(r["summary"], {"set": 0, "total": 16, "agents": False})
        self.assertEqual(self.c.put("/api/connections/anthropic", json={"values": {"ANTHROPIC_API_KEY": "sk-ant-secret-1234"}}).status_code, 200)
        item = next(c for c in self.c.get("/api/connections").json()["items"] if c["id"] == "anthropic")
        self.assertEqual((item["status"], item["fields"][0]["value"]), ("set", "••••1234"))
        self.assertNotIn("sk-ant-secret", json.dumps(self.c.get("/api/connections").json()))
        self.assertEqual(json.loads((self.repo / "secrets.local.json").read_text())["ANTHROPIC_API_KEY"], "sk-ant-secret-1234")
        with mock.patch("aie.app.connections._http", return_value=(200, "")):
            self.assertEqual(self.c.post("/api/connections/anthropic/test").json(), {"ok": True, "message": "key works"})
        with mock.patch("aie.app.connections._http", return_value=(401, "Unauthorized")):
            self.assertIn("rejected", self.c.post("/api/connections/anthropic/test").json()["message"])
        item = next(c for c in self.c.get("/api/connections").json()["items"] if c["id"] == "anthropic")
        self.assertEqual(item["status"], "failed")
        self.assertEqual(self.c.put("/api/connections/anthropic", json={"values": {"NOPE": "x"}}).status_code, 400)
        self.assertEqual(self.c.post("/api/connections/heygen/test").json()["ok"], False)      # not set
        d = self.repo / "drive"
        d.mkdir()
        self.c.put("/api/connections/drive", json={"values": {"DRIVE_FOLDER": str(d)}})
        self.assertEqual(self.c.post("/api/connections/drive/test").json()["ok"], True)

    def test_media_is_served_safely(self):
        clip(self.repo / "take.mp4")
        pid = self.brief([self.repo / "take.mp4"])["id"]
        r = self.c.get(f"/media/{pid}/raw/take.mp4", headers={"Range": "bytes=0-99"})
        self.assertEqual((r.status_code, len(r.content)), (206, 100))
        self.assertEqual(self.c.get(f"/media/{pid}/../../settings.json").status_code, 404)
        self.assertEqual(self.c.get(f"/media/{pid}/%2e%2e/%2e%2e/settings.json").status_code, 404)

    def test_drive_waits_for_approval_and_qa(self):
        clip(self.repo / "take.mp4")
        pid = self.brief([self.repo / "take.mp4"])["id"]
        self.c.post(f"/api/projects/{pid}/gates", json={"storyboard_approved": True})
        self.wait(self.c.post(f"/api/projects/{pid}/run", json={"stage": "all"}).json()["run"])
        self.assertIn("approve the final", self.c.post(f"/api/projects/{pid}/drive").json()["detail"])
        self.c.post(f"/api/projects/{pid}/gates", json={"final_approved": True})
        self.assertIn("QA", self.c.post(f"/api/projects/{pid}/drive").json()["detail"])
        d = self.repo / self.c.get(f"/api/projects/{pid}").json()["path"]
        (d / "build/qa").mkdir(parents=True)
        (d / "build/qa/qa.json").write_text(json.dumps({"score": 9.9, "passed": True, "checks": {}}))
        self.assertIn("Drive folder", self.c.post(f"/api/projects/{pid}/drive").json()["detail"])
        drive = self.repo / "drive"
        drive.mkdir()
        self.c.put("/api/connections/drive", json={"values": {"DRIVE_FOLDER": str(drive)}})
        r = self.c.post(f"/api/projects/{pid}/drive").json()
        self.assertEqual(r["files"], ["X_instagram.mp4"])
        self.assertTrue((Path(r["folder"]) / "X_instagram.mp4").exists())

    def test_avatar_tools(self):
        pid = self.brief(mode="avatar", script="Claude ka apna number")["id"]
        self.assertEqual(self.c.post(f"/api/projects/{pid}/avatar/tts").status_code, 400)        # no TTS script yet
        self.c.put(f"/api/projects/{pid}/script", json={"file": "script_tts.txt", "text": "{Claude|क्लॉड} का अपना number"})
        self.assertIn("क्लॉड", self.c.post(f"/api/projects/{pid}/avatar/tts").json()["text"])
        self.assertEqual(self.c.put(f"/api/projects/{pid}/script", json={"file": "../x.txt", "text": "x"}).status_code, 400)
        for step in ("preview", "render"):                       # placeholder mode: both wait for HeyGen's MCP
            r = self.c.post(f"/api/projects/{pid}/avatar/{step}")
            self.assertEqual(r.status_code, 409)
            self.assertIn("HeyGen isn't connected", r.json()["detail"])
        r = self.c.post(f"/api/projects/{pid}/avatar/approve", json={"value": True})
        self.assertEqual(r.status_code, 409)                      # nothing heard, nothing to approve
        self.assertIn("make a voice preview first", r.json()["detail"])

    def test_the_pages_and_the_library(self):
        self.assertIn('<div id="app">', self.c.get("/").text)
        for f in ("/static/js/app.js", "/static/js/screens/review.js", "/static/vendor/preact.module.js", "/static/styles.css"):
            self.assertEqual(self.c.get(f).status_code, 200, f)
        fx = self.c.get("/api/effects").json()
        self.assertEqual(fx["errors"], [])
        self.assertGreaterEqual(len(fx["effects"]), 22)
        self.assertEqual(self.c.get(fx["effects"][0]["preview"]).status_code, 200)
        styles = self.c.get("/api/styles").json()
        self.assertEqual((len(styles["styles"]), styles["errors"]), (25, []))
        self.assertEqual(self.c.get("/fonts/Inter-Bold.ttf").status_code, 200)

    def test_demo_project_is_valid(self):
        made = self.c.post("/api/demo").json()
        p = self.c.get(f"/api/projects/{made['id']}").json()
        self.assertEqual(p["errors"], [])
        self.assertEqual(p["next"], "storyboard")
        self.assertEqual(len(p["job"]["effects"]), 4)


if __name__ == "__main__":
    unittest.main()
