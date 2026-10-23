"""Turn a job's cut decisions into frame-exact pieces in output order.

Two modes (job.json "cut"):
  spans   keep/drop spans on one source; every edge is measured on the audio (long-form, from body_edl.py):
          split at silences >= gap, snap each edge to the quietest 10 ms, never pad into the neighbouring word,
          then land on the frame grid.
  pieces  edges already measured by hand (reel-04, from edl.py); only the output times are laid out.

A piece: {"src", "in", "out", "out0", ...} with in/out in source seconds and out0 = where it starts in the output.
"""
from .audio import Envelope

# Search windows of the span cutter, in seconds. Kept exactly as tuned on the long-form.
WIN_IN, WIN_OUT = 0.05, 0.10         # look this far outside a keep span for its first/last word
EDGE_SNAP = 0.03                     # an edge inside running speech snaps within +-30 ms of the word boundary
TOUCH = 0.011                        # an island this close to the window edge is cut inside running speech
NEIGHBOUR = 0.30                     # how far to look for the next/previous word's onset
GAP_BEFORE_NEXT, GAP_AFTER_PREV = 0.03, 0.04


def minus_drops(m0: float, m1: float, drop: list) -> list:
    """[m0, m1] with every drop span cut out; slivers of 50 ms or less are discarded."""
    spans = [(m0, m1)]
    for d0, d1, *_ in drop:
        spans = [x for a, b in spans for x in ((a, min(b, d0)), (max(a, d1), b)) if x[1] - x[0] > 0.05]
    return spans


def build_spans(env: Envelope, keep: list, drop: list, fps: int, src: str, gap: float = 0.40, pad_in: float = 0.08,
                pad_out: float = 0.12, silence_db: float = -55.0, speech_db: float = -45.0,
                min_island: float = 0.12) -> list:
    pieces, out_t = [], 0.0
    for k0, k1, sec, *_ in keep:
        for m0, m1 in minus_drops(k0, k1, drop):
            w0, w1 = m0 - WIN_IN, m1 + WIN_OUT
            for s, e in env.islands(w0, w1, silence_db, gap):
                if e - s < min_island:                       # clicks / breaths
                    continue
                # an island touching the window edge = a cut inside running speech: cut at the word boundary
                # itself (snapped +-30 ms), never padded into the neighbouring word (that left "time | time")
                s2 = (env.quiet(m0 - EDGE_SNAP, m0 + EDGE_SNAP) if s <= w0 + TOUCH
                      else env.quiet(s - pad_in - 0.04, s - pad_in + 0.02))
                e2 = (env.quiet(m1 - EDGE_SNAP, m1 + EDGE_SNAP) if e >= w1 - TOUCH
                      else env.quiet(e + pad_out - 0.02, e + pad_out + 0.05))
                # padding never reaches into the neighbouring word (a faint closure can stretch an island, then
                # the pad lands inside the next word's burst - that's how "bhai | b-" leaked in)
                nxt = env.onset(e + 0.02, NEIGHBOUR, True, speech_db)
                prv = env.onset(s - 0.02, NEIGHBOUR, False, speech_db)
                if nxt is not None:
                    e2 = min(e2, nxt - GAP_BEFORE_NEXT)
                if prv is not None:
                    s2 = max(s2, prv + GAP_AFTER_PREV)
                if pieces and s2 < pieces[-1]["out"]:
                    s2 = pieces[-1]["out"]
                s2 = round(round(s2 * fps) / fps, 3)
                d = max(1, round((e2 - s2) * fps)) / fps
                pieces.append({"src": src, "in": s2, "out": round(s2 + d, 3), "sec": sec, "out0": round(out_t, 3)})
                out_t += d
    return pieces


def layout_pieces(pieces: list) -> list:
    """Measured pieces in output order -> the same pieces with out0 (output start)."""
    out, t = [], 0.0
    for p in pieces:
        out.append({**p, "out0": round(t, 4)})
        t += p["out"] - p["in"]
    return out


def total(pieces: list) -> float:
    return sum(p["out"] - p["in"] for p in pieces)


def to_output(t: float, pieces: list, src: str | None = None) -> float:
    """Source time -> output time. A time inside a removed gap maps to the start of the next kept piece."""
    ps = [p for p in pieces if src is None or p["src"] == src]
    for p in ps:
        if t < p["in"]:
            return p["out0"]
        if t < p["out"]:
            return round(p["out0"] + (t - p["in"]), 3)
    last = ps[-1]
    return round(last["out0"] + last["out"] - last["in"], 3)


def sections(pieces: list) -> list:
    """(section, output start, output end) per section label, in order (the cutter's report)."""
    out = []
    for p in pieces:
        end = p["out0"] + (p["out"] - p["in"])
        if out and out[-1][0] == p.get("sec"):
            out[-1] = (out[-1][0], out[-1][1], end)
        else:
            out.append((p.get("sec"), p["out0"], end))
    return out
