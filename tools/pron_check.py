"""Pronunciation gate (run BEFORE any HeyGen avatar render).

Takes the TTS script (Devanagari for Hindi words, Latin for English terms, numbers spelled out) and a
speech preview of it (HeyGen create_speech, same voice), transcribes the preview with Whisper (Hindi),
aligns heard words to script words and flags every word that drifted. Paras listens to the flagged
words; only an approved preview's exact text goes to the avatar render.

Script convention: Hindi words in Devanagari, English words in Latin, numbers spelled out in English,
and words the voice mangles pinned as {Shown|बोला} (e.g. {Claude|क्लॉड}, {Meta|मेटा}).

Usage: python pron_check.py <script_tts.txt> --tts            (text to paste into HeyGen)
       python pron_check.py <script_tts.txt> <preview_audio> [--out report.md]
       python pron_check.py --selftest
"""
import argparse
import os
import re
import subprocess
import sys
from difflib import SequenceMatcher

CONS = dict(zip("कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह",
                "k kh g gh n ch chh j jh n t th d dh n t th d dh n p f b bh m y r l v sh sh s h".split()))
NUKTA = {"ज": "z", "फ": "f", "ड": "r", "ढ": "rh", "क": "q", "ख": "kh", "ग": "g"}
VOW = dict(zip("अआइईउऊएऐओऔऑऋ", "a aa i ee u oo e ai o au o ri".split()))
MATRA = dict(zip("ािीुूेैोौॉृ", "aa i ee u oo e ai o au o ri".split()))
NASAL, VIRAMA, NUK = "ंँ", "्", "़"


def roman(w):
    """rough Devanagari -> Latin (inherent 'a' kept except word-final), Latin passes through."""
    out, i = [], 0
    while i < len(w):
        c = w[i]
        if c in CONS:
            nxt = w[i + 1] if i + 1 < len(w) else ""
            if nxt == NUK:
                out.append(NUKTA.get(c, CONS[c])); i += 1
                nxt = w[i + 1] if i + 1 < len(w) else ""
            else:
                out.append(CONS[c])
            if nxt not in MATRA and nxt != VIRAMA and i + 1 < len(w):
                out.append("a")
        elif c in MATRA:
            out.append(MATRA[c])
        elif c in VOW:
            out.append(VOW[c])
        elif c in NASAL:
            out.append("n")
        elif c in (VIRAMA, NUK):
            pass
        else:
            out.append(c)
        i += 1
    return "".join(out)


def key(w):
    """comparison form: romanised, lower, vowel lengths and doubled letters collapsed."""
    s = roman(re.sub(r"[^\wऀ-ॿ]|[।॥]", "", w)).lower()
    s = s.replace("aa", "a").replace("ee", "i").replace("oo", "u").replace("w", "v").replace("c", "k")
    s = re.sub(r"(.)\1+", r"\1", s)
    latin = not re.search(r"[ऀ-ॿ]", w)
    return s[:-1] if latin and len(s) > 3 and s.endswith("e") and not s.endswith("ae") else s


PIN = re.compile(r"\{([^|}]+)\|([^}]+)\}")   # {Claude|क्लॉड}: captions say Claude, the voice gets क्लॉड


def tts(line):
    """the text that goes to HeyGen (pins resolved to their spoken spelling)."""
    return PIN.sub(r"\2", line)


def sim(a, b):
    m = PIN.fullmatch(re.sub(r"[^\wऀ-ॿ{}|]|[।॥]", "", a))
    if m:                                       # a pinned word may come back in either script
        return max(sim(m.group(1), b), sim(m.group(2), b))
    return SequenceMatcher(None, key(a), key(b)).ratio()


def align(exp, heard):
    """global alignment (gap -0.6, match = similarity) -> [(expected or None, heard or None, score)]."""
    n, m, G = len(exp), len(heard), -0.6
    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        D[i][0] = i * G
    for j in range(1, m + 1):
        D[0][j] = j * G
    S = [[sim(e, h) for h in heard] for e in exp]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j] = max(D[i - 1][j - 1] + S[i - 1][j - 1] * 2 - 1, D[i - 1][j] + G, D[i][j - 1] + G)
    out, i, j = [], n, m
    while i or j:
        if i and j and D[i][j] == D[i - 1][j - 1] + S[i - 1][j - 1] * 2 - 1:
            out.append((exp[i - 1], heard[j - 1], S[i - 1][j - 1])); i -= 1; j -= 1
        elif i and D[i][j] == D[i - 1][j] + G:
            out.append((exp[i - 1], None, 0.0)); i -= 1
        else:
            out.append((None, heard[j - 1], 0.0)); j -= 1
    return out[::-1]


ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def spell(n):
    """English words for 0..99999 (TTS scripts spell numbers out; Whisper writes digits)."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + spell(n % 100))
    return spell(n // 1000) + " thousand" + ("" if n % 1000 == 0 else " " + spell(n % 1000))


def expand(words):
    out = []
    for w, t in words:
        d = re.sub(r"[,.]", "", w)
        out += [(x, t) for x in spell(int(d)).split()] if d.isdigit() and int(d) < 100000 else [(w, t)]
    return out


def transcribe(audio):
    from faster_whisper import WhisperModel
    m = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=os.cpu_count())
    segs, _ = m.transcribe(audio, language="hi", beam_size=5, word_timestamps=True, vad_filter=False,
                           condition_on_previous_text=False, temperature=(0.0, 0.2, 0.4))
    return expand([(w.word.strip(), w.start) for s in segs for w in s.words if w.word.strip()])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", nargs="?")
    ap.add_argument("audio", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--th", type=float, default=0.62, help="flag words below this similarity")
    ap.add_argument("--tts", action="store_true", help="print the text to send to HeyGen and exit")
    a = ap.parse_args()
    lines = [l.strip() for l in open(a.script, encoding="utf-8") if l.strip()]
    if a.tts:
        print("\n".join(tts(l) for l in lines))
        return
    exp, line_of = [], []
    for li, l in enumerate(lines):
        for w in re.sub(r"(?<=[ऀ-ॿ])-(?=[ऀ-ॿ])", " ", l).split():   # कौन-सा = कौन सा
            if key(w):
                exp.append(w); line_of.append(li)
    heard = transcribe(a.audio)
    al = align(exp, [h for h, _ in heard])
    times = iter(t for _, t in heard)
    rows, k = [], 0
    for e, h, s in al:
        t = next(times) if h is not None else None
        li = line_of[k] if e is not None else (line_of[k] if k < len(line_of) else line_of[-1])
        if e is not None:
            k += 1
        deva = lambda x: bool(re.search(r"[ऀ-ॿ]", x or ""))   # Hindi word heard in Latin = said like English
        pinned = e is not None and "{" in e     # pins exist because the voice gets them wrong: exact match only
        flag = (e is None or h is None or s < (0.99 if pinned else a.th)
                or (deva(e) and not deva(h) and not pinned))
        rows.append((li, e, h, s, t, flag))
    flagged = [r for r in rows if r[5]]
    rep = [f"# Pronunciation check: {len(flagged)} word(s) to listen to\n",
           "| line | at (s) | script | heard | match |", "|---|---|---|---|---|"]
    rep += [f"| {li + 1} | {'' if t is None else f'{t:.1f}'} | {e or '—'} | {h or '— (missing)'} | {s:.2f} |"
            for li, e, h, s, t, f in flagged]
    rep.append("\nHeard, line by line:\n")
    for li, l in enumerate(lines):
        rep.append(f"{li + 1}. {' '.join(h for r_li, _, h, _, _, _ in rows if r_li == li and h)}")
    txt = "\n".join(rep)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        assert key("मैंने") != key("मेन"), (key("मैंने"), key("मेन"))      # the bug Paras heard: Maine -> "main"
        assert sim("ज़्यादा", "ज़्यादा") == 1.0 and sim("ज़्यादा", "जायदा") < 0.9
        assert sim("Claude", "क्लॉड") > 0.6 and sim("मेटा", "मेटा") == 1.0
        assert spell(9800) == "nine thousand eight hundred" and spell(33) == "thirty three" and spell(7) == "seven"
        assert [w for w, _ in expand([("9,800", 0)])] == ["nine", "thousand", "eight", "hundred"]
        assert tts("इस {Claude|क्लॉड} plugin") == "इस क्लॉड plugin"
        assert sim("{Claude|क्लॉड}", "Claude") == 1.0 and sim("{Claude|क्लॉड}", "क्लॉड") == 1.0
        assert sim("{Claude|क्लॉड}", "Cloud") < 0.9
        assert sim("{META|मेटा}।", "मेटा") == 1.0 and sim("दो।", "दो") == 1.0
        al = align(["a", "मैंने", "इस"], ["a", "मेन", "इस"])
        assert [x[1] for x in al] == ["a", "मेन", "इस"], al
        print("selftest ok", key("मैंने"), key("मेन"), key("Claude"), key("क्लॉड"))
    else:
        main()
