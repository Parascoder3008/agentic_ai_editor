"""Word-by-word captions for the Equal ad (Poppins ExtraBold, white, current word Equal lime), reusing the
chunking from tools/captions_ass.py. Hidden on full-screen app cutaways, the Equal-voice card and the end card."""
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
import captions_ass as ca  # noqa: E402

ED = Path(__file__).resolve().parent
W = json.loads((ED / "words_fa.json").read_text(encoding="utf-8"))
E = json.loads((ED / "edl.json").read_text(encoding="utf-8"))
SEG = {s["id"]: s for s in E["body"]}


def insert(words, after, text):
    """the aligner drops numerals: put one back between `after` and the next word"""
    i = next(k for k, w in enumerate(words) if w["text"].strip(",.").lower() == after)
    a, b = words[i]["end"], words[i + 1]["start"]
    words.insert(i + 1, {"text": text, "start": round(a, 3), "end": round(max(b, a + 0.12), 3)})


insert(W["s11"], "ki", "9")
insert(W["s12"], "almost", "10")
words = [{"text": w["text"], "start": w["start"], "end": w["end"]} for k, v in W.items() if k != "s8" for w in v]
words.sort(key=lambda w: w["start"])
hide = [[18.40, 21.95], [23.80, 28.235], [28.76, 32.48], [42.45, 45.57], [47.30, 50.45],   # app UI cutaways
        SEG["s8"]["out"], [E["end_card"][0], E["length"] + 1]]

ca.HEAD = ca.HEAD.replace("Style: Cap,Inter,64,&H00FFFFFF,&H00FFFFFF,&H000F0E0C,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,60,60,{mv},1",
                          "Style: Cap,Poppins ExtraBold,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,150,150,{mv},1\n"
                          "Style: CapI,Poppins ExtraBold,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,150,150,720,1")
assert "Poppins" in ca.HEAD
ca.BLUE = r"{\c&H2AE2A6&\fscx110\fscy110\t(0,90,\fscx100\fscy100)}"      # Equal lime #A6E22A (ASS is BGR)
body = ca.build(words, hide)
# intro captions sit above the phones in the AI shots (baseline y 1200); body captions just below the lapel mic (y 1530)
sec = lambda ts: int(ts.split(":")[1]) * 60 + float(ts.split(":")[2])
HIGH = [(0, E["intro_end"]), (56.40, 58.36), (66.05, 67.59)]          # AI shots: phone sits where body captions go
body = [l.replace(",Cap,", ",CapI,") if any(a <= sec(l.split(",")[1]) < b for a, b in HIGH) else l for l in body]
(ED / "captions.ass").write_text(ca.HEAD.format(mv=1920 - 1530) + "\n".join(body) + "\n", encoding="utf-8")
print(len(body), "caption events")
