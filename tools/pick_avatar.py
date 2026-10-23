"""Pick the HeyGen look for the next video: random among shorts/avatar_rotation.json looks, never the
previous one. Records the pick (job name) in history so the rotation survives sessions.

Usage: python pick_avatar.py <job-name>      -> prints the chosen look as JSON
"""
import json
import random
import sys
from datetime import date
from pathlib import Path

ROT = Path(r"C:\Users\PARAS ARORA\AI_Editor\shorts\avatar_rotation.json")


def pick(rot, rng=random):
    last = rot["history"][-1]["id"] if rot["history"] else None
    return rng.choice([l for l in rot["looks"] if l["id"] != last] or rot["looks"])


if __name__ == "__main__":
    rot = json.loads(ROT.read_text(encoding="utf-8"))
    look = pick(rot)
    rot["history"].append({"id": look["id"], "name": look["name"], "job": sys.argv[1], "date": str(date.today())})
    ROT.write_text(json.dumps(rot, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(look))
    r = {"looks": [{"id": "a"}, {"id": "b"}], "history": [{"id": "a"}]}
    assert all(pick(r)["id"] == "b" for _ in range(20))   # never repeats the previous look
