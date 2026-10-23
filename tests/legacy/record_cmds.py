"""Run a shipped compose script with every subprocess.run recorded instead of run.

Usage: python record_cmds.py OUT.json SCRIPT [args]
Measurement calls get plausible answers (loudnorm JSON, an ebur128 summary, a duration) so the script runs to the end.
"""
import json
import runpy
import subprocess
import sys
from pathlib import Path

out, script = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
LOUD = json.dumps({"input_i": "-20.00", "input_tp": "-3.00", "input_lra": "5.00", "input_thresh": "-30.00",
                   "target_offset": "0.10"})
cmds = []


class Done:
    returncode = 0
    stdout = "60.000000\n"
    stderr = LOUD + "\n  Summary:\n  I: -14.0 LUFS\n  Peak: -1.6 dBFS\n"


def record(cmd, *a, **k):
    cmds.append([str(c) for c in cmd])
    return Done()


subprocess.run = record
sys.argv = [str(script)] + sys.argv[3:]
sys.path.insert(0, str(script.parent))
try:
    runpy.run_path(str(script), run_name="__main__")
finally:
    out.write_text(json.dumps(cmds), encoding="utf-8")
