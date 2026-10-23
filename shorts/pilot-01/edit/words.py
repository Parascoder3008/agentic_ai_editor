"""Word timings for captions: HeyGen SRT windows -> MMS_FA force-align (windows with digits get
character-proportional timing, the aligner can't read numerals). Output: words.json for captions_ass.py."""
import json
import re
import subprocess
import sys
from pathlib import Path

JOB = Path(__file__).resolve().parent.parent
TOOLS = Path(r"C:\Users\PARAS ARORA\AI_Editor\tools")


def srt(path):
    out = []
    for blk in path.read_text(encoding="utf-8").strip().split("\n\n"):
        ln = blk.strip().splitlines()
        a, b = [sum(float(x) * m for x, m in zip(t.replace(",", ".").split(":"), (3600, 60, 1))) for t in ln[1].split(" --> ")]
        out.append((a, b, " ".join(ln[2:])))
    return out


subs = srt(JOB / "avatar.srt")
lines, prop = [], {}
for i, (a, b, text) in enumerate(subs):
    lo = max(a - 0.06, subs[i - 1][1] + 0.01) if i else max(0, a - 0.06)
    hi = min(b + 0.06, subs[i + 1][0] - 0.01) if i + 1 < len(subs) else b + 0.06
    if re.search(r"\d", text):
        prop[i] = (a, b, text)
    else:
        lines.append({"id": str(i), "win": [round(lo, 3), round(hi, 3)], "text": text})
(JOB / "edit" / "fa_lines.json").write_text(json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
subprocess.run([sys.executable, str(TOOLS / "force_align.py"), str(JOB / "avatar.mp4"),
                str(JOB / "edit" / "fa_lines.json"), str(JOB / "edit" / "fa_out.json")], check=True)
fa = json.loads((JOB / "edit" / "fa_out.json").read_text(encoding="utf-8"))

words = []
for i, (a, b, text) in enumerate(subs):
    if i in prop:  # spread by character count
        toks = text.split()
        n = sum(len(t) + 1 for t in toks)
        t = a
        for tok in toks:
            d = (b - a) * (len(tok) + 1) / n
            words.append({"text": tok, "start": round(t, 3), "end": round(t + d - 0.02, 3)})
            t += d
    else:
        words += [{"text": w["text"], "start": w["start"], "end": w["end"]} for w in fa[str(i)]]
(JOB / "edit" / "words.json").write_text(json.dumps({"words": words}, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(words), "words")
