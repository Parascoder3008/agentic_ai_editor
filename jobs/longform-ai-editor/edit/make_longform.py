"""Plan the long-form edit: segments (layout + framing), graphics (anchored to spoken words), SFX, music.
Writes lf.json (compose config) and gfx_spec.json (graphics to render).
Usage: python make_longform.py [final]
"""
import json
import sys

E = r"C:\Users\PARAS ARORA\AI_Editor\inbox\longform-ai-editor\edit"
FINAL = len(sys.argv) > 1 and sys.argv[1] == "final"
FPS = 25
CAM_OFF, SCR_OFF = 36.165, -234.106          # cam = master + 36.165 ; scr = master - 234.106
INTRO = E + (r"\intro\intro_final.mkv" if FINAL else r"\intro\intro_preview.mkv")
INTRO_LEN = 42.40
GFX = E + (r"\gfx4k" if FINAL else r"\gfx")             # final = 3840x2160 renders of the same graphics
M = r"C:\Users\PARAS ARORA\Desktop\edit\edit\assets\.media\audio\sfx"
V = r"C:\Users\PARAS ARORA\.claude\skills\video-edit\sfx"
WHOOSH, POP, BASS = M + r"\sfx_001.mp3", M + r"\sfx_004.mp3", M + r"\sfx_002.mp3"
CLICK, CPOP, SWOOSH = V + r"\click.wav", V + r"\card-pop.wav", V + r"\hook-whoosh.wav"
PEAK = {WHOOSH: 0.162, POP: 0.119, BASS: 0.126, CLICK: 0.003, CPOP: 0.003, SWOOSH: 0.19}
GRADE = "eq=contrast=1.07:saturation=1.05:brightness=0.025:gamma=1.05,colorbalance=rs=-0.015:bs=0.03:rm=0.015:bm=-0.005,vignette=angle=0.3"

pieces = json.load(open(E + r"\body_pieces.json"))
faces = {float(k): v for k, v in json.load(open(E + r"\faces.json")).items()}
words = json.load(open(E + r"\transcript_hi.json", encoding="utf-8"))["words"]


def out_of(m):
    """master time -> output time (a time inside a removed gap maps to the next kept piece)."""
    for p in pieces:
        if m < p["m0"]:
            return round(INTRO_LEN + p["out0"], 3)
        if m < p["m1"]:
            return round(INTRO_LEN + p["out0"] + (m - p["m0"]), 3)
    return round(INTRO_LEN + pieces[-1]["out0"] + pieces[-1]["m1"] - pieces[-1]["m0"], 3)


def face_for(m0, m1):
    pts = [v for t, v in faces.items() if m0 + CAM_OFF - 0.3 <= t <= m1 + CAM_OFF + 0.3]
    if not pts:
        return 1001, 443, False
    cx = sorted(p[0] for p in pts)[len(pts) // 2]; cy = sorted(p[1] for p in pts)[len(pts) // 2]
    return cx, cy, min(p[0] for p in pts) >= 700


# ---------------- graphics (master anchor time, id, template, duration, vars) ----------------
HL = lambda w: f'<span class="hl">{w}</span>'
WA = '<svg viewBox="0 0 24 24"><path fill="#FFFFFF" d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.3-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2c0 1.3.9 2.6 1.1 2.7.1.2 1.8 2.8 4.4 3.9 1.6.7 2.3.8 3.1.6.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.2-1.2-.1-.1-.3-.2-.5-.3z"/></svg>'
PEOPLE = '<svg viewBox="0 0 24 24"><path fill="#FFFFFF" d="M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM9 13c-3.3 0-7 1.6-7 4v3h14v-3c0-2.4-3.7-4-7-4zm8 0c-.5 0-1 0-1.5.1 1.5.9 2.5 2.2 2.5 3.9v3h5v-3c0-2.3-3.3-4-6-4z"/></svg>'
INSTA = '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="#FFFFFF" stroke-width="2.2"/><circle cx="12" cy="12" r="4.2" fill="none" stroke="#FFFFFF" stroke-width="2.2"/><circle cx="17.4" cy="6.6" r="1.3" fill="#FFFFFF"/></svg>'
DOC = '<svg viewBox="0 0 24 24"><path fill="#FFFFFF" d="M6 2h8l6 6v14H6zM14 3.5V9h5.5" /><path d="M9 13h8M9 17h6" stroke="#1A9FD1" stroke-width="1.8"/></svg>'

G = [
    # body opener
    (9.30, "lower", "lower", 3.6, {"NAME": "PARAS ARORA", "ROLE": "Founder · Exponential World AI"}),
    (19.30, "kw_opus", "kw", 2.6, {"KICK": "Edited by", "MAIN": "Claude " + HL("Opus 5.5")}),
    (25.54, "kw_cuts", "kw", 2.4, {"KICK": "My manual cuts", "MAIN": HL("Zero")}),
    (57.40, "kw_break", "kw", 2.4, {"KICK": "This video", "MAIN": "Full process " + HL("breakdown")}),
    (74.96, "kw_cost", "kw", 2.6, {"KICK": "At the end", "MAIN": HL("Cost") + " breakdown"}),
    (92.90, "kw_vs", "kw", 2.8, {"KICK": "Editor vs AI", "MAIN": "Cost · " + HL("Quality")}),
    (126.20, "kw_bottle", "kw", 2.8, {"KICK": "The real problem", "MAIN": "Editing = " + HL("bottleneck")}),
    (138.17, "kw_fro", "kw", 2.4, {"KICK": "Freelancers", "MAIN": "Endless " + HL("back &amp; forth")}),
    (163.29, "sub1", "sub", 5.0, {}),
    (174.23, "kw_10x", "kw", 2.6, {"KICK": "Editors", "MAIN": "Become " + HL("10x") + " with AI"}),
    (253.40, "kw_day", "kw", 2.4, {"KICK": "Normal editor", "MAIN": "Up to " + HL("1 day")}),
    (257.80, "kw_hrs", "kw", 2.4, {"KICK": "Even at 100%", "MAIN": HL("3–4 hrs") + " a reel"}),
    (263.80, "kw_ai1h", "kw", 2.6, {"KICK": "Claude", "MAIN": "~" + HL("1 hour")}),
    (275.84, "chip_res", "chip", 3.6, {"TOP": "300", "ICON": DOC, "T1": "Every resource", "T2": "Linked in the <b>description</b>"}),
    # steps
    (293.40, "sec1", "section", 1.8, {"NUM": "", "STEP": "HOW I SET IT UP", "TITLE": "1 skill + 2 GitHub repos", "SUB": "video-use · HyperFrames — both free"}),
    (358.50, "sec2", "section", 1.8, {"NUM": "1", "STEP": "STEP 1", "TITLE": "Create your AI employee", "SUB": "Claude → Code → New project → AI Editor folder"}),
    (448.20, "sec3", "section", 1.8, {"NUM": "2", "STEP": "STEP 2", "TITLE": "Install everything", "SUB": "Paste the guide — it installs itself"}),
    (457.20, "kw_self", "kw", 2.6, {"KICK": "Paste the guide", "MAIN": "It " + HL("installs itself")}),
    (512.70, "sec4", "section", 1.8, {"NUM": "3", "STEP": "STEP 3", "TITLE": "What you need", "SUB": "A $20 Claude plan + free open-source tools"}),
    (607.50, "sec5", "section", 1.8, {"NUM": "4", "STEP": "STEP 4", "TITLE": "Feed it like an editor", "SUB": "Raw footage · brand colours · a style to copy"}),
    (611.80, "kw_raw", "kw", 2.4, {"KICK": "New folder", "MAIN": HL("raw footage")}),
    (628.20, "kw_brand", "kw", 2.4, {"KICK": "Also give it", "MAIN": "Brand " + HL("guidelines")}),
    (637.40, "kw_style", "kw", 2.4, {"KICK": "Bonus", "MAIN": "A style to " + HL("copy")}),
    (649.60, "sec6", "section", 1.8, {"NUM": "5", "STEP": "STEP 5", "TITLE": "Let it edit", "SUB": "Frame by frame — then demand 9.5/10"}),
    (675.32, "kw_95", "kw", 3.0, {"KICK": "My #1 prompt tip", "MAIN": "Rate it " + HL("9.5/10")}),
    (686.60, "kw_fix", "kw", 2.4, {"KICK": "It self-checks", "MAIN": HL("Fix") + " → re-check"}),
    (718.00, "kw_sync", "kw", 2.4, {"KICK": "Automatically", "MAIN": "Audio " + HL("synced")}),
    (768.40, "kw_meta", "kw", 3.0, {"KICK": "Wait…", "MAIN": "AI editing a video " + HL("about AI")}),
    (795.50, "kw_proj", "kw", 2.4, {"KICK": "One job =", "MAIN": "One " + HL("project")}),
    (799.70, "kw_ctx", "kw", 2.6, {"KICK": "Give it", "MAIN": "Skills · assets · " + HL("context")}),
    (821.90, "kw_80", "kw", 2.6, {"KICK": "Personal brand", "MAIN": HL("80%") + " done by AI"}),
    (826.50, "sec7", "section", 1.6, {"NUM": "", "STEP": "MY RULE", "TITLE": "10 · 80 · 10", "SUB": "You think. AI executes. You add taste."}),
    (828.20, "rule", "rule", 16.6, {"T1": 1.0, "T2": 5.8, "T3": 11.7}),
    (853.90, "kw_solo", "kw", 2.8, {"KICK": "This channel", "MAIN": "Single-person " + HL("AI business")}),
    (858.60, "kw_emp", "kw", 2.4, {"KICK": "Hire", "MAIN": HL("AI employees")}),
    (888.50, "chip_wa", "chip", 3.8, {"TOP": "300", "ICON": WA, "T1": "WhatsApp community", "T2": "Link in the <b>description</b>"}),
    (901.50, "chip_sk", "chip", 3.8, {"TOP": "300", "ICON": PEOPLE, "T1": "Skool community", "T2": "Link in the <b>description</b>"}),
    (912.70, "chip_ig", "chip", 3.4, {"TOP": "300", "ICON": INSTA, "T1": "This reel is on Instagram", "T2": "Follow for <b>more</b>"}),
    (918.80, "sub2", "sub", 4.4, {}),
    (935.43, "sec8", "section", 1.8, {"NUM": "", "STEP": "THE NUMBERS", "TITLE": "What it actually costs", "SUB": "Human editor vs Claude — my real numbers"}),
    (947.00, "kw_ed", "kw", 2.8, {"KICK": "Human editor", "MAIN": "₹500–1,000 " + HL("/ reel")}),
    (958.60, "kw_glob", "kw", 2.8, {"KICK": "Global clients", "MAIN": "$20–30 " + HL("/ reel")}),
    (992.80, "kw_plan", "kw", 2.8, {"KICK": "This entire edit", "MAIN": "Claude " + HL("$20") + " plan"}),
    (1015.50, "kw_5h", "kw", 2.4, {"KICK": "Usage limit resets", "MAIN": "Every " + HL("5 hrs")}),
    (1021.10, "kw_120", "kw", 2.6, {"KICK": "$20 plan", "MAIN": HL("120") + " limits / month"}),
    (1029.47, "kw_lim", "kw", 2.8, {"KICK": "One limit", "MAIN": "≈ ₹" + HL("10–30")}),
    (1057.60, "kw_max", "kw", 2.8, {"KICK": "Max plan · ₹10,000", "MAIN": "~" + HL("100 reels")}),
    (1061.87, "kw_100", "kw", 2.6, {"KICK": "Cost per reel", "MAIN": "~₹" + HL("100")}),
    (1073.60, "compare", "compare", 5.4, {}),
    (1090.50, "end", "end", 6.0, {}),
]

spec, overlays, sfx = [], [], []
pop_windows = []
T = {}                                                    # graphic id -> output start time
for m, gid, tpl, dur, var in G:
    t0 = out_of(m) - (0.12 if tpl == "kw" else 0.0)       # pops land a beat before the word
    T[gid] = round(t0, 3)
    spec.append({"id": gid, "tpl": tpl, "dur": dur, "vars": {k: str(v) for k, v in var.items()}})
    overlays.append({"file": f"{GFX}\\{gid}\\render.webm", "start": round(t0, 3), "dur": dur})
    if tpl in ("kw", "chip", "rule", "compare", "end", "sub", "lower"):
        pop_windows.append((t0, t0 + dur))
    if tpl == "section":
        sfx.append({"file": SWOOSH, "at": round(max(0, t0 + 0.05 - PEAK[SWOOSH]), 3), "gain_db": -17})
    elif tpl == "kw":
        sfx.append({"file": CPOP, "at": round(t0 + 0.02, 3), "gain_db": -19})
    elif tpl in ("chip", "compare", "end"):
        sfx.append({"file": POP, "at": round(max(0, t0 + 0.1 - PEAK[POP]), 3), "gain_db": -19})
    elif tpl == "sub":
        sfx.append({"file": CLICK, "at": round(t0 + 1.30, 3), "gain_db": -14})
    elif tpl == "rule":
        for k in ("T1", "T2", "T3"):
            sfx.append({"file": CPOP, "at": round(t0 + float(var[k]), 3), "gain_db": -18})


# ---------------- segments ----------------
def scr_kind(m):
    s = m + SCR_OFF
    if 270 <= s <= 356:      # PDF scroll states measured on frames: cover / list low / list high / scrolled on
        mm = m
        return "pdf_cover" if mm < 517.5 else "pdf_a" if mm < 540 else "pdf_b" if mm < 585 else "pdf_c"
    if 156 <= s < 183: return "explorer"
    if 136 <= s < 156 or 183 <= s < 216: return "welcome"
    if 400 <= s < 440: return "frames"
    if 500 <= s < 515: return "reel"
    return "chat"


CROPS = {"chat": [[245, 45, 1440, 810], [325, 90, 1280, 720]],
         "pdf_cover": [[40, 0, 1840, 1035], [40, 0, 1840, 1035]],
         "pdf_a": [[400, 204, 1477, 831], [430, 210, 1400, 788]],
         "pdf_b": [[400, 100, 1477, 831], [430, 120, 1400, 788]],
         "pdf_c": [[400, 120, 1477, 831], [430, 140, 1400, 788]],
         "explorer": [[0, 0, 1280, 720], [0, 0, 1280, 720]], "welcome": [[40, 0, 1840, 1035], [240, 60, 1600, 900]],
         "frames": [[290, 0, 1280, 720], [290, 0, 1280, 720]], "reel": [[40, 0, 1840, 1035], [40, 0, 1840, 1035]]}


def framing(kind, fx, fy):
    z = {"W": 1.06, "W2": 1.14, "M": 1.25, "T": 1.55, "L": 1.25, "L2": 1.12, "LT": 1.4}[kind]
    w, h = 1920 / z, 1080 / z
    if kind in ("W", "W2"):            # >=1.06 and shifted: crops the stand intruding top-left of the camera frame
        return z, 990, 560
    if kind in ("L", "L2", "LT"):
        return z, 1920 - w / 2, fy + 0.12 * h
    return z, fx + (0.08 if kind == "M" else 0.06) * w, fy + (0.12 if kind == "M" else 0.10) * h


def overlaps(a, b):
    return any(a < y and b > x for x, y in pop_windows)


segs = [{"type": "clip", "file": INTRO}]
cycle = ["M", "T", "M", "W", "T", "M", "T", "W"]
LCYCLE = ["L", "LT", "L2"]
ci, li, last_kind, last_cam, scr_flip = 0, 0, None, None, 0
for i, p in enumerate(pieces):
    fx, fy, ok = face_for(p["m0"], p["m1"])
    is_scr = p["sec"].startswith("s_")
    kind_s = scr_kind((p["m0"] + p["m1"]) / 2) if is_scr else None
    # static screens (chat / welcome) alternate with the camera so the face keeps coming back
    if is_scr and kind_s in ("chat", "welcome") and i % 2 == 1:
        is_scr = False
    # split long pieces into 4-7 s shots (continuous audio: no fade at the internal joins)
    d = p["m1"] - p["m0"]
    n = 1 if d < 7.5 else int(round(d / 5.5))
    bounds = [p["m0"]]
    for k in range(1, n):
        target = p["m0"] + d * k / n
        # camera changes land on a phrase pause when one is near, never between two identical words
        # ("poora | poora" across an angle change reads as a repeated word)
        cands = [(w["start"], w["start"] - words[j - 1]["end"]) for j, w in enumerate(words)
                 if j and p["m0"] + 1.5 < w["start"] < p["m1"] - 1.5
                 and words[j - 1]["text"].strip(",.?! ") != w["text"].strip(",.?! ")]
        if cands:
            best = min(cands, key=lambda c: abs(c[0] - target) - (0.8 if c[1] >= 0.12 else 0))[0]
            best = round(round(best * FPS) / FPS, 3)
            if best - bounds[-1] > 1.2:
                bounds.append(best)
    bounds.append(p["m1"])
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        o0, o1 = out_of(a), out_of(a) + (b - a)
        seg = {"m0": a, "m1": b, "fade_in": k == 0, "fade_out": k == len(bounds) - 2, "sec": p["sec"]}
        if is_scr:
            kind_seg = scr_kind((a + b) / 2)          # classify per shot: the screen changes inside a piece
            crop = CROPS[kind_seg][scr_flip % 2]; scr_flip += 1
            seg.update({"type": "scr", "crop": crop, "bubble": True,
                        "bubble_xy": [1520, 660], "face": [fx, fy]})
            last_kind = "scr"
        else:
            if (b - a) < 1.0 and last_cam:
                # tiny shot: keep the framing, push 6% so the jump cut still reads as intentional
                z, cx, cy = min(1.7, last_cam[0] * 1.06), last_cam[1], last_cam[2]
                kind = last_kind + "+"
            else:
                if not ok:
                    kind = "W2" if last_kind == "W" else "W"
                elif overlaps(o0 + 0.05, o1 - 0.05):
                    kind = LCYCLE[li % 3]; li += 1
                    if kind == last_kind:
                        kind = LCYCLE[li % 3]; li += 1
                else:
                    kind = cycle[ci % len(cycle)]; ci += 1
                    if kind == last_kind:
                        kind = cycle[ci % len(cycle)]; ci += 1
                z, cx, cy = framing(kind, fx, fy)
            seg.update({"type": "cam", "zoom": round(z, 4), "cx": round(cx), "cy": round(cy), "shot": kind})
            last_kind, last_cam = kind.rstrip("+"), (z, cx, cy)
        segs.append(seg)

# whoosh on every camera <-> screen switch
prev = "clip"
for s in segs[1:]:
    if s["type"] != prev and prev != "clip":
        t = out_of(s["m0"])
        sfx.append({"file": WHOOSH, "at": round(max(0, t - PEAK[WHOOSH]), 3), "gain_db": -22})
    prev = s["type"]

# ---------------- music: an original score cut to picture (rendered by tools/score_music.py) ----------------
END = out_of(1e9)
H = lambda gid: round(T[gid] + 0.05, 3)                  # downbeat on the card's whoosh peak
SLAM, GLASS, DOC = 2.02, 21.19, 39.52                    # intro hits: reel boom 1.89, glass 22.99, doc flare 67.72 (intro BLOCKS)
STOP = round(T["kw_meta"] - 0.35, 3)                     # music cuts out under "AI is making the video with AI"...
BACK = round(out_of(773.514) - 0.16, 3)                  # ...and drops back in on "aur" (word at master 773.514)
CARDS = ["sec1", "sec2", "sec3", "sec4", "sec5", "sec6", "sec7", "sec8"]
score = {
    "length": END,
    "blocks": [
        {"t0": 0.0, "t1": SLAM, "cue": "hook", "level": 0, "start": "fade", "end": "riser"},
        {"t0": SLAM, "t1": GLASS, "cue": "hook", "level": 3, "start": "hit", "end": "riser"},
        {"t0": GLASS, "t1": DOC, "cue": "hook", "level": 4, "start": "hit", "end": "cut"},
        {"t0": DOC, "t1": INTRO_LEN, "cue": "hook", "level": 0, "start": "drop", "end": "riser", "riser": 1.4},
        {"t0": INTRO_LEN, "t1": H("sec1"), "cue": "story", "level": 1, "level_at": [[T["sub1"], 2]],
         "start": "hit", "drums_in": 2, "end": "riser"},
        {"t0": H("sec1"), "t1": H("sec2"), "cue": "build", "level": 1, "start": "hit", "end": "riser", "build": "roll"},
        {"t0": H("sec2"), "t1": H("sec3"), "cue": "build", "level": 2, "start": "hit", "end": "riser"},
        {"t0": H("sec3"), "t1": H("sec4"), "cue": "build", "level": 3, "start": "hit", "end": "riser", "build": "roll"},
        {"t0": H("sec4"), "t1": H("sec5"), "cue": "build", "level": 3, "start": "hit", "end": "riser"},
        {"t0": H("sec5"), "t1": H("sec6"), "cue": "build", "level": 4, "start": "hit", "end": "riser", "build": "roll"},
        {"t0": H("sec6"), "t1": STOP, "cue": "build", "level": 4, "start": "hit", "end": "tapestop"},
        {"t0": BACK, "t1": H("sec7"), "cue": "build", "level": 5, "start": "drop", "end": "riser"},
        {"t0": H("sec7"), "t1": H("sec8"), "cue": "reflect", "level": 1, "level_at": [[T["chip_wa"], 2]],
         "start": "hit", "end": "riser", "build": "roll"},
        {"t0": H("sec8"), "t1": round(T["compare"] + 0.1, 3), "cue": "numbers", "level": 3, "start": "hit", "end": "riser", "riser": 2},
        {"t0": round(T["compare"] + 0.1, 3), "t1": H("end"), "cue": "numbers", "level": 4, "start": "hit", "end": "riser"},
        {"t0": H("end"), "t1": END, "cue": "outro", "level": 4, "start": "hit", "end": "ring", "ring": 0.7},
    ],
    "events": [
        {"type": "dip", "t0": round(T["kw_95"] - 0.6, 3), "t1": round(T["kw_95"] + 2.2, 3)},   # spotlight the 9.5/10 tip
        {"type": "bell", "t": round(T["kw_95"] + 0.12, 3), "note": 88},
        *({"type": "bell", "t": round(T["rule"] + k, 3), "note": n} for k, n in ((1.0, 76), (5.8, 79), (11.7, 84))),
        *({"type": "lift", "t0": H(g) - 0.35, "t1": H(g) + 1.6, "db": 6} for g in CARDS),
        *({"type": "lift", "t0": t - 0.3, "t1": t + 0.9, "db": 4} for t in (SLAM, GLASS, INTRO_LEN)),
        *({"type": "lift", "t0": T[g], "t1": T[g] + d, "db": 3} for g, d in (("sub1", 5.0), ("sub2", 4.4))),
        {"type": "lift", "t0": T["compare"] - 0.25, "t1": T["compare"] + 1.4, "db": 5},
    ],
    "duck": [{"t0": 0.0, "t1": INTRO_LEN, "speech": -15, "gap": -7},
             {"t0": INTRO_LEN, "t1": H("end"), "speech": -18, "gap": -9},
             {"t0": H("end"), "t1": 1e9, "speech": -15, "gap": -7}],
}
print(f"music: stop {STOP} -> back {BACK}; cards at {[H(g) for g in CARDS]}")

cfg = {
    "fps": FPS,
    "cam": {"path": r"D:\october videos\ai editor\C7443.MP4" if FINAL else E + r"\cam_proxy.mp4", "offset": CAM_OFF, "px": 2.0 if FINAL else 1.0},
    "scr": {"path": r"D:\october videos\ai editor\2026-10-06 21-27-13.mp4", "offset": SCR_OFF},
    "wav": r"D:\october videos\ai editor\ai editor.wav",
    "grade": GRADE,
    "bubble": {"x": 1520, "y": 660, "d": 360, "size": 520, "cx": 1001, "cy": 470},
    "segments": segs,
    "overlays": overlays,
    "sfx": sorted(sfx, key=lambda s: s["at"]),
    "music": {"file": E + r"\music_score.wav", "gain_db": 0, "sidechain": False, "score": score},
    "voice_gain": [[0.0, INTRO_LEN, -5.0]],               # reel audio runs ~6 dB hotter than the long-form voice
    "out": E + (r"\LONGFORM_final.mp4" if FINAL else r"\longform_preview.mp4"),
    "preset": "medium" if FINAL else "veryfast", "crf": 18 if FINAL else 21,
    "out_scale": 2 if FINAL else 1,                       # final exports 3840x2160 (camera is native 4K)
}
json.dump(cfg, open(E + r"\lf.json", "w"), indent=1)
json.dump(spec, open(E + r"\gfx_spec.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
total = INTRO_LEN + pieces[-1]["out0"] + pieces[-1]["m1"] - pieces[-1]["m0"]
shots = {}
for s in segs[1:]:
    shots[s.get("shot", s["type"])] = shots.get(s.get("shot", s["type"]), 0) + 1
print(f"{len(segs)} segments, {len(overlays)} overlays, {len(sfx)} sfx, total {total:.1f}s ({total / 60:.2f} min)")
print("shots:", shots)
