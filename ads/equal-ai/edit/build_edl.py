"""Equal AI ad: voice EDL. Lav ("equal ai.wav") ranges in story order, edges snapped to the quietest 10 ms
nearby (start edges look only earlier, end edges only later, so no word is clipped). Camera time = lav + OFFSET.
Writes edl.json with output-timeline positions. Intro voice lines are placed over the AI shots, not concatenated.
"""
import json
from pathlib import Path

import numpy as np
import soundfile as sf

ED = Path(__file__).resolve().parent
LAV = r"C:\Users\PARAS ARORA\Desktop\equal ai\equal ai.wav"
OFFSET = 21.22                      # cam = lav + OFFSET (checked at 60/300/500/780 s, drift <= 10 ms)
PAD_IN, PAD_OUT = 0.06, 0.09        # breathing room kept around the words

# (id, lav_start, lav_end, roman text for captions, kind)
INTRO = [
    ("v1", 32.95, 33.92, "Meeting mein ho,"),
    ("v2", 34.60, 35.42, "gym mein ho,"),
    ("v3", 42.62, 44.00, "ya raat ko kaam kar rahe ho."),
    ("v4", 44.82, 47.80, "Koi hai jo aapki saari call sambhal leta hai."),
]
BODY = [
    ("s1", 58.05, 59.55, "aur salary bhi nahi maangta,", "cam"),
    ("s2", 65.28, 69.30, "kyunki ye assistant jo hai, wo mere phone mein hai, jiska naam hai bhai, Equal AI.", "cam"),
    ("s3", 269.12, 273.24, "Number saved ho ya phir unknown number ho, Equal AI call uthata hai,", "cam"),
    ("s4", 275.38, 277.08, "aur bhai meri jagah pe baat karta hai.", "cam"),
    ("s5", 290.30, 296.45, "Aur call ke baad mujhe actually batata bhi hai ki kisne call kiya, kyun kiya, aur uski poori ki poori summary aur transcription de deta hai.", "cam"),
    ("s6", 307.95, 311.95, "Kisi ko call back chahiye? Ek tap. WhatsApp pe reply chahiye? Ek tap.", "cam"),
    ("s7", 734.58, 737.38, "Aur dekho bhai, ye mere paas call aa raha hai isi assistant se.", "cam"),
    ("s8", 741.72, 743.95, "I am Equal, your personal call assistant.", "ai_voice"),
    ("s9", 321.96, 325.70, "Main isko instruction de sakta hoon ki kaun se calls ko kaise handle karna hai,", "cam"),
    ("s10", 333.48, 337.25, "jaise agar bhai delivery wale call kar rahe hon, to bhai parcel mere reception pe chhudwa do.", "cam"),
    ("s11", 361.38, 366.15, "Ye Hindi, English, yahan tak ki 9 se zyada languages mein answer kar sakta hai.", "cam"),
    ("s12", 452.68, 456.05, "Aur India mein almost 10 lakh se zyada log is app ko roz use karte hain.", "cam"),
    ("s13", 788.27, 794.90, "Jaise bade-bade bosses hote hain, apne call ke liye ek assistant rakhte hain, aapke paas ek assistant aapke phone mein aa jayega.", "cam"),
    ("s14", 493.85, 496.48, "Abhi Equal app download karo, Play Store aur App Store se.", "cam"),
    ("s15", 504.50, 508.22, "Arre yaar, phir call aa raha hai... koi baat nahi, mera assistant handle kar lega.", "cam"),
]
INTRO_END = 9.85                    # AI intro length on the output timeline (body starts here)
INTRO_AT = {"v1": 0.30, "v2": 2.85, "v3": 5.05, "v4": 6.68}   # output time each intro line starts

x, sr = sf.read(LAV)
x = x.mean(1) if x.ndim > 1 else x
hop = int(0.01 * sr)
rms = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, mode="same"))


def snap(t, direction, span=0.12):
    """quietest point within span before (direction=-1) or after (+1) t."""
    a, b = (t - span, t) if direction < 0 else (t, t + span)
    i0, i1 = int(a * sr), int(b * sr)
    return (i0 + int(np.argmin(rms[i0:i1:hop // 2]) * (hop // 2))) / sr


NOSNAP_IN = {"s8", "s9"}            # starts sit right after another word: keep them exactly


def edges(s, e, sid=""):
    a = s if sid in NOSNAP_IN else snap(s - PAD_IN + 0.06, -1)
    return round(a, 3), round(snap(e + PAD_OUT - 0.06, +1), 3)


out = {"offset": OFFSET, "intro_end": INTRO_END, "intro": [], "body": []}
for vid, s, e, txt in INTRO:
    a, b = edges(s, e)
    out["intro"].append({"id": vid, "lav": [a, b], "at": INTRO_AT[vid], "text": txt})
t = INTRO_END
for sid, s, e, txt, kind in BODY:
    a, b = edges(s, e, sid)
    d = round(b - a, 3)
    out["body"].append({"id": sid, "lav": [a, b], "cam": [round(a + OFFSET, 3), round(b + OFFSET, 3)],
                        "out": [round(t, 3), round(t + d, 3)], "text": txt, "kind": kind})
    t += d
out["end_card"] = [round(t, 3), round(t + 2.6, 3)]
out["length"] = round(t + 2.6, 3)
(ED / "edl.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
for v in out["intro"]:
    print(f"  {v['id']:4s} lav {v['lav'][0]:7.2f}-{v['lav'][1]:7.2f}  @ {v['at']:5.2f}  {v['text']}")
for s in out["body"]:
    print(f"  {s['id']:4s} lav {s['lav'][0]:7.2f}-{s['lav'][1]:7.2f}  out {s['out'][0]:6.2f}-{s['out'][1]:6.2f}  {s['text'][:60]}")
print("end card", out["end_card"], "length", out["length"])
