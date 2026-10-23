"""Find repeated words at every cut and camera change of the long-form body, from the verbatim CTC transcript
(verbatim_master.json, master time). Prints each joint/split with the romanized words either side; '<<' marks a
likely repeat (same word/phrase on both sides). Also lists stutters (adjacent near-identical words) inside pieces.
Usage: python check_repeats.py [lf.json]
"""
import difflib
import json
import sys

E = r"C:\Users\PARAS ARORA\AI_Editor\inbox\longform-ai-editor\edit"
W = json.load(open(E + r"\verbatim_master.json"))["words"]
P = json.load(open(E + r"\body_pieces.json"))
segs = json.load(open(sys.argv[1] if len(sys.argv) > 1 else E + r"\lf.json"))["segments"][1:]
INTRO = 42.40


def words(a, b):
    return [w for w in W if a - 0.02 <= (w[0] + w[1]) / 2 < b + 0.02]


def sim(x, y):
    return difflib.SequenceMatcher(None, x, y).ratio()


def repeat(tail, head):
    """longest n (1..3 words) where tail's last n words ~ head's first n words."""
    for n in (3, 2, 1):
        if len(tail) >= n and len(head) >= n:
            t, h = "".join(w[2] for w in tail[-n:]), "".join(w[2] for w in head[:n])
            if len(t) >= 2 and sim(t, h) >= 0.75:
                return n
    return 0


def show(ws):
    return " ".join(w[2] for w in ws)


out = 0.0
cuts = []                       # (output time, master end of left, master start of right, is_joint)
for i, s in enumerate(segs[:-1]):
    out += s["m1"] - s["m0"]
    nxt = segs[i + 1]
    cuts.append((INTRO + out, s["m1"], nxt["m0"], abs(nxt["m0"] - s["m1"]) > 0.005))

n_flag = 0
for t, ml, mr, joint in cuts:
    pl = next(p for p in P if p["m0"] - 0.01 <= ml - 0.02 <= p["m1"])      # piece that contains the left side
    pr = next(p for p in P if p["m0"] - 0.01 <= mr + 0.02 <= p["m1"])
    tail = words(max(pl["m0"], ml - 2.0), ml)
    head = words(mr, min(pr["m1"], mr + 2.0))
    r = repeat(tail, head)
    n_flag += r > 0
    gap = show(words(ml, mr)) if joint else ""
    print(f"{'<<' if r else '  '} out {t:7.2f} {'CUT ' if joint else 'cam '} m {ml:8.2f}|{mr:8.2f}  ...{show(tail[-5:])} || {show(head[:5])}..."
          + (f"   [removed: {gap[:60]}]" if gap else ""))

print(f"\n{n_flag} cuts flagged as repeats out of {len(cuts)}")
print("\nstutters inside kept pieces (adjacent near-identical words):")
for p in P:
    ws = words(p["m0"], p["m1"])
    for a, b in zip(ws, ws[1:]):
        if len(a[2]) >= 2 and sim(a[2], b[2]) >= 0.8 and b[0] - a[1] < 0.6:
            print(f"  m {a[0]:8.2f}  out {INTRO + p['out0'] + a[0] - p['m0']:7.2f}  {a[2]} {b[2]}   ...{show(words(a[0] - 1.2, b[1] + 1.2))}")
