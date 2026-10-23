"""Checks that no word is repeated, clipped or left behind as a false start at any cut.

Whisper quietly deletes restarts ("aur... aur yahan tak"), so a cut list made from its transcript can keep both takes
and glue them together. These checks look at every joint from both sides instead:
  joints()         each kept piece transcribed on its own (so Whisper can't merge a repeat across the cut), then the
                   last words of one piece against the first words of the next  (from review_joints.py)
  repeat_report()  the same check on a verbatim, letter-level transcript, plus stutters inside pieces
                   (from check_repeats.py)
  ctc_letters()    letter timings in a short window, to place a cut between two words by hand  (from ctc_chars.py)
"""
import difflib
import os
import re
import subprocess

import numpy as np

from .audio import SR


def _norm(w):
    return re.sub(r"[^\w]", "", w.lower())


def _same(a, b):
    a, b = _norm(a), _norm(b)
    return bool(a) and difflib.SequenceMatcher(None, a, b).ratio() >= 0.75


def _fmt(ws):
    return " ".join(f"{w[2]}@{w[0]:.2f}" for w in ws)


def joints(items: list) -> list:
    """items: per-piece transcripts in output order, [{"i", "in", "out", "words": [[start, end, word], ...]}].
    repeat = the next piece opens with a word this one ends on (a restart); lone = this piece is under 1 s (a
    likely false start)."""
    out = []
    for a, b in zip(items, items[1:]):
        ta, hb = a["words"][-4:], b["words"][:4]
        out.append({"a": a, "b": b, "tail": ta, "head": hb,
                    "repeat": any(_same(x[2], y[2]) for x in ta[-2:] for y in hb[:2]),
                    "lone": a["out"] - a["in"] < 1.0})
    return out


def format_joints(js: list) -> list:
    """One line per joint; '<<' marks a repeat, '!!' a lone short piece. Read every line, not just the flags."""
    return [f"{'<<' if j['repeat'] else '  '}{'!!' if j['lone'] else '  '} P{j['a']['i']:03d}|P{j['b']['i']:03d} "
            f"m {j['a']['out']:8.2f}|{j['b']['in']:8.2f} gap {j['b']['in'] - j['a']['out']:5.2f}  "
            f"...{_fmt(j['tail'])} || {_fmt(j['head'])}..." for j in js]


def _sim(x, y):
    return difflib.SequenceMatcher(None, x, y).ratio()


def _repeat(tail, head):
    """Longest n (1..3 words) where tail's last n words ~ head's first n words."""
    for n in (3, 2, 1):
        if len(tail) >= n and len(head) >= n:
            t, h = "".join(w[2] for w in tail[-n:]), "".join(w[2] for w in head[:n])
            if len(t) >= 2 and _sim(t, h) >= 0.75:
                return n
    return 0


def _show(ws):
    return " ".join(w[2] for w in ws)


def cuts_from_pieces(pieces: list, offset: float = 0.0) -> list:
    """Every joint between consecutive pieces: (output time, source end of left, source start of right, is_cut).
    is_cut is False when the right piece continues the left one (a camera change inside a take, not an audio cut)."""
    cuts, out = [], 0.0
    for a, b in zip(pieces, pieces[1:]):
        out += a["out"] - a["in"]
        cuts.append((offset + out, a["out"], b["in"], abs(b["in"] - a["out"]) > 0.005))
    return cuts


def repeat_report(words: list, pieces: list, cuts: list, offset: float = 0.0) -> list:
    """words: verbatim [start, end, word] in source time. Lines: one per cut ('<<' = repeat), a count, then
    stutters (adjacent near-identical words) inside kept pieces."""
    def within(a, b):
        return [w for w in words if a - 0.02 <= (w[0] + w[1]) / 2 < b + 0.02]

    lines, n_flag = [], 0
    for t, ml, mr, joint in cuts:
        pl = next(p for p in pieces if p["in"] - 0.01 <= ml - 0.02 <= p["out"])     # piece holding the left side
        pr = next(p for p in pieces if p["in"] - 0.01 <= mr + 0.02 <= p["out"])
        tail = within(max(pl["in"], ml - 2.0), ml)
        head = within(mr, min(pr["out"], mr + 2.0))
        r = _repeat(tail, head)
        n_flag += r > 0
        gap = _show(within(ml, mr)) if joint else ""
        lines.append(f"{'<<' if r else '  '} out {t:7.2f} {'CUT ' if joint else 'cam '} m {ml:8.2f}|{mr:8.2f}  "
                     f"...{_show(tail[-5:])} || {_show(head[:5])}..." + (f"   [removed: {gap[:60]}]" if gap else ""))
    lines += ["", f"{n_flag} cuts flagged as repeats out of {len(cuts)}", "",
              "stutters inside kept pieces (adjacent near-identical words):"]
    for p in pieces:
        ws = within(p["in"], p["out"])
        for a, b in zip(ws, ws[1:]):
            if len(a[2]) >= 2 and _sim(a[2], b[2]) >= 0.8 and b[0] - a[1] < 0.6:
                lines.append(f"  m {a[0]:8.2f}  out {offset + p['out0'] + a[0] - p['in']:7.2f}  {a[2]} {b[2]}   "
                             f"...{_show(within(a[0] - 1.2, b[1] + 1.2))}")
    return lines


def transcribe_pieces(pieces: list, audio: dict, model_name: str, language: str, cache: list | None = None) -> list:
    """Each piece transcribed on its own (no prompt: a prompt full of repeats makes Whisper loop).
    audio: {source name: mono float array at 16 kHz}. Pieces whose edges didn't change are reused from cache."""
    from faster_whisper import WhisperModel     # heavy; only this stage needs it

    known = {(c["src"], c["in"], c["out"]): c for c in (cache or [])}
    model, out = None, []
    for i, p in enumerate(pieces):
        hit = known.get((p["src"], p["in"], p["out"]))
        if hit:
            out.append({**hit, "i": i})
            continue
        model = model or WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=os.cpu_count())
        seg = audio[p["src"]][int(p["in"] * SR): int(p["out"] * SR)]
        res, _ = model.transcribe(seg, language=language, word_timestamps=True, beam_size=5, vad_filter=False,
                                  condition_on_previous_text=False, temperature=(0.0, 0.2, 0.4))
        ws = [[round(p["in"] + w.start, 2), round(p["in"] + w.end, 2), w.word.strip()]
              for s in res for w in (s.words or [])]
        out.append({"i": i, "src": p["src"], "in": p["in"], "out": p["out"], "text": " ".join(w[2] for w in ws),
                    "words": ws})
    return out


def ctc_letters(path, a: float, b: float) -> str:
    """Letter-level CTC timeline (20 ms frames) for [a, b] of a source: 'char@time', '|' marks gaps >= 60 ms.
    No language model, so restarts and repeats are kept (Whisper drops them)."""
    import torch                                # heavy; diagnostics only
    from torchaudio.pipelines import MMS_FA as bundle

    model, labels = bundle.get_model(with_star=False).eval(), bundle.get_labels(star=None)
    lo = a - 1.0
    x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-ss", str(lo), "-to", str(b + 1.0), "-i", str(path),
                                      "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout,
                      np.float32).copy()
    with torch.inference_mode():
        em, _ = model(torch.from_numpy(x)[None])
    ids = em[0].log_softmax(-1).argmax(-1).numpy()
    step = len(x) / SR / len(ids)
    out, prev, last_t = [], 0, None
    for k, i in enumerate(ids):
        t = lo + k * step
        if i != prev and i != 0 and a <= t <= b:
            if last_t is not None and t - last_t >= 0.06:
                out.append("|")
            out.append(f"{labels[i]}{t:.2f}")
            last_t = t
        prev = i
    return f"{a:.2f}-{b:.2f}: " + " ".join(out)
