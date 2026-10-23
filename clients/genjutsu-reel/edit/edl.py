"""DJI how-to cut: pieces defined by first/last word (force-aligned, edit/fa_out.json), edges snapped to the quietest
10 ms inside the gap next to the word (never inside a word), then every piece is transcribed on its own and each joint
printed (last words || first words) so a repeated or clipped word at a cut can't hide.
Writes pieces_ig.json / pieces_yt.json (source seconds, frame-snapped at 25 fps). Usage: python edl.py"""
import json
import subprocess
from pathlib import Path

import numpy as np

ED = Path(__file__).resolve().parent
WAV = ED.parent / "src" / "dji.wav"
FPS = 25
x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(WAV), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                                 capture_output=True, check=True).stdout, np.float32)
db = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(160) / 160, mode="same"))[::160] + 1e-9)   # 10 ms RMS
fa = json.loads((ED / "fa_out.json").read_text(encoding="utf-8"))
W = [(k, i, w) for k, ws in fa.items() for i, w in enumerate(ws)]


def word(win, text, nth=1):
    hits = [w for k, i, w in W if k == win and w["text"] == text]
    return hits[nth - 1]


def valley(lo, hi):
    """quietest 10 ms between lo and hi (seconds)"""
    a, b = int(lo * 100), max(int(lo * 100) + 1, int(hi * 100))
    return (a + int(np.argmin(db[a:b]))) / 100


def edge_in(w, prev_end):
    return valley(max(prev_end, w["start"] - 0.10), w["start"] - 0.02)             # tight: <= 0.10 s lead-in


def edge_out(w, next_start):
    """<= 0.12 s tail; if that window never gets quiet (word decays slowly), allow up to 0.22 s"""
    lo, hi = w["end"] + 0.03, min(next_start, w["end"] + 0.12)
    t = valley(lo, hi)
    if db[int(t * 100)] > np.percentile(db[int(lo * 100): int(max(lo + 0.05, min(next_start, w["end"] + 0.6)) * 100) + 1], 10) + 8:
        t = valley(lo, min(next_start, w["end"] + 0.22))
    return t


def nxt(win, w):
    ws = fa[win]; i = ws.index(w)
    return ws[i + 1]["start"] if i + 1 < len(ws) else w["end"] + 0.6


def prv(win, w):
    ws = fa[win]; i = ws.index(w)
    return ws[i - 1]["end"] if i > 0 else w["start"] - 0.6


def piece(win, first, last, f_nth=1, l_nth=1, lwin=None):
    lwin = lwin or win
    a, b = word(win, first, f_nth), word(lwin, last, l_nth)
    s, e = edge_in(a, prv(win, a)), edge_out(b, nxt(lwin, b))
    snap = lambda t: round(round(t * FPS) / FPS, 3)
    return {"src": [snap(s), snap(e)], "text": f"{first} … {last}"}


# v3: edges measured by hand (5 ms energy + CTC letter times + Whisper on candidate cuts). He restarts mid-sentence with
# no pause and Whisper silently deletes the restart, so every one of these was a hidden repeat or a clipped word in v1/v2.
P = lambda s, e, text: {"src": [s, e], "text": text}
COMMON = [P(24.96, 26.44, "aur bhai ye karna na bahut easy hai"),      # 26.49 abandoned "maine na poori ek" begins
          P(27.48, 33.64, "maine na poori ek guide … connect"),         # restart onset 27.53
          P(92.48, 94.04, "phir apni raw video de do chatgpt ko"),      # "ko|jo" run together; 94.08 already has the "j"
          P(94.80, 97.60, "jo bhi usmein changes … kar lega"),          # abandoned "jo bhi usmein cha-" 94.07-94.75
          P(65.24, 69.00, "jo guide … kar lega"),
          P(104.72, 107.68, "lekin ek cheez … use karte"),              # 104.72 dip after a first "lekin"; stray "aur" from 107.70
          P(108.60, 110.00, "aur is type ke videos aap banate"),        # "uske" (abandoned) starts 110.03
          P(112.44, 113.68, "usmein aapke credits lagte hain"),         # dip before the abandoned "obviously"
          P(114.48, 116.56, "and obviously uske andar kharcha aata hai"),
          P(126.60, 131.96, "but agar dekha jaaye … sasta hi hai, agar flex karna ho to")]   # one take, no cut needed
# CTA: drops "to agar aapko poori guide chahiye" (IG) and "agar poori guide chahiye to" (YT): "agar … to agar" and
# "poori guide … poori guide" repeated within three seconds.
IG_TAIL = [P(140.84, 143.48, "comment kar do flex aapke dm mein poori guide bhej doonga"),   # "k" closure / "b" closure
           P(146.24, 148.00, "bas follow kar lena warna dm nahi jaayega")]                 # breath before "bas" 146.29 cut
YT_TAIL = [P(150.32, 153.72, "hamara whatsapp channel … youtube ke"),     # abandoned "u-" onset 153.77
           P(154.24, 156.12, "uske andar aapko poori guide mil jaayegi"),
           P(158.16, 159.88, "baaki aise content ke liye subscribe kar do")]   # second "baaki" (b closure; first one dropped)
IG, YT = COMMON + IG_TAIL, COMMON + YT_TAIL

if __name__ == "__main__":
    from faster_whisper import WhisperModel
    m = WhisperModel("large-v3-turbo", compute_type="int8")
    for name, P in (("ig", IG), ("yt", YT)):
        out, t = [], 0.0
        for p in P:
            s, e = p["src"]
            seg = x[int(s * 16000): int(e * 16000)]
            res, _ = m.transcribe(seg, language="hi", beam_size=5, condition_on_previous_text=False, vad_filter=False)
            p = {**p, "heard": " ".join(r.text.strip() for r in res), "out": [round(t, 3), round(t + e - s, 3)]}
            t += e - s
            out.append(p)
        (ED / f"pieces_{name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"== {name}: {len(out)} pieces, {t:.2f} s")
        for p in out:
            print(f"  {p['src'][0]:7.2f}-{p['src'][1]:7.2f} ({p['src'][1] - p['src'][0]:4.2f}s) | {p['heard']}")
