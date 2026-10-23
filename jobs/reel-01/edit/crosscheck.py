"""Cross-check forced-alignment word times against (a) Whisper chunk word times and
(b) the loudness curve. Flags: words in silence, stretched words, and first/last-word
disagreement with Whisper > 0.35 s."""
import json

E = r"C:\Users\PARAS ARORA\Desktop\edit\edit"
al = json.load(open(E + r"\aligned.json", encoding="utf-8"))
wh = [w for w in json.load(open(E + r"\hi\transcripts\C6944_chunks.json", encoding="utf-8"))["words"]]
rms = json.load(open(E + r"\waveform.json"))["rms"]
lines = {l["id"]: l for l in json.load(open(E + r"\lines.json", encoding="utf-8"))}


def energy(a, b):
    seg = rms[int(a * 10): max(int(a * 10) + 1, int(b * 10))]
    return sum(seg) / len(seg)


for k, ws in al.items():
    s, e = lines[k]["win"]
    wwin = [w for w in wh if s - 0.2 <= w["start"] <= e + 0.2]
    flags = []
    for w in ws:
        d = w["end"] - w["start"]
        if d > 0.75:
            flags.append(f"stretched '{w['text']}' {d:.2f}s@{w['start']:.2f}")
        if energy(w["start"], w["end"]) < 0.03:
            flags.append(f"silent '{w['text']}'@{w['start']:.2f}")
    if wwin:
        if abs(wwin[0]["start"] - ws[0]["start"]) > 0.35:
            flags.append(f"first word: align {ws[0]['start']:.2f} vs whisper {wwin[0]['start']:.2f}")
        if abs(wwin[-1]["end"] - ws[-1]["end"]) > 0.35:
            flags.append(f"last word: align {ws[-1]['end']:.2f} vs whisper {wwin[-1]['end']:.2f}")
    # speech energy inside the window but before/after the aligned words = untranscribed speech
    if energy(s, ws[0]["start"] - 0.15) > 0.12 and ws[0]["start"] - s > 0.5:
        flags.append(f"speech before first word ({s:.2f}-{ws[0]['start']:.2f})")
    print(f"{k:4s} " + ("OK" if not flags else " | ".join(flags)))
