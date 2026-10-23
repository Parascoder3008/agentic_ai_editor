# Reel 05: verification (2026-10-22)

**Topic:** "Claude ka apna WhatsApp number" (Kapso). Research and fact sources are in `research/RESEARCH.md`.

**Outputs** (edit only, NOT posted). Both are 1080x1920 at 25 fps.
| File | Length | Ends on |
|---|---|---|
| `REEL05_instagram.mp4` | 54.40 s | "comment AGENT", then a 0.6 s freeze |
| `REEL05_youtube.mp4` | 53.64 s | The WhatsApp channel line |

## Sources
- **Voice:** a new HeyGen instant model voice, `84c9815d`. It was cloned from a clean 2-minute clip of the lecture-1 lav-mic audio, with similarity set to max and no denoise. Paras approved the preview audio.
- **Avatar:** HeyGen digital twin "Paras Arora -- 15" (black tee), rendered with Avatar V. It was driven by the approved preview audio, so the words match it exactly.
- **Generated shots (Google Flow, Omni 1.1 Flash, 4 x 15 credits, 1080p upscales):**
  - Hook: Paras's "Me" avatar at night, phone lights up, he turns it to camera. Three cuts, mouth closed.
  - 2 AM customer texting, including a real "2:04" clock.
  - Salon owner: grin and thumbs-up.
  - Owner asleep while his phone pulses.
- **Style:** the reel-03 system.
  - Top-half HyperFrames stage plus a presenter card.
  - Kinetic seam captions.
  - Real logos only: Claude, WhatsApp, Kapso.
  - Synthesized SFX and an original score.

## Checks on the final files
| Check | Result |
|---|---|
| A/V sync | 4 ms on every kept range (IG and YT) |
| Loudness | -13.9 LUFS integrated; true peak -4.1 dBFS |
| Masked words | The force-aligned script on the final mix flagged 3 sentence-final words (score drop from the music tail): "hai" 12.58, "hai" 23.31, "pehle" 45.40. Whisper hears all 3 clearly on the final mix. |
| Kit validators | `validate-plan` ok (15 scenes on spoken anchors, frame-aligned, 90 events, max event gap 2.2 s); `validate-footage` ok (4 B-roll scenes, each once, hashed) |
| Safe zone | Every label measured in a headless browser at rest scale, inside x 90-930 (widest: "PATA HI NAHI" 152-928, "24 GHANTE" 151-929) |
| Cut edges | Frames on either side of all 7 cuts: overlay and picture change on the same frame |
| Hook | Text on frame 1; first word at 0.08 s (0.24 s of TTS lead-in trimmed) |

## Fixed during QA
- **Cut edges:** moved onto the 25 fps grid and onto spoken anchors (validator).
- **Hook dead air:** voice lead-in trimmed by 0.24 s; every layer shifted with it.
- **Overlay timing:** the HyperFrames renderer half-applied `tl.shiftChildren`. Fix: the overlay is rendered on the aligned clock and offset in compose.
- **Text too wide:** hook and 24 GHANTE labels were under the IG right rail; shrunk and re-measured.
- **Graphics fixes:**
  - "4 SKILLS" stamp no longer overlaps the skills list.
  - Salon BOOKED chip removed (it was over his face).
  - Chip moved up on the face beat.

- **IG freeze leak (Paras, 2026-10-22):** the start of the WhatsApp line leaked into the 0.6 s freeze. Fix: the IG mix mutes the voice after 53.80 s, so the tail is music only. Re-transcribed, the IG cut now ends on 'Guide seedha aapke DM mein.'

## Known minor
- At 42.44 s the stage sits empty for 0.77 s before "1 RULE" slams on the word "rule".
