"""Master timeline + caption words. Master = split (raw 0-15.36) + 8 shared how-to pieces + IG tail + YT tail.
IG = master[0 : end of IG tail]; YT = master[0 : end of shared] + master[YT tail]. Writes timeline.json, words_master.json."""
import json
import subprocess
import sys
from pathlib import Path

ED = Path(__file__).resolve().parent
sys.path.insert(0, str(ED))
import edl  # noqa: E402  (pieces_ig / pieces_yt definitions)

SPLIT = 15.36
SPLIT_LINES = [("S1", 0.40, 3.95, "Bhai aajkal social media pe kuch bhi flex karna bahut aasaan hai"),
               ("S2", 3.90, 6.52, "Jaise ki mere paas Rolls Royce nahi hai"),
               ("S3", 6.45, 7.62, "Badhiya dikh rahi hai"),
               ("S4", 7.55, 10.57, "Aur mere koi haath mein crore rupay ki ghadi nahi hai"),
               ("S5", 10.50, 11.72, "Badhiya humpe dikh rahi hai"),
               ("S6", 11.65, 14.20, "Uske alawa peeche mere paas koi mansion nahi hai"),
               ("S7", 14.15, 15.36, "Badhiya toh dikh raha hai na")]
NICE = {"bhai": "bhai", "chatgpt": "ChatGPT", "higgsfield": "Higgsfield", "flex": "FLEX", "dm": "DM", "whatsapp": "WhatsApp",
        "youtube": "YouTube", "rolls": "Rolls", "royce": "Royce", "about": "About", "easy": "easy"}

if __name__ == "__main__":
    lines = [{"id": i, "win": [a, b], "text": t.lower()} for i, a, b, t in SPLIT_LINES]
    (ED / "fa_split_lines.json").write_text(json.dumps(lines, indent=1), encoding="utf-8")
    subprocess.run([sys.executable, r"C:\Users\PARAS ARORA\AI_Editor\tools\force_align.py", str(ED.parent / "src" / "raw.wav"),
                    str(ED / "fa_split_lines.json"), str(ED / "fa_split.json")], check=True)
    fs = json.loads((ED / "fa_split.json").read_text(encoding="utf-8"))
    words = []
    for i, a, b, t in SPLIT_LINES:                      # display text keeps the line's own capitalisation
        for w, d in zip(fs[i], t.split()):
            words.append({"text": d, "start": w["start"], "end": min(w["end"], SPLIT)})

    fa = json.loads((ED / "fa_out.json").read_text(encoding="utf-8"))
    allw = sorted((w for ws in fa.values() for w in ws), key=lambda w: w["start"])
    common, igt, ytt = edl.COMMON, edl.IG_TAIL, edl.YT_TAIL
    master, t = [], SPLIT
    for tag, P in (("common", common), ("ig", igt), ("yt", ytt)):
        for p in P:
            s, e = p["src"]
            master.append({"tag": tag, "src": [s, e], "out": [round(t, 3), round(t + e - s, 3)]})
            first = True
            for w in allw:
                if w["start"] >= s - 0.02 and w["start"] < e - 0.05:
                    txt = NICE.get(w["text"], w["text"])
                    if first:
                        txt = txt[:1].upper() + txt[1:]; first = False
                    words.append({"text": txt, "start": round(t + w["start"] - s, 3), "end": round(t + min(w["end"], e) - s, 3)})
            t += e - s
    for i, w in enumerate(words):                       # FLEX is the keyword only in "comment kar do FLEX"
        if w["text"] == "FLEX" and (i == 0 or words[i - 1]["text"] != "do"):
            w["text"] = "flex"
    end_common = master[len(common) - 1]["out"][1]
    ig_end = master[len(common) + len(igt) - 1]["out"][1]
    yt_start = master[len(common) + len(igt)]["out"][0]
    tl = {"split": SPLIT, "length": round(t, 3), "pieces": master, "end_common": end_common,
          "ig": {"ranges": [[0.0, ig_end]]}, "yt": {"ranges": [[0.0, end_common], [yt_start, round(t, 3)]]}}
    (ED / "timeline.json").write_text(json.dumps(tl, indent=1), encoding="utf-8")
    (ED / "words_master.json").write_text(json.dumps({"words": words}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"master {t:.2f}s | IG {ig_end:.2f}s | YT {end_common + t - yt_start:.2f}s | {len(words)} words")
    for p in master:
        print(f"  {p['tag']:6s} src {p['src'][0]:7.2f}-{p['src'][1]:7.2f} -> out {p['out'][0]:6.2f}-{p['out'][1]:6.2f}")
