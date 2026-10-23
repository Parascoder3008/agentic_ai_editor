"""Long-form Hinglish transcription that doesn't loop: VAD-split into short speech chunks
(<= MAX_S, cut at silences), large-v3-turbo in Hindi on each chunk, absolute word times.
Output: {"words": [{text,start,end,prob}], "chunks": [[s,e,text]]}. Progress log on stdout.

Usage: python transcribe_hinglish.py <audio> <out.json> [--prompt "..."]
"""
import argparse
import json
import os
import subprocess
import time

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.vad import VadOptions, get_speech_timestamps

SR, MAX_S = 16000, 14.0

ap = argparse.ArgumentParser()
ap.add_argument("audio")
ap.add_argument("out")
ap.add_argument("--prompt", default="भाई, Claude Opus 5.5, Claude Code, HyperFrames, video editor. अम्म, तो, मतलब.")
a = ap.parse_args()

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", a.audio, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
speech = get_speech_timestamps(x, VadOptions(min_silence_duration_ms=300, speech_pad_ms=150))

# merge VAD regions into chunks <= MAX_S, splitting only at silences
chunks, cur = [], None
for r in speech:
    s, e = r["start"] / SR, r["end"] / SR
    if cur and e - cur[0] <= MAX_S:
        cur[1] = e
    else:
        if cur:
            chunks.append(cur)
        cur = [s, e]
if cur:
    chunks.append(cur)
print(f"{len(chunks)} chunks, {sum(e - s for s, e in chunks):.0f}s speech of {len(x) / SR:.0f}s", flush=True)

m = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=os.cpu_count())
words, out_chunks, t0 = [], [], time.time()
for i, (s, e) in enumerate(chunks):
    seg = x[int(s * SR): int(e * SR)]
    res, _ = m.transcribe(seg, language="hi", word_timestamps=True, beam_size=5, vad_filter=False,
                          condition_on_previous_text=False, initial_prompt=a.prompt, temperature=0.0)
    txt = []
    for sg in res:
        for w in sg.words or []:
            words.append({"text": w.word.strip(), "start": round(s + w.start, 3), "end": round(s + w.end, 3),
                          "prob": round(w.probability, 3)})
            txt.append(w.word.strip())
    out_chunks.append([round(s, 2), round(e, 2), " ".join(txt)])
    print(f"[{i + 1}/{len(chunks)} {s:7.2f}-{e:7.2f}] {' '.join(txt)}  ({time.time() - t0:.0f}s)", flush=True)
    if i % 20 == 0:
        json.dump({"words": words, "chunks": out_chunks}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"words": words, "chunks": out_chunks}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"DONE {len(words)} words in {time.time() - t0:.0f}s", flush=True)
