"""Chunked Hindi transcription: every phrase (from the English timing pass) and every gap
between phrases is decoded on its own, so a bad patch can't snowball. Words keep
absolute (camera-timeline) timestamps."""
import json, os, re, subprocess, time
import numpy as np
from faster_whisper import WhisperModel

E = r"C:\Users\PARAS ARORA\Desktop\edit\edit"
SRC = E + r"\C6944_clean.wav"
OUT = E + r"\hi\transcripts\C6944_chunks.json"
PROMPT = "भाई, मैंने video editor की छुट्टी कर दी. Claude Opus 5.5, Content OS, Business OS, Money OS. अम्म, तो, मतलब."

ranges = [tuple(map(float, m)) for m in re.findall(r"\[(\d+\.\d+)-(\d+\.\d+)\]", open(E + r"\takes_packed.md", encoding="utf-8").read())]
chunks = []
for i, (s, e) in enumerate(ranges):
    chunks.append((max(0, s - 0.35), e + 0.35, "phrase"))
    if i + 1 < len(ranges) and ranges[i + 1][0] - e > 1.5:
        chunks.append((e + 0.2, ranges[i + 1][0] - 0.2, "gap"))
chunks.append((ranges[-1][1] + 0.2, 308.9, "gap"))

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

m = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=os.cpu_count())
words, t0 = [], time.time()
for s, e, kind in chunks:
    clip = audio[int(s * 16000): int(e * 16000)]
    if len(clip) < 8000 or float(np.sqrt((clip ** 2).mean())) < 0.004:   # silent gap
        continue
    segs, _ = m.transcribe(clip, language="hi", word_timestamps=True, beam_size=5, vad_filter=False,
                           condition_on_previous_text=False, initial_prompt=PROMPT, temperature=0.0)
    txt = []
    for sg in segs:
        for w in sg.words or []:
            words.append({"text": w.word.strip(), "start": round(s + w.start, 3), "end": round(s + w.end, 3),
                          "type": "word", "speaker_id": "speaker_0", "prob": round(w.probability, 3), "chunk": kind})
            txt.append(w.word.strip())
    print(f"[{s:7.2f}-{e:7.2f}] {kind:6s} {' '.join(txt)}  ({time.time() - t0:.0f}s)", flush=True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({"language_code": "hi", "words": words}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"DONE {len(words)} words in {time.time() - t0:.0f}s", flush=True)
