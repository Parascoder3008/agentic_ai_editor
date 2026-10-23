"""Final-file QA. For each delivered cut: transcribe every kept piece and every joint (+-1.2 s) from the FINAL mp4 audio
(masking / repeated words), and cross-correlate each piece against voice.wav (A/V drift; picture and voice.wav share the
master timeline). Writes qa/final_qa.json. Usage: python qa_final.py"""
import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

ED = Path(__file__).resolve().parent
JOB = ED.parent
TL = json.loads((ED / "timeline.json").read_text())
SR = 16000


def pcm(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def env(x):
    e = np.abs(x[: len(x) // 80 * 80]).reshape(-1, 80).mean(1)       # 200 Hz envelope
    return (e - e.mean()) / (e.std() + 1e-9)


def lag_ms(a, b, max_ms=200):
    a, b = env(a), env(b); n = min(len(a), len(b)); a, b = a[:n], b[:n]
    k = max_ms // 5
    c = [np.dot(a[max(0, -l):n - max(0, l)], b[max(0, l):n - max(0, -l)]) for l in range(-k, k + 1)]
    return (int(np.argmax(c)) - k) * 5, float(max(c) / n)


v, vsr = sf.read(ED / "voice.wav", dtype="float32")
voice = v.mean(1)
voice = np.interp(np.arange(int(len(voice) * SR / vsr)) / SR, np.arange(len(voice)) / vsr, voice).astype(np.float32)
pieces = TL["pieces"]
m = WhisperModel("large-v3-turbo", compute_type="int8")
ask = lambda x: " ".join(r.text.strip() for r in m.transcribe(x, language="hi", beam_size=5, condition_on_previous_text=False, vad_filter=False)[0])
report = {}
for name in ("instagram", "youtube"):
    fin = pcm(JOB / f"REEL04_{name}.mp4")
    rows, joints, t = [], [], 0.0
    for a, b in TL[{"instagram": "ig", "youtube": "yt"}[name]]["ranges"]:
        for p in pieces:
            s, e = p["out"]
            if s < a - 0.01 or e > b + 0.01:
                continue
            o0, o1 = t + s - a, t + e - a
            seg = fin[int(o0 * SR): int(o1 * SR)]
            lag, peak = lag_ms(seg, voice[int(s * SR): int(e * SR)])
            rows.append({"out": [round(o0, 2), round(o1, 2)], "master": [s, e], "lag_ms": lag, "corr": round(peak, 2), "heard": ask(seg)})
            if o0 > 0.01:
                joints.append({"at": round(o0, 2), "heard": ask(fin[int((o0 - 1.2) * SR): int((o0 + 1.2) * SR)])})
        t += b - a
    report[name] = {"length": round(len(fin) / SR, 2), "pieces": rows, "joints": joints}
    print(f"== {name} {len(fin) / SR:.2f}s  max |lag| {max(abs(r['lag_ms']) for r in rows)} ms")
    for r in rows:
        print(f"  {r['out'][0]:6.2f}-{r['out'][1]:6.2f} lag {r['lag_ms']:+4d} ms corr {r['corr']:.2f} | {r['heard']}")
    print("  -- joints")
    for j in joints:
        print(f"  @{j['at']:6.2f} | {j['heard']}")
(JOB / "qa" / "final_qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
