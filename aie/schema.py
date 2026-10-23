"""job.json checks for the sound sections (sfx, music, mix). Kept free of numpy and scipy, so validate and doctor run
on a machine that has neither; the modules that render these sections import their settings from here."""

# ---------------------------------------------------------------- sfx
SFX_KEYS = {"seed", "length", "voice", "duck", "cues"}
CUE_KEYS = {"kind", "t", "db", "pan", "note"}
# kind: {setting: default}. "t" is the start in output seconds (whoosh_into is placed from "word" instead).
SFX_KINDS = {
    "impact": {},
    "buzz": {"d": 0.36},
    "chime": {"notes": [88], "gap": 0.08},
    "whoosh": {"d": 0.42, "up": True},
    "whoosh_into": {"word": None, "d": 0.42, "db": -28},       # peak 0.2 s before the word that starts at "word"
    "pop": {},
    "tick": {"d": 0.012, "lo": 2500, "hi": 7000, "release": 0.01},
    "thud": {},
    "typing": {"until": None, "db": -36, "cps": None},          # keys from t to until; cps = a steady rate (reel-04)
    "rustle": {"d": 0.35},
    "pitch_drop": {"d": 0.32, "f0": 920.0, "f1": 380.0},
    "glitch": {"d": 0.3},
    "riser": {"d": 1.0},
    "crash": {},
    "bed": {"until": None, "sound": "room"},                    # ambience from t to until: room | office | belt
}
SFX_NEEDS = {"whoosh_into": "word", "typing": "until", "bed": "until"}


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def check_sfx(cfg, data: dict) -> list:
    if not isinstance(cfg, dict):
        return ['sfx: must be an object like {"cues": [{"kind": "whoosh", "t": 1.2, "db": -34}]}']
    errs = [f"sfx: unknown key {k!r} (allowed: {', '.join(sorted(SFX_KEYS))})" for k in sorted(set(cfg) - SFX_KEYS)]
    if "voice" in cfg and cfg["voice"] not in data.get("sources", {}):
        errs.append(f"sfx.voice: {cfg['voice']!r} is not one of the sources")
    cues = cfg.get("cues", [])
    if not isinstance(cues, list):
        return errs + ["sfx.cues: must be a list"]
    for i, c in enumerate(cues):
        p = f"sfx.cues[{i}]"
        if not isinstance(c, dict) or c.get("kind") not in SFX_KINDS:
            errs.append(f"{p}.kind: must be one of {', '.join(sorted(SFX_KINDS))}")
            continue
        k = c["kind"]
        for x in sorted(set(c) - CUE_KEYS - set(SFX_KINDS[k])):
            errs.append(f"{p}: {k} has no setting {x!r} (it has: {', '.join(SFX_KINDS[k]) or 'none'})")
        if k != "whoosh_into" and not (_num(c.get("t")) and c["t"] >= 0):
            errs.append(f"{p}.t: start time in output seconds")
        if k in SFX_NEEDS and not _num(c.get(SFX_NEEDS[k])):
            errs.append(f"{p}.{SFX_NEEDS[k]}: required for {k}")
        if "db" in c and not (_num(c["db"]) and c["db"] <= 0):
            errs.append(f"{p}.db: a level in dB, 0 or below")
        if "pan" in c and not (_num(c["pan"]) and 0 <= c["pan"] <= 1):
            errs.append(f"{p}.pan: 0 (left) to 1 (right)")
    return errs


# ---------------------------------------------------------------- music
MUSIC_KEYS = {"score", "voice_gain"}
SCORE_KEYS = {"length", "blocks", "events", "duck"}
CUES = {"hook", "story", "build", "reflect", "numbers", "outro"}
STARTS = {"hit", "drop", "fade", "none"}
ENDS = {"riser", "tapestop", "cut", "ring"}
EVENTS = {"bell": ("t", "note"), "dip": ("t0", "t1"), "lift": ("t0", "t1", "db")}


def check_music(cfg, data: dict) -> list:
    if not isinstance(cfg, dict) or not isinstance(cfg.get("score"), dict):
        return ['music: must be {"score": {"length", "blocks", "duck"}} (an original score composed to picture)']
    errs = [f"music: unknown key {k!r}" for k in sorted(set(cfg) - MUSIC_KEYS)]
    sc = cfg["score"]
    errs += [f"music.score: unknown key {k!r}" for k in sorted(set(sc) - SCORE_KEYS)]
    if not (_num(sc.get("length")) and sc["length"] > 0):
        errs.append("music.score.length: seconds of score")
    blocks = sc.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        errs.append("music.score.blocks: at least one block {t0, t1, cue, level}")
        blocks = []
    for i, b in enumerate(blocks):
        p = f"music.score.blocks[{i}]"
        if not isinstance(b, dict):
            errs.append(f"{p}: must be an object")
            continue
        if not (_num(b.get("t0")) and _num(b.get("t1")) and b["t0"] < b["t1"]):
            errs.append(f"{p}: t0 < t1 in output seconds")
        if b.get("cue") not in CUES:
            errs.append(f"{p}.cue: one of {', '.join(sorted(CUES))}")
        if b.get("level") not in range(0, 6):
            errs.append(f"{p}.level: 0 (quiet) to 5")
        if b.get("start", "none") not in STARTS:
            errs.append(f"{p}.start: one of {', '.join(sorted(STARTS))}")
        if b.get("end", "cut") not in ENDS:
            errs.append(f"{p}.end: one of {', '.join(sorted(ENDS))}")
    for i, e in enumerate(sc.get("events", [])):
        if not isinstance(e, dict) or e.get("type") not in EVENTS:
            errs.append(f"music.score.events[{i}].type: one of {', '.join(EVENTS)}")
        elif not all(_num(e.get(k)) for k in EVENTS[e["type"]]):
            errs.append(f"music.score.events[{i}]: {e['type']} needs {', '.join(EVENTS[e['type']])}")
    duck = sc.get("duck")
    if not isinstance(duck, list) or not duck:
        errs.append("music.score.duck: [{t0, t1, speech, gap}] covering the whole score (music level vs the voice, LU)")
    else:
        for i, r in enumerate(duck):
            if not (isinstance(r, dict) and all(_num(r.get(k)) for k in ("t0", "t1", "speech", "gap"))):
                errs.append(f"music.score.duck[{i}]: needs t0, t1, speech, gap")
        if all(isinstance(r, dict) and _num(r.get("t0")) and _num(r.get("t1")) for r in duck) and _num(sc.get("length")):
            if min(r["t0"] for r in duck) > 0 or max(r["t1"] for r in duck) < sc["length"] + 1.0:
                errs.append(f"music.score.duck: must cover 0 to length + 1 s ({sc['length'] + 1.0:.2f})")
    return errs


# ---------------------------------------------------------------- mix
MIX_KEYS = {"voice", "gain_db", "voice_lufs", "joint_fade", "tail"}


def check_mix(cfg, data: dict) -> list:
    if not isinstance(cfg, dict):
        return ["mix: must be an object"]
    errs = [f"mix: unknown key {k!r} (allowed: {', '.join(sorted(MIX_KEYS))})" for k in sorted(set(cfg) - MIX_KEYS)]
    if "voice" in cfg and cfg["voice"] not in data.get("sources", {}):
        errs.append(f"mix.voice: {cfg['voice']!r} is not one of the sources")
    g = cfg.get("gain_db", "auto")
    if g != "auto" and not _num(g):
        errs.append('mix.gain_db: "auto" or a number of dB')
    for k in ("joint_fade", "tail"):
        if k in cfg and not (_num(cfg[k]) and 0 <= cfg[k] <= 2):
            errs.append(f"mix.{k}: seconds, 0-2")
    return errs
