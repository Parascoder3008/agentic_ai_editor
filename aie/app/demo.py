"""A demo project that runs end to end with no keys and no footage: generated stand-in footage (a hook, B-roll and a
'presenter' with a voice of speech-like bursts), Hinglish captions aligned to those bursts, four real catalog effects,
SFX cues and both gates closed, so the whole flow (storyboard, approval, render, QA, notes, versions) can be checked.
"""
import json
import math
import subprocess
from pathlib import Path

from ..job import save_job

WORDS = ("Ye demo reel hai jo AI ne edit kiya hai bina kisi footage ke Claude agent customer ko jawab deta hai "
         "aur booking ho jaati hai comment karo AGENT aur guide aapke DM mein").split()
SPLIT = {"card": [97, 975, 886, 924], "crop": [840, 876, 540, 50], "radius": 28, "border": "#3AB0D88C"}


def _gate(t: float) -> bool:
    """When the stand-in voice is 'speaking' (the same expression the audio is made from)."""
    return math.sin(2 * math.pi * 1.7 * t + 1.3 * math.sin(2 * math.pi * 0.4 * t)) > 0.2


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)


def _words(voice_offset: float, length: float) -> list:
    """A word every ~0.3 s inside each voiced stretch, on the avatar's own clock (captions subtract voice_offset)."""
    spans, on, t0 = [], False, 0.0
    for i in range(int((length + voice_offset) * 100) + 1):
        t = i / 100
        g = _gate(t) and t >= voice_offset + 0.05
        if g and not on:
            on, t0 = True, t
        elif not g and on:
            on = False
            spans.append((t0, t))
    out, k = [], 0
    for a, b in spans:
        n = max(1, int((b - a) / 0.3))
        for j in range(n):
            s = a + j * (b - a) / n
            out.append({"text": WORDS[k % len(WORDS)], "start": round(s, 3), "end": round(s + (b - a) / n - 0.03, 3)})
            k += 1
    return out


def create_demo(repo: Path, name: str = "demo-reel") -> str:
    d = repo / "jobs" / name
    n = 2
    while d.exists():
        d = repo / "jobs" / f"{name}-{n}"
        n += 1
    (d / "raw").mkdir(parents=True)
    (d / "edit").mkdir()
    off = 0.2
    _ff("-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=25:d=2.5", "-vf", "hue=s=0.35,eq=brightness=-0.15",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", d / "raw/hook.mp4")
    _ff("-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=25:d=2", "-vf", "hue=H=2:s=0.4",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", d / "raw/broll.mp4")
    _ff("-f", "lavfi", "-i", "color=c=0x2A3540:s=1920x1080:r=25:d=10", "-f", "lavfi", "-i",
        "aevalsrc='0.3*sin(2*PI*180*t)*(0.6+0.4*sin(2*PI*3*t))*gt(sin(2*PI*1.7*t+1.3*sin(2*PI*0.4*t)),0.2)':s=48000:d=10",
        "-vf", "drawbox=x=840:y=170:w=240:h=300:c=0xC9A27E:t=fill,drawbox=x=780:y=470:w=360:h=430:c=0x1A9FD1:t=fill",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", d / "raw/presenter.mp4")
    words = _words(off, 12.0)
    cta = next(w for w in words if w["start"] - off >= 6.1)      # the CTA lands on a spoken "AGENT"
    cta["text"] = "AGENT"
    at = round(cta["start"] - off, 2)
    length = round(round((at + 3.25) / 0.04) * 0.04, 2)           # on the 25 fps grid, room for the 3 s CTA
    (d / "edit/words.json").write_text(json.dumps(words), encoding="utf-8")
    save_job(d, {
        "id": d.name, "title": "Demo reel (placeholder mode)", "mode": "avatar", "fps": 25, "size": [1080, 1920],
        "language": "hi",
        "sources": {"presenter": {"path": "raw/presenter.mp4", "voice_offset": off, "rights": "generated",
                                  "note": "stand-in for a HeyGen render"},
                    "hook": {"path": "raw/hook.mp4", "rights": "generated"}, "broll": {"path": "raw/broll.mp4", "rights": "generated"}},
        "timeline": [{"t": [0.0, 2.0], "layout": "hook", "src": "hook", "in": 0.0},
                     {"t": [2.0, 5.0], "layout": "split", "src": "presenter", "in": 2.0 + off},
                     {"t": [5.0, 6.0], "layout": "broll", "src": "broll", "in": 0.2, "note": "B-roll stand-in"},
                     {"t": [6.0, length], "layout": "split", "src": "presenter", "in": 6.0 + off}],
        "layouts": {"split": SPLIT, "face": {"crop": [608, 1080, 656, 0]}},
        "variants": {"instagram": {"ranges": [[0.0, length]], "freeze": 0.6},
                     "youtube": {"ranges": [[0.0, 6.0]], "freeze": 0.4}},
        "captions": {"words": {"from": "aligned", "source": "presenter", "file": "edit/words.json"},
                     "styles": {"Cap": {"size": 70, "outline_color": "#0C0E0F", "back_color": "#0000009B", "outline": 6,
                                        "shadow": 2, "margins": [150, 150], "baseline": 1000},
                                "Low": {"size": 66, "outline_color": "#000000", "back_color": "#0F0E0C73", "border": "box",
                                        "outline": 14, "margins": [150, 150], "baseline": 1440}},
                     "highlight": {"color": "#3AB0D8"}, "zones": [{"style": "Low", "layouts": ["hook", "broll"]}],
                     "hide": [[0.0, 2.0]]},
        "effects": [
            {"effect": "reel-hook", "at": 0.0, "dur": 2.0, "params": {"LINE1": "AI ne edit kiya", "LINE2": "POORA REEL"}},
            {"effect": "reel-chat", "at": 2.0, "dur": 3.0, "params": {"CHIP": "&#x1F916; CLAUDE", "CHIP_SMALL": "· demo",
             "MESSAGES": [{"from": "in", "text": "Friday ko slot hai?", "time": "2:04"},
                          {"from": "out", "text": "Haan ji! Free slots 👇", "time": "2:04 ✓✓", "buttons": ["11 AM", "4 PM"], "pick": 1},
                          {"from": "out", "text": "✅ Booked: Friday, 4 PM", "time": "2:05 ✓✓"}]}},
            {"effect": "reel-label", "at": 5.05, "dur": 0.9, "params": {"TEXT": "DEMO · stand-in footage", "COLOR": "amber"}},
            {"effect": "reel-cta-comment", "at": at, "dur": round(length - at - 0.05, 2), "params": {"KEYWORD": "AGENT"},
             "word": "AGENT", "variants": ["instagram"]}],
        "sfx": {"seed": 1, "length": length + 0.6, "cues": [{"kind": "impact", "t": 0.0, "db": -31}, {"kind": "whoosh", "t": 1.85, "db": -36},
                                                    {"kind": "pop", "t": 2.3, "db": -38}, {"kind": "whoosh", "t": 4.85, "db": -36},
                                                    {"kind": "whoosh", "t": 5.85, "db": -36}]},
        "mix": {"voice": "presenter", "tail": 0.6},
        "package": {"prefix": "DEMO"},
        "qa": {"words": ["Claude"]},
        "gates": {"storyboard_approved": False, "final_approved": False},
        "notes": "Made by the app's demo button: everything is generated, nothing needs a key."})
    (d / "brief.json").write_text(json.dumps({"title": "Demo reel (placeholder mode)", "mode": "avatar",
                                              "platforms": ["instagram", "youtube"], "cta": "AGENT", "style": "ai-os-blue"},
                                             indent=1), encoding="utf-8")
    return d.relative_to(repo).as_posix()
