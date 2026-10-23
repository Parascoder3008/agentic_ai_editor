"""Moved to aie/music.py (the pipeline's music stage). This keeps the old command working:
    python tools/score_music.py <lf.json> [--raw]
"""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # repo root, for the aie package
runpy.run_module("aie.music", run_name="__main__")
