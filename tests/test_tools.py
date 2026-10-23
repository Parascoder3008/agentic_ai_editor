import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from aie.settings import REPO

MACHINE_PATH = re.compile(r"\b[A-Z]:\\[A-Za-z]{2,}|PARAS ARORA")


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem + "_t", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class ToolsTest(unittest.TestCase):
    def test_no_machine_paths_in_shared_code(self):
        for f in sorted((REPO / "aie").rglob("*.py")) + sorted((REPO / "tools").glob("*.py")):
            with self.subTest(f=f.name):
                self.assertIsNone(MACHINE_PATH.search(f.read_text(encoding="utf-8")), f"machine path in {f}")

    def test_gfx_batch_rebuilds_the_long_form_graphics_exactly(self):
        g = module(REPO / "tools/gfx_batch.py")
        spec = json.loads((REPO / "jobs/longform-ai-editor/edit/gfx_spec.json").read_text(encoding="utf-8"))
        out = Path(tempfile.mkdtemp())
        for item in spec:
            with self.subTest(id=item["id"]):
                built = g.build(item, out, g.S.path("hyperframes_base")) / "index.html"
                ref = REPO / "jobs/longform-ai-editor/edit/gfx" / item["id"] / "index.html"
                self.assertEqual(built.read_text(encoding="utf-8"),
                                 ref.read_text(encoding="utf-8").replace("\r\n", "\n"))
        self.assertEqual(len(spec), 50)

    def test_pick_avatar_reads_the_repo_rotation(self):
        from aie.settings import load_settings
        p = module(REPO / "tools/pick_avatar.py")
        self.assertEqual(p.ROT, load_settings().path("avatar_rotation"))
        rot = json.loads(p.ROT.read_text(encoding="utf-8"))
        last = rot["history"][-1]["id"] if rot["history"] else None
        self.assertNotEqual(p.pick(rot)["id"], last)

    def test_cli(self):
        def run(*args):
            return subprocess.run([sys.executable, "-m", "aie", *args], cwd=REPO, capture_output=True, text=True)
        r = run("validate", "shorts/reel-05", "shorts/reel-04")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.count("OK "), 2)
        r = run("effects", "--kind", "overlay")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("kw", r.stdout)
        r = run("validate", "no/such/job")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no job.json", r.stdout)


if __name__ == "__main__":
    unittest.main()
