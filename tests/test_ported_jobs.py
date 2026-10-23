"""The ported job.json files hold exactly what the shipped reels were built from."""
import importlib.util
import json
import unittest
from pathlib import Path

from aie.job import load_job
from aie.settings import REPO


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem + "_ported", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Reel05Test(unittest.TestCase):
    def test_matches_plan_py(self):
        job = load_job(REPO / "shorts/reel-05")
        plan = module(REPO / "shorts/reel-05/edit/plan.py")
        d = job.data
        self.assertEqual(d["fps"], plan.FPS)
        self.assertEqual(d["sources"]["avatar"]["voice_offset"], plan.OFF)
        self.assertEqual(job.length, plan.END)
        got = [(s["t"][0], s["t"][1], s["layout"], d["sources"][s["src"]]["path"], s["in"], s.get("speed", 1.0))
               for s in d["timeline"]]
        self.assertEqual(got, list(plan.SEGMENTS))
        for name, v in plan.VARIANTS.items():
            mine = d["variants"][name]
            self.assertEqual([tuple(r) for r in mine["ranges"]], v["ranges"])
            for k in ("freeze", "mute_voice_after"):
                self.assertEqual(mine.get(k), v.get(k))


class Reel04Test(unittest.TestCase):
    def test_matches_timeline_json(self):
        job = load_job(REPO / "shorts/reel-04")
        tl = json.loads((REPO / "shorts/reel-04/edit/timeline.json").read_text())
        d = job.data
        self.assertEqual(d["fps"], tl["fps"])
        self.assertAlmostEqual(job.length, tl["length"], places=3)
        got = [(p["src"], [p["in"], p["out"]], p["tag"], p["text"], p.get("zoom", 1.0)) for p in d["cut"]["pieces"]]
        want = [(p["file"], p["src"], p["tag"], p["text"], p["zoom"]) for p in tl["pieces"]]
        self.assertEqual(got, want)
        self.assertEqual(d["variants"]["instagram"]["ranges"], tl["ig"]["ranges"])
        self.assertEqual(d["variants"]["youtube"]["ranges"], tl["yt"]["ranges"])
        for k, f in tl["files"].items():                       # same camera files, now via @downloads
            self.assertEqual(Path(d["sources"][k]["path"]).name, f.replace("\\", "/").rsplit("/", 1)[-1])


if __name__ == "__main__":
    unittest.main()
