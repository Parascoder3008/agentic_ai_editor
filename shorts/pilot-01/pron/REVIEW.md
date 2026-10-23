# Pronunciation gate: pilot-01 (preview_v1.wav, 48.0 s)

Your HeyGen voice "Paras Arora -- 14", audio only, from `script_tts.txt` (Devanagari for Hindi, Latin for English,
pinned words). **The avatar render waits for your OK on this audio.**

## Fixed vs the old avatar
| Word | Old avatar | Preview | How we know |
|---|---|---|---|
| Maine (मैंने), lines 2 + 12 | "main" ✗ | "mainne" ✓ | Whisper + phonetic aligner |
| zyada | "jaayda" ✗ | "ज़्यादा" ✓ | Whisper |
| ghanton / minuton | "ghantaun / minuton" ✗ | "घंटों / मिनटों" ✓ | Whisper |
| bina | "bheena" ✗ | "बिना" ✓ | Whisper |
| bhej dunga | "bhe dunga" ✗ | "भेज दूँगा" ✓ | Whisper |
| di gayi | "digaye" ✗ | "दी गई" ✓ | Whisper |
| Claude | "klod" | "klod" ✓ | phonetic aligner (Whisper always writes "Cloud", so ignore Whisper here) |

## Please listen to these 3 moments
| Time | Line | What to check |
|---|---|---|
| **0:01** and **0:43** | 1 + 13 | **Meta**: does it sound like "मेटा" or still "metta"? |
| **0:04** | 2 | "plugin **ko** test kiya": the aligner heard "po" |
| **0:27** | 10 | **Higgsfield**: it sounds like "Hicks-field" |

If any of these is wrong, tell me how you'd say it (e.g. "Meta like may-ta"). I'll respell it, re-run the
gate (audio only, a few seconds), and render the avatar only after it passes.

## After you approve
1. **One** HeyGen avatar render of all 15 lines (~41 credits), using exactly this text.
2. **Instagram cut:** lines 1–14, "follow + comment META, link in DM".
3. **YouTube cut:** lines 1–12 + 15, "channel ke description se WhatsApp channel join karo". The jump between lines 12
   and 15 is hidden under a graphic change.
4. Captions stay in Roman Hinglish (from `script.txt`), the edit is re-timed to the new audio, then both get the full QA.
