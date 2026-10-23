"""reel-04 captions: <= 3 words, current word bright blue (#3AB0D8), every cut/layout change starts a fresh phrase.
  Low  boxed, baseline 1450 (default: over the shirt, clear of the IG bottom bar)
  Pip  left column under his top-left card (card layout 8.55-13.87), baseline 1112
  Mid  boxed, baseline 1010 (B-roll beat 31.40-35.80: clears the sticker in the bottom-left)
Usage: python captions.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
import captions_ass as ca  # noqa: E402

ED = Path(__file__).resolve().parent
TL = json.loads((ED / "timeline.json").read_text())
words = json.loads((ED / "words_master.json").read_text(encoding="utf-8"))["words"]
PIP, BROLL = (8.55, 13.87), (31.40, 35.80)

ca.HEAD = ca.HEAD.replace(
    "Style: Cap,Inter,64,&H00FFFFFF,&H00FFFFFF,&H000F0E0C,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,60,60,{mv},1",
    "Style: Cap,Inter,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H8C0F0E0C,-1,0,0,0,100,100,0,0,3,14,0,2,150,150,{mv},1\n"
    "Style: Pip,Inter,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H8C0F0E0C,-1,0,0,0,100,100,0,0,3,12,0,1,92,600,808,1\n"
    "Style: Mid,Inter,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H8C0F0E0C,-1,0,0,0,100,100,0,0,3,14,0,2,150,150,910,1")
assert "Style: Mid" in ca.HEAD
ca.BLUE = r"{\c&HD8B03A&\fscx112\fscy112\t(0,90,\fscx100\fscy100)}"        # #3AB0D8 (ASS is BGR)
CUTS = sorted({0.0, TL["length"] + 1, *(p["out"][0] for p in TL["pieces"]), *PIP, *BROLL})
sec = lambda s: int(s.split(":")[1]) * 60 + float(s.split(":")[2])
body = [l for a, b in zip(CUTS, CUTS[1:]) for l in ca.build([w for w in words if a <= w["start"] < b], [])]


def style(line):
    f = line.split(",", 3); t = sec(f[1])
    cut = min(c for c in CUTS if c > t + 0.01)                  # never let a word linger past its cut
    if sec(f[2]) > cut:
        f[2] = f"0:{int(cut // 60):02d}:{cut % 60:05.2f}"; line = ",".join(f)
    if PIP[0] <= t < PIP[1]:
        return line.replace(",Cap,", ",Pip,")
    if BROLL[0] <= t < BROLL[1]:
        return line.replace(",Cap,", ",Mid,")
    return line


body = [style(l) for l in body]
(ED / "captions.ass").write_text(ca.HEAD.format(mv=1920 - 1450) + "\n".join(body) + "\n", encoding="utf-8")
print(len(body), "events:", sum(",Pip," in l for l in body), "pip,", sum(",Mid," in l for l in body), "mid")
