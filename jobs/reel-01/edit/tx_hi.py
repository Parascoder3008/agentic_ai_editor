import json, os, sys, time
from faster_whisper import WhisperModel

SRC = r"C:\Users\PARAS ARORA\Desktop\edit\edit\C6944_clean.wav"
OUT = r"C:\Users\PARAS ARORA\Desktop\edit\edit\hi\transcripts\C6944_clean.json"
PROMPT = ("अम्म, तो, मतलब, हाँ, अच्छा, अह, basically. भाई, मैंने video editor को छुट्टी दे दी क्योंकि "
          "Claude Opus 5.5 ने पूरी video edit की. Content OS, Business OS, Money OS, workflow.")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
t0 = time.time()
m = WhisperModel("medium", device="cpu", compute_type="int8", cpu_threads=os.cpu_count())
segs, info = m.transcribe(SRC, language="hi", word_timestamps=True, beam_size=1, vad_filter=True,
                          vad_parameters={"min_silence_duration_ms": 400},
                          condition_on_previous_text=False, initial_prompt=PROMPT)
words = []
for s in segs:
    print(f"[{s.start:7.2f}-{s.end:7.2f}] {s.text.strip()}  ({time.time() - t0:.0f}s)", flush=True)
    for w in s.words or []:
        words.append({"text": w.word.strip(), "start": w.start, "end": w.end, "type": "word",
                      "speaker_id": "speaker_0", "logprob": w.probability})
json.dump({"language_code": "hi", "words": words}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"DONE {len(words)} words in {time.time() - t0:.0f}s", flush=True)
