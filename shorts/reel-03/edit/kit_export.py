"""Export the Instagram cut to the Herk Edit Kit schema (short-form-edit/references/plan-schema.md) so its
validate-plan / validate-footage run on this job. Writes ../kit/assets/*.json, ../kit/OPEN-LOOPS.json.
Scenes start on spoken anchors; events are the real visual actions from gfx/index.html."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\PARAS ARORA\AI_Editor\tools")
import captions_ass as ca  # noqa: E402

ED = Path(__file__).resolve().parent
KIT = ED.parent / "kit"
A = KIT / "assets"
A.mkdir(parents=True, exist_ok=True)
FPS, CUT, FREEZE = 25, 54.88, 0.6
DUR = round(CUT + FREEZE, 2)
words = [w for w in json.loads((ED / "words_master.json").read_text(encoding="utf-8"))["words"] if w["start"] < CUT]
r3 = lambda x: round(x, 3)
tw = [{"text": w["text"], "start": r3(w["start"]), "end": r3(min(w["end"], CUT)), "sourceStart": r3(w["start"]),
       "sourceEnd": r3(min(w["end"], CUT))} for w in words]
anchor = lambda t: next(w for w in tw if w["start"] >= t - 0.151)      # first word at/after the cut

SC = [("s00", 0.00, 1.40, "broll", "hook-night-a"), ("s01", 1.40, 3.12, "broll", "hook-night-b"),
      ("s02", 3.12, 5.00, "broll", "hook-morning"), ("s03", 5.00, 7.40, "face", "question"),
      ("s04", 7.40, 11.48, "split", "level-1-chat"), ("s05", 11.48, 21.04, "split", "level-2-projects"),
      ("s06", 21.04, 32.64, "split", "level-3-connectors"), ("s07", 32.64, 43.04, "split", "level-4-scheduled"),
      ("s08", 43.04, 46.48, "paper", "payoff"), ("s09", 46.48, 50.52, "split", "free-guide"),
      ("s10", 50.52, DUR, "split", "cta-comment-level")]
scenes = []
for sid, a, b, lay, kind in SC:
    w = anchor(a)
    s = {"id": sid, "start": a, "end": b, "layout": lay, "kind": kind, "anchor": w["text"], "anchorTime": w["start"]}
    if sid == "s03":
        s["holdReason"] = "Direct-address question on the speaker's face; the expression carries the beat (2.4 s)."
    if sid == "s10":
        s["holdReason"] = "CTA: keyword pill held, then a 0.6 s freeze for the last read."
    scenes.append(s)
EV = {"s00": [0.0], "s01": [1.40], "s02": [3.12], "s03": [5.0],
      "s04": [7.40, 7.42, 7.85, 8.0, 8.88, 9.74, 10.0, 10.12, 10.84, 11.32],
      "s05": [11.5, 11.86, 12.3, 13.64, 14.52, 15.28, 16.34, 17.75, 18.0, 18.4, 19.74, 20.72],
      "s06": [21.06, 21.38, 21.82, 22.86, 23.38, 24.16, 24.5, 24.85, 25.98, 26.76, 27.4, 28.3, 28.64, 30.05, 30.25, 30.95, 31.61, 32.05, 32.5],
      "s07": [32.66, 32.98, 33.47, 33.97, 34.6, 34.69, 35.75, 36.45, 37.55, 38.3, 38.85, 38.95, 39.75, 40.71, 41.41, 41.87, 42.95],
      "s08": [43.05, 43.3, 43.45, 44.0, 44.29, 45.13, 46.43],
      "s09": [46.57, 46.81, 47.25, 47.91, 48.99, 50.4],
      "s10": [50.5, 51.03, 51.35, 51.99, 52.35, 52.75, 53.29, 54.25]}
events = [{"time": t, "type": "visual-change", "visual": sid, "anchor": anchor(t)["text"] if t < CUT - 0.2 else "freeze"}
          for sid, ts in EV.items() for t in ts]
caps = [{"start": c[0]["start"], "end": c[-1]["end"], "words": c} for c in ca.chunks(tw)]
(A / "plan.json").write_text(json.dumps({"duration": DUR, "fps": FPS, "scenes": scenes, "events": events, "captions": caps}, indent=1, ensure_ascii=False), encoding="utf-8")
(A / "transcript.json").write_text(json.dumps({"text": " ".join(w["text"] for w in tw), "words": tw}, indent=1, ensure_ascii=False), encoding="utf-8")
(A / "edit-decisions.json").write_text(json.dumps({"duration": DUR, "fps": FPS,
    "keeps": [{"sourceStart": 0.0, "sourceEnd": CUT, "start": 0.0, "end": CUT}],
    "removals": [{"sourceStart": CUT, "sourceEnd": 59.1, "reason": "YouTube-only CTA line; Instagram ends on the comment CTA"}],
    "note": "Voice is a pronunciation-gated TTS read with no flubs, so no silence/mistake cuts were needed."}, indent=1), encoding="utf-8")
# B-roll: the three hook shots are moving footage (Google Flow, Paras's own avatar)
H = ED.parent / "hook"
for kind, src in (("hook-night-a", "shotA_flow_1080.mp4"), ("hook-night-b", "shotA_flow_1080.mp4"), ("hook-morning", "shotB_flow_1080.mp4")):
    shutil.copyfile(H / src, A / f"{kind}.mp4")
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
ledger = [{"scene": "s00", "sourceSceneId": "flow-night-forehead", "asset": "assets/hook-night-a.mp4", "sha256": sha(A / "hook-night-a.mp4"),
           "sourceStart": 0.15, "sourceEnd": 1.55, "framing": {"9x16": "Full frame; face and sticky notes visible; LEVEL 1 above the head"}},
          {"scene": "s01", "sourceSceneId": "flow-night-typing", "asset": "assets/hook-night-b.mp4", "sha256": sha(A / "hook-night-b.mp4"),
           "sourceStart": 5.30, "sourceEnd": 7.02, "framing": {"9x16": "Full frame; typing hands and lit phone visible"}},
          {"scene": "s02", "sourceSceneId": "flow-morning-smirk", "asset": "assets/hook-morning.mp4", "sha256": sha(A / "hook-morning.mp4"),
           "sourceStart": 8.20, "sourceEnd": 9.89, "framing": {"9x16": "Close-up smirk; mouth closed; no laptop/Apple logo in frame"}}]
(A / "footage-ledger.json").write_text(json.dumps(ledger, indent=1), encoding="utf-8")
(KIT / "OPEN-LOOPS.json").write_text(json.dumps([{
    "id": "main", "question": "Which level am I on, and what does Level 4 look like?",
    "object": "The 'YOU?' marker planted on step 1 of the staircase", "setup": 5.16,
    "updates": [{"time": 7.42, "state": "YOU? drops onto step 1 among the crowd"},
                {"time": 11.5, "state": "Camera climbs to step 2"}, {"time": 21.06, "state": "Step 3"}, {"time": 32.66, "state": "Step 4 reached"}],
    "closure": 45.13, "resolution": "YOU? climbs to step 4 and the frame lands on ASSISTANT",
    "supportingSpeech": "Yahan Claude chatbot nahi, aapka assistant ban jaata hai"}], indent=1), encoding="utf-8")
print(f"plan: {len(scenes)} scenes, {len(events)} events, {len(caps)} caption groups, {len(tw)} words, duration {DUR}")
