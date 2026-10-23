"""Reel-03 captions on the master timeline (0-59.1 s). Times = force-aligned TTS words + the measured avatar
offset; display text = script.txt tokens (digits, LEVEL), index-matched to the aligned words.
Split beats: seam captions (baseline y 1000). Full-frame beats (hook, face-only): low, on a dark box (y 1440).
Hidden during the payoff's big CHATBOT/ASSISTANT text."""
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
import captions_ass as ca  # noqa: E402

ED = Path(__file__).resolve().parent
OFFSET = 0.023                                   # avatar audio lags the TTS by 23 ms (cross-correlation)
SPLIT = 7.40                                     # hook + face-only end here
HIDE = [[43.10, 46.45]]                          # payoff big text

fa = json.loads((ED / "fa_out.json").read_text(encoding="utf-8"))["all"]
toks = (ED.parent / "script.txt").read_text(encoding="utf-8").split()
assert len(toks) == len(fa), (len(toks), len(fa))
words = [{"text": t.rstrip(":"), "start": w["start"] + OFFSET, "end": w["end"] + OFFSET} for t, w in zip(toks, fa)]

ca.HEAD = ca.HEAD.replace(
    "Style: Cap,Inter,64,&H00FFFFFF,&H00FFFFFF,&H000F0E0C,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,60,60,{mv},1",
    "Style: Cap,Inter,70,&H00FFFFFF,&H00FFFFFF,&H000F0E0C,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,150,150,{mv},1\n"
    "Style: Low,Inter,66,&H00FFFFFF,&H00FFFFFF,&H00000000,&H8C0C0E0F,-1,0,0,0,100,100,0,0,3,14,0,2,150,150,480,1")
assert "Style: Low" in ca.HEAD
ca.BLUE = r"{\c&HD8B03A&\fscx112\fscy112\t(0,90,\fscx100\fscy100)}"      # brand blue-bright #3AB0D8 (ASS is BGR)
body = ca.build(words, HIDE)
sec = lambda s: int(s.split(":")[1]) * 60 + float(s.split(":")[2])
body = [l.replace(",Cap,", ",Low,") if sec(l.split(",")[1]) < SPLIT else l for l in body]
(ED / "captions.ass").write_text(ca.HEAD.format(mv=1920 - 1000) + "\n".join(body) + "\n", encoding="utf-8")
json.dump({"words": words}, open(ED / "words_master.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(body), "caption events;", sum(",Low," in l for l in body), "low")
