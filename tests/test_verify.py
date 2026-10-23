"""The ported joint checks print exactly what the long-form's own scripts printed, on its real data."""
import contextlib
import io
import json
import re
import subprocess
import sys
import unittest
import warnings

from aie import verify
from aie.settings import REPO

E = REPO / "jobs/longform-ai-editor/edit"
INTRO = 42.40


class JointsTest(unittest.TestCase):
    def test_review_joints_matches_the_original_script(self):
        old = subprocess.run([sys.executable, str(E / "review_joints.py"), str(E / "piece_tx.json")],
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
        items = [{**t, "in": t["m0"], "out": t["m1"]} for t in json.loads((E / "piece_tx.json").read_text("utf-8"))]
        js = verify.joints(items)
        self.assertEqual("\n".join(verify.format_joints(js)) + "\n", old)
        self.assertEqual(sum(j["repeat"] for j in js), 3)

    def test_repeat_report_matches_the_original_script(self):
        src = (E / "check_repeats.py").read_text(encoding="utf-8")
        src = re.sub(r'^E = r".*"$', lambda m: f"E = {str(E)!r}", src, flags=re.M).replace('E + r"\\', 'E + r"/')
        buf, argv = io.StringIO(), sys.argv
        sys.argv = ["check_repeats.py"]
        try:
            with contextlib.redirect_stdout(buf), warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)      # the original leaves its files open
                exec(compile(src, "check_repeats.py", "exec"), {"__name__": "__main__"})
        finally:
            sys.argv = argv
        words = json.loads((E / "verbatim_master.json").read_text())["words"]
        pieces = [{**p, "src": "wav", "in": p["m0"], "out": p["m1"]} for p in json.loads((E / "body_pieces.json").read_text())]
        segs = json.loads((E / "lf.json").read_text())["segments"][1:]
        cuts, out = [], 0.0
        for a, b in zip(segs, segs[1:]):                  # camera changes and audio cuts of the shipped edit
            out += a["m1"] - a["m0"]
            cuts.append((INTRO + out, a["m1"], b["m0"], abs(b["m0"] - a["m1"]) > 0.005))
        self.assertEqual("\n".join(verify.repeat_report(words, pieces, cuts, INTRO)) + "\n", buf.getvalue())

    def test_flags(self):
        items = [{"i": 0, "in": 0.0, "out": 0.6, "words": [[0.1, 0.4, "aur"]]},
                 {"i": 1, "in": 1.0, "out": 3.0, "words": [[1.1, 1.3, "aur"], [1.4, 1.8, "phir"]]},
                 {"i": 2, "in": 4.0, "out": 6.0, "words": [[4.1, 4.5, "nahi"]]}]
        js = verify.joints(items)
        self.assertEqual([(j["repeat"], j["lone"]) for j in js], [(True, True), (False, False)])
        self.assertTrue(verify.format_joints(js)[0].startswith("<<!!"))

    def test_cuts_from_pieces(self):
        ps = [{"in": 0.0, "out": 2.0}, {"in": 2.0, "out": 3.0}, {"in": 5.0, "out": 6.0}]
        self.assertEqual(verify.cuts_from_pieces(ps, 10.0), [(12.0, 2.0, 2.0, False), (13.0, 3.0, 5.0, True)])


if __name__ == "__main__":
    unittest.main()
