"""Re-time everything authored on the v1 master (gfx_index_v1.html, sfx_v1.py cues) onto the current timeline.json, through
the source clip (remap.R). Writes gfx/index.html, the cue block of sfx.py, TL["ff"] (full-frame beats, read by captions/
compose/sfx) and music_cfg.json blocks. Run after words.py whenever the cut changes. Usage: python retime.py"""
import json
import re
from pathlib import Path

from remap import NEW as TL, R

ED = Path(__file__).resolve().parent
L, CE, YS = TL["length"], TL["end_common"], TL["yt"]["ranges"][1][0]          # length, end of shared part, YT tail start
TL["ff"] = [[R(33.24), R(36.28)], [CE, YS], [R(60.92), L]]
(ED / "timeline.json").write_text(json.dumps(TL, indent=1))
remap = lambda txt: re.sub(r"(?<![\w.])(\d+\.\d+)(?![\w.])",
                           lambda m: f"{R(float(m.group(1))):.2f}" if 15.36 < float(m.group(1)) < 70 else m.group(1), txt)


def swap(s, a, b):
    assert s.count(a) == 1, a[:60]
    return s.replace(a, b)


# ---- gfx
g = (ED / "gfx_index_v1.html").read_text(encoding="utf-8")
i = g.index("<script>\n      const tl"); head, scr = g[:i], remap(g[i:])
for cid, (t0, t1) in {"root": (0, L), "stage": (15.36, L), "ff1": TL["ff"][0], "ff2": TL["ff"][1], "ff3": TL["ff"][2]}.items():
    head, n = re.subn(rf'(id="{cid}"[^>]*?data-start=")[\d.]+(" data-duration=")[\d.]+',
                      lambda m: f"{m.group(1)}{t0:.2f}{m.group(2)}{t1 - t0:.2f}", head)
    assert n == 1, cid
a, b = scr.index("      // IG tail"), scr.index("      // ---- full-frame overlays")
scr = scr[:a] + f"""      // IG tail: full-frame CTA from "comment kar do FLEX"
      hide("#stage", {CE:.2f}); show("#stage", {YS:.2f});
      // YT tail
      scene("#sc8", {YS:.2f}, {TL['ff'][2][0]:.2f}); pop("#w1", {R(56.63):.2f}); pop("#w2", {R(59.68):.2f});
      hide("#stage", {TL['ff'][2][0]:.2f});

""" + scr[b:]
scr = re.sub(r'scene\("#sc5", ([\d.]+), [\d.]+\)', lambda m: f'scene("#sc5", {m.group(1)}, {CE:.2f})', scr, count=1)   # holds through "agar flex karna ho to"
(ED.parent / "gfx" / "index.html").write_text(head + scr, encoding="utf-8")

# ---- sfx cues
old = (ED / "sfx_v1.py").read_text(encoding="utf-8")
cues = remap(old[old.index("# steps"): old.index("# duck under the voice")])
cues = cues.replace(f", {R(46.38):.2f})", ")")                                  # FREE GUIDE scene no longer exists
cues = re.sub(r"for t0, t1 in \(\(.*?\)\):", 'for t0, t1 in TL["ff"]:', cues)
cues = swap(cues, "put(whoosh(0.3), t1 - 0.2, db(-34))",                        # no exit whoosh where a cut ends
            'put(whoosh(0.3), t1 - 0.2, db(-34)) if t1 not in (TL["yt"]["ranges"][1][0], TL["length"]) else None')
s = (ED / "sfx.py").read_text(encoding="utf-8")
s = s[: s.index("# steps")] + cues + s[s.index("# duck under the voice"):]
(ED / "sfx.py").write_text(s, encoding="utf-8")

# ---- music
m = json.loads((ED / "music_cfg.json").read_text())
sc = m["music"]["score"]; bl = sc["blocks"]
bl[1]["t1"] = bl[2]["t0"] = CE; bl[2]["t1"] = sc["length"] = round(L + 0.8, 2); sc["duck"][0]["t1"] = round(L + 1.8, 2)
(ED / "music_cfg.json").write_text(json.dumps(m, indent=1))
print("ff", TL["ff"], "| common ends", CE, "| yt tail", YS, "| length", L)
print(cues)
