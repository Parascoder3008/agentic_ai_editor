# Genjutsu reel — verification v3 (2026-10-20)

Deliverables (edit only, NOT posted):
- `GENJUTSU_REEL_instagram.mp4` — 49.16 s, 1080x1920, 25 fps, -14.0 LUFS. CTA: comment FLEX -> DM + follow.
- `GENJUTSU_REEL_youtube.mp4` — 51.56 s, same spec, -13.9 LUFS. CTA: WhatsApp channel (YouTube About section) + subscribe.

## What v3 fixed (Paras: "repetition in the maine na poori guide part, cuts not refined")
The talking-head take has mid-sentence restarts with no pause. Whisper deletes them, so v1/v2 checks passed while the
audio still repeated. Found with 5 ms energy + CTC letter scan + Whisper on short windows, then cut by hand:
- "maine na poori ek, maine na poori ek guide" -> one "maine na poori ek guide" (the reported repeat)
- "jo bhi usmein cha-, jo bhi usmein changes" -> one
- "use karte aur, aur is type ke" -> one "aur"
- "banate ho-u(ske)" bleed, "lagte hain-o(bviously)" bleed -> cut in the dip between words
- "uske, uske andar" and "baaki, baaki aise" (YT) -> one each
- CTA: "agar flex karna ho, to agar aapko poori guide chahiye, ... poori guide bhej doonga" -> "agar flex karna ho to,
  comment kar do FLEX, aapke DM mein poori guide bhej doonga" (IG); YT drops "agar poori guide chahiye to" the same way
- dead air cut: 1.0 s after "easy hai", 0.7 s after "chatgpt ko", 0.5 s after "youtube ke"; joints now ~0.05-0.15 s
- captions said "Aur ye karna" -> "Aur bhai ye karna" (re-aligned); every cut now starts a fresh caption phrase
- audio joints: room-tone handles (energy-limited) crossfade across each cut instead of fading to silence
- full-frame CTA alternates punch-in (1.04/1.14) so the take change reads as a zoom, not a jump

## Checks on the FINAL files
- Verbatim CTC per piece (`qa/verbatim.txt`) + Whisper per piece and per joint (`qa/final_qa.json`): no repeats, no clipped words.
- Every edge checked against source energy; continuous-speech junctions cut at the measured dip.
- Sync: each piece cross-correlated with the voice master: max 5 ms (one frame = 40 ms).
- Room tone at joints: no gating below the source's own room-tone level.
- Frame pairs at every cut (`qa/*_joints.jpg`) and contact sheets (`qa/*_sheet.jpg`): graphics land on their spoken words,
  captions never cross a cut, face/CTA clear of IG UI zones. HyperFrames lint: 0 errors.

## Notes
- Three junctions are continuous speech with no gap at all ("chatgpt ko|jo", "banate|uske", "hain|obviously"). The cut sits in
  the best measured dip; the word end is a touch quicker than natural. Only a re-take would make it softer.
- Step 3 prompt text on screen is illustrative, not the client's real prompt (swap in `edit/gfx_index_v1.html`, then `python retime.py`).
- The REAL/FAKE -> AI VIDEO/ORIGINAL flip at 14.9 s is an addition beyond the brief.
- Re-cut pipeline: edl.py -> words.py -> retime.py -> captions.py -> sfx.py -> score_music.py -> hyperframes render -> compose.py
  -> qa_joints.py + qa_final.py.
