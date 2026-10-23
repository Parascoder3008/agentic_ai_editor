# Reel 05: topic research (2026-10-22)

## Sources
- **Instagram:** Apify reel scraper, 293 reels (last 12 each) from the same 25 reference creators as reel-03. Outlier = plays ÷ that creator's median, for reels posted since 5 Oct. Raw: `ig_competitors.json`, ranked: `outliers.json`.
- **Own account:** @ai_with_paras, last 30 reels (`ig_own.json`).
- **YouTube Shorts:** 98 results across 5 Hindi queries, last month (`yt_shorts.json`).

## Own account
- **All-time winners are still free / money-saving reels built on one named tool:**
  - Claude limit hack: 106K
  - ₹12,000 government AI course: 66K
  - Free NVIDIA coding model: 57K
- **Since September:** 130–2,100 plays.
- **Best recent reels:**
  - "Claude Opus 5.5 is my video editor": 2.1K plays, 120 comments
  - Free local leads: 1.7K
  - Free GitHub repos: 1.7K
- **Reel-03 (4 levels):** 574 plays in 2 days.

## What's breaking out (reference creators, since 5 Oct)
| Signal | Evidence |
|---|---|
| Anthropic engineer's 4-part prompt | gennaroautomates 756× (81K) |
| Free AI tiers stacked into one endpoint (FreeLLMAPI) | sebastianhardy_ 14× (54K) |
| Claude gets its own WhatsApp number (Kapso) | tessa.fairbrook 5.7×. vibha's WhatsApp agent was 8.3× in reel-03 research, so this is the second round it has shown up |
| Animation libraries for Claude websites | kayvon.ai 20× (109K) |
| Claude Dashboards (beta) | sebastianhardy_ 2.6× |
| Hindi YouTube | "Claude Code ka limit jaldi khatam hota hai? 4 plugins" 15K; "Free Claude Code on free models" 5K |

## Pick: "Claude ka apna WhatsApp number" (Kapso), business-owner edition
- **Why:**
  - It's a free tool with a name, which is the pattern behind his winners.
  - Indian SMBs run on WhatsApp.
  - The SETUP lead CTA follows naturally ("we'll set this up for your business").
  - It has now shown up in two research rounds.
  - It needs no screen recording: the WhatsApp chat and the 3 setup steps can be shown as motion graphics.
- **Runner-up:** FreeLLMAPI, which pools free AI tiers. It sits closest to the 106K limit-hack winner, but it's a developer tool (a self-hosted proxy), the free models are weaker, and the token totals are only third-party estimates.
- **Third:** the 4-part prompt. The source credit ("Claude's eng lead") is not verified yet.

## Facts checked (2026-10-22)
- **Kapso Free plan:** $0/month. 2,000 WhatsApp messages a month, and every message sent or received counts. One connected number, unlimited AI agents and workflows, sandbox access, $2 of credits. Meta's WhatsApp fees are separate. (kapso.com/pricing)
- **Skills:** `npx skills add gokapso/agent-skills` installs four skills: integrate-whatsapp, automate-whatsapp, observe-whatsapp and integrate-whatsapp-calling. They need `KAPSO_API_KEY` from app.kapso.ai. (github.com/gokapso/agent-skills)
- **For the guide:** the usual WhatsApp rules apply. Customers must opt in first, and after 24 hours without a reply you can only message them with an approved template. Meta charges are separate from Kapso's plan.
