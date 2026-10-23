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
from plan import END, OFF, SEGMENTS  # noqa: E402

ED = Path(__file__).resolve().parent
JOB = ED.parent
KIT = JOB / "kit"
A = KIT / "assets"
A.mkdir(parents=True, exist_ok=True)
FPS, CUT, FREEZE = 25, 53.80, 0.6
DUR = round(CUT + FREEZE, 2)
words = [w for w in json.loads((ED / "words_master.json").read_text(encoding="utf-8"))["words"] if w["start"] < CUT]
r3 = lambda x: round(x, 3)
tw = [{"text": w["text"], "start": r3(w["start"]), "end": r3(min(w["end"], CUT)), "sourceStart": r3(w["start"]),
       "sourceEnd": r3(min(w["end"], CUT))} for w in words]
anchor = lambda t: next(w for w in tw if w["start"] >= t - 0.151)      # first word at/after the cut

SC = [("s00", 0.00, 5.40, "broll", "hook-flow"), ("s01", 5.40, 9.32, "broll", "customer-2am"),
      ("s02", 9.32, 12.04, "split", "agent-replies"), ("s03", 12.04, 13.36, "broll", "owner-booked"),
      ("s04", 13.36, 16.28, "split", "free-tool-kapso"), ("s05", 16.28, 22.12, "split", "official-api-free-plan"),
      ("s06", 22.12, 24.04, "face", "three-steps"), ("s07", 24.04, 28.28, "split", "step-1-signup"),
      ("s08", 28.28, 32.88, "split", "step-2-command"), ("s09", 32.88, 37.76, "split", "step-3-prompt"),
      ("s10", 37.76, 39.68, "split", "claude-writes-code"), ("s11", 39.68, 42.68, "broll", "agent-24h"),
      ("s12", 42.68, 46.20, "split", "rule-permission"), ("s13", 46.20, 49.28, "split", "free-guide"),
      ("s14", 49.28, DUR, "split", "cta-comment-agent")]
sh = lambda t: t if t <= 5.40 + 1e-6 else round(t - OFF, 2)          # the hook video itself is not shifted
SC = [(sid, sh(a), (b if b == DUR else sh(b)), lay, kind) for sid, a, b, lay, kind in SC]
scenes = []
for sid, a, b, lay, kind in SC:
    w = anchor(a)
    s = {"id": sid, "start": a, "end": b, "layout": lay, "kind": kind, "anchor": w["text"], "anchorTime": w["start"]}
    if sid == "s06":
        s["holdReason"] = "Direct address on the speaker's face before the steps; the '3 STEPS' chip lands on 'teen' (2 s)."
    if sid == "s14":
        s["holdReason"] = "CTA: keyword pill held, then a 0.6 s freeze (voice muted) for the last read."
    scenes.append(s)
EV = {"s00": [0.0, 0.04, 1.40, 3.20, 3.34], "s01": [5.40, 6.80, 7.72, 8.16],
      "s02": [9.32, 9.36, 9.74, 10.02, 10.92, 11.14, 11.46, 11.56, 11.80], "s03": [12.04],
      "s04": [13.36, 13.61, 13.90, 14.40, 15.40, 15.50, 15.75],
      "s05": [16.28, 16.59, 17.09, 17.79, 18.37, 18.55, 18.95, 19.15, 19.74, 20.42, 21.05, 21.53, 21.70],
      "s06": [22.12, 22.91], "s07": [24.04, 24.19, 24.45, 25.15, 25.61, 26.53, 26.93, 27.57],
      "s08": [28.28, 28.43, 28.60, 29.25, 30.95, 31.09, 31.23, 31.37, 31.73],
      "s09": [32.88, 33.01, 33.40, 34.81, 35.60, 36.40, 37.25], "s10": [37.76, 37.78, 38.21, 39.29],
      "s11": [39.68, 41.08], "s12": [42.68, 43.45, 44.55, 45.20],
      "s13": [46.20, 46.34, 46.70, 46.92, 47.14, 47.36, 48.00],
      "s14": [49.28, 49.80, 50.10, 50.72, 51.16, 51.60, 52.40, 53.44]}
EV = {sid: [sh(t) for t in ts] for sid, ts in EV.items()}
EV["s00"] = [0.0, 0.04, 1.40, 3.10, 3.20]   # label swap moves with the voice ('Aur' 3.10)
events = [{"time": t, "type": "visual-change", "visual": sid, "anchor": anchor(t)["text"] if t < CUT - 0.2 else "freeze"}
          for sid, ts in EV.items() for t in ts]
caps = [{"start": c[0]["start"], "end": c[-1]["end"], "words": c} for c in ca.chunks(tw)]
(A / "plan.json").write_text(json.dumps({"duration": DUR, "fps": FPS, "scenes": scenes, "events": events, "captions": caps}, indent=1, ensure_ascii=False), encoding="utf-8")
(A / "transcript.json").write_text(json.dumps({"text": " ".join(w["text"] for w in tw), "words": tw}, indent=1, ensure_ascii=False), encoding="utf-8")
(A / "edit-decisions.json").write_text(json.dumps({"duration": DUR, "fps": FPS,
    "keeps": [{"sourceStart": 0.0, "sourceEnd": CUT, "start": 0.0, "end": CUT}],
    "removals": [{"sourceStart": CUT, "sourceEnd": END, "reason": "YouTube-only CTA line; Instagram ends on the comment CTA, voice muted in the freeze"}],
    "note": "Voice is a pronunciation-gated clone read with no flubs, so no silence/mistake cuts were needed."}, indent=1), encoding="utf-8")
# B-roll ledger: every Flow shot used once, with the exact source window from plan.SEGMENTS
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
SRC = {"s00": ("hook-flow", "hook/hook_video.mp4", 0.0, 5.40, "flow-paras-night-phone", "Three moments of one Flow shot (1.75-3.15, 4.40-6.20, 6.90-9.10); mouth closed; hook text low over the desk"),
       "s01": ("customer-2am", "broll/woman_1080.mp4", None, None, "flow-customer-2am", "Typing, the 2:04 clock, close-up; her message bubble at the top"),
       "s03": ("owner-booked", "broll/salon_1080.mp4", None, None, "flow-salon-owner", "Grin at the phone into a thumbs-up; no label"),
       "s11": ("agent-24h", "broll/sleeping_1080.mp4", None, None, "flow-owner-asleep", "Phone pulses on the nightstand while he sleeps; 24 GHANTE above")}
win = {}
for t0, t1, lay, src, s_in, sp in SEGMENTS:
    if lay == "broll":
        a, b = win.get(src, (1e9, -1e9)); win[src] = (min(a, s_in), max(b, s_in + (t1 - t0) * sp))
ledger = []
for sid, (kind, src, s0, s1, scene_id, framing) in SRC.items():
    shutil.copyfile(JOB / src, A / f"{kind}.mp4")
    if s0 is None:
        s0, s1 = win[src]
    ledger.append({"scene": sid, "sourceSceneId": scene_id, "asset": f"assets/{kind}.mp4", "sha256": sha(A / f"{kind}.mp4"),
                   "sourceStart": round(s0, 2), "sourceEnd": round(s1, 2), "framing": {"9x16": framing}})
(A / "footage-ledger.json").write_text(json.dumps(ledger, indent=1), encoding="utf-8")
(KIT / "OPEN-LOOPS.json").write_text(json.dumps([{
    "id": "main", "question": "Who answers the customer's 2 AM message, and how do I set that up?",
    "object": "The customer's 'Friday ko slot hai?' message", "setup": 8.16,
    "updates": [{"time": 10.02, "state": "Claude's agent replies with free slots"},
                {"time": 11.80, "state": "Booked: Friday, 4 PM"},
                {"time": 15.40, "state": "The tool is named: Kapso"},
                {"time": 24.19, "state": "Setup steps 1-3 begin"}],
    "closure": 41.11, "resolution": "The agent runs 24 hours on his number while the owner sleeps",
    "supportingSpeech": "Aur agent aapke number pe 24 ghante chalta hai"}], indent=1), encoding="utf-8")
print(f"plan: {len(scenes)} scenes, {len(events)} events, {len(caps)} caption groups, {len(tw)} words, duration {DUR}")
