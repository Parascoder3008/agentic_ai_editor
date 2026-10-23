"""Word-by-word ASS captions for a 1080x1920 reel (brand: Inter, white, current word #1A9FD1).

Input JSON: {"words": [{"text": "...", "start": s, "end": e}, ...],   # OUTPUT-timeline seconds
             "hide": [[t0, t1], ...]}                                  # windows with big on-screen text
Usage: python captions_ass.py words_out.json captions.ass [--y 905]
"""
import argparse
import json

HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter,64,&H00FFFFFF,&H00FFFFFF,&H000F0E0C,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,60,60,{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
BLUE = r"{\c&HD19F1A&\fscx112\fscy112\t(0,90,\fscx100\fscy100)}"
WHITE = r"{\c&HFFFFFF&}"


def ts(t):
    t = max(0.0, t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def chunks(words, max_words=3, max_chars=22, gap=0.3):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        text_len = len(" ".join(x["text"] for x in cur))
        punct = w["text"][-1:] in ",.?!"
        if (not nxt or len(cur) >= max_words or text_len >= max_chars or punct
                or nxt["start"] - w["end"] > gap):
            out.append(cur)
            cur = []
    return out


def build(words, hide):
    hidden = lambda a, b: any(a < h1 and b > h0 for h0, h1 in hide)
    lines = []
    cs = chunks(words)
    for ci, ch in enumerate(cs):
        nxt = cs[ci + 1][0]["start"] if ci + 1 < len(cs) else 1e9   # never overlap the next chunk (stacked lines)
        for j, w in enumerate(ch):
            a = w["start"]
            b = ch[j + 1]["start"] if j + 1 < len(ch) else min(w["end"] + 0.12, nxt)
            if hidden(a, b):
                continue
            txt = " ".join((BLUE + x["text"] + WHITE) if k == j else x["text"] for k, x in enumerate(ch))
            lines.append(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{txt}")
    return lines


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("words")
    ap.add_argument("out")
    ap.add_argument("--y", type=int, default=905, help="caption baseline y on the 1920 canvas")
    a = ap.parse_args()
    d = json.load(open(a.words, encoding="utf-8"))
    body = build(d["words"], d.get("hide", []))
    open(a.out, "w", encoding="utf-8").write(HEAD.format(mv=1920 - a.y) + "\n".join(body) + "\n")
    print(f"{len(body)} caption events -> {a.out}")
