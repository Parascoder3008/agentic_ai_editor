import copy
import json
import tempfile
import unittest
from pathlib import Path

from aie.job import JobError, load_job, on_grid, validate
from aie.settings import load_settings

BASE = {
    "id": "reel-99", "mode": "avatar", "fps": 25, "size": [1080, 1920],
    "sources": {"avatar": {"path": "avatar.mp4"}, "broll": {"path": "@footage/b.mp4"}},
    "timeline": [
        {"t": [0.0, 2.0], "layout": "split", "src": "avatar", "in": 0.24},
        {"t": [2.0, 4.04], "layout": "broll", "src": "broll", "in": 1.0},
    ],
    "layouts": {"split": {"card": [97, 975, 886, 924], "crop": [840, 876, 540, 50]}},
    "variants": {"instagram": {"ranges": [[0.0, 4.04]], "freeze": 0.6}},
}


def errs(change):
    d = copy.deepcopy(BASE)
    change(d)
    return validate(d)


class JobTest(unittest.TestCase):
    def assertFlags(self, change, msg):
        e = errs(change)
        self.assertTrue(any(msg in x for x in e), f"expected {msg!r} in {e}")

    def test_minimal_job_is_valid(self):
        self.assertEqual(validate(copy.deepcopy(BASE)), [])

    def test_frame_grid(self):
        self.assertTrue(on_grid(5.40, 25) and on_grid(15.0667, 30))
        self.assertFalse(on_grid(5.41, 25))

    def test_top_level_typo(self):
        self.assertFlags(lambda d: d.update(captoins={}), "unknown key 'captoins'")

    def test_required_fields(self):
        self.assertFlags(lambda d: d.update(id="Reel 9"), "id: required")
        self.assertFlags(lambda d: d.update(mode="vlog"), "mode: must be one of")
        self.assertFlags(lambda d: d.update(fps=29), "fps: must be one of")
        self.assertFlags(lambda d: d.update(size=[1081, 1920]), "must be even")
        self.assertFlags(lambda d: d.pop("timeline"), 'needs a "cut"')
        self.assertFlags(lambda d: d.update(variants={}), "variants: required")

    def test_timeline_must_be_continuous_and_on_grid(self):
        self.assertFlags(lambda d: d["timeline"][1].update(t=[2.04, 4.04]), "no gap or overlap")
        self.assertFlags(lambda d: d["timeline"][1].update(t=[2.0, 4.03]), "frame grid")
        self.assertFlags(lambda d: d["timeline"][1].update(src="avtar"), "must name one of the sources")
        self.assertFlags(lambda d: d["timeline"][1].update(layout="pip"), "layout: must be one of")

    def test_variant_ranges(self):
        self.assertFlags(lambda d: d["variants"]["instagram"].update(ranges=[[0.0, 5.0]]), "after the video ends")
        self.assertFlags(lambda d: d["variants"]["instagram"].update(ranges=[[2.0, 3.0], [1.0, 2.0]]), "in order")
        self.assertFlags(lambda d: d["variants"]["instagram"].update(freeze=-1), "freeze")

    def test_cut_spans(self):
        def spans(d):
            d.pop("timeline")
            d["cut"] = {"mode": "spans", "source": "avatar", "keep": [[9.1, 22.61, "open"]],
                        "drop": [[21.95, 22.85, "lone fragment"]], "gap": 0.4}
            d["variants"]["instagram"]["ranges"] = [[0.0, 4.0]]
        self.assertEqual(errs(spans), [])
        self.assertFlags(lambda d: (spans(d), d["cut"].update(source="cam")), "cut.source")
        self.assertFlags(lambda d: (spans(d), d["cut"].update(keep=[[5.0, 2.0]])), "before end")

    def test_cut_pieces_set_the_length(self):
        def pieces(d):
            d.pop("timeline")
            d["cut"] = {"mode": "pieces", "pieces": [{"src": "avatar", "in": 1.0, "out": 3.0}]}
        self.assertFlags(pieces, "after the video ends")          # IG range 4.04 s > 2.0 s of pieces
        self.assertFlags(lambda d: (pieces(d), d["cut"]["pieces"][0].update(out=0.5)), "in < out")

    def test_gates_and_custom(self):
        self.assertFlags(lambda d: d.update(gates={"storyboard_approved": "yes"}), "gates")
        self.assertFlags(lambda d: d.update(gates={"approved": True}), "unknown key 'approved'")
        self.assertFlags(lambda d: d.update(custom="edit/x.py"), "custom")

    def test_stage_effects_only_over_split_beats(self):
        chat = {"effect": "reel-chat", "at": 0.5, "dur": 2.0, "params": {"MESSAGES": [{"from": "in", "text": "hi"}]}}
        self.assertEqual(errs(lambda d: d.update(effects=[{**chat, "at": 0.0}])), [])            # 0-2 is split
        self.assertFlags(lambda d: d.update(effects=[chat]), "2.00-4.04 is a broll beat")
        self.assertEqual(errs(lambda d: d.update(effects=[{**chat, "params": {**chat["params"], "BG": "none"}}])), [])
        self.assertEqual(errs(lambda d: d.update(effects=[{"effect": "reel-stamp", "at": 2.5, "params": {"TEXT": "x"}}])), [])

    def test_layouts_and_graphics(self):
        self.assertFlags(lambda d: d.pop("layouts"), "the timeline uses split or face layouts")
        self.assertFlags(lambda d: d["timeline"][1].update(layout="face"), "layouts.face: the timeline uses")
        self.assertFlags(lambda d: d["layouts"]["split"].update(card=[97, 975, 886]), "layouts.split")
        self.assertFlags(lambda d: d["layouts"].update(camera={"head": [440, 760], "crop": [1, 2]}), "layouts.camera")
        self.assertFlags(lambda d: d["layouts"].update(pip={}), "unknown key 'pip'")
        self.assertFlags(lambda d: d.update(graphics={"offset": 0.2}), '"composition"')
        self.assertFlags(lambda d: d.update(graphics={"composition": "gfx/main.html"}), "index.html")
        self.assertFlags(lambda d: d.update(graphics={"render": "gfx/r.webm", "pad": -1}), "graphics.pad")
        self.assertEqual(errs(lambda d: d.update(graphics={"composition": "gfx/index.html", "offset": 0.24})), [])

    def test_load_job_checks_files(self):
        d = Path(tempfile.mkdtemp())
        footage = Path(tempfile.mkdtemp())
        (d / "job.json").write_text(json.dumps(BASE), encoding="utf-8")
        local = d / "aie.local.json"
        local.write_text(json.dumps({"roots": {"footage": str(footage)}}), encoding="utf-8")
        s = load_settings(local)
        self.assertEqual(load_job(d, s).id, "reel-99")                  # files not checked by default
        with self.assertRaises(JobError) as cm:
            load_job(d, s, check_files=True)
        self.assertEqual(len(cm.exception.errors), 2)                    # avatar.mp4 and @footage/b.mp4 missing
        (d / "avatar.mp4").write_bytes(b"")
        (footage / "b.mp4").write_bytes(b"")
        self.assertEqual(load_job(d, s, check_files=True).length, 4.04)

    def test_broken_json_is_reported(self):
        d = Path(tempfile.mkdtemp())
        (d / "job.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(JobError, "not valid JSON"):
            load_job(d)


if __name__ == "__main__":
    unittest.main()
