"""Voice, SFX and music stems rebuilt from job.json equal what the shipped reels' own scripts produce from the same
inputs (synthetic voices here: the real ones aren't in the repo), and the mix delivers each variant at -14 LUFS."""
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from aie import sound
from aie.job import load_job, save_job, validate
from aie.settings import REPO, load_settings

HAVE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "soundfile"))
LEGACY = REPO / "tests/legacy"
SR = 48000


def speech(seconds, seed, gap=0.9):
    """Bursts of a modulated tone at about -24 dBFS with pauses, over -70 dBFS room tone: speech enough for the
    voice-activity, ducking and handle logic."""
    import numpy as np
    n, t = int(seconds * SR), None
    t = np.arange(n) / SR
    x = np.random.default_rng(seed).normal(0, 3e-4, n).astype(np.float32)
    for a in np.arange(0.3, seconds - 1, gap):
        m = (t >= a) & (t < a + 0.55)
        x[m] += (0.1 * np.sin(2 * np.pi * 180 * t[m]) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t[m]))).astype(np.float32)
    return np.stack([x, x], 1)


def write(path, x):
    import soundfile as sf
    sf.write(path, x, SR, subtype="PCM_24")


def legacy_script(src: Path, dst: Path):
    """A reel script set up to run here: its tools import pointed at the legacy score_music."""
    text = src.read_text(encoding="utf-8")
    text = re.sub(r'^sys\.path\.insert\(0, r"C:\\Users\\PARAS ARORA\\AI_Editor\\tools"\)$',
                  f"sys.path.insert(0, {str(LEGACY)!r})", text, flags=re.M)
    assert str(LEGACY) in text
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")


def run(*cmd, cwd=None):
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True, capture_output=True)


@unittest.skipUnless(HAVE, "needs numpy, scipy and soundfile")
class Reel05SoundTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = d = Path(tempfile.mkdtemp())
        write(d / "voice_src.wav", speech(59.3, 11))
        run("ffmpeg", "-y", "-v", "error", "-i", d / "voice_src.wav", "-c:a", "aac", "-b:a", "192k", d / "avatar.mp4")
        # the shipped script, as it ran
        (d / "legacy").mkdir()
        shutil.copy(d / "avatar.mp4", d / "legacy/avatar.mp4")
        legacy_script(LEGACY / "reel05_sfx.py", d / "legacy/edit/sfx.py")
        run(sys.executable, "sfx.py", cwd=d / "legacy/edit")
        # the pipeline
        (d / "new").mkdir()
        shutil.copy(REPO / "shorts/reel-05/job.json", d / "new/job.json")
        shutil.copy(d / "avatar.mp4", d / "new/avatar.mp4")
        cls.s = load_settings(d / "none.json")
        cls.log = []
        from aie import runner
        cls.mix = runner.run(load_job(d / "new", cls.s), cls.s, "mix", log=cls.log.append)

    def test_voice_and_sfx_match_the_shipped_script(self):
        for f in ("voice.wav", "sfx.wav"):
            with self.subTest(f=f):
                self.assertEqual((self.d / "new/build" / f).read_bytes(), (self.d / "legacy/edit" / f).read_bytes())

    def test_music_matches_the_original_scorer(self):
        d = self.d / "music"
        (d / "reel").mkdir(parents=True)
        shutil.copy(self.d / "new/build/voice.wav", d / "reel/base.mkv.wav")
        run("ffmpeg", "-y", "-v", "error", "-i", d / "reel/base.mkv.wav", "-c:a", "pcm_s24le", d / "reel/base.mkv")
        cfg = json.loads((REPO / "shorts/reel-05/edit/music_cfg.json").read_text())
        cfg["music"]["file"] = str(d / "legacy.wav")
        (d / "cfg.json").write_text(json.dumps(cfg))
        run(sys.executable, LEGACY / "score_music.py", d / "cfg.json")
        self.assertEqual((self.d / "new/build/music.wav").read_bytes(), (d / "legacy.wav").read_bytes())

    def test_variants_are_delivered_at_minus_14_lufs(self):
        v = self.mix["variants"]
        self.assertEqual((v["instagram"]["seconds"], v["youtube"]["seconds"]), (54.4, 53.64))   # as shipped
        for name, x in v.items():
            with self.subTest(variant=name):
                self.assertAlmostEqual(x["lufs"], -14.0, delta=0.5)
                self.assertLessEqual(x["true_peak"], -1.4)

    def test_stages_skip_when_nothing_changed(self):
        from aie import runner
        log = []
        runner.run(load_job(self.d / "new", self.s), self.s, "mix", log=log.append)
        self.assertEqual(log, ["mix: up to date"])


@unittest.skipUnless(HAVE, "needs numpy, scipy and soundfile")
class Reel04SoundTest(unittest.TestCase):
    """Camera takes: the voice is built piece by piece with room-tone handles at every joint."""

    @classmethod
    def setUpClass(cls):
        cls.d = d = Path(tempfile.mkdtemp())
        write(d / "a.wav", speech(150, 21, 1.1))
        write(d / "b.wav", speech(15, 22, 1.1))
        tl = json.loads((REPO / "shorts/reel-04/edit/timeline.json").read_text())
        tl["files"] = {"a": str(d / "a.wav"), "b": str(d / "b.wav")}
        legacy_script(LEGACY / "reel04_sfx.py", d / "legacy/edit/sfx.py")
        (d / "legacy/edit/timeline.json").write_text(json.dumps(tl))
        run(sys.executable, "sfx.py", cwd=d / "legacy/edit")
        job = json.loads((REPO / "shorts/reel-04/job.json").read_text(encoding="utf-8"))
        job["sources"] = {"a": {"path": str(d / "a.wav")}, "b": {"path": str(d / "b.wav")}}
        (d / "new").mkdir()
        save_job(d / "new", job)
        cls.s = load_settings(d / "none.json")
        from aie import runner
        runner.run(load_job(d / "new", cls.s), cls.s, "sfx", log=lambda *_: None)

    def test_voice_matches_the_shipped_script(self):
        self.assertEqual((self.d / "new/build/voice.wav").read_bytes(), (self.d / "legacy/edit/voice.wav").read_bytes())

    def test_sfx_stem_follows_the_shipped_one(self):
        """The shipped script ducked against its voice before saving it; the pipeline ducks against the saved
        voice.wav. Same cues and sounds, so the stems agree to within a hair."""
        import numpy as np
        import soundfile as sf
        a, _ = sf.read(self.d / "new/build/sfx.wav")
        b, _ = sf.read(self.d / "legacy/edit/sfx.wav")
        self.assertEqual(a.shape, b.shape)
        self.assertLess(np.abs(a - b).max(), 1e-3)
        self.assertGreater(np.corrcoef(a[:, 0], b[:, 0])[0, 1], 0.9999)


class MixGraphTest(unittest.TestCase):
    """The ffmpeg graphs are the ones the shipped compose.py scripts ran."""

    def test_variant_graph_reel05(self):
        rs, fz = [(0.0, 49.04), (53.80, 58.0)], 0.4
        aparts = "".join(f"[0:a]atrim={a}:{b + (fz if i == len(rs) - 1 else 0)},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:st=0:d=0.03,afade=t=out:st={b - a + (fz if i == len(rs) - 1 else 0) - 0.03:.3f}:d=0.03[a{i}];"
                         for i, (a, b) in enumerate(rs))
        total = sum(b - a for a, b in rs) + fz
        acat = "".join(f"[a{i}]" for i in range(len(rs))) + f"concat=n={len(rs)}:v=0:a=1,afade=t=out:st={total - 0.5:.3f}:d=0.5[a]"
        self.assertEqual(sound.variant_graph(rs, fz, 0.03), (aparts + acat, total))

    def test_premix_reel04(self):
        cmd = sound.premix_cmd("voice.wav", "sfx.wav", "music_score.wav", "mix.wav", 67.5667 + 0.8, -3.217, 56.8)
        graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertEqual(graph, "[0:a]volume=0:enable='gte(t,56.800)'[vo];[vo][1:a][2:a]amix=inputs=3:normalize=0:"
                                "duration=longest,atrim=0:68.367,volume=-3.22dB,alimiter=limit=0.72:attack=4:release=60:"
                                "level=disabled")

    def test_premix_without_music(self):
        cmd = sound.premix_cmd("v.wav", "s.wav", None, "m.wav", 10.0, 0.0)
        self.assertIn("[vo][1:a]amix=inputs=2", cmd[cmd.index("-filter_complex") + 1])


class SchemaTest(unittest.TestCase):
    def test_sound_settings_are_checked(self):
        d = load_job(REPO / "shorts/reel-05").data
        d = json.loads(json.dumps(d))
        d["sfx"]["cues"][0]["kind"] = "boom"
        d["sfx"]["cues"][1]["size"] = 3
        d["sfx"]["cues"].append({"kind": "typing", "t": 1.0})
        d["music"]["score"]["blocks"][0]["cue"] = "jazz"
        d["music"]["score"]["duck"][0]["t1"] = 20.0
        d["mix"]["gain_db"] = "loud"
        e = "\n".join(validate(d))
        for msg in ("cues[0].kind", "no setting 'size'", "until: required for typing", "blocks[0].cue",
                    "must cover 0 to length", "mix.gain_db"):
            self.assertIn(msg, e)


if __name__ == "__main__":
    unittest.main()
