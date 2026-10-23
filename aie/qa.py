"""The 9.5 audit: every delivered variant checked against the plan's pass lines; each finding names the agent that owns
the fix.

  check        pass line                                                               owner on fail
  length       each variant runs its expected length, within a frame                   Producer
  loudness     -14 LUFS (+-0.5), true peak <= -1.5 dBTP                                Sound Designer
  sync         every kept stretch lines up with the voice stem, |lag| <= 10 ms         Sound Designer
  joints       no hole in the room tone at an audio joint (cut jobs)                   Cut Surgeon
  words        no word lost under music or at a joint (Whisper on the final mix)       Cut Surgeon
  spelling     caption words spelled as the job's word list says; no doubled words     Proofreader
  safe_zone    captions and effects inside x 90-930, y 200-1560 (9:16 jobs)             Motion Designer
  on_word      an effect placed on a "word" starts within -0.15 / +0.2 s of it          Story Editor
  rights       client jobs use only client, generated or licensed sources               Producer
  compliance   no income, return or guarantee claims (script, captions, effects)       blocks the job, flags Paras
Advisory (warnings): something on screen in the first second; no picture held still for over 3 s (the Herk kit's
2.2 s event-gap rule, measured on the picture itself); every cut on a spoken word, -0.15 / +0.2 s (the kit's anchor
rule); no B-roll window used twice (the kit's footage ledger).

A check that can't run on this machine (Whisper missing) is "not run", listed, and doesn't count either way.
Score: 10, minus 1 per failed check and 0.1 per warning (0.5 at most). The gate passes at 9.5 with no failure.
Ported from reel-04's qa_final.py / qa_joints.py / qa_sheet.py and the checks in reel-05's VERIFY.md.
"""
import json
import re
import subprocess
from pathlib import Path

import numpy as np

SR = 16000
SAFE = (90, 200, 930, 1560)
OWNER = {"length": "Producer", "loudness": "Sound Designer", "sync": "Sound Designer", "joints": "Cut Surgeon",
         "words": "Cut Surgeon", "spelling": "Proofreader", "safe_zone": "Motion Designer", "on_word": "Story Editor",
         "rights": "Producer", "compliance": "Paras", "hook": "Story Editor", "static": "Story Editor",
         "anchors": "Story Editor", "footage": "Story Editor"}
CLAIMS = [r"guarantee\w*", r"\d+\s*%\s*(?:return|profit|roi)\w*", r"\b(?:returns?|profits?)\s+(?:of|upto|up to)\s+\d",
          r"passive income", r"get rich", r"financial freedom", r"double (?:your|apna|aapka) (?:money|paisa)",
          r"paisa double", r"(?:earn|kama\w*)\s+(?:₹|rs\.?|inr)?\s*\d[\d,.]*\s*(?:k|lakh|lac|crore|cr)?",
          r"(?:₹|rs\.?)\s*\d[\d,.]*\s*(?:k|lakh|lac|crore|cr)?\s*(?:per|a|every|har|/)\s*(?:month|mahina|mahine|week|day|din)",
          r"\d+\s*(?:lakh|lac|crore|cr)\s*(?:per|a|every|har|/)\s*(?:month|mahina|mahine|week|day|din)",
          r"income\s+(?:of|upto|up to|guarantee)", r"risk[- ]free", r"sure[- ]shot", r"pakka (?:profit|paisa|return)"]


def _pcm(path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def _env(x):
    e = np.abs(x[: len(x) // 80 * 80]).reshape(-1, 80).mean(1)       # 200 Hz envelope (5 ms)
    return (e - e.mean()) / (e.std() + 1e-9)


def lag_ms(a: np.ndarray, b: np.ndarray, max_ms: int = 200) -> tuple:
    """Lag of a against b in ms (5 ms steps; negative when a runs late) and the correlation peak; from reel-04's
    qa_final.py."""
    a, b = _env(a), _env(b)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    k = max_ms // 5
    c = [np.dot(a[max(0, -lg):n - max(0, lg)], b[max(0, lg):n - max(0, -lg)]) for lg in range(-k, k + 1)]
    return (int(np.argmax(c)) - k) * 5, float(max(c) / n)


def out_map(ranges: list):
    """Master time -> this variant's output time, or None when the variant cut it."""
    def f(m):
        t = 0.0
        for a, b in ranges:
            if a - 1e-6 <= m < b - 1e-6:
                return t + m - a
            t += b - a
        return None
    return f


def cuts(data: dict, pieces: list | None, ranges: list) -> list:
    """Output times of every cut in a variant: camera or layout changes, and the joins between its ranges."""
    if pieces:
        starts = [p["out0"] for p in pieces]
    else:
        starts = [s["t"][0] for s in data.get("timeline", [])]
    f, out = out_map(ranges), set()
    for m in starts:
        o = f(m)
        if o is not None and o > 0.01:
            out.add(round(o, 3))
    t = 0.0
    for a, b in ranges[:-1]:
        t += b - a
        out.add(round(t, 3))
    return sorted(out)


def stretches(data: dict, pieces: list | None, ranges: list, length: float) -> list:
    """[(master a, master b, output start)] of every piece or segment inside the variant, for the sync check."""
    spans = [(p["out0"], p["out0"] + p["out"] - p["in"]) for p in pieces] if pieces else \
        [tuple(s["t"]) for s in data.get("timeline", [])] or [(0.0, length)]
    out, t = [], 0.0
    for a, b in ranges:
        for s, e in spans:
            lo, hi = max(a, s), min(b, e)
            if hi - lo >= 1.0:
                out.append((lo, hi, t + lo - a))
        t += b - a
    return out


def sync(final: np.ndarray, voice: np.ndarray, items: list) -> list:
    rows = []
    for a, b, o in items:
        v = voice[int(a * SR): int(b * SR)]
        if len(v) < SR or np.sqrt((v ** 2).mean()) < 1e-3:          # no voice to line up with
            continue
        lag, peak = lag_ms(final[int(o * SR): int((o + b - a) * SR)], v)
        rows.append({"master": [round(a, 2), round(b, 2)], "out": round(o, 2), "lag_ms": lag, "corr": round(peak, 2)})
    return rows


def holes(voice: np.ndarray, at: list) -> list:
    """Joints where the room tone drops into silence: the quietest 10 ms within +-30 ms of the cut against the quietest
    10 ms 50-150 ms either side (reel-04's qa_joints.py)."""
    def rms(a, b):
        x = voice[max(0, int(a * SR)): int(b * SR)]
        return 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9) if len(x) else -120.0
    out = []
    for c in at:
        lo = min(rms(t, t + 0.01) for t in np.arange(c - 0.03, c + 0.03, 0.005))
        ar = min(rms(t, t + 0.01) for t in [*np.arange(c - 0.15, c - 0.05, 0.005), *np.arange(c + 0.05, c + 0.15, 0.005)])
        if lo < ar - 10:
            out.append({"at": round(c, 2), "at_cut_db": round(lo, 1), "around_db": round(ar, 1)})
    return out


def _norm(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower())


def spelling(words: list, canon: list) -> list:
    """Caption words that match a name on the word list but are spelled or cased differently, and doubled words."""
    want = {_norm(c): c for c in canon if _norm(c)}
    out = []
    for i, w in enumerate(words):
        txt = re.sub(r"^[^\w]+|[^\w]+$", "", w["text"])
        n = _norm(txt)
        if n in want and txt != want[n] and txt.upper() != txt:         # ALL CAPS is a style, not a misspelling
            out.append({"at": w["start"], "found": txt, "want": want[n]})
        if i and n and n == _norm(words[i - 1]["text"]) and w["start"] - words[i - 1]["end"] < 0.6:
            out.append({"at": w["start"], "found": f"{words[i - 1]['text']} {w['text']}", "want": "one word (doubled)"})
    return out


def caption_zone(cap: dict, size) -> list:
    """Each caption style's box against the safe zone: margins left/right, baseline at the bottom, two lines up."""
    from .captions import STYLE_DEFAULTS
    W, H = size
    out = []
    for name, st in (cap.get("styles") or {}).items():
        st = {**STYLE_DEFAULTS, **st}
        ml, mr = st["margins"]
        base = st.get("baseline", H - 60)
        top = base - 2 * st["size"] * 1.2
        x0, y0, x1, y1 = SAFE
        if ml < x0 or W - mr > x1 or base > y1 or top < y0:
            out.append({"style": name, "box": [ml, round(top), W - mr, base]})
    return out


def alpha_box(webm: Path, times: list, size) -> list:
    """Bounding box of what an overlay draws at each time (None when nothing): decoded with libvpx so alpha survives."""
    w, h = size
    out = []
    for t in times:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", str(webm), "-vf",
                              f"select='gte(t\\,{t:.3f})',format=rgba", "-frames:v", "1", "-f", "rawvideo", "-"],
                             capture_output=True, check=True).stdout
        a = np.frombuffer(raw[:w * h * 4], np.uint8).reshape(h, w, 4)[..., 3]
        ys, xs = np.nonzero(a > 40)
        out.append(None if len(xs) < 500 else [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())])
    return out


def effect_zone(zone: str, boxes: list) -> list:
    out = []
    for b in boxes:
        if b is None:
            continue
        if zone == "stage" and b[3] >= 966:
            out.append(f"draws below the stage (y {b[3]})")
        if zone == "full" and (b[0] < SAFE[0] - 40 or b[2] > SAFE[2] + 40 or b[1] < SAFE[1] or b[3] > SAFE[3]):
            out.append(f"outside the safe zone {b}")
    return sorted(set(out))


def on_word(places: list, words: list) -> list:
    """Effects with a "word": the nearest caption word with that text (within 2 s) and how far the effect is from it."""
    rows = []
    for i, p in enumerate(places):
        if "word" not in p:
            continue
        want = _norm(p["word"])
        near = [w for w in words if _norm(w["text"]) == want and abs(w["start"] - p["at"]) <= 2.0]
        if not near:
            rows.append({"effect": i, "word": p["word"], "at": p["at"], "off": None})
            continue
        w = min(near, key=lambda w: abs(w["start"] - p["at"]))
        rows.append({"effect": i, "word": p["word"], "at": p["at"], "word_at": w["start"],
                     "off": round(p["at"] - w["start"], 3)})
    return rows


def anchors(timeline: list, words: list) -> list:
    """Cuts that don't start on a spoken word (-0.15 / +0.2 s); a cut with no word within a second is in a pause, fine."""
    out = []
    for s in timeline[1:]:
        c = s["t"][0]
        if any(-0.15 <= w["start"] - c <= 0.2 for w in words) or not any(abs(w["start"] - c) <= 1.0 for w in words):
            continue
        nxt = min((w for w in words if w["start"] >= c - 0.15), key=lambda w: w["start"], default=None)
        out.append({"cut": c, "next_word": nxt and nxt["text"], "off": nxt and round(nxt["start"] - c, 2)})
    return out


def reused(timeline: list) -> list:
    """B-roll windows of one source that overlap (the same shot shown twice)."""
    seen, out = {}, []
    for s in timeline:
        if s.get("layout") not in ("broll", "hook"):
            continue
        a = s["in"]
        b = a + (s["t"][1] - s["t"][0]) * s.get("speed", 1.0)
        for a2, b2, t in seen.get(s["src"], []):
            if a < b2 - 0.05 and a2 < b - 0.05:
                out.append({"src": s["src"], "at": [t, s["t"][0]], "window": [round(max(a, a2), 2), round(min(b, b2), 2)]})
        seen.setdefault(s["src"], []).append((a, b, s["t"][0]))
    return out


def claims(texts: list, cleared: list) -> list:
    """Phrases that read as income, return or guarantee claims. A screen, not a verdict: Paras reviews every hit, and
    one he clears goes into qa.cleared in job.json."""
    ok = [c.lower() for c in cleared]
    out = []
    for where, text in texts:
        for pat in CLAIMS:
            for m in re.finditer(pat, text, flags=re.I):
                hit = m.group(0)
                if not any(hit.lower() in c or c in hit.lower() for c in ok):
                    out.append({"where": where, "phrase": hit})
    return out


def still_spans(video: Path, size, min_s: float = 3.0) -> list:
    """Stretches where the picture barely changes for over min_s (sampled at 4 fps, 54x96 grey)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", "fps=4,scale=54:96,format=gray", "-f",
                          "rawvideo", "-"], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, 96, 54).astype(np.float32)
    if len(f) < 2:
        return []
    d = np.abs(np.diff(f, axis=0)).mean((1, 2))
    still, out, start = d < 0.6, [], None
    for i, s in enumerate(list(still) + [False]):
        if s and start is None:
            start = i
        if not s and start is not None:
            if (i - start) / 4 >= min_s:
                out.append([round(start / 4, 2), round(i / 4, 2)])
            start = None
    return out


def frame(video: Path, t: float, w: int, h: int):
    from PIL import Image
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1", "-vf",
                          f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return Image.frombytes("RGB", (w, h), raw[:w * h * 3]) if len(raw) >= w * h * 3 else Image.new("RGB", (w, h))


def joints_sheet(video: Path, at: list, size, out: Path) -> Path:
    """Last frame before | first frame after every cut (reel-04's qa_joints.py)."""
    from PIL import Image, ImageDraw
    W, H = (216, 384) if size[1] > size[0] else (384, 216)
    cols = 4
    rows = max(1, -(-len(at) // cols))
    sheet = Image.new("RGB", (cols * (2 * W + 8), rows * (H + 20)), "white")
    for i, c in enumerate(at):
        x0, y0 = i % cols * (2 * W + 8), i // cols * (H + 20)
        for j, t in enumerate((c - 0.04, c + 0.001)):
            sheet.paste(frame(video, t, W, H), (x0 + j * W, y0 + 20))
        ImageDraw.Draw(sheet).text((x0 + 4, y0 + 4), f"cut {c:.2f}s", fill="black")
    sheet.save(out, quality=88)
    return out


def zones_sheet(video: Path, times: list, size, out: Path) -> Path:
    """Frames at the given times with Instagram's UI zones drawn (reel-04's qa_sheet.py)."""
    from PIL import Image, ImageDraw
    vertical = size[1] > size[0]
    W, H = (270, 480) if vertical else (480, 270)
    cols = 8 if vertical else 4
    sheet = Image.new("RGB", (W * cols, (H + 22) * max(1, -(-len(times) // cols))), "white")
    for i, t in enumerate(times):
        im = frame(video, t, W, H)
        if vertical:
            d, k = ImageDraw.Draw(im), W / size[0]
            d.line([(0, 200 * k), (W, 200 * k)], fill="red")
            d.line([(0, 1560 * k), (W, 1560 * k)], fill="red")
            d.rectangle([930 * k, 1000 * k, W - 1, 1700 * k], outline="red")
        x, y = i % cols * W, i // cols * (H + 22)
        sheet.paste(im, (x, y + 22))
        ImageDraw.Draw(sheet).text((x + 4, y + 4), f"{t:.2f}s", fill="black")
    sheet.save(out, quality=88)
    return out


def heard(final: np.ndarray, voice: np.ndarray, items: list, model_name: str, language: str) -> list | None:
    """Words the voice stem says that the final mix loses (masked by music or clipped at a joint), per stretch.
    None when Whisper isn't installed here."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    m = WhisperModel(model_name, compute_type="int8")
    ask = lambda x: [_norm(w) for r in m.transcribe(x, language=language, beam_size=5, condition_on_previous_text=False,
                                                   vad_filter=False)[0] for w in r.text.split()]
    rows = []
    for a, b, o in items:
        v = voice[int(a * SR): int(b * SR)]
        f = final[int(o * SR): int((o + b - a) * SR)]
        said, got = ask(v), ask(f)
        left = list(got)
        lost = []
        for w in said:
            if w in left:
                left.remove(w)
            elif w:
                lost.append(w)
        rows.append({"out": round(o, 2), "said": " ".join(said), "lost": lost})
    return rows


def score(checks: dict) -> tuple:
    fails = sum(c["status"] == "FAIL" for c in checks.values())
    warns = sum(c["status"] == "WARN" for c in checks.values())
    s = round(max(0.0, 10.0 - fails - min(0.5, 0.1 * warns)), 2)
    return s, fails == 0 and s >= 9.5


def report_lines(rep: dict) -> list:
    out = [f"QA {rep['score']:.1f}/10  {'PASS' if rep['passed'] else 'FAIL'} (the gate is 9.5 with no failed check)"]
    for name, c in rep["checks"].items():
        out.append(f"  {c['status']:7s} {name:11s} {c['summary']}" + (f"  -> {c['owner']}" if c["status"] == "FAIL" else ""))
    return out


def check(status: str, name: str, summary: str, **detail) -> dict:
    return {"status": status, "owner": OWNER[name], "summary": summary, **detail}


def write(path: Path, rep: dict):
    path.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
