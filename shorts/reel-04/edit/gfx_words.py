"""gfx/words.js for the kinetic captions: [start, end, text, accent] per word on the master timeline.
Accent = the one word per line that turns pink serif (Clauditing style). Usage: python gfx_words.py"""
import json
from pathlib import Path

ED = Path(__file__).resolve().parent
W = json.loads((ED / "words_master.json").read_text(encoding="utf-8"))["words"]
ACCENT_AT = [2.35, 8.18, 10.61, 12.17, 15.31, 17.30, 22.33, 25.50, 27.02, 29.35, 41.88, 44.83, 46.73, 47.53, 50.17, 52.27,
             54.55, 56.06, 58.21, 60.31, 61.78, 64.80, 66.85]
out = []
for w in W:
    acc = any(abs(w["start"] - a) < 0.06 for a in ACCENT_AT)
    out.append([w["start"], w["end"], w["text"], 1 if acc else 0])
hit = sum(o[3] for o in out)
(ED.parent / "gfx" / "words.js").write_text("window.WORDS=" + json.dumps(out, ensure_ascii=False) + ";", encoding="utf-8")
print(len(out), "words,", hit, "accents of", len(ACCENT_AT))
