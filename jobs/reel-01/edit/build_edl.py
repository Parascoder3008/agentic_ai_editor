"""Build the cut list from aligned words: keep spans (by first/last word), split internal
pauses >= GAP, pad edges and snap them to the quietest 10 ms nearby. Writes:
  edl_ranges.json  - [[src_start, src_end], ...]
  words_out.json   - caption words on the OUTPUT timeline (display spelling)
  cues.json        - output time of every kept word, keyed "<line>:<word index>"
"""
import json
import re
import subprocess

import numpy as np

E = r"C:\Users\PARAS ARORA\Desktop\edit\edit"
GAP, PRE, POST = 0.45, 0.07, 0.11

al = json.load(open(E + r"\aligned.json", encoding="utf-8"))
al.update(json.load(open(E + r"\aligned_fix.json", encoding="utf-8")))

# (line, first word index, last word index)  — the editorial decisions
KEEP = [
    ("W2", 0, 23),                 # Bhai, maine kar diya apne video editor ki chhutti ... edit kiya hai
    ("W3", 0, 9),                  # Matlab, jahan par bhi main ruka tha, un bad pauses
    ("W4", 1, 13),                 # cut-vut lagane se leke, bad take se leke, maine kuch nahi kiya
    ("W5", 4, 11),                 # aur ek extra cheez main karke dikhata hoon
    ("W6", 0, 8),                  # Aisa karo, ek Claude ka logo lao yahan par
    ("W7", 0, 21),                 # isko 3D mein spin karke dikhao, thoda sa zoom in karo, ... hit kiya
    ("W8", 0, 4),                  # aur glass break ho gaya
    ("W9", 0, 4),                  # dekha, kya tagda cheez hai
    ("W10", 1, 16),                # ab aisa karo, mere ko side pe le jao, aur mere jo important workflows hain dikhao
    ("W12", 0, 26),                # One is the Content OS ... kaise kaam karte hain
    ("W13", 0, 3),                 # yeh sab cheezein dikhao
    ("W15", 6, 24),                # kaise hum content ke liye ideate karte hain ... manage karte hain
    ("W17", 0, 20),                # aur kaise mere bots ... check bhi nahi karta
    ("W18", 0, 14), ("W19", 0, 12),  # ab ek kaam karte hain ... let my finger turn that
    ("W20", 0, 20),                # when I'm moving the finger ... hit my head
    ("W21", 0, 4),                 # Oh no, ye kya kiya?
    ("W22", 3, 11), ("W22", 14, 17), ("W22", 26, 36),  # ab ek tagda sa effect lagao jaise hi main | aise khada hota hoon | aur aisa lage ki main ek documentary shoot kar raha hoon
    ("W23", 0, 4),                 # is type ka shot chahiye
    ("W25", 9, 9), ("W25b", 0, 11),  # agar | aapko bhi poori ki step by step guide chahiye aur workflow chahiye
    ("W26", 0, 12),                # to comment kar do EDIT, main saara kuch aapke DM mein bhej doonga
    ("W28a", 0, 9),                # agar aapko bhi poora ka poora workflow seekhna hai to
    ("W28b", 2, 35),               # maine apne channel ke description mein ... showcase karte hue
    ("W28b", 37, 44),              # to wahan pe sab kuch aapko mil jaega
    ("W28c", 7, 20),               # follow subscribe zaroor kar lena, agar maza aa raha hai aise content dekh ke
]
TAIL_HOLD = {("W21", 4): 0.75}     # hold after "kiya" for the head-grab reaction

DISPLAY = {"claude": "Claude", "opus": "Opus", "os": "OS", "dm": "DM", "whatsapp": "WhatsApp", "youtube": "YouTube",
           "i'm": "I'm", "i": "I"}

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", E + r"\C6944_clean.wav", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
env = np.sqrt(np.convolve(x ** 2, np.ones(160) / 160, mode="same"))[::160]   # 10 ms RMS


def quiet(t0, t1):
    a, b = int(max(0, t0) * 100), int(t1 * 100) + 1
    return (a + int(np.argmin(env[a:b]))) / 100 if b > a else t0


spans = []   # (src_s, src_e, [words with line/index])
for line, i0, i1 in KEEP:
    ws = [dict(w, line=line, idx=k) for k, w in enumerate(al[line]) if i0 <= k <= i1]
    cur = [ws[0]]
    for w in ws[1:]:
        if w["start"] - cur[-1]["end"] >= GAP:
            spans.append(cur); cur = [w]
        else:
            cur.append(w)
    spans.append(cur)

ranges, words_out, cues, t_out = [], [], {}, 0.0
for k, sp in enumerate(spans):
    hold = TAIL_HOLD.get((sp[-1]["line"], sp[-1]["idx"]), 0.0)
    s = quiet(sp[0]["start"] - PRE - 0.05, sp[0]["start"] - PRE + 0.03)
    e = quiet(sp[-1]["end"] + POST - 0.03, sp[-1]["end"] + POST + 0.05) + hold
    if ranges and s < ranges[-1][1]:
        s = ranges[-1][1]
    s = round(s * 25) / 25                      # frame-exact segments: cue math == real file
    e = s + max(1, round((e - s) * 25)) / 25
    ranges.append([round(s, 3), round(e, 3)])
    for w in sp:
        o0, o1 = t_out + (w["start"] - s), t_out + (w["end"] - s)
        cues[f"{w['line']}:{w['idx']}"] = round(o0, 3)
        words_out.append({"text": w["text"], "start": round(o0, 3), "end": round(o1, 3), "line": w["line"]})
    t_out += e - s

# display spelling for captions
txt = " ".join(w["text"] for w in words_out)
for i, w in enumerate(words_out):
    t = DISPLAY.get(w["text"], w["text"])
    if t == "five" and i + 2 < len(words_out) and words_out[i + 1]["text"] == "point":
        words_out[i]["text"] = "5.5"; words_out[i]["end"] = words_out[i + 2]["end"]
        words_out[i + 1]["text"] = words_out[i + 2]["text"] = ""; continue
    if t == "three" and i + 1 < len(words_out) and words_out[i + 1]["text"] == "d":
        words_out[i]["text"] = "3D"; words_out[i]["end"] = words_out[i + 1]["end"]; words_out[i + 1]["text"] = ""; continue
    if t in ("content", "business", "money") and i + 1 < len(words_out) and words_out[i + 1]["text"] == "os":
        t = t.capitalize()
    if t == "edit" and w["line"] == "W26":
        t = "EDIT"
    if t:
        words_out[i]["text"] = t
words_out = [w for w in words_out if w["text"]]
for i, w in enumerate(words_out):   # capitalise line starts
    if i == 0 or (words_out[i - 1]["line"] != w["line"] and w["line"] not in ("W4", "W19", "W25b", "W28b")):
        w["text"] = w["text"][:1].upper() + w["text"][1:]

json.dump(ranges, open(E + r"\edl_ranges.json", "w"), indent=0)
json.dump({"words": words_out}, open(E + r"\words_out.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump(cues, open(E + r"\cues.json", "w"), indent=0)
raw_len = 308.9
print(f"{len(ranges)} ranges, final {t_out:.2f}s (raw {raw_len:.1f}s, cut {raw_len - t_out:.1f}s)")
for line in dict.fromkeys(l for l, _, _ in KEEP):
    ws = [w for w in words_out if w["line"] == line]
    print(f"  {line:5s} {ws[0]['start']:6.2f}  {' '.join(w['text'] for w in ws)}")
