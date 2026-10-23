"""Map a time on the v1 master (timeline_v1.json) to the current master (timeline.json) through the source clip, so a
graphic/SFX cue authored on a spoken word stays on that word after re-cutting. A time inside removed footage
collapses onto the nearest kept cut. Split (0-15.36) is unchanged. Usage: from remap import R"""
import json
from pathlib import Path

ED = Path(__file__).resolve().parent
OLD = json.loads((ED / "timeline_v1.json").read_text())
NEW = json.loads((ED / "timeline.json").read_text())


def R(t):
    if t < OLD["split"]:
        return t
    p = next((p for p in OLD["pieces"] if p["out"][0] <= t < p["out"][1]), OLD["pieces"][-1])
    src = p["src"][0] + t - p["out"][0]
    for q in NEW["pieces"]:
        if q["src"][0] - 1e-3 <= src <= q["src"][1] + 1e-3:
            return round(q["out"][0] + src - q["src"][0], 2)
    edges = [(abs(src - q["src"][i]), q["out"][i]) for q in NEW["pieces"] for i in (0, 1)]
    return round(min(edges)[1], 2)


if __name__ == "__main__":
    for t in (15.36, 19.92, 23.61, 24.16, 29.36, 33.24, 36.28, 45.10, 47.70, 50.44, 56.63, 62.26, 63.12):
        print(t, "->", R(t))
