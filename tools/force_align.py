"""Force-align known (Roman-script) text to audio windows with torchaudio MMS_FA.

Input JSON: [{"id": "W2", "win": [s, e], "text": "bhai maine kar diya ..."}, ...]   (camera-timeline seconds)
Output JSON: {"W2": [{"text": "bhai", "start": s, "end": e, "score": p}, ...], ...}
Each window must contain exactly the words in its text (the aligner can't skip speech).

Usage: python force_align.py <audio> <lines.json> <out.json>
"""
import json
import re
import subprocess
import sys

import numpy as np
import torch
from torchaudio.pipelines import MMS_FA as bundle

SR = bundle.sample_rate  # 16 kHz


def norm(w):
    return re.sub(r"[^a-z']", "", w.lower()).replace("'", "")


def main(audio, lines_path, out_path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", audio, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    sig = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    model, tok, aligner = bundle.get_model(), bundle.get_tokenizer(), bundle.get_aligner()
    out = {}
    for ln in json.load(open(lines_path, encoding="utf-8")):
        s, e = ln["win"]
        words = [w for w in ln["text"].split() if norm(w)]
        wav = torch.from_numpy(sig[int(s * SR): int(e * SR)].copy()).unsqueeze(0)
        with torch.inference_mode():
            em, _ = model(wav)
            spans = aligner(em[0], tok([norm(w) for w in words]))
        ratio = wav.size(1) / em.size(1) / SR
        out[ln["id"]] = [{"text": w, "start": round(s + sp[0].start * ratio, 3), "end": round(s + sp[-1].end * ratio, 3),
                          "score": round(float(sum(x.score for x in sp) / len(sp)), 3)} for w, sp in zip(words, spans)]
        low = [x["text"] for x in out[ln["id"]] if x["score"] < 0.3]
        print(f"{ln['id']:4s} {len(words):3d} words  {out[ln['id']][0]['start']:7.2f}-{out[ln['id']][-1]['end']:7.2f}"
              + (f"  LOW: {' '.join(low)}" if low else ""), flush=True)
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main(*sys.argv[1:4])
