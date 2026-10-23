"""Local, free stand-in for video-use's helpers/transcribe.py (ElevenLabs Scribe).

Writes the same Scribe-shaped JSON to <edit_dir>/transcripts/<stem>.json, so
pack_transcripts.py, timeline_view.py and render.py work unchanged.

Fillers are kept on purpose (literal mode + filler-seeded prompt, no VAD):
the editor needs to SEE "um"/"uh" to cut them.

Usage:
    python transcribe_local.py <video> [--edit-dir DIR] [--model small] [--language en]
"""
import argparse
import json
import sys
from pathlib import Path

from faster_whisper import WhisperModel

FILLER_PROMPT = "Umm, uh, so, like, you know, I mean, hmm. Okay, uh, so basically, um."
# Roman-script Hinglish prompt: nudges Whisper to write Hindi words in Latin script
# (captions stay readable) and keeps Hinglish fillers visible for cutting.
HINGLISH_PROMPT = ("Umm, toh basically, matlab, haan, achha, uh, dekho, you know, "
                   "toh main aapko bataata hoon, so yeh AI tool hai, na, theek hai.")


def transcribe(video: Path, edit_dir: Path, model: str, language: str | None,
               prompt: str = FILLER_PROMPT) -> Path:
    out = edit_dir / "transcripts" / f"{video.stem}.json"
    if out.exists():
        print(f"cached: {out.name}")
        return out
    out.parent.mkdir(parents=True, exist_ok=True)

    m = WhisperModel(model, device="cpu", compute_type="int8")
    segments, info = m.transcribe(
        str(video), language=language, word_timestamps=True, vad_filter=False,
        condition_on_previous_text=False, initial_prompt=prompt, beam_size=5,
    )
    words, prev_end = [], 0.0
    for seg in segments:
        for w in seg.words or []:
            if w.start > prev_end:
                words.append({"text": " ", "start": prev_end, "end": w.start,
                              "type": "spacing", "speaker_id": "speaker_0"})
            words.append({"text": w.word.strip(), "start": w.start, "end": w.end,
                          "type": "word", "speaker_id": "speaker_0", "logprob": w.probability})
            prev_end = w.end

    payload = {"language_code": info.language, "text": " ".join(
        w["text"] for w in words if w["type"] == "word"), "words": words}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"saved: {out} ({sum(w['type'] == 'word' for w in words)} words, lang={info.language})")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--edit-dir", type=Path)
    ap.add_argument("--model", default="small", help="tiny/base/small/medium/large-v3")
    ap.add_argument("--language", default=None)
    ap.add_argument("--hinglish", action="store_true",
                    help="Hindi+English speech, Roman-script output (sets language=en + Hinglish prompt)")
    ap.add_argument("--names", default="", help="Comma-separated names/brands to spell right")
    a = ap.parse_args()
    v = a.video.resolve()
    if not v.exists():
        sys.exit(f"video not found: {v}")
    prompt = HINGLISH_PROMPT if a.hinglish else FILLER_PROMPT
    if a.names:
        prompt += " " + ", ".join(n.strip() for n in a.names.split(",")) + "."
    lang = "en" if a.hinglish else a.language
    transcribe(v, (a.edit_dir or v.parent / "edit").resolve(), a.model, lang, prompt)
