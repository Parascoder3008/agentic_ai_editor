"""Captions and publish files rebuilt from job.json match what the shipped reels were delivered with."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from aie import captions, cuts, runner
from aie.job import load_job, validate
from aie.settings import REPO, load_settings

R5, R4 = REPO / "shorts/reel-05", REPO / "shorts/reel-04"


def words_file(words) -> str:
    """words_master.json exactly as the reel scripts wrote it."""
    return json.dumps({"words": words}, ensure_ascii=False, indent=1)


class Reel05Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.job = load_job(R5)
        cls.words = captions.caption_words(R5, cls.job.data)

    def test_words(self):
        self.assertEqual(words_file(self.words), (R5 / "edit/words_master.json").read_text(encoding="utf-8"))

    def test_ass(self):
        self.assertEqual(captions.build_ass(self.job.data, self.words),
                         (R5 / "edit/captions.ass").read_text(encoding="utf-8"))

    def test_srt_per_variant(self):
        for name, v in self.job.data["variants"].items():
            with self.subTest(variant=name):
                self.assertEqual(captions.build_srt(self.words, v["ranges"]),
                                 (R5 / f"publish/REEL05_{name}.srt").read_text(encoding="utf-8"))

    def test_cover(self):
        from PIL import Image, ImageChops
        out = Path(tempfile.mkdtemp()) / "cover.jpg"
        from aie.package import cover
        cover(R5 / "edit/cover_src.png", self.job.data["package"]["cover"], load_settings().path("fonts"), out)
        a, b = Image.open(out).convert("RGB"), Image.open(R5 / "publish/cover.jpg").convert("RGB")
        self.assertEqual(a.size, b.size)
        diff = ImageChops.difference(a, b).convert("L")
        mean = sum(i * n for i, n in enumerate(diff.histogram())) / (a.size[0] * a.size[1])
        self.assertLess(mean, 1.0)                          # same picture; JPEG encoders may differ by a level


class Reel04Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.job = load_job(R4)
        cls.pieces = cuts.layout_pieces(cls.job.data["cut"]["pieces"])
        cls.words = captions.caption_words(R4, cls.job.data, cls.pieces)

    def test_words_with_text_fixes(self):
        self.assertEqual(words_file(self.words), (R4 / "edit/words_master.json").read_text(encoding="utf-8"))

    def test_ass_with_cut_breaks_and_zones(self):
        self.assertEqual(captions.build_ass(self.job.data, self.words, self.pieces, cuts.total(self.pieces)),
                         (R4 / "edit/captions.ass").read_text(encoding="utf-8"))

    def test_srt_per_variant(self):
        for name, f in (("instagram", "captions_ig.srt"), ("youtube", "captions_yt.srt")):
            with self.subTest(variant=name):
                self.assertEqual(captions.build_srt(self.words, self.job.data["variants"][name]["ranges"]),
                                 (R4 / "publish" / f).read_text(encoding="utf-8"))


class UnitsTest(unittest.TestCase):
    def test_colours(self):
        self.assertEqual(captions.ass_color("#0C0E0F"), "&H000F0E0C")
        self.assertEqual(captions.ass_color("#0F0E0C73"), "&H8C0C0E0F")       # 0x73 opacity = 0x8C transparency
        self.assertEqual(captions.ass_bgr("#3AB0D8"), "D8B03A")

    def test_chunks_break_on_limits(self):
        w = lambda t, s, e: {"text": t, "start": s, "end": e}
        ws = [w("ek", 0, .2), w("do", .2, .4), w("teen", .4, .6), w("char", .6, .8), w("paanch.", .8, 1.0),
              w("chhe", 2.0, 2.2)]
        self.assertEqual([[x["text"] for x in c] for c in captions.chunks(ws)],
                         [["ek", "do", "teen"], ["char", "paanch."], ["chhe"]])

    def test_join_and_keyword_rules(self):
        ws = [{"text": t, "start": i, "end": i + 0.5} for i, t in enumerate(["comment", "kar", "do", "edit", "b", "roll"])]
        out = captions.fix_text(ws, {"keywords": [{"word": "edit", "after": "do", "as": "EDIT"}],
                                     "join": [{"words": ["b", "roll"], "as": "B-roll"}]}, {0})
        self.assertEqual([x["text"] for x in out], ["comment", "kar", "do", "EDIT", "B-roll"])
        self.assertEqual(out[-1]["end"], 5.5)

    def test_validation(self):
        d = copy.deepcopy(load_job(R5).data)
        d["captions"]["styles"]["Low"]["back_color"] = "dark"
        d["captions"]["zones"][0]["style"] = "Lower"
        d["captions"]["words"]["from"] = "whisper"
        d["package"]["cover"]["lines"][0].pop("size")
        e = "\n".join(validate(d))
        for msg in ("back_color", "zones[0].style", "words.from", "lines[0].size"):
            self.assertIn(msg, e)


class StagesTest(unittest.TestCase):
    def copy_job(self, src, files):
        d = Path(tempfile.mkdtemp())
        shutil.copy(src / "job.json", d / "job.json")
        for f in files:
            (d / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src / f, d / f)
        return d

    def test_reel05_captions_and_package(self):
        d = self.copy_job(R5, ["edit/fa_out.json", "script.txt", "edit/cover_src.png"])
        s, log = load_settings(d / "none.json"), []
        runner.run(load_job(d, s), s, "package", log=log.append)
        self.assertEqual((d / "build/captions.ass").read_text(encoding="utf-8"),
                         (R5 / "edit/captions.ass").read_text(encoding="utf-8"))
        for name in ("instagram", "youtube"):
            self.assertEqual((d / f"build/publish/REEL05_{name}.srt").read_text(encoding="utf-8"),
                             (R5 / f"publish/REEL05_{name}.srt").read_text(encoding="utf-8"))
        self.assertTrue((d / "build/publish/cover.jpg").exists())
        runner.run(load_job(d, s), s, "captions", log=log.append)
        self.assertIn("up to date", log[-1])

    def test_reel04_runs_the_cut_first(self):
        d = self.copy_job(R4, ["edit/fa_a.json", "edit/fa_b.json"])
        s, log = load_settings(d / "none.json"), []
        runner.run(load_job(d, s), s, "captions", log=log.append)
        self.assertTrue(log[0].startswith("cut: "))
        self.assertEqual((d / "build/captions.ass").read_text(encoding="utf-8"),
                         (R4 / "edit/captions.ass").read_text(encoding="utf-8"))

    def test_cover_text_outside_the_safe_zone_is_refused(self):
        d = self.copy_job(R5, ["edit/fa_out.json", "script.txt", "edit/cover_src.png"])
        data = json.loads((d / "job.json").read_text(encoding="utf-8"))
        data["package"]["cover"]["lines"][1]["size"] = 140
        (d / "job.json").write_text(json.dumps(data), encoding="utf-8")
        s = load_settings(d / "none.json")
        with self.assertRaisesRegex(runner.StageError, "doesn't fit inside x 90-930"):
            runner.run(load_job(d, s), s, "package", log=lambda *_: None)


if __name__ == "__main__":
    unittest.main()
