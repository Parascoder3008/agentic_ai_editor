# reel-04 (CLIENT: Shivam Arora, @venomstech) — verification v2 (2026-10-21)

Deliverables (edit only, NOT posted): `REEL04_instagram.mp4` 57.40 s and `REEL04_youtube.mp4` 50.97 s, 1080x1920 @30,
-13.9 LUFS, true peak -1.8 / -1.6 dBFS. Package in `publish/` (client links left as placeholders).

## v2 = client version
- Every agency asset removed (no reel-03, no Accelerator hub, no AI-OS links). All footage is the client's: his two DJI takes
  + clips from his own @venomstech reels (Apify scrape): RTX 5090 PC reel in the "meri poori reel" card (his ₹12-lakh product
  cards land on "graphics"); DDR5 + cooler-mount renders as the product B-roll.
- Style = Paras's reference (Video-84626, "Clauditing"): one-word kinetic captions with blur-in and ghosted previous word,
  pink Instrument-Serif accents, heavy-white + serif headlines, selection-handle stickers (CLAUDE, EDIT), "TO CLAUDE" prompt
  card, navy/plum/cream palette, film strip, before/after wipe, comment bar, "✓ Following" pill.
- Plus the client's own best reel (Video-58079): pitch-drop hit (tone ~920→380 Hz, measured on his reel) + crash zoom on
  4 punchlines, yellow black-outlined numbers (0 EDITORS, edit counter #1-#8, ₹? vs ₹?), product B-roll in stacked rounded
  panels with a bold italic label.

## Every edit he asks for happens on screen, on the word
corner card (7.95) · his reel + graphics (10.45/12.17) · text behind him → serif cinematic (15.31/17.30) · watch spotlight +
graphics out/back (22.33/25.04/27.02) · wipe → paper cut (29.40) · sticker + product B-roll (31.19/32.07) · back + bye (35.80/36.86)

## Checks on the final files
- Whisper per piece + per joint and at all 4 pitch-drop hits: no repeated, clipped or masked words.
- Sync max 5 ms. Cuts unchanged from v1 (measured edges, restarts removed).
- Kit validate-plan: ok, 0 errors (18 scenes on spoken anchors, 244 words, 92 events; hook gap has holdReason).
  validate-footage: ok, 2 B-roll scenes, client assets hashed, each once.
- Contact sheets IG + YT at every beat with IG UI zones; snapshot QA of the overlay over the footage. Fixed in audit:
  faint serif accents (lighter gradient + dark shadow, +30 % size), wipe labels over a caption, Following pill on the chin.

## Choices to confirm
- Product label on the B-roll panels reads "Gaming PC Build ⚡".
- His reels come from Instagram at 720p; the B-roll panels upscale them ~1.2x.
