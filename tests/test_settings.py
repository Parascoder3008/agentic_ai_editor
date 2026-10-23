import json
import tempfile
import unittest
from pathlib import Path

from aie.settings import REPO, SettingsError, load_settings


class SettingsTest(unittest.TestCase):
    def write(self, data):
        d = tempfile.mkdtemp()
        f = Path(d) / "aie.local.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        return f

    def test_defaults_without_a_file(self):
        s = load_settings(Path(tempfile.mkdtemp()) / "missing.json")
        self.assertIsNone(s.source)
        self.assertEqual(s.path("templates"), REPO / "templates")
        self.assertEqual(s.path("hyperframes_base"), REPO / "aie/hyperframes_base")

    def test_file_overrides_and_roots(self):
        root = tempfile.mkdtemp()
        s = load_settings(self.write({"roots": {"downloads": root}, "fonts": root}))
        self.assertEqual(s.path("fonts"), Path(root))
        self.assertEqual(s.resolve("@downloads/take.MP4", REPO), Path(root) / "take.MP4")

    def test_relative_paths_resolve_under_the_job(self):
        s = load_settings(self.write({}))
        self.assertEqual(s.resolve("broll/a.mp4", Path("/jobs/x")), Path("/jobs/x/broll/a.mp4"))

    def test_unknown_root_is_explained(self):
        s = load_settings(self.write({"roots": {}}))
        with self.assertRaisesRegex(SettingsError, 'no root named "footage"'):
            s.resolve("@footage/a.mp4", REPO)

    def test_unknown_key_is_rejected(self):
        with self.assertRaisesRegex(SettingsError, "unknown keys"):
            load_settings(self.write({"font": "x"}))

    def test_example_file_is_valid(self):
        s = load_settings(REPO / "aie.local.example.json")
        self.assertIn("downloads", s.data["roots"])


if __name__ == "__main__":
    unittest.main()
