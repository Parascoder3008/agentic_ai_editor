"""The agent roster: the plan's agents that edit a job. Expensive reasoning sits where judgment matters (the Story
Editor), the lanes run on Sonnet. Each lane owns parts of job.json and can only change those. The Producer and the QA
Auditor are code (aie/agents/dispatch.py): routing a note or a failed check to its owner is a lookup, and queueing a
render is never a model's call.
"""
OPUS, SONNET, HAIKU = "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"
# $ per million tokens (input, output, cache read), for the per-dispatch budget; a 5-minute cache write is 1.25x input.
PRICE = {OPUS: (4.0, 20.0, 0.20), SONNET: (2.0, 10.0, 0.20), HAIKU: (0.10, 0.50, 0.01)}

ROLES = {
    "Story Editor": {
        "model": OPUS, "effort": "high", "iterations": 24,
        "owns": ["timeline", "cut", "effects", "sfx", "variants", "captions"],
        "brief": "You own the edit as a whole: the hook, the beats and their layouts, which effects go where and on which "
                 "word, the cut, the variants. Plan from the transcript and the brief; keep the storyboard tight "
                 "(hook within 1 s, nothing static over ~3 s, end on the CTA).",
    },
    "Proofreader": {
        "model": SONNET, "effort": "medium", "iterations": 12, "owns": ["captions", "qa"],
        "brief": "You own every word on screen: caption spellings (captions.text.replace maps a heard word to its display "
                 "spelling), brand names, Hinglish consistency in Roman script, the job's word list (qa.words), and the "
                 "text inside effect parameters only through a note to the Motion Designer.",
    },
    "Sound Designer": {
        "model": SONNET, "effort": "medium", "iterations": 12, "owns": ["sfx", "music", "mix"],
        "brief": "You own the sound: SFX cues (whoosh into cuts, pops on cards, hits on payoffs, never more than +3 dB over "
                 "the voice), the score settings and the mix. Masked words under a hit: lower or move that cue.",
    },
    "Motion Designer": {
        "model": SONNET, "effort": "medium", "iterations": 14, "owns": ["effects", "graphics"],
        "brief": "You own the graphics: which catalog effect, when, for how long, with what text, on which word. Stage "
                 "effects only over split beats; full-frame text inside the safe zone; never over the face.",
    },
    "Compositor": {
        "model": SONNET, "effort": "medium", "iterations": 12, "owns": ["timeline", "layouts"],
        "brief": "You own the frame: each beat's layout (split, face, broll, hook, full), crop windows and punch-ins. "
                 "Change a beat's layout or split a beat in two; keep segments contiguous and on the frame grid.",
    },
    "Cut Surgeon": {
        "model": SONNET, "effort": "medium", "iterations": 14, "owns": ["cut", "timeline", "variants"],
        "brief": "You own the cut: drop false starts, repeated words and dead air; never cut inside a word; a lone piece "
                 "under 1 s is almost always a false start. Every cut sits in a gap between words.",
    },
    "Generator": {
        "model": SONNET, "effort": "medium", "iterations": 10, "owns": ["sources", "timeline"],
        "brief": "You own generated shots: hooks, hero shots and B-roll. Write the prompt, keep within the credit cap, "
                 "and check every clip for stray logos, silent mouth moves and identity drift before it is used.",
    },
}


def cost(model: str, usage) -> float:
    """Dollars for one response's usage (the SDK object or a dict). An unknown model is priced as Opus."""
    u = usage if isinstance(usage, dict) else usage.model_dump() if hasattr(usage, "model_dump") else vars(usage)
    n = lambda k: u.get(k) or 0
    pi, po, pr = PRICE.get(model, PRICE[OPUS])
    return (n("input_tokens") * pi + n("cache_creation_input_tokens") * pi * 1.25 + n("cache_read_input_tokens") * pr
            + n("output_tokens") * po) / 1e6
