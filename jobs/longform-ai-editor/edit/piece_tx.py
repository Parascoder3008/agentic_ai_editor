"""Transcribe every kept body piece on its own, so Whisper can't merge a word repeated across a cut
(no prompt: a prompt full of repeats makes it loop). -> piece_tx.json (master times)."""
import json
import os
import subprocess

import numpy as np
from faster_whisper import WhisperModel

E = r"C:\Users\PARAS ARORA\AI_Editor\inbox\longform-ai-editor\edit"
WAV = r"D:\october videos\ai editor\ai editor.wav"
P = json.load(open(E + r"\body_pieces.json"))
x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", WAV, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                                 capture_output=True, check=True).stdout, np.float32)
m = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=os.cpu_count())
cache = {}
if os.path.exists(E + r"\piece_tx.json"):                     # reuse pieces whose edges didn't change
    cache = {(c["m0"], c["m1"]): c for c in json.load(open(E + r"\piece_tx.json", encoding="utf-8"))}
out = []
for i, p in enumerate(P):
    if (p["m0"], p["m1"]) in cache:
        out.append({**cache[(p["m0"], p["m1"])], "i": i})
        continue
    seg = x[int(p["m0"] * 16000): int(p["m1"] * 16000)]
    res, _ = m.transcribe(seg, language="hi", word_timestamps=True, beam_size=5, vad_filter=False,
                          condition_on_previous_text=False, temperature=(0.0, 0.2, 0.4))
    ws = [[round(p["m0"] + w.start, 2), round(p["m0"] + w.end, 2), w.word.strip()] for s in res for w in (s.words or [])]
    out.append({"i": i, "m0": p["m0"], "m1": p["m1"], "text": " ".join(w[2] for w in ws), "words": ws})
    print(i, round(p["m1"] - p["m0"], 2), out[-1]["text"][:90], flush=True)
json.dump(out, open(E + r"\piece_tx.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
