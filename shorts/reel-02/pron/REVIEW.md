# Reel 02: YouTube Agent Skill, pronunciation gate (preview_v2.wav, 51.2 s)

Voice "Paras Arora -- 14", audio only. **The avatar render waits for your OK on this audio.**

## Machine check: passed
- Whisper flagged only its known quirks: "Claude" always comes out as "cloud", "API key" is written as "की", "पढ़ के" as one word.
- The letter-level aligner hears both "Claude"s as **"klaud"**.
- Line 9 ("Claude Code") first came out as "plod". It was re-voiced on its own, spliced in at the sentence pause and level-matched; it now reads "klo-d".

## Please listen to these moments
| Time | Words | What to check |
|---|---|---|
| **0:01** | "tool **Claude** ko" | Claude should sound like "klod", not "cloud" |
| **0:09** | "YouTube **Agent Skill**" | the product name is clear |
| **0:26** | "aapke **niche** ke viral videos" | "niche" said as **"neesh"** (pinned). If you say "nitch", tell me |
| **0:29–0:34** | line 9 (the spliced line) | no jump in tone or volume at 0:29.7 or at 0:34.5 |
| **0:35** | "koi **API key** nahi" | A-P-I key |
| **0:45** | "comment karo **SKILL**" | keyword is clear |

## Fact check (every spoken claim)
| Claim | Source | ✓ |
|---|---|---|
| Free | MIT licence, "no signup, no API key" (README) | ✓ |
| 1,000+ stars | GitHub API: 1,037 stars, 312 forks (2026-10-11) | ✓ |
| 11 skills | `skills/` has 11 `yt-*` folders | ✓ |
| 21 hook formulas | `skills/yt-script/hooks.json` has 21 entries | ✓ |
| Title + thumbnail checked together | `/yt-package` | ✓ |
| Retention: the exact second viewers leave | `/yt-retention` reads the Studio retention export | ✓ |
| Finds viral videos in your niche and names the formula | `/yt-viral` ranks by multiple over each channel's median and names the formula | ✓ |
| Install: paste the link in Claude Code, say install | README "Install" section | ✓ |
| Doesn't post by itself | README: "Nothing gets published until you do it" | ✓ |
