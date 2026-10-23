"""reel-04 cut: every edge measured (5 ms energy + CTC letters + Whisper on candidate cuts), snapped to the 30 fps grid.
Master = SHARED + IG tail + YT tail. IG = shared + IG tail; YT = shared + YT tail.
Writes timeline.json + words_master.json (Roman Hinglish caption words). Usage: python edl.py"""
import json
from pathlib import Path

ED = Path(__file__).resolve().parent
FPS = 30
A = r"C:\Users\PARAS ARORA\Downloads\DJI_20261019161031_0358_D.MP4"     # main take
B = r"C:\Users\PARAS ARORA\Downloads\DJI_20261019161340_0359_D.MP4"     # YT CTA take
snap = lambda t: round(round(t * FPS) / FPS, 4)
P = lambda f, s, e, text, z=1.0: {"file": f, "src": [snap(s), snap(e)], "text": text, "zoom": z}

SHARED = [P("a", 15.0667, 26.0, "ye jo aap video dekh rahe ho … meri poori reel"),             # starts after "3,2,1 and go"
          P("a", 26.2667, 43.0333, "aur dikhaye usmein badhiya graphics … wapas le jaaye"),      # 0.46 s pause cut; drops "chashma" line
          P("a", 51.5667, 61.2333, "aur iske baad main bolun … bhai saab bye", 1.06),           # third "aur iske baad" (two restarts before)
          P("a", 62.0333, 64.4667, "ab ye sab kuch aap bhi kar sakte ho bahut aasaan hai")]       # hai|aapko run together: cut in the glide
IG_TAIL = [P("a", 64.4667, 67.8667, "aapko apne claude ko … convert karna hai"),                 # continues the same take (no cut on IG)
           P("a", 68.1667, 73.9667, "ab iski ek bana rakhi … dm nahi jaayega", 1.08),
           P("a", 74.2333, 76.1667, "aur bhai aap apni editing … karwa sakte ho"),               # before the first "lekin"
           P("a", 138.5333, 142.4667, "ab obviously ai hai … zyada lagega ya kam", 1.08),         # clean retake; skips "ab ab"
           P("a", 142.6, 144.5333, "wo main bataunga uske liye follow kar lena")]
YT_TAIL = [P("b", 0.3333, 11.1, "ab iski bana rakhi … subscribe kar lo", 1.04)]
NICE = {"claude": "Claude", "ai": "AI", "dm": "DM", "whatsapp": "WhatsApp", "youtube": "YouTube", "chatgpt": "ChatGPT", "about": "About"}

if __name__ == "__main__":
    fa = {"a": json.loads((ED / "fa_a.json").read_text(encoding="utf-8")), "b": json.loads((ED / "fa_b.json").read_text(encoding="utf-8"))}
    allw = {k: sorted((w for ws in v.values() for w in ws), key=lambda w: w["start"]) for k, v in fa.items()}
    pieces, words, t = [], [], 0.0
    for tag, PS in (("shared", SHARED), ("ig", IG_TAIL), ("yt", YT_TAIL)):
        for p in PS:
            s, e = p["src"]
            pieces.append({**p, "tag": tag, "out": [round(t, 4), round(t + e - s, 4)]})
            first = True
            for w in allw[p["file"]]:
                if s - 0.02 <= w["start"] < e - 0.04:
                    txt = NICE.get(w["text"], w["text"])
                    if first:
                        txt = txt[:1].upper() + txt[1:]; first = False
                    words.append({"text": txt, "start": round(t + w["start"] - s, 3), "end": round(t + min(w["end"], e) - s, 3)})
            t += e - s
    for i, w in enumerate(words):                    # EDIT is the keyword only in "comment kar do EDIT"
        if w["text"].lower() == "edit" and i and words[i - 1]["text"] == "do":
            w["text"] = "EDIT"
    for i in range(len(words) - 2, -1, -1):          # "b" + "roll" -> one caption word
        if words[i]["text"].lower() == "b" and words[i + 1]["text"] == "roll":
            words[i] = {"text": "B-roll", "start": words[i]["start"], "end": words[i + 1]["end"]}; del words[i + 1]
    n_sh, n_ig = len(SHARED), len(IG_TAIL)
    end_shared = pieces[n_sh - 1]["out"][1]; ig_end = pieces[n_sh + n_ig - 1]["out"][1]
    tl = {"fps": FPS, "length": round(t, 4), "end_shared": end_shared, "pieces": pieces, "files": {"a": A, "b": B},
          "ig": {"ranges": [[0.0, ig_end]]}, "yt": {"ranges": [[0.0, end_shared], [ig_end, round(t, 4)]]}}
    (ED / "timeline.json").write_text(json.dumps(tl, indent=1))
    (ED / "words_master.json").write_text(json.dumps({"words": words}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"master {t:.2f}s | shared {end_shared:.2f} | IG {ig_end:.2f}s | YT {end_shared + t - ig_end:.2f}s | {len(words)} words")
    for p in pieces:
        print(f"  {p['tag']:6s} {p['file']} {p['src'][0]:8.3f}-{p['src'][1]:8.3f} -> {p['out'][0]:6.2f}-{p['out'][1]:6.2f} z{p['zoom']}")
