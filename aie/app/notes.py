"""Review notes: each note goes to the agent that owns the fix (the plan's agent roster), by what it talks about.

"0:47.80 caption galat hai: 'clod'" -> Proofreader; "music too loud here" -> Sound Designer; "cut the repeat" ->
Cut Surgeon. A note matching nothing goes to the Story Editor, who owns the edit as a whole.
"""
import re

OWNERS = [
    ("Proofreader", ["caption", "subtitle", "spelling", "spell", "typo", "galat likha", "wrong word", "srt", "hinglish"]),
    ("Sound Designer", ["music", "sound", "sfx", "loud", "quiet", "volume", "audio", "mix", "whoosh", "awaaz", "hit",
                        "beat drop", "score"]),
    ("Cut Surgeon", ["cut", "repeat", "stutter", "filler", "pause", "restart", "jump", "kaat", "dead air", "umm", "silence"]),
    ("Compositor", ["layout", "crop", "zoom", "frame", "face", "split", "full screen", "fullscreen", "pip", "bubble",
                    "position", "punch"]),
    ("Generator", ["b-roll", "broll", "b roll", "generated", "ai shot", "stock", "footage"]),
    ("Motion Designer", ["graphic", "text", "title", "animation", "effect", "chip", "card", "sticker", "font", "colour",
                         "color", "logo", "overlay", "stamp", "label"]),
    ("Story Editor", ["hook", "order", "pacing", "slow", "boring", "story", "ending", "cta", "beat", "storyboard"]),
]


def route(text: str) -> tuple:
    """(owner, the words that decided it)."""
    t = text.lower()
    for owner, words in OWNERS:
        hit = [w for w in words if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", t)]
        if hit:
            return owner, ", ".join(hit)
    return "Story Editor", "no lane named; the Story Editor owns the edit as a whole"


def timecode(t: float | None, fps: int = 25) -> str:
    if t is None:
        return ""
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{int(s):02d}.{int(round((s % 1) * 100)):02d}"
