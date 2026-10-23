"""The picture stages issue the ffmpeg commands the shipped reels' own compose scripts ran (reel-05: compose.py;
reel-04: prep.py + compose.py), recorded instead of run since the footage isn't in the repo; then a small synthetic
job renders for real, end to end, and its frames, length and loudness are checked."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aie import picture, runner
from aie.job import load_job, save_job
from aie.settings import REPO, load_settings

HAVE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "soundfile", "PIL"))
RECORD = REPO / "tests/legacy/record_cmds.py"
LEGACY_FONTS = 'FONTS = r"C:\\Users\\PARAS ARORA\\AI_Editor\\fonts"'


def is_video(cmd) -> bool:
    return cmd[0] == "ffmpeg" and ("libx264" in cmd or "+faststart" in cmd or "concat" in cmd)


def norm(cmds, table) -> list:
    """Paths replaced by names, longest first, so the two sides' different folders compare equal."""
    pairs = sorted(((str(k), v) for k, v in table.items()), key=lambda kv: -len(kv[0]))
    out = []
    for c in cmds:
        s = json.dumps(c)
        for k, v in pairs:
            s = s.replace(k, v)
        out.append(json.loads(s))
    return out


def legacy(script: Path, dst: Path, *args, fonts=None) -> list:
    """Copy a shipped script (and its folder's plan.py) to dst and run it with its commands recorded."""
    dst.mkdir(parents=True, exist_ok=True)
    text = script.read_text(encoding="utf-8")
    if fonts:
        assert LEGACY_FONTS in text
        text = text.replace(LEGACY_FONTS, f"FONTS = {str(fonts)!r}")
    (dst / script.name).write_text(text, encoding="utf-8")
    if (script.parent / "plan.py").exists():
        shutil.copy(script.parent / "plan.py", dst / "plan.py")
    rec = dst / f"{script.stem}_cmds.json"
    subprocess.run([sys.executable, RECORD, rec, dst / script.name, *args], check=True, capture_output=True)
    return json.loads(rec.read_text(encoding="utf-8"))


class Recorder:
    """Stands in for subprocess.run inside the pipeline: records each call and answers measurements."""

    def __init__(self, durations):
        self.cmds, self.calls, self.durations = [], [], durations

    def __call__(self, cmd, *a, **k):
        cmd = [str(c) for c in cmd]
        self.cmds.append(cmd)
        self.calls.append((cmd, k))
        out = "60.0\n"
        if cmd[0] == "ffprobe":
            out = f"{self.durations[Path(cmd[-1]).name]}\n"
        if cmd[0] == sys.executable:            # a custom base script: it writes AIE_OUT
            Path(k["env"]["AIE_OUT"]).write_bytes(b"")
        return subprocess.CompletedProcess(cmd, 0, out, "  Summary:\n  I: -14.0 LUFS\n  Peak: -1.6 dBFS\n")


def touch(*paths):
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")


def fake_mix(job_dir):
    return lambda job, *a, **k: {"key": "m", "variants": {n: {"path": str(job_dir / "build" / f"audio_{n}.wav")}
                                                           for n in job.data["variants"]}}


def totals(job, prefix):
    return {f"{prefix}_{n}.mp4": sum(b - a for a, b in v["ranges"]) + v["freeze"] for n, v in job["variants"].items()}


@unittest.skipUnless(HAVE, "needs numpy, scipy, soundfile and Pillow")
class Reel05PictureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = d = Path(tempfile.mkdtemp()).resolve()
        (d / "aie.local.json").write_text(json.dumps({"min_free_gb": 0}))
        cls.s = s = load_settings(d / "aie.local.json")
        L, N = d / "legacy", d / "new"
        cls.old = legacy(REPO / "shorts/reel-05/edit/compose.py", L / "edit", fonts=s.path("fonts"))
        src = REPO / "shorts/reel-05"
        N.mkdir()
        for f in ("job.json", "script.txt", "edit/fa_out.json", "edit/cover_src.png"):
            (N / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src / f, N / f)
        job = json.loads((src / "job.json").read_text(encoding="utf-8"))
        touch(*(N / v["path"] for v in job["sources"].values()), N / "gfx/render.webm")
        rec = Recorder(totals(job, "REEL05"))
        with mock.patch("subprocess.run", rec), mock.patch.object(runner, "stage_mix", fake_mix(N)):
            cls.report = runner.run(load_job(N, s), s, "deliver", log=lambda *_: None)
        cls.new = rec.cmds
        table = {L / "edit/card_mask.png": "MASK", N / "build/card_mask.png": "MASK",
                 L / "edit/card_border.png": "BORDER", N / "build/card_border.png": "BORDER",
                 L / "edit/base_video.mp4": "BASE", N / "build/base.mp4": "BASE",
                 L / "edit/video_master.mp4": "MASTER", N / "build/picture.mp4": "MASTER",
                 L / "edit/captions.ass": "ASS", N / "build/captions.ass": "ASS", L: "JOB", N: "JOB"}
        for n in job["variants"]:
            table.update({L / f"edit/v_{n}.mp4": f"V_{n}", N / f"build/video_{n}.mp4": f"V_{n}",
                          L / f"edit/a_{n}.wav": f"A_{n}", N / f"build/audio_{n}.wav": f"A_{n}",
                          L / f"REEL05_{n}.mp4": f"OUT_{n}", N / f"build/publish/REEL05_{n}.mp4": f"OUT_{n}"})
        cls.table = table

    def test_commands_match_the_shipped_compose(self):
        old = norm([c for c in self.old if is_video(c)], self.table)
        new = norm([c for c in self.new if is_video(c)], self.table)
        self.assertEqual(len(new), 6)          # base, master, then cut + mux for each variant
        for i, (a, b) in enumerate(zip(old, new)):
            with self.subTest(command=i):
                self.assertEqual(b, a)
        self.assertEqual(len(new), len(old))

    def test_card_mask_and_border_match(self):
        from PIL import Image
        import numpy as np
        for f in ("card_mask.png", "card_border.png"):
            with self.subTest(f=f):
                a = np.array(Image.open(self.d / "legacy/edit" / f))
                b = np.array(Image.open(self.d / "new/build" / f))
                self.assertTrue(np.array_equal(a, b))

    def test_final_names_and_lengths(self):
        v = self.report["variants"]
        self.assertTrue(v["instagram"]["path"].endswith("REEL05_instagram.mp4"))
        self.assertEqual((v["instagram"]["seconds"], v["youtube"]["seconds"]), (54.4, 53.64))

    def test_captions_and_srt_ride_along(self):
        pub = self.d / "new/build/publish"
        self.assertEqual(sorted(p.name for p in pub.iterdir()),
                         ["REEL05_instagram.srt", "REEL05_youtube.srt", "cover.jpg"])   # the mp4s were recorded


@unittest.skipUnless(HAVE, "needs numpy, scipy, soundfile and Pillow")
class Reel04PictureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = d = Path(tempfile.mkdtemp()).resolve()
        dl = d / "downloads"
        (d / "aie.local.json").write_text(json.dumps({"min_free_gb": 0, "roots": {"downloads": str(dl)}}))
        cls.s = s = load_settings(d / "aie.local.json")
        src = REPO / "shorts/reel-04"
        job = json.loads((src / "job.json").read_text(encoding="utf-8"))
        files = {n: dl / v["path"].split("/", 1)[1] for n, v in job["sources"].items()}
        touch(*files.values())
        L, N = d / "legacy", d / "new"
        tl = json.loads((src / "edit/timeline.json").read_text(encoding="utf-8"))
        tl["files"] = {n: str(p) for n, p in files.items()}
        (L / "edit").mkdir(parents=True)
        (L / "edit/timeline.json").write_text(json.dumps(tl))
        touch(L / "edit/base_video.mp4", L / "edit/captions.ass", L / "gfx/render.webm")
        cls.old = legacy(src / "edit/prep.py", L / "edit") + legacy(src / "edit/compose.py", L / "edit")
        N.mkdir()
        for f in ("job.json", "edit/fa_a.json", "edit/fa_b.json", "edit/compose_base.py"):
            (N / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src / f, N / f)
        touch(N / "gfx/render.webm")
        rec = cls.rec = Recorder(totals(job, "REEL04"))
        with mock.patch("subprocess.run", rec), mock.patch.object(runner, "stage_mix", fake_mix(N)):
            runner.run(load_job(N, s), s, "deliver", log=lambda *_: None)
        cls.L, cls.N = L, N
        table = {L / "edit/segs": "SEGS", N / "build/segs": "SEGS",
                 L / "edit/face_concat.txt": "LIST", N / "build/segs.txt": "LIST",
                 L / "edit/base_face.mp4": "FOOT", N / "build/base_footage.mp4": "FOOT",
                 L / "edit/base_video.mp4": "BASE", N / "build/base.mp4": "BASE",
                 L / "edit/video_master.mp4": "MASTER", N / "build/picture.mp4": "MASTER", L: "JOB", N: "JOB"}
        for n in job["variants"]:
            table.update({L / f"edit/v_{n}.mp4": f"V_{n}", N / f"build/video_{n}.mp4": f"V_{n}",
                          L / f"edit/a_{n}.wav": f"A_{n}", N / f"build/audio_{n}.wav": f"A_{n}",
                          L / f"REEL04_{n}.mp4": f"OUT_{n}", N / f"build/publish/REEL04_{n}.mp4": f"OUT_{n}"})
        cls.table = table

    def test_commands_match_the_shipped_prep_and_compose(self):
        old = norm([c for c in self.old if is_video(c)], self.table)
        new = norm([c for c in self.rec.cmds if is_video(c)], self.table)
        self.assertEqual(len(new), 10 + 1 + 1 + 4)     # pieces, concat, master, cut + mux per variant
        for i, (a, b) in enumerate(zip(old, new)):
            with self.subTest(command=i):
                self.assertEqual(b, a)
        self.assertEqual(len(new), len(old))

    def test_concat_list_matches(self):
        a = (self.L / "edit/face_concat.txt").read_text()
        b = (self.N / "build/segs.txt").read_text()
        self.assertEqual(norm([b], self.table), norm([a], self.table))

    def test_custom_base_script_gets_its_paths(self):
        calls = [(c, k) for c, k in self.rec.calls if c[0] == sys.executable]
        self.assertEqual(len(calls), 1)
        cmd, k = calls[0]
        self.assertEqual(cmd[1], str(self.N / "edit/compose_base.py"))
        self.assertEqual(Path(k["cwd"]), self.N / "edit")
        self.assertEqual((k["env"]["AIE_IN"], k["env"]["AIE_OUT"]),
                         (str(self.N / "build/base_footage.mp4"), str(self.N / "build/base.mp4")))

    def test_legacy_script_still_runs_on_its_own(self):
        """The pipeline patch to compose_base.py keeps its own paths when AIE_IN / AIE_OUT aren't set."""
        text = (REPO / "shorts/reel-04/edit/compose_base.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("AIE_IN", ED / "base_face.mp4")', text)
        self.assertIn('ED / ("base_test.mp4" if len(sys.argv) > 2 else "base_video.mp4")', text)


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)


def pixel(video, t, x, y):
    """RGB of one point at time t (2x2 block averaged: yuv420 chroma is shared by 2x2 pixels)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-vf",
                          f"crop=2:2:{x}:{y},scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return tuple(raw)


@unittest.skipUnless(HAVE and shutil.which("ffmpeg"), "needs ffmpeg and the media libraries")
class SyntheticRenderTest(unittest.TestCase):
    """A 3-second avatar job rendered for real: hook, split card and face beats, a transparent graphics layer, one
    catalog effect shown in one variant only (its HyperFrames render stood in by an ffmpeg one), voice only."""

    @classmethod
    def setUpClass(cls):
        cls.d = d = Path(tempfile.mkdtemp()).resolve()
        fx = d / "effects/box"
        fx.mkdir(parents=True)
        (fx / "box.html").write_text("<div data-duration=\"{{DUR}}\">{{WORD}}<img src=\"{{LOGO}}\"></div>")
        (fx / "box.css").write_text("div {}")
        (fx / "effect.json").write_text(json.dumps({
            "name": "box", "title": "Test box", "kind": "overlay", "engine": "hyperframes-template",
            "source": "box.html", "files": ["box.css"], "formats": ["9:16"],
            "params": {"WORD": {"default": "hi"}, "LOGO": {"type": "file", "required": True}},
            "duration": {"default": 1.0}, "origin": "test", "license": "own", "example": {"LOGO": "logo.png"}}))
        (d / "aie.local.json").write_text(json.dumps({"min_free_gb": 0, "effects": str(d / "effects")}))
        cls.s = load_settings(d / "aie.local.json")
        j = d / "job"
        (j / "gfx").mkdir(parents=True)
        (j / "logo.png").write_bytes(b"PNG")
        # the avatar: a green 1920x1080 frame with a white box (where both crops look) and a 440 Hz voice
        ff("-f", "lavfi", "-i", "color=c=0x22AA44:s=1920x1080:r=25:d=4", "-f", "lavfi", "-i",
           "aevalsrc='0.3*sin(2*PI*440*t)*gt(sin(2*PI*1.7*t+1.3*sin(2*PI*0.4*t)),0.2)':s=48000:d=4",   # voice-like bursts
           "-vf", "drawbox=x=900:y=300:w=120:h=120:c=white:t=fill",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", j / "avatar.mp4")
        ff("-f", "lavfi", "-i", "color=c=0x2244CC:s=1080x1920:r=25:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           j / "hook.mp4")
        # graphics: a red bar across the top on a transparent frame, the whole video long
        ff("-f", "lavfi", "-i", "color=c=0xFF0000@0.0:s=1080x1920:r=25:d=3,format=yuva420p,"
           "drawbox=x=0:y=0:w=1080:h=200:c=0xFF0000@1.0:t=fill:replace=1", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
           j / "gfx/render.webm")
        save_job(j, {
            "id": "synth-01", "mode": "avatar", "fps": 25, "size": [1080, 1920],
            "sources": {"avatar": {"path": "avatar.mp4", "voice_offset": 0.2}, "hook": {"path": "hook.mp4"}},
            "timeline": [{"t": [0.0, 1.0], "layout": "hook", "src": "hook", "in": 0.0},
                         {"t": [1.0, 2.0], "layout": "split", "src": "avatar", "in": 1.2},
                         {"t": [2.0, 3.0], "layout": "face", "src": "avatar", "in": 2.2}],
            "layouts": {"split": {"card": [97, 975, 886, 924], "crop": [840, 876, 540, 50]},
                        "face": {"crop": [608, 1080, 656, 0]}},
            "variants": {"instagram": {"ranges": [[0.0, 3.0]], "freeze": 0.4},
                         "youtube": {"ranges": [[0.0, 1.0], [2.0, 3.0]]}},
            "graphics": {"render": "gfx/render.webm"},
            "effects": [{"effect": "box", "at": 2.0, "variants": ["youtube"], "params": {"LOGO": "logo.png"}}],
            "mix": {"voice": "avatar", "tail": 0.5},
            "gates": {"storyboard_approved": True, "final_approved": False},
        })

        def stand_in(settings, folder, fps, out):      # what HyperFrames would render: a white square for 1 s
            assert (folder / "index.html").read_text() == "<div data-duration=\"1.0\">hi<img src=\"asset_logo.png\"></div>"
            assert (folder / "box.css").exists() and (folder / "asset_logo.png").read_bytes() == b"PNG"
            ff("-f", "lavfi", "-i", "color=c=white@0.0:s=1080x1920:r=25:d=1,format=yuva420p,"
               "drawbox=x=440:y=1600:w=200:h=200:c=white@1.0:t=fill:replace=1", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", out)

        cls.log = []
        with mock.patch.object(runner, "_hyperframes", stand_in):
            cls.rep = runner.run(load_job(j, cls.s), cls.s, "deliver", log=cls.log.append)
        cls.pub = j / "build/publish"

    @unittest.skipUnless(importlib.util.find_spec("opentimelineio"), "needs opentimelineio")
    def test_nle_timeline(self):
        import opentimelineio as otio
        j = load_job(self.d / "job", self.s)
        rep = runner.run(j, self.s, "otio", log=lambda *_: None)
        tl = otio.adapters.read_from_file(rep["otio"])
        self.assertEqual([t.name for t in tl.tracks], ["V1 originals", "V2 base", "V3 graphics", "V4 effects", "A1 voice"])
        self.assertFalse(tl.tracks[0].enabled)
        spans = lambda t: [(c.name, t.range_of_child(c).start_time.to_seconds(), c.duration().to_seconds(),
                            c.source_range.start_time.to_seconds()) for c in t if isinstance(c, otio.schema.Clip)]
        self.assertEqual(spans(tl.tracks[0]), [("beat 1 hook", 0.0, 1.0, 0.0), ("beat 2 avatar", 1.0, 1.0, 1.2),
                                               ("beat 3 avatar", 2.0, 1.0, 2.2)])
        self.assertEqual(spans(tl.tracks[3]), [("00_box", 2.0, 1.0, 0.0)])     # where the picture shows it
        self.assertEqual(tl.duration().to_seconds(), 3.0)
        self.assertEqual([m.name for m in tl.tracks.markers], ["beat 1: hook", "beat 2: split", "beat 3: face"])
        for t in tl.tracks:
            for c in t:
                if isinstance(c, otio.schema.Clip):
                    self.assertTrue(Path(otio.url_utils.filepath_from_url(c.media_reference.target_url)).exists())
        xml = Path(rep["xml"]).read_text()
        self.assertEqual((xml.count("<marker>"), xml.count("<enabled>FALSE</enabled>")), (3, 1))
        self.assertEqual(runner.run(j, self.s, "otio", log=lambda *_: None)["key"], rep["key"])   # up to date

    def test_preview_until_approved(self):
        self.assertEqual(sorted(p.name for p in self.pub.glob("*.mp4")),
                         ["SYNTH01_instagram_PREVIEW.mp4", "SYNTH01_youtube_PREVIEW.mp4"])
        self.assertFalse(self.rep["final"])
        self.assertTrue(any("PREVIEW quality" in m for m in self.log))

    def test_lengths_and_loudness(self):
        v = self.rep["variants"]
        self.assertAlmostEqual(v["instagram"]["seconds"], 3.4, delta=0.05)
        self.assertAlmostEqual(v["youtube"]["seconds"], 2.0, delta=0.05)
        for name, x in v.items():
            with self.subTest(variant=name):
                self.assertAlmostEqual(x["lufs"], -14.0, delta=1.0)
                self.assertLessEqual(x["true_peak"], -1.0)

    def test_layouts_land_where_the_job_says(self):
        ig = self.pub / "SYNTH01_instagram_PREVIEW.mp4"
        checks = [(0.5, 540, 1000, (0x22, 0x44, 0xCC), "hook fills the frame"),
                  (1.5, 40, 1000, (0x0C, 0x0E, 0x0F), "void around the split card"),
                  (1.5, 540, 1800, (0x22, 0xAA, 0x44), "avatar inside the card"),
                  (1.5, 540, 1300, (0xFF, 0xFF, 0xFF), "the card shows the crop window from layouts.split"),
                  (2.5, 540, 1500, (0x22, 0xAA, 0x44), "face beat fills the frame"),
                  (2.5, 540, 640, (0xFF, 0xFF, 0xFF), "the face beat shows the crop window from layouts.face"),
                  (1.5, 540, 100, (0xFF, 0x00, 0x00), "graphics layer on top"),
                  (3.2, 540, 640, (0xFF, 0xFF, 0xFF), "the freeze holds the last frame")]
        for t, x, y, want, what in checks:
            with self.subTest(what):
                got = pixel(ig, t, x, y)
                self.assertTrue(all(abs(a - b) < 24 for a, b in zip(got, want)), f"{got} != {want}")

    def test_effect_only_in_its_variant(self):
        ig, yt = self.pub / "SYNTH01_instagram_PREVIEW.mp4", self.pub / "SYNTH01_youtube_PREVIEW.mp4"
        white = lambda p: all(c > 230 for c in p)
        self.assertFalse(white(pixel(yt, 0.5, 540, 1700)))       # before the effect
        self.assertTrue(white(pixel(yt, 1.5, 540, 1700)))        # master 2.0-3.0 is youtube's 1.0-2.0
        self.assertFalse(white(pixel(ig, 2.5, 540, 1700)))       # instagram doesn't show it
        self.assertTrue((self.d / "job/build/picture_youtube.mp4").exists())

    def test_rerun_is_up_to_date(self):
        log = []
        runner.run(load_job(self.d / "job", self.s), self.s, "deliver", log=log.append)
        self.assertEqual(log, ["deliver: up to date"])

    def test_storyboard(self):
        rep = runner.run(load_job(self.d / "job", self.s), self.s, "storyboard", log=lambda *_: None)
        b = self.d / "job/build"
        self.assertEqual([r["layout"] for r in rep["beats"]], ["hook", "split", "face"])
        self.assertTrue(all((b / r["still"]).exists() for r in rep["beats"]))
        self.assertIn("#1 Test box @2.00", rep["beats"][2]["on_screen"][-1])
        page = (b / "storyboard.html").read_text()
        self.assertIn("3 beats", page)
        from PIL import Image
        still = Image.open(b / rep["beats"][1]["still"]).convert("RGB")      # split: void outside, avatar in the card
        k = still.width / 1080
        self.assertTrue(all(abs(a - c) < 20 for a, c in zip(still.getpixel((int(40 * k), int(1000 * k))), (12, 14, 15))))
        self.assertTrue(all(abs(a - c) < 30 for a, c in zip(still.getpixel((int(540 * k), int(1800 * k))), (0x22, 0xAA, 0x44))))

    def test_gate_holds_the_picture_until_the_storyboard_is_approved(self):
        job = load_job(self.d / "job", self.s)
        job.data["gates"]["storyboard_approved"] = False
        with self.assertRaisesRegex(runner.StageError, "storyboard isn't approved"):
            runner.run(job, self.s, "picture", log=lambda *_: None)

    def test_qa_audit(self):
        log = []
        rep = runner.run(load_job(self.d / "job", self.s), self.s, "qa", log=log.append)
        c = rep["checks"]
        for name in ("length", "loudness", "sync", "spelling", "safe_zone", "on_word", "compliance", "hook"):
            with self.subTest(check=name):
                self.assertEqual(c[name]["status"], "OK", c[name]["summary"])
        self.assertLessEqual(max(abs(r["lag_ms"]) for rs in c["sync"]["rows"].values() for r in rs), 10)
        self.assertIn(c["words"]["status"], ("OK", "NOT RUN"))
        self.assertTrue(rep["passed"])
        self.assertTrue(all(Path(x).exists() for x in rep["sheets"]))
        self.assertTrue(log[0].startswith("QA 10.0/10  PASS") or log[0].startswith("QA 9."), log[0])


class LockTest(unittest.TestCase):
    def test_one_render_at_a_time(self):
        if os.name == "nt":
            self.skipTest("flock check is POSIX; Windows uses msvcrt.locking")
        import fcntl
        with open(runner.LOCK_FILE, "a+") as other:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)        # another process holds the lock
            try:
                with self.assertRaises(runner.StageError):
                    with runner.render_lock():
                        pass
            finally:
                fcntl.flock(other, fcntl.LOCK_UN)
        with runner.render_lock():                                   # free again; and re-entrant
            with runner.render_lock():
                pass


class MasterGraphTest(unittest.TestCase):
    def test_reel04_graph(self):
        cmd = picture.master_cmd("base.mp4", 30, 67.5667, "out.mp4", "render.webm")
        self.assertEqual(cmd[cmd.index("-filter_complex") + 1],
                         "[1:v]fps=30,format=yuva420p[g];[0:v][g]overlay=0:0:format=auto,format=yuv420p[v]")

    def test_effects_chain_over_graphics(self):
        cmd = picture.master_cmd("b.mp4", 25, 3.0, "o.mp4", "g.webm", effects=[{"path": "e.webm", "at": 1.0},
                                                                             {"path": "f.webm", "at": 2.0}])
        self.assertEqual(cmd[cmd.index("-filter_complex") + 1],
                         "[1:v]fps=25,format=yuva420p[g];"
                         "[2:v]fps=25,format=yuva420p,setpts=PTS-STARTPTS+1.0/TB[e0];"
                         "[3:v]fps=25,format=yuva420p,setpts=PTS-STARTPTS+2.0/TB[e1];"
                         "[0:v][g]overlay=0:0:format=auto[c0];[c0][e0]overlay=0:0:format=auto:eof_action=pass[c1];"
                         "[c1][e1]overlay=0:0:format=auto:eof_action=pass,format=yuv420p[v]")


if __name__ == "__main__":
    unittest.main()
