"""Final-file QA for reel-05. For each delivered cut:
  - sync: cross-correlate every kept range of the final audio against voice.wav (picture and voice share the master clock)
  - masking: force-align the script to the FINAL mix (MMS_FA letters) and compare each word's score with the clean voice;
    a word that drops sharply is hidden under SFX/music
  - loudness: integrated LUFS and true peak
Writes ../qa/final_qa.json. Usage: python qa_final.py"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from plan import OFF, VARIANTS

ED = Path(__file__).resolve().parent
JOB = ED.parent
TOOLS = Path(r"C:\Users\PARAS ARORA\AI_Editor\tools")
SR = 8000
M = {"2": "do", "2,000": "twothousand", "24": "chaubees", "1:": "one", "2:": "two", "3:": "three"}
toks = (JOB / "script.txt").read_text(encoding="utf-8").split()
clean = json.loads((ED / "fa_out.json").read_text(encoding="utf-8"))["all"]          # aligned on the clean preview voice
words = [{"tok": t, "fa": M.get(t, t), "start": w["start"] - OFF, "end": w["end"] - OFF, "clean": w["score"]} for t, w in zip(toks, clean)]


def pcm(path, sr=SR):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


voice = pcm(ED / "voice.wav")
report = {}
for name, v in VARIANTS.items():
    out = JOB / f"REEL05_{name}.mp4"
    fin = pcm(out)
    sync, lines, pos = [], [], 0.0
    for i, (a, b) in enumerate(v["ranges"]):
        seg_v = voice[int(a * SR):int(b * SR)]
        seg_f = fin[int(pos * SR):int((pos + b - a) * SR)]
        n = min(len(seg_v), len(seg_f)); L = 1 << int(np.ceil(np.log2(2 * n)))
        f = np.fft.irfft(np.fft.rfft(seg_f[:n], L) * np.conj(np.fft.rfft(seg_v[:n], L)), L)
        lag = int(np.argmax(np.r_[f[:int(0.2 * SR)], f[-int(0.2 * SR):]]))
        lag = lag if lag < int(0.2 * SR) else lag - 2 * int(0.2 * SR)
        sync.append(round(lag / SR * 1000, 1))
        ws = [w for w in words if a <= w["start"] < b]
        lines.append({"id": f"r{i}", "win": [round(max(0.0, pos + ws[0]["start"] - a - 0.15), 3), round(pos + min(b - a, ws[-1]["end"] - a + 0.25), 3)],
                      "text": " ".join(w["fa"] for w in ws)})
        pos += b - a
    lj, oj = ED / f"qa_fa_{name}.json", ED / f"qa_fa_{name}_out.json"
    lj.write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
    subprocess.run([sys.executable, str(TOOLS / "force_align.py"), str(out), str(lj), str(oj)], check=True, capture_output=True)
    got = json.loads(oj.read_text(encoding="utf-8"))
    flags = []
    for i, (a, b) in enumerate(v["ranges"]):
        ws = [w for w in words if a <= w["start"] < b]
        for w, g in zip(ws, got[f"r{i}"]):
            if g["score"] < 0.5 and g["score"] < w["clean"] - 0.25:
                flags.append({"word": w["tok"], "master_t": round(w["start"], 2), "clean": round(w["clean"], 2), "final": round(g["score"], 2)})
    eb = subprocess.run(["ffmpeg", "-v", "info", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    tail = eb[eb.rfind("Summary:"):]
    lufs = float(tail.split("I:")[1].split("LUFS")[0]); tp = float(tail.split("Peak:")[1].split("dBFS")[0])
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True).stdout)
    report[name] = {"duration": round(dur, 2), "lufs": lufs, "true_peak_dbfs": tp, "sync_ms_per_range": sync, "masked_words": flags}
    print(f"{name}: {dur:.2f}s  {lufs} LUFS  TP {tp}  sync {sync} ms  masked {len(flags)}", flags[:6])
(JOB / "qa" / "final_qa.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
