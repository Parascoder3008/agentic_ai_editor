"""Word-by-word captions: the words (with their output times), then ASS subtitles, then SRT per variant.

job.json "captions":
  words      where the words come from (see caption_words):
               {"from": "aligned", "source": "avatar", "file": "edit/fa_out.json", "key": "all",
                "display": "script.txt", "strip": ":"}             one aligned list; display text from the script
               {"from": "pieces", "aligned": {"a": "edit/fa_a.json", "b": "edit/fa_b.json"}}
                                                                    each source's aligned words, through the cut
  text       fixes to the display text: replace, capitalize ("piece_start"), keywords, join
  styles     named caption styles; "Cap" is the default (see STYLE_KEYS)
  highlight  the current word: {"color": "#3AB0D8", "pop": 112, "pop_ms": 90}
  zones      [{"style": "Low", "layouts": ["hook", "broll", "face"], "lead": 0.05}, {"style": "Pip", "t": [a, b]}]
  break_at_cuts  start a fresh phrase at every cut and zone change, and never let a word linger past one
  hide       [[a, b], ...] windows with big on-screen text: no captions there
  chunk      {"max_words": 3, "max_chars": 22, "gap": 0.3}

Ported from tools/captions_ass.py and the reel-04 / reel-05 captions scripts; their output is reproduced byte for byte.
"""
import json
import re
from pathlib import Path

STYLE_KEYS = {"font", "size", "color", "outline_color", "back_color", "bold", "border", "outline", "shadow", "align",
              "margins", "baseline"}
STYLE_DEFAULTS = {"font": "Inter", "size": 64, "color": "#FFFFFF", "outline_color": "#0C0E0F", "back_color": "#000000",
                  "bold": True, "border": "outline", "outline": 5, "shadow": 0, "align": 2, "margins": [60, 60]}
CAPTION_KEYS = {"words", "text", "styles", "highlight", "zones", "break_at_cuts", "hide", "chunk"}
HIGHLIGHT = {"color": "#1A9FD1", "pop": 112, "pop_ms": 90}
CHUNK = {"max_words": 3, "max_chars": 22, "gap": 0.3}
HEX = re.compile(r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?")
EVENT_FORMAT = "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"


def ass_color(c: str) -> str:
    """CSS "#RRGGBB" or "#RRGGBBAA" (AA = opacity) -> ASS style colour "&HAABBGGRR" (AA = transparency)."""
    alpha = 255 - int(c[7:9], 16) if len(c) == 9 else 0
    return f"&H{alpha:02X}{ass_bgr(c)}"


def ass_bgr(c: str) -> str:
    """CSS "#RRGGBB" -> "BBGGRR", the colour part of an ASS override tag."""
    return f"{c[5:7]}{c[3:5]}{c[1:3]}".upper()


def ts(t: float) -> str:
    t = max(0.0, t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def sec(s: str) -> float:
    """ASS time back to seconds (rounded to 1/100, as written)."""
    h, m, x = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(x)


def style_line(name: str, st: dict, height: int) -> str:
    s = {**STYLE_DEFAULTS, **st}
    border = {"outline": 1, "box": 3}[s["border"]]
    mv = height - s["baseline"]
    return (f"Style: {name},{s['font']},{s['size']},{ass_color(s['color'])},{ass_color(s['color'])},"
            f"{ass_color(s['outline_color'])},{ass_color(s['back_color'])},{-1 if s['bold'] else 0},0,0,0,100,100,0,0,"
            f"{border},{s['outline']},{s['shadow']},{s['align']},{s['margins'][0]},{s['margins'][1]},{mv},1")


def header(styles: dict, size) -> str:
    w, h = size
    return ("[Script Info]\nScriptType: v4.00+\n" f"PlayResX: {w}\nPlayResY: {h}\n"
            "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding\n"
            + "\n".join(style_line(n, s, h) for n, s in styles.items())
            + f"\n\n[Events]\n{EVENT_FORMAT}\n")


def highlight_tag(hl: dict) -> str:
    h = {**HIGHLIGHT, **hl}
    return (rf"{{\c&H{ass_bgr(h['color'])}&\fscx{h['pop']}\fscy{h['pop']}"
            rf"\t(0,{h['pop_ms']},\fscx100\fscy100)}}")


def chunks(words: list, max_words: int = 3, max_chars: int = 22, gap: float = 0.3) -> list:
    """Short phrases: at most max_words / max_chars, ending at punctuation or a pause longer than gap."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        text_len = len(" ".join(x["text"] for x in cur))
        punct = w["text"][-1:] in ",.?!"
        if not nxt or len(cur) >= max_words or text_len >= max_chars or punct or nxt["start"] - w["end"] > gap:
            out.append(cur)
            cur = []
    return out


def events(words: list, hide: list, tag: str, chunk: dict | None = None) -> list:
    """One Dialogue line per word: its phrase on screen with the current word highlighted. Ends at the next word,
    and the last word of a phrase never overlaps the next phrase (stacked lines)."""
    def hidden(a, b):
        return any(a < h1 and b > h0 for h0, h1 in hide)
    lines, cs = [], chunks(words, **{**CHUNK, **(chunk or {})})
    for ci, ch in enumerate(cs):
        nxt = cs[ci + 1][0]["start"] if ci + 1 < len(cs) else 1e9
        for j, w in enumerate(ch):
            a = w["start"]
            b = ch[j + 1]["start"] if j + 1 < len(ch) else min(w["end"] + 0.12, nxt)
            if hidden(a, b):
                continue
            txt = " ".join((tag + x["text"] + r"{\c&HFFFFFF&}") if k == j else x["text"] for k, x in enumerate(ch))
            lines.append(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{txt}")
    return lines


# ---------------------------------------------------------------- words

def _aligned(path: Path, key: str | None = None) -> list:
    d = json.loads(path.read_text(encoding="utf-8"))
    if key:
        d = d[key]
    if isinstance(d, dict):                       # {chunk: [words]} -> one list in time order
        d = sorted((w for ws in d.values() for w in ws), key=lambda w: w["start"])
    return d


def fix_text(words: list, rules: dict, starts: set) -> list:
    """Display fixes, in this order: replace (exact word), capitalize at piece starts, keywords, joins."""
    rep = rules.get("replace", {})
    out = []
    for i, w in enumerate(words):
        txt = rep.get(w["text"], w["text"])
        if rules.get("capitalize") == "piece_start" and i in starts:
            txt = txt[:1].upper() + txt[1:]
        out.append({**w, "text": txt})
    for kw in rules.get("keywords", []):
        for i, w in enumerate(out):
            if w["text"].lower() == kw["word"] and i and out[i - 1]["text"] == kw.get("after", out[i - 1]["text"]):
                w["text"] = kw["as"]
    for jn in rules.get("join", []):
        first, rest = jn["words"][0], jn["words"][1:]
        for i in range(len(out) - len(rest) - 1, -1, -1):
            if out[i]["text"].lower() == first and [x["text"] for x in out[i + 1: i + 1 + len(rest)]] == rest:
                out[i] = {"text": jn["as"], "start": out[i]["start"], "end": out[i + len(rest)]["end"]}
                del out[i + 1: i + 1 + len(rest)]
    return out


def caption_words(job_dir: Path, data: dict, pieces: list | None = None) -> list:
    """Words on the output timeline: [{"text", "start", "end"}]."""
    cfg = data["captions"]["words"]
    rules = data["captions"].get("text", {})
    if cfg["from"] == "aligned":
        al = _aligned(job_dir / cfg["file"], cfg.get("key"))
        shift = data["sources"][cfg["source"]].get("voice_offset", 0.0) if cfg.get("source") else 0.0
        if cfg.get("display"):
            toks = (job_dir / cfg["display"]).read_text(encoding="utf-8").split()
            if len(toks) != len(al):
                raise ValueError(f"{cfg['display']} has {len(toks)} words but {cfg['file']} aligned {len(al)}")
            names = [t.rstrip(cfg.get("strip", "")) for t in toks]
        else:
            names = [w["text"] for w in al]
        words = [{"text": n, "start": round(w["start"] - shift, 3), "end": round(w["end"] - shift, 3)}
                 for n, w in zip(names, al)]
        return fix_text(words, rules, set())
    # through the cut: each piece takes the words that start inside it
    al = {src: _aligned(job_dir / f) for src, f in cfg["aligned"].items()}
    words, starts, t = [], set(), 0.0
    for p in pieces:
        s, e = p["in"], p["out"]
        first = True
        for w in al[p["src"]]:
            if s - 0.02 <= w["start"] < e - 0.04:
                if first:
                    starts.add(len(words))
                    first = False
                words.append({"text": w["text"], "start": round(t + w["start"] - s, 3),
                              "end": round(t + min(w["end"], e) - s, 3)})
        t += e - s
    return fix_text(words, rules, starts)


# ---------------------------------------------------------------- ASS

def zone_spans(cap: dict, data: dict) -> list:
    """(style, a, b, lead) for every zone, resolved to output time."""
    out = []
    for z in cap.get("zones", []):
        if "t" in z:
            out.append((z["style"], z["t"][0], z["t"][1], z.get("lead", 0.0)))
        for seg in data.get("timeline", []):
            if seg["layout"] in z.get("layouts", []):
                out.append((z["style"], seg["t"][0], seg["t"][1], z.get("lead", 0.0)))
    return out


def build_ass(data: dict, words: list, pieces: list | None = None, length: float | None = None) -> str:
    cap = data["captions"]
    styles = cap.get("styles") or {"Cap": {"baseline": 905}}
    tag = highlight_tag(cap.get("highlight", {}))
    hide = cap.get("hide", [])
    zones = zone_spans(cap, data)
    if cap.get("break_at_cuts"):
        cuts = sorted({0.0, (length or 0) + 1, *(p["out0"] for p in (pieces or [])),
                       *(x for _, a, b, _ in zones for x in (a, b))})
        body = [ln for a, b in zip(cuts, cuts[1:])
                for ln in events([w for w in words if a <= w["start"] < b], hide, tag, cap.get("chunk"))]
    else:
        cuts, body = None, events(words, hide, tag, cap.get("chunk"))
    out = []
    for ln in body:
        f = ln.split(",", 3)
        t = sec(f[1])
        if cuts:
            cut = min(c for c in cuts if c > t + 0.01)       # never let a word linger past its cut
            if sec(f[2]) > cut:
                f[2] = ts(cut)
                ln = ",".join(f)
        for name, a, b, lead in zones:
            if a - lead <= t < b:
                ln = ln.replace(",Cap,", f",{name},")
                break
        out.append(ln)
    return header(styles, data["size"]) + "\n".join(out) + "\n"


# ---------------------------------------------------------------- SRT

def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(words: list, ranges: list, chunk: dict | None = None) -> str:
    """SRT for one variant: words inside its ranges, moved onto the variant's own timeline."""
    out, off = [], 0.0
    for a, b in ranges:
        out += [dict(w, start=w["start"] - a + off, end=min(w["end"], b) - a + off) for w in words if a <= w["start"] < b]
        off += b - a
    cues = [f"{i}\n{srt_time(c[0]['start'])} --> {srt_time(c[-1]['end'])}\n{' '.join(w['text'] for w in c)}\n"
            for i, c in enumerate(chunks(out, **{**CHUNK, **(chunk or {})}), 1)]
    return "\n".join(cues)


# ---------------------------------------------------------------- job.json checks

def check(cap, data: dict) -> list:
    errs = []
    if not isinstance(cap, dict):
        return ["captions: must be an object"]
    errs += [f"captions: unknown key {k!r} (allowed: {', '.join(sorted(CAPTION_KEYS))})" for k in sorted(set(cap) - CAPTION_KEYS)]
    w = cap.get("words")
    if w is not None:
        if not isinstance(w, dict) or w.get("from") not in ("aligned", "pieces"):
            errs.append('captions.words.from: must be "aligned" (one aligned word list) or "pieces" (through the cut)')
        elif w["from"] == "aligned":
            if not isinstance(w.get("file"), str):
                errs.append("captions.words.file: the aligned words JSON, relative to the job folder")
            if "source" in w and w["source"] not in data.get("sources", {}):
                errs.append(f"captions.words.source: {w['source']!r} is not one of the sources")
        else:
            if not isinstance(w.get("aligned"), dict) or not w["aligned"]:
                errs.append("captions.words.aligned: {source: aligned words JSON} for each source the cut uses")
            elif data.get("cut", {}).get("mode") != "pieces" and "cut" not in data:
                errs.append("captions.words: \"from\": \"pieces\" needs a cut")
    styles = cap.get("styles", {})
    if not isinstance(styles, dict) or (styles and "Cap" not in styles):
        errs.append('captions.styles: an object of named styles, including the default "Cap"')
        styles = {}
    h = (data.get("size") or [0, 1920])[1]
    for name, st in styles.items():
        p = f"captions.styles.{name}"
        if not isinstance(st, dict):
            errs.append(f"{p}: must be an object")
            continue
        errs += [f"{p}: unknown key {k!r}" for k in sorted(set(st) - STYLE_KEYS)]
        if not isinstance(st.get("baseline"), int) or not 0 < st["baseline"] <= h:
            errs.append(f"{p}.baseline: the text baseline in px from the top, 1-{h}")
        for k in ("color", "outline_color", "back_color"):
            if k in st and not (isinstance(st[k], str) and HEX.fullmatch(st[k])):
                errs.append(f"{p}.{k}: \"#RRGGBB\" or \"#RRGGBBAA\" (AA = opacity)")
        if "border" in st and st["border"] not in ("outline", "box"):
            errs.append(f'{p}.border: "outline" or "box"')
        if "align" in st and st["align"] not in range(1, 10):
            errs.append(f"{p}.align: 1-9 like a phone keypad (2 = bottom centre, 1 = bottom left)")
    hl = cap.get("highlight", {})
    if "color" in hl and not (isinstance(hl["color"], str) and HEX.fullmatch(hl["color"])):
        errs.append('captions.highlight.color: "#RRGGBB"')
    for i, z in enumerate(cap.get("zones", [])):
        if not isinstance(z, dict) or z.get("style") not in styles:
            errs.append(f"captions.zones[{i}].style: must name one of the styles ({', '.join(styles) or 'none'})")
        elif "t" not in z and "layouts" not in z:
            errs.append(f"captions.zones[{i}]: give \"t\": [start, end] or \"layouts\": [...]")
    return errs
