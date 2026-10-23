import json
import unittest

from aie.effects import Catalog
from aie.settings import REPO


class CatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = Catalog.load()

    def test_catalog_loads_cleanly(self):
        self.assertEqual(self.cat.errors, [])
        self.assertTrue({"kw", "section", "chip", "lower", "subscribe"} <= set(self.cat.effects))

    def check(self, p, mode="footage", aspect="16:9", length=None):
        return self.cat.check_placement(p, "fx", mode, aspect, length)

    def test_valid_placement(self):
        self.assertEqual(self.check({"effect": "kw", "at": 1.0, "params": {"MAIN": "Hi", "SIDE": "left"}}), [])

    def test_defaults_fill_in(self):
        self.assertEqual(self.cat.get("kw").filled({"MAIN": "x"})["SIDE"], "right")

    def test_placement_errors(self):
        cases = [
            ({"effect": "kw", "at": 1.0}, "needs parameter 'MAIN'"),
            ({"effect": "kw", "at": 1.0, "params": {"MAIN": "x", "COLOR": "red"}}, "no parameter 'COLOR'"),
            ({"effect": "kw", "at": 1.0, "params": {"MAIN": "x", "SIDE": "top"}}, "not one of"),
            ({"effect": "nope", "at": 1.0}, "unknown effect 'nope'"),
            ({"effect": "kw", "at": -1, "params": {"MAIN": "x"}}, '"at" must be'),
            ({"effect": "kw", "at": 1.0, "dur": 30, "params": {"MAIN": "x"}}, "outside kw's range"),
            ({"effect": "kw", "at": 1.0, "params": {"MAIN": "x"}, "colour": 1}, "unknown key 'colour'"),
        ]
        for p, msg in cases:
            with self.subTest(msg=msg):
                self.assertTrue(any(msg in e for e in self.check(p)), self.check(p))

    def test_paras_only_effect_rejected_in_client_jobs(self):
        p = {"effect": "subscribe", "at": 1.0}
        self.assertEqual(self.check(p, mode="footage"), [])
        self.assertTrue(any("own brand" in e for e in self.check(p, mode="client")))

    def test_format_mismatch(self):
        errs = self.check({"effect": "kw", "at": 1.0, "params": {"MAIN": "x"}}, aspect="9:16")
        self.assertTrue(any("built for 16:9" in e for e in errs))

    def test_ends_after_the_video(self):
        errs = self.check({"effect": "kw", "at": 9.0, "params": {"MAIN": "x"}}, length=10.0)
        self.assertTrue(any("after the video ends" in e for e in errs))

    def test_every_long_form_use_fits_the_catalog(self):
        """The 47 long-form graphics made from catalog templates all validate as placements."""
        names = {"kw": "kw", "section": "section", "chip": "chip", "lower": "lower", "sub": "subscribe"}
        spec = json.loads((REPO / "jobs/longform-ai-editor/edit/gfx_spec.json").read_text(encoding="utf-8"))
        uses = [i for i in spec if i["tpl"] in names]
        self.assertEqual(len(uses), 47)
        for i in uses:
            p = {"effect": names[i["tpl"]], "at": 0.0, "dur": i["dur"], "params": i.get("vars", {})}
            self.assertEqual(self.check(p), [], i["id"])

    def test_broken_effect_files_are_reported(self):
        import tempfile
        from pathlib import Path
        root = Path(tempfile.mkdtemp())
        (root / "bad").mkdir()
        (root / "bad/effect.json").write_text(json.dumps({"name": "wrong", "kind": "glow", "params": {
            "X": {"required": True, "default": 1}}}), encoding="utf-8")
        cat = Catalog.load(root)
        self.assertEqual(cat.effects, {})
        text = "\n".join(cat.errors)
        for msg in ('"name" must be', "kind must be", "'source' is required", "can't have a default"):
            self.assertIn(msg, text)


if __name__ == "__main__":
    unittest.main()
