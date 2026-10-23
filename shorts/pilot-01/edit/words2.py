"""Caption word timings for the pronunciation-approved audio: force-align the Roman script (captions
stay Roman) to the audio in one window; numerals are aligned by their spoken form and shown as digits.
Also writes line_times.json (start/end of each script line) for the IG / YT cuts.

Usage: python words2.py <audio>   -> words.json, line_times.json
"""
import json
import subprocess
import sys
from pathlib import Path

ED = Path(__file__).resolve().parent
JOB = ED.parent
TOOLS = Path(r"C:\Users\PARAS ARORA\AI_Editor\tools")
SPOKEN = {"9,800": "nine thousand eight hundred", "33": "thirty three", "25": "twenty five", "7": "seven"}

audio = sys.argv[1]
lines = [l.strip() for l in (JOB / "script.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
toks = [(li, w) for li, l in enumerate(lines) for w in l.split()]
spoken = [(li, w, SPOKEN.get(w.rstrip(",.:!?"), w).split()) for li, w in toks]
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio],
                           capture_output=True, text=True, check=True).stdout)
text = " ".join(" ".join(s) for _, _, s in spoken)
(ED / "fa2_lines.json").write_text(json.dumps([{"id": "A", "win": [0.0, round(dur, 3)], "text": text}]), encoding="utf-8")
subprocess.run([sys.executable, str(TOOLS / "force_align.py"), audio, str(ED / "fa2_lines.json"), str(ED / "fa2_out.json")], check=True)
fa = iter(json.loads((ED / "fa2_out.json").read_text(encoding="utf-8"))["A"])

words, lt = [], {}
for li, w, s in spoken:
    parts = [next(fa) for _ in s]
    words.append({"text": w, "start": parts[0]["start"], "end": parts[-1]["end"], "line": li + 1})
    a, b = lt.get(li + 1, (parts[0]["start"], 0))
    lt[li + 1] = (a, parts[-1]["end"])
(ED / "words.json").write_text(json.dumps({"words": words}, ensure_ascii=False, indent=1), encoding="utf-8")
(ED / "line_times.json").write_text(json.dumps({k: [round(a, 3), round(b, 3)] for k, (a, b) in lt.items()}, indent=1), encoding="utf-8")
print(len(words), "words;", " | ".join(f"L{k} {a:.2f}-{b:.2f}" for k, (a, b) in lt.items()))
