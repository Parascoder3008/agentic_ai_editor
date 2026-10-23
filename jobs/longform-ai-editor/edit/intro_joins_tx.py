"""Whisper each side of the intro's two block joins separately (repeat check across the reel-block jumps)."""
import os
import subprocess

import numpy as np
from faster_whisper import WhisperModel

INTRO = r"C:\Users\PARAS ARORA\AI_Editor\inbox\longform-ai-editor\edit\intro\intro_preview.mkv"
x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", INTRO, "-map", "0:a", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                                 capture_output=True, check=True).stdout, np.float32)
m = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=os.cpu_count())
for j in (13.40, 24.16, 42.40):
    sides = []
    for a, b in ((j - 2.5, j), (j, j + 2.5)):
        seg = x[int(max(0, a) * 16000): int(b * 16000)]
        if len(seg) < 1600:
            sides.append("(end)")
            continue
        res, _ = m.transcribe(seg, language="hi", beam_size=5, vad_filter=False, condition_on_previous_text=False,
                              temperature=(0.0, 0.2, 0.4))
        sides.append(" ".join(s.text.strip() for s in res))
    print(f"intro join {j:6.2f}: ...{sides[0]} || {sides[1]}...", flush=True)
