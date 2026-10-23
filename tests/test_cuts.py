import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from aie import audio, cuts, runner
from aie.job import load_job
from aie.settings import REPO, load_settings

SR = audio.SR
WORDS = [(1.00, 1.50), (1.70, 2.20), (3.00, 3.60), (4.40, 4.90), (7.00, 7.40), (7.62, 8.00)]
CLICK = (6.00, 6.05)


def voice(length=9.0, words=WORDS, click=CLICK):
    """Room tone at about -87 dBFS with 'words' (a 220 Hz tone at about -36 dBFS) and one 50 ms click."""
    rng = np.random.default_rng(1)
    x = rng.normal(0, 4e-5, int(length * SR)).astype(np.float32)
    t = np.arange(len(x)) / SR
    for a, b in list(words) + [click]:
        m = (t >= a) & (t < b)
        x[m] += (0.0224 * np.sin(2 * np.pi * 220 * t[m])).astype(np.float32)
    return x


def write_wav(path, x):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def on_grid(t, fps=25):
    return abs(t * fps - round(t * fps)) < 1e-6


class SpanCutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = audio.Envelope(voice())

    def build(self, keep, drop=()):
        return cuts.build_spans(self.env, keep, list(drop), 25, "v")

    def test_long_pauses_split_short_ones_dont(self):
        ps = self.build([[0.9, 5.0, "a"]])
        self.assertEqual(len(ps), 3)                                   # 1.0-2.2 (0.2 s pause kept), 3.0-3.6, 4.4-4.9
        for p, (a, b) in zip(ps, [(1.00, 2.20), (3.00, 3.60), (4.40, 4.90)]):
            self.assertLessEqual(p["in"], a)
            self.assertGreaterEqual(p["out"], b - 0.02)
            self.assertLess(p["out"] - p["in"], (b - a) + 0.30)        # padded, not swallowing the pause

    def test_pieces_are_frame_exact_ordered_and_laid_out(self):
        ps = self.build([[0.9, 5.0, "a"], [6.9, 8.1, "b"]])
        t = 0.0
        for a, b in zip(ps, ps[1:] + [None]):
            self.assertTrue(on_grid(a["in"]) and on_grid(a["out"] - a["in"]), a)
            self.assertAlmostEqual(a["out0"], round(t, 3))
            t += a["out"] - a["in"]
            if b:
                self.assertLessEqual(a["out"], b["in"])

    def test_drop_removes_a_word(self):
        self.assertEqual(len(self.build([[0.9, 5.0, "a"]], [[2.9, 3.7, "retake"]])), 2)

    def test_clicks_are_skipped(self):
        self.assertEqual(self.build([[5.8, 6.3, "c"]]), [])

    def test_never_pads_into_the_next_word(self):
        ps = self.build([[6.95, 7.41, "b"]])                          # keep ends mid-phrase; next word at 7.62
        self.assertEqual(len(ps), 1)
        self.assertLess(ps[0]["out"], 7.62)
        self.assertGreaterEqual(ps[0]["out"], 7.40)

    def test_minus_drops(self):
        self.assertEqual(cuts.minus_drops(1.0, 5.0, [[2.0, 3.0, "x"]]), [(1.0, 2.0), (3.0, 5.0)])
        self.assertEqual(cuts.minus_drops(1.0, 5.0, [[0.0, 1.04, "x"]]), [(1.04, 5.0)])
        self.assertEqual(cuts.minus_drops(1.0, 1.04, [[1.02, 2.0, "x"]]), [])   # slivers of <= 50 ms go

    def test_load_reads_a_wav_like_the_cutter_did(self):
        d = Path(tempfile.mkdtemp())
        write_wav(d / "v.wav", voice())
        x = audio.load(d / "v.wav")
        self.assertEqual(len(x), int(9.0 * SR))
        self.assertLess(np.abs(x - voice()).max(), 1e-4)               # 16-bit rounding only

    def test_gap_bar(self):
        line = self.env.bar(2.6)
        self.assertIn("|", line)
        self.assertIn("deepest", line)


class PiecesTest(unittest.TestCase):
    def test_reel04_output_times_match_timeline_json(self):
        job = load_job(REPO / "shorts/reel-04")
        tl = json.loads((REPO / "shorts/reel-04/edit/timeline.json").read_text())
        ps = cuts.layout_pieces(job.data["cut"]["pieces"])
        self.assertEqual([[p["out0"], round(p["out0"] + p["out"] - p["in"], 4)] for p in ps],
                         [q["out"] for q in tl["pieces"]])
        self.assertEqual(round(cuts.total(ps), 4), tl["length"])

    def test_to_output_and_sections(self):
        ps = cuts.layout_pieces([{"src": "a", "in": 10.0, "out": 12.0, "sec": "x"},
                                 {"src": "a", "in": 20.0, "out": 21.0, "sec": "y"}])
        self.assertEqual(cuts.to_output(11.0, ps), 1.0)
        self.assertEqual(cuts.to_output(15.0, ps), 2.0)                 # inside a removed gap -> next piece
        self.assertEqual(cuts.to_output(99.0, ps), 3.0)
        self.assertEqual(cuts.sections(ps), [("x", 0.0, 2.0), ("y", 2.0, 3.0)])


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.settings = load_settings(self.d / "none.json")
        self.log = []

    def run_stage(self, stage, force=False):
        return runner.run(load_job(self.d, self.settings), self.settings, stage, force, self.log.append)

    def test_cut_spans_then_up_to_date(self):
        write_wav(self.d / "voice.wav", voice())
        job = {"id": "t", "mode": "footage", "fps": 25, "size": [1080, 1920], "sources": {"v": {"path": "voice.wav"}},
               "cut": {"mode": "spans", "source": "v", "keep": [[0.9, 5.0, "a"], [6.9, 8.1, "b"]]},
               "variants": {"ig": {}}}
        (self.d / "job.json").write_text(json.dumps(job))
        res = self.run_stage("cut")
        self.assertEqual(len(res["pieces"]), 4)
        self.assertTrue((self.d / "build/pieces.json").exists())
        self.run_stage("cut")
        self.assertIn("up to date", self.log[-1])
        self.run_stage("cut", force=True)
        self.assertNotIn("up to date", self.log[-1])

    def test_cut_pieces_mode(self):
        shutil.copy(REPO / "shorts/reel-04/job.json", self.d / "job.json")
        res = self.run_stage("cut")
        self.assertEqual(res["length"], 67.5667)

    def test_missing_source_is_explained(self):
        job = {"id": "t", "mode": "footage", "fps": 25, "size": [1080, 1920], "sources": {"v": {"path": "gone.wav"}},
               "cut": {"mode": "spans", "source": "v", "keep": [[0.0, 1.0]]}, "variants": {"ig": {}}}
        (self.d / "job.json").write_text(json.dumps(job))
        with self.assertRaisesRegex(runner.StageError, "source 'v' not found"):
            self.run_stage("cut")

    def test_verify_needs_a_cut_first(self):
        shutil.copy(REPO / "shorts/reel-04/job.json", self.d / "job.json")
        with self.assertRaisesRegex(runner.StageError, "run the cut stage first"):
            self.run_stage("verify")

    def test_cli_run_and_diag(self):
        write_wav(self.d / "voice.wav", voice())
        job = {"id": "t", "mode": "footage", "fps": 25, "size": [1080, 1920], "sources": {"v": {"path": "voice.wav"}},
               "cut": {"mode": "spans", "source": "v", "keep": [[0.9, 5.0, "a"]]}, "variants": {"ig": {}}}
        (self.d / "job.json").write_text(json.dumps(job))
        r = subprocess.run([sys.executable, "-m", "aie", "run", str(self.d), "cut"], cwd=REPO,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("3 pieces", r.stdout)
        r = subprocess.run([sys.executable, "-m", "aie", "diag", "gap", str(self.d), "2.6", "3.0"], cwd=REPO,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.count("deepest"), 2)


if __name__ == "__main__":
    unittest.main()
