"""Phrase-level Hinglish transcript: split on >= 0.35 s pauses (energy), then large-v3-turbo per phrase in hi AND en
(hi keeps Hindi words, en keeps English terms; I write the Roman line from both). Usage: python phrases.py <wav> <out.json>"""
import json
import sys

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

x, sr = sf.read(sys.argv[1], dtype="float32")
db = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(160) / 160, mode="same"))[::160] + 1e-9)   # 10 ms
floor = np.percentile(db, 10); speech = db > floor + 14
segs, i, n = [], 0, len(speech)
while i < n:
    if speech[i]:
        j = i
        while j < n and (speech[j] or (j + 35 < n and speech[j:j + 35].any())):
            j += 1
        if j - i > 15:
            segs.append((max(0, i - 8) / 100, min(n, j + 8) / 100))
        i = j
    i += 1
m = WhisperModel("large-v3-turbo", compute_type="int8")
out = []
for a, b in segs:
    c = x[int(a * sr): int(b * sr)]
    t = {lang: " ".join(s.text.strip() for s in m.transcribe(c, language=lang, beam_size=5, condition_on_previous_text=False,
                                                             vad_filter=False)[0]) for lang in ("hi", "en")}
    out.append({"win": [round(a, 2), round(b, 2)], **t})
    print(f"{a:7.2f}-{b:7.2f} | {t['hi']}\n                | {t['en']}", flush=True)
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
