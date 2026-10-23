"""Captions on the master timeline (inspiration look: white Inter, current word lime #D2F620, <= 3 words).
Split (0-15.36): between the panels (baseline 1022). Card layout: between stage and presenter card (baseline 938).
Full-frame beats: boxed, low on the shirt (baseline 1450)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
import captions_ass as ca  # noqa: E402

ED = Path(__file__).resolve().parent
TL = json.loads((ED / "timeline.json").read_text())
FF = [tuple(x) for x in TL["ff"]]                           # full-frame presenter beats (written by retime.py)
words = json.loads((ED / "words_master.json").read_text(encoding="utf-8"))["words"]

ca.HEAD = ca.HEAD.replace(
    "Style: Cap,Inter,64,&H00FFFFFF,&H00FFFFFF,&H000F0E0C,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,60,60,{mv},1",
    "Style: Cap,Inter,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,1,2,140,140,{mv},1\n"
    "Style: Mid,Inter,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,1,2,140,140,898,1\n"
    "Style: Low,Inter,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H8C0B0B0B,-1,0,0,0,100,100,0,0,3,14,0,2,150,150,470,1")
assert "Style: Low" in ca.HEAD
ca.BLUE = r"{\c&H20F6D2&\fscx112\fscy112\t(0,90,\fscx100\fscy100)}"      # lime #D2F620 (ASS is BGR)
CUTS = sorted({0.0, TL["split"], TL["length"] + 1, *(p["out"][0] for p in TL["pieces"]), *(t for ab in FF for t in ab)})   # every cut starts a fresh phrase
body = [l for a, b in zip(CUTS, CUTS[1:]) for l in ca.build([w for w in words if a <= w["start"] < b], [])]
sec = lambda s: int(s.split(":")[1]) * 60 + float(s.split(":")[2])


def style(line):
    f = line.split(",", 3); t = sec(f[1])
    cut = min(c for c in CUTS if c > t + 0.01)                        # never let a word linger past its cut
    if sec(f[2]) > cut:
        f[2] = f"0:{int(cut // 60):02d}:{cut % 60:05.2f}"; line = ",".join(f)
    if t < TL["split"]:
        return line.replace(",Cap,", ",Mid,")
    if any(a <= t < b for a, b in FF):
        return line.replace(",Cap,", ",Low,")
    return line


body = [style(l) for l in body]
(ED / "captions.ass").write_text(ca.HEAD.format(mv=1920 - 938) + "\n".join(body) + "\n", encoding="utf-8")
print(len(body), "events:", sum(",Mid," in l for l in body), "split,", sum(",Low," in l for l in body), "full-frame")
