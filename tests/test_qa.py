"""The QA checks on their own, with inputs built to pass and to fail."""
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from aie.settings import REPO

HAVE = bool(importlib.util.find_spec("numpy"))


@unittest.skipUnless(HAVE, "needs numpy")
class QaTest(unittest.TestCase):
    def test_lag_found_in_5_ms_steps(self):
        import numpy as np
        from aie import qa
        rng = np.random.default_rng(1)
        env = np.repeat(rng.random(400) > 0.6, 160).astype(np.float32)          # 4 s of on/off bursts
        x = env * np.sin(np.arange(len(env)) * 0.3).astype(np.float32)
        for shift_ms in (0, 15, -40):
            n = int(abs(shift_ms) * 16)
            y = np.concatenate([np.zeros(n, np.float32), x])[:len(x)] if shift_ms > 0 else np.concatenate([x[n:], np.zeros(n, np.float32)])
            with self.subTest(shift=shift_ms):
                self.assertEqual(qa.lag_ms(y, x)[0], -shift_ms)          # y late by 15 ms -> -15

    def test_variant_time_map_and_cuts(self):
        from aie import qa
        f = qa.out_map([[0.0, 49.04], [53.8, 58.0]])
        self.assertEqual((f(10.0), f(50.0), round(f(54.0), 3)), (10.0, None, 49.24))
        data = {"timeline": [{"t": [0.0, 5.4]}, {"t": [5.4, 9.08]}, {"t": [9.08, 58.0]}]}
        self.assertEqual(qa.cuts(data, None, [[0.0, 49.04], [53.8, 58.0]]), [5.4, 9.08, 49.04])

    def test_hole_at_a_gated_joint(self):
        import numpy as np
        from aie import qa
        v = np.random.default_rng(2).normal(0, 3e-3, qa.SR * 2).astype(np.float32)   # room tone
        v[int(0.99 * qa.SR): int(1.01 * qa.SR)] = 0                                  # gated to silence at 1.0 s
        self.assertEqual([h["at"] for h in qa.holes(v, [0.5, 1.0])], [1.0])

    def test_spelling(self):
        from aie import qa
        w = lambda t, s: {"text": t, "start": s, "end": s + 0.3}
        found = qa.spelling([w("claude", 0), w("CLAUDE", 1), w("Claude", 2), w("Whatsapp", 3), w("hai", 4), w("hai", 4.4)],
                            ["Claude", "WhatsApp"])
        self.assertEqual([(f["found"], f["want"]) for f in found],
                         [("claude", "Claude"), ("Whatsapp", "WhatsApp"), ("hai hai", "one word (doubled)")])

    def test_caption_zone(self):
        from aie import qa
        ok = {"styles": {"Cap": {"size": 70, "margins": [150, 150], "baseline": 1000}}}
        bad = {"styles": {"Low": {"size": 66, "margins": [40, 150], "baseline": 1700}}}
        self.assertEqual(qa.caption_zone(ok, [1080, 1920]), [])
        self.assertEqual(qa.caption_zone(bad, [1080, 1920])[0]["style"], "Low")

    def test_compliance_screen(self):
        from aie import qa
        texts = [("script", "Is course se aap 50,000 per month kamao, guaranteed"),
                 ("captions", "₹2 lakh har mahine ki income"), ("effects[0].TEXT", "20% returns pakka"),
                 ("title", "Kapso free plan: 2000 messages / mahina")]
        hits = qa.claims(texts, [])
        self.assertEqual(sorted({h["where"] for h in hits}), ["captions", "effects[0].TEXT", "script"])
        self.assertEqual(qa.claims([("script", "guaranteed")], ["guaranteed"]), [])           # cleared by Paras
        self.assertEqual(len(qa.claims([("lf", "isse 80% profitability aati hai")], [])), 1)   # cut from the long-form
        self.assertEqual(qa.claims([("lf", "80% of the task by AI")], []), [])                  # kept in it
        shipped = [(f, (REPO / f).read_text(encoding="utf-8")) for f in
                   ("shorts/reel-05/script.txt", "shorts/reel-03/script.txt", "shorts/pilot-01/script.txt")]
        self.assertEqual(qa.claims(shipped, []), [])                                           # no false alarms

    def test_effects_on_their_words(self):
        from aie import qa
        words = [{"text": "comment", "start": 50.7}, {"text": "AGENT,", "start": 51.2}]
        rows = qa.on_word([{"at": 51.16, "word": "agent"}, {"at": 48.0, "word": "comment"}, {"at": 10.0}], words)
        self.assertEqual([r["off"] for r in rows], [-0.04, None])

    def test_cut_anchors_and_reused_broll(self):
        from aie import qa
        words = [{"text": "Socho,", "start": 5.44}, {"text": "raat", "start": 5.9}, {"text": "aur", "start": 9.6}]
        tl = [{"t": [0.0, 5.4], "layout": "hook", "src": "h", "in": 0.0},
              {"t": [5.4, 9.0], "layout": "broll", "src": "w", "in": 1.0},       # 'Socho' +0.04: on its word
              {"t": [9.0, 12.0], "layout": "broll", "src": "w", "in": 3.0},      # 'aur' +0.60: off; window 3-6 overlaps 1-4.6
              {"t": [12.0, 20.0], "layout": "split", "src": "a", "in": 12.0}]    # no word within 1 s: a pause
        self.assertEqual(qa.anchors(tl, words), [{"cut": 9.0, "next_word": "aur", "off": 0.6}])
        self.assertEqual(qa.reused(tl), [{"src": "w", "at": [5.4, 9.0], "window": [3.0, 4.6]}])

    def test_score_and_gate(self):
        from aie import qa
        ok = lambda: {"status": "OK"}
        self.assertEqual(qa.score({"a": ok(), "b": {"status": "NOT RUN"}}), (10.0, True))
        self.assertEqual(qa.score({"a": ok(), "b": {"status": "WARN"}}), (9.9, True))
        self.assertEqual(qa.score({"a": {"status": "FAIL"}}), (9.0, False))
        self.assertEqual(qa.score({k: {"status": "WARN"} for k in "abcdefgh"}), (9.5, True))

    @unittest.skipUnless(shutil.which("ffmpeg"), "needs ffmpeg")
    def test_still_picture_found(self):
        from aie import qa
        d = Path(tempfile.mkdtemp())
        v = d / "v.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=320x240:r=25:d=2", "-f", "lavfi", "-i",
                        "color=c=gray:s=320x240:r=25:d=4", "-filter_complex", "[0:v][1:v]concat=n=2:v=1", "-pix_fmt", "yuv420p",
                        str(v)], check=True)
        spans = qa.still_spans(v, [320, 240])
        self.assertEqual(len(spans), 1)
        self.assertAlmostEqual(spans[0][0], 2.0, delta=0.3)


if __name__ == "__main__":
    unittest.main()
