"""Re-time the whole edit to a new voice take of the same script: every cue was authored on word times,
so map old -> new through the matching word starts (piecewise-linear between words).

Writes timemap.json, gfx/top/index.html (from index_v1.html), music_cfg.json; sfx.py reads timemap.json.
Usage: python retime.py <new_audio_duration>
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

ED = Path(__file__).resolve().parent
JOB = ED.parent
old = json.loads((ED / "words_v1.json").read_text(encoding="utf-8"))["words"]
new = json.loads((ED / "words.json").read_text(encoding="utf-8"))["words"]
OLD_LEN, NEW_LEN = 49.84, float(sys.argv[1])
xo = [0.0] + [w["start"] for w in old] + [old[-1]["end"], OLD_LEN]
xn = [0.0] + [w["start"] for w in new] + [new[-1]["end"], NEW_LEN]
(ED / "timemap.json").write_text(json.dumps({"old": xo, "new": xn}), encoding="utf-8")
M = lambda t: round(float(np.interp(float(t), xo, xn)), 3)
f = lambda m, *g: m.group(0)

# --- composition
src = (ED / "gfx_top_index_v1.html").read_text(encoding="utf-8")
head, script = src.split("<script>\n      const tl", 1)


def clip(m):
    s, d = float(m.group(1)), float(m.group(2))
    return f'data-start="{M(s)}" data-duration="{round(M(s + d) - M(s), 3)}"'


head = re.sub(r'data-start="([\d.]+)" data-duration="([\d.]+)"', clip, head)
rules = [
    (r'(pop\("[^"]*", )([\d.]+)', lambda m: f"{m.group(1)}{M(m.group(2))}"),
    (r'((?:enter|leave)\("[^"]*", )([\d.]+)\)', lambda m: f"{m.group(1)}{M(m.group(2))})"),
    (r'(type\("[^"]*", "(?:[^"\\]|\\.)*", )([\d.]+), ([\d.]+)\)', lambda m: f"{m.group(1)}{M(m.group(2))}, {M(m.group(3))})"),
    (r'(count\("[^"]*", \d+, )([\d.]+)', lambda m: f"{m.group(1)}{M(m.group(2))}"),
    (r'\}, ([\d.]+)\)', lambda m: f"}}, {M(m.group(1))})"),
    (r'([\d.]+) \+ i \* ([\d.]+)', lambda m: f"{M(m.group(1))} + i * {m.group(2)}"),
]
for pat, rep in rules:
    script = re.sub(pat, rep, script)
(JOB / "gfx" / "top" / "index.html").write_text(head + "<script>\n      const tl" + script, encoding="utf-8")

# --- music blocks on the new timeline
mc = json.loads((ED / "music_cfg.json").read_text(encoding="utf-8"))
sc = mc["music"]["score"]
sc["length"] = NEW_LEN
for b in sc["blocks"]:
    b["t0"], b["t1"] = M(b["t0"]), M(b["t1"])
sc["duck"] = [{"t0": 0.0, "t1": NEW_LEN + 1.2, "speech": -16, "gap": -8}]
(ED / "music_cfg.json").write_text(json.dumps(mc, indent=1), encoding="utf-8")
print("M(3.05)=", M(3.05), " M(8.85)=", M(8.85), " M(25.06)=", M(25.06), " end", M(OLD_LEN))
