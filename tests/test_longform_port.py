"""The long-form's job.json holds exactly the cut it shipped with, and (on a machine with its WAV) rebuilds it."""
import ast
import json
import unittest

from aie import audio, cuts
from aie.job import load_job
from aie.settings import REPO, SettingsError, load_settings

J = REPO / "jobs/longform-ai-editor"


def body_edl_constants():
    out = {}
    for n in ast.parse((J / "edit/body_edl.py").read_text(encoding="utf-8")).body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id in ("KEEP", "DROP"):
                    out[t.id] = ast.literal_eval(n.value)
                if isinstance(t, ast.Tuple):
                    out.update(zip([e.id for e in t.elts], ast.literal_eval(n.value)))
    return out


def wav_path():
    """The long-form WAV via aie.local.json, or None when this machine doesn't have it."""
    try:
        job = load_job(J)
        p = job.source("wav", load_settings())
    except SettingsError:
        return None
    return p if p.exists() else None


class LongformPortTest(unittest.TestCase):
    def test_keep_and_drop_are_the_shipped_ones(self):
        c, cut = body_edl_constants(), load_job(J).data["cut"]
        self.assertEqual([tuple(k) for k in cut["keep"]], c["KEEP"])
        self.assertEqual([tuple(d) for d in cut["drop"]], c["DROP"])
        self.assertEqual((load_job(J).data["fps"], cut["gap"], cut["pad_in"], cut["pad_out"]),
                         (c["FPS"], c["GAP"], c["PAD_IN"], c["PAD_OUT"]))

    @unittest.skipUnless(wav_path(), "needs the long-form WAV (set \"footage\" under roots in aie.local.json)")
    def test_cutter_rebuilds_body_pieces_exactly(self):
        cut = load_job(J).data["cut"]
        ps = cuts.build_spans(audio.Envelope.of(wav_path()), cut["keep"], cut["drop"], 25, "wav",
                              cut["gap"], cut["pad_in"], cut["pad_out"])
        want = json.loads((J / "edit/body_pieces.json").read_text())
        self.assertEqual([{"m0": p["in"], "m1": p["out"], "sec": p["sec"], "out0": p["out0"]} for p in ps], want)


if __name__ == "__main__":
    unittest.main()
