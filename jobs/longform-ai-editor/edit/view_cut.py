"""Show verbatim CTC chunks around master times, marking kept (K, with output time) vs removed (x)."""
import json, sys
W = json.load(open("verbatim_master.json"))["words"]
P = json.load(open("body_pieces.json"))
def kept(t):
    return next((p for p in P if p["m0"] <= t < p["m1"]), None)
for c in map(float, sys.argv[1:]):
    row = []
    for s, e, w in W:
        if c - 3.0 <= s <= c + 3.0:
            p = kept((s + e) / 2)
            row.append(f"{'K' if p else 'x'}{s:.2f}{'/o' + format(42.4 + p['out0'] + s - p['m0'], '.2f') if p else ''}:{w}")
    print(f"--- {c}\n  " + "  ".join(row))
