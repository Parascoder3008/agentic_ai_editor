"""Export the Instagram cut to the Herk Edit Kit schema so validate-plan / validate-footage run on this job.
Scenes start on spoken anchors; events are the real visual actions (compose_base.py layouts + gfx/index.html).
Writes ../kit/assets/*.json and ../kit/OPEN-LOOPS.json. Usage: python kit_export.py"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
import captions_ass as ca  # noqa: E402

ED = Path(__file__).resolve().parent
TL = json.loads((ED / "timeline.json").read_text())
KIT = ED.parent / "kit"; A = KIT / "assets"; A.mkdir(parents=True, exist_ok=True)
FPS, CUT, FREEZE = 30, TL["ig"]["ranges"][0][1], 0.6
DUR = round(CUT + FREEZE, 2)
r3 = lambda x: round(x, 3)
PCS = [p for p in TL["pieces"] if p["out"][0] < CUT]


def src_of(w):
    """map an output-time word to its source time through the piece that holds it"""
    p = next(p for p in PCS if p["out"][0] - 1e-3 <= w["start"] < p["out"][1])
    e = min(w["end"], p["out"][1])
    return {"text": w["text"], "start": r3(w["start"]), "end": r3(e), "sourceStart": r3(p["src"][0] + w["start"] - p["out"][0]),
            "sourceEnd": r3(p["src"][0] + e - p["out"][0])}


tw = [src_of(w) for w in json.loads((ED / "words_master.json").read_text(encoding="utf-8"))["words"] if w["start"] < CUT]
anchor = lambda t: next(w for w in tw if w["start"] >= t - 0.151)

SC = [("s00", 0.00, 5.71, "face", "hook"), ("s01", 5.71, 7.95, "face", "prompt-corner"), ("s02", 7.95, 13.87, "card", "corner-plus-reel"),
      ("s03", 13.87, 15.31, "face", "come-forward"), ("s04", 15.31, 19.81, "face", "text-behind-cinematic"),
      ("s05", 19.81, 22.33, "face", "ask-highlight"), ("s06", 22.33, 27.70, "face", "spotlight-watch-graphics"),
      ("s07", 27.70, 29.40, "face", "ask-paper-cut"), ("s08", 29.40, 31.19, "paper", "paper-cut"), ("s09", 31.19, 32.07, "paper", "sticker-aside"),
      ("s10", 32.07, 35.80, "broll", "product-broll"), ("s11", 35.80, 37.37, "face", "back-and-bye"), ("s12", 37.37, 39.80, "face", "you-can-too"),
      ("s13", 39.80, 45.45, "face", "claude-video-editor-guide"), ("s14", 45.45, 49.05, "face", "cta-comment-edit"),
      ("s15", 49.05, 50.96, "face", "ghar-baithe"), ("s16", 50.96, 54.98, "face", "cost-question"), ("s17", 54.98, DUR, "face", "follow")]
HOLD = {"s00": "Hook: '0 EDITORS' on frame 1 over a continuous 5 % push-in; the second line lands on the word 'AI'.",
        "s17": "Follow CTA held, then a 0.6 s freeze for the last read."}
fr = lambda t: round(t * FPS) / FPS                      # scene edges on the 30 fps grid
SC = [(sid, fr(a), (fr(b) if b != DUR else DUR), lay, kind) for sid, a, b, lay, kind in SC]
scenes = []
for sid, a, b, lay, kind in SC:
    w = anchor(a)
    s = {"id": sid, "start": a, "end": b, "layout": lay, "kind": kind, "anchor": w["text"], "anchorTime": w["start"]}
    if sid in HOLD:
        s["holdReason"] = HOLD[sid]
    if sid == "s02":
        s["mode"] = "footage"                    # his own reel plays in the card
    scenes.append(s)
EV = {"s00": [0.0, 0.05, 4.37], "s01": [5.71, 6.5, 7.25], "s02": [7.95, 8.55, 9.2, 9.9, 10.45, 10.85, 11.64, 11.88, 12.17, 12.30, 12.95, 13.6],
      "s03": [13.87, 14.37, 14.9], "s04": [15.31, 15.9, 16.6, 17.30, 17.90, 18.68, 19.5],
      "s05": [19.85, 20.6, 21.4, 22.2], "s06": [22.33, 22.45, 23.42, 24.2, 25.0, 25.04, 25.34, 25.7, 26.4, 27.02, 27.30],
      "s07": [27.70, 27.80, 28.5, 29.30], "s08": [29.40, 29.5, 29.95, 30.40, 31.0], "s09": [31.19, 31.64],
      "s10": [32.07, 33.07, 34.07, 34.40, 34.8, 35.5], "s11": [35.80, 36.06, 36.45, 36.86, 37.18],
      "s12": [37.37, 38.12, 39.48], "s13": [39.80, 40.54, 42.48, 43.20, 44.70], "s14": [45.45, 46.05, 46.45, 46.73, 47.53, 48.84],
      "s15": [49.05, 50.17, 50.93], "s16": [50.96, 52.20, 53.23, 53.57, 54.37, 54.87], "s17": [55.30, 56.06, 56.40, 56.80]}
events = [{"time": t, "type": "visual-change", "visual": sid, "anchor": anchor(t)["text"] if t < CUT - 0.2 else "freeze"}
          for sid, ts in EV.items() for t in ts]
caps = [{"start": c[0]["start"], "end": c[-1]["end"], "words": c} for c in ca.chunks(tw)]
(A / "plan.json").write_text(json.dumps({"duration": DUR, "fps": FPS, "scenes": scenes, "events": events, "captions": caps}, indent=1, ensure_ascii=False), encoding="utf-8")
(A / "transcript.json").write_text(json.dumps({"text": " ".join(w["text"] for w in tw), "words": tw}, indent=1, ensure_ascii=False), encoding="utf-8")
keeps = [{"sourceStart": p["src"][0], "sourceEnd": p["src"][1], "start": p["out"][0], "end": p["out"][1], "file": p["file"]}
         for p in TL["pieces"] if p["out"][1] <= CUT + 1e-3]
(A / "edit-decisions.json").write_text(json.dumps({"duration": DUR, "fps": FPS, "keeps": keeps,
    "removals": [{"reason": "count-in '3,2,1 and go' and the first false start (0-15.07)"},
                 {"reason": "abandoned 'mera jo chashma hai isko...' line + 'aur, aur iske baad' restarts (43.03-51.57)"},
                 {"reason": "five retakes of the cost line; kept the clean one at 138.53"},
                 {"reason": "pauses >= 0.3 s trimmed at 26.0, 67.87, 73.97, 142.47"}],
    "note": "Every edge measured on 5 ms energy + CTC letters; restarts Whisper hides were checked line by line."}, indent=1), encoding="utf-8")
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
# client footage only (@venomstech): his RTX 5090 reel in the card; the product beat = his DDR5 + cooler renders on panels
import subprocess  # noqa: E402
for f in A.glob("*"):
    if f.name in ("reel03.mp4", "hub_full.png"):
        f.unlink()
shutil.copyfile(ED.parent / "client_reels" / "rtx5090_pc.mp4", A / "rtx5090_pc.mp4")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "32.07", "-i", str(ED / "base_video.mp4"), "-t", "3.73", "-an", "-c:v", "libx264",
                "-crf", "18", "-pix_fmt", "yuv420p", str(A / "product-broll.mp4")], check=True)
ledger = [{"scene": "s02", "sourceSceneId": "venomstech-rtx5090-reel", "asset": "assets/rtx5090_pc.mp4", "sha256": sha(A / "rtx5090_pc.mp4"),
           "sourceStart": 34.5, "sourceEnd": 37.92, "framing": {"9x16": "420x747 film-strip card bottom-right; his 12-lakh product cards land on 'graphics'"}},
          {"scene": "s10", "sourceSceneId": "venomstech-ddr5-and-cooler-renders", "asset": "assets/product-broll.mp4", "sha256": sha(A / "product-broll.mp4"),
           "sourceStart": 0.0, "sourceEnd": 3.73, "framing": {"9x16": "Two rounded panels on cream: DDR5 render (ddr5_ram reel 32.3 s) over the cooler-mount render (laptop_vs_pc reel 32.05 s, 0.75x)"}}]
(A / "footage-ledger.json").write_text(json.dumps(ledger, indent=1), encoding="utf-8")
(KIT / "OPEN-LOOPS.json").write_text(json.dumps([
    {"id": "main", "question": "Can Claude really do the edits he is asking for, on this same video?", "object": "The Claude prompt bar",
     "setup": 5.71, "updates": [{"time": 8.55, "state": "corner done"}, {"time": 17.90, "state": "cinematic text done"},
                                {"time": 27.40, "state": "watch graphics done"}, {"time": 34.40, "state": "B-roll done"}],
     "closure": 36.06, "resolution": "Every instruction ticked; he comes back and says bye", "supportingSpeech": "finally main aaun aur bolun bhai saab bye"},
    {"id": "cost", "question": "Is AI editing cheaper than an editor?", "object": "AI vs Editor cost card", "setup": 52.20,
     "updates": [{"time": 53.23, "state": "AI ₹? vs Editor ₹?"}], "closure": 56.06,
     "resolution": "Deliberately carried to the next video (follow CTA)", "supportingSpeech": "wo main bataunga, uske liye follow kar lena"}],
    indent=1, ensure_ascii=False), encoding="utf-8")
print(f"plan: {len(scenes)} scenes, {len(events)} events, {len(caps)} caption groups, {len(tw)} words, duration {DUR}")
