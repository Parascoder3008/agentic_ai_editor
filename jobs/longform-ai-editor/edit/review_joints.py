"""Per-joint review from piece_tx.json: last words of each piece || first words of the next, with master times.
'<<' = the next piece opens with the word(s) this one ends on (a restart); '!!' = lone short piece (likely false start).
Usage: python review_joints.py [piece_tx.json]
"""
import difflib
import json
import re
import sys

E = r"C:\Users\PARAS ARORA\AI_Editor\inbox\longform-ai-editor\edit"
T = json.load(open(sys.argv[1] if len(sys.argv) > 1 else E + r"\piece_tx.json", encoding="utf-8"))


def norm(w):
    return re.sub(r"[^\w]", "", w.lower())


def same(a, b):
    a, b = norm(a), norm(b)
    return bool(a) and difflib.SequenceMatcher(None, a, b).ratio() >= 0.75


def fmt(ws):
    return " ".join(f"{w[2]}@{w[0]:.2f}" for w in ws)


for a, b in zip(T, T[1:]):
    ta, hb = a["words"][-4:], b["words"][:4]
    rep = any(same(x[2], y[2]) for x in ta[-2:] for y in hb[:2])
    lone = a["m1"] - a["m0"] < 1.0
    print(f"{'<<' if rep else '  '}{'!!' if lone else '  '} P{a['i']:03d}|P{b['i']:03d} m {a['m1']:8.2f}|{b['m0']:8.2f} gap {b['m0'] - a['m1']:5.2f}  "
          f"...{fmt(ta)} || {fmt(hb)}...")
