# Reel 03: verification (2026-10-19)

**Outputs:**
- `REEL03_instagram.mp4`: 55.48 s, 1080x1920, 25 fps, ends on "comment LEVEL"
- `REEL03_youtube.mp4`: 54.94 s, ends on the WhatsApp channel line
- Earlier version kept in `v1/`

| Check | Result | How |
|---|---|---|
| Topic backed by data | ✅ | 344 competitor reels (23 accounts) + 100 YT Shorts + 26 own reels (`research/RESEARCH.md`). YT outlier "4 levels of Claude" = 12x the channel's subscribers |
| Facts | ✅ | Projects / Google connectors / scheduled tasks checked against Anthropic help-centre articles (links in the guide footer) |
| Compliance §4 | ✅ | Education only, no income/result claims, paid-plan limit disclosed in the video (Level 4 "PAID PLAN" tag), caption and guide |
| Pronunciation gate | ✅ | 3× "Claude" letter-checked = "klod" (same as approved pilot); "chaar levels" for 4 |
| Storyboard first | ✅ | `storyboard.html` (17 beats, true-position mocks, IG UI hatched), hook + direction approved |
| Hook (first 3 s) | ✅ | Flow shots of Paras's own avatar; text on frame 1; no brand logos (Apple logo avoided); mouth-move frames avoided |
| Cuts on spoken anchors | ✅ | Kit `validate-plan`: ok, 0 errors, 11 scenes, 158 words caption-synced, 83 visual events, max gap 2.4 s (face beat, holdReason) |
| Footage ledger | ✅ | Kit `validate-footage`: ok, 3 B-roll scenes hashed, each used once |
| Open loop | ✅ | "YOU?" planted 7.42 s → climbs to step 4 at 45.13 s with "ASSISTANT" (`kit/OPEN-LOOPS.json`) |
| IG safe zones | ✅ | Contact sheet with zones drawn: face/text clear of top 200, right rail (x>930, y1000-1700) and bottom (y>1560); presenter card keeps chin ≈ y1549 |
| Captions | ✅ | ≤ 3 words, current word in brand blue; seam style (split) / boxed low style (full frame); hidden under payoff text |
| A/V sync | ✅ | Final audio vs avatar voice: 4 ms at 10/30/50 s and after the YT join |
| Masking | ✅ | Final mix transcribed per line: every word present; "FAQs" and "owners" checked against the clean voice; SFX ≤ −33 dB under voice there |
| Loudness | ✅ | IG −13.9 LUFS, YT −14.0 LUFS, sample peak −5 dBFS |
| Music | ✅ | Original score (`tools/score_music.py`), royalty-free by construction, ducked −16 LU under speech |
| Guide page | ✅ | `resources-site/claude-levels/`: Playwright 390 px, no horizontal overflow; copy buttons; discovery-call + brand-collab CTAs |
| Cover | ✅ | `publish/cover.jpg` readable full-frame and in the 4:5 grid crop |

## Limits (honest)
- The voice is Paras's cloned HeyGen voice and the face is an Avatar V render, not a filmed take.
- Views are not guaranteed. The topic and structure follow measured outliers; real retention will recalibrate the next one.
- YouTube upload goes through the GHL Social Planner (Composio's YT quota failed before). This is the first run on this reel.
