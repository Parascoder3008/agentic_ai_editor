# AI Editor — Paras's video editing project

Claude acts as Paras's video editor here. Paras drops a raw recording into `inbox/<project-name>/`;
Claude removes filler words / dead air / retakes, adds on-brand motion graphics and captions,
and renders a preview for review.

## Stack (installed 2026-10-02)

| Tool | Where | Role |
|---|---|---|
| **video-use** skill | `C:\Users\PARAS ARORA\Developer\video-use` (junction at `~/.claude/skills/video-use`) | Main workflow: transcribe → plan cuts → EDL → render. Follow its SKILL.md (hard rules, ask → confirm → execute). |
| **HyperFrames** | `npx --yes hyperframes …` + `/hyperframes*` skills | Motion graphics overlays (HTML/GSAP → transparent webm). |
| `tools/transcribe_local.py` | this folder | Free local transcription (faster-whisper) producing Scribe-shaped JSON. Used because no ElevenLabs key is set. |
| ffmpeg 8.1, Node 24, uv, faster-whisper, Chrome | system | Render deps |
| **Herk Edit Kit** (MIT, installed 2026-10-19) | `C:\Users\PARAS ARORA\Developer\herk-edit-kit` (9 skills junctioned into `~/.claude/skills`) | Story/motion layer: `short-form-edit` (reels/Shorts/ads), `edit-video` (long-form), `cut-silences`, `cut-mistakes`, `video-storytelling`, `hyperframes-video-beats`, `style-library` (406 cards), `make-a-video`, `motion-showreel`. |

## Herk Edit Kit — how it plugs in

- Kit-relative paths in its skills (`docs/EDITING-PLAYBOOK.md`, `MOTION_PHILOSOPHY.md`, `video-projects/<slug>/`,
  `node .claude/skills/...`) resolve at the **kit root**. Run its scripts from there; its projects live in its `video-projects/`.
- **Transcription stays ours** (free, Hinglish-tuned): `transcribe_local.py` / `force_align.py` output
  `{words:[{text,start,end}]}` already feeds the kit's cut tools as-is (tested on the 3,099-word long-form transcript).
  No ElevenLabs/Kie keys needed; `.env` in the kit is empty on purpose.
- **Brand overrides the kit's defaults:** Inter only, blue palette (§ Brand below). The AIS logo/tokens in the kit are
  Nate's brand and NOT licensed for us; never use them. Card handles/stats are placeholders; replace with verified copy.
- Use its gates on every reel: three rough openings judged on the first 3 s, `OPEN-LOOPS.json`, footage ledger
  (each B-roll scene once), real logos only (never redrawn), `validate-plan.mjs` + `validate-footage.mjs`, `VERIFY.md`.
- Keep our audio rules (original score via `score_music.py`, SFX ≤ +3 dB over voice and ducked, A/V rendered separately
  then muxed) over the kit's defaults; they are what passed QA on the Equal ad.

## Workflow per video

Session outputs go to `inbox/<project>/edit/` (video-use rule 12 — never inside the video-use repo).

```powershell
$VU = "C:\Users\PARAS ARORA\Developer\video-use"
# 1. Transcribe (cached). Use --model medium for better filler detection on long/Hinglish takes.
python "C:\Users\PARAS ARORA\AI_Editor\tools\transcribe_local.py" "<raw.mp4>" --model small
# 2. Pack to phrase view → edit/takes_packed.md
uv run --project $VU python "$VU\helpers\pack_transcripts.py" --edit-dir "<inbox/project>/edit"
# 3. Plan cuts from takes_packed.md + transcripts/*.json word times; write edit/edl.json
#    (write JSON with the Write tool — PowerShell 5 Set-Content adds a BOM that breaks json.loads)
# 4. Motion graphics: one slot per overlay in edit/animations/slot_<id>/
#    npx --yes hyperframes init . --example blank --non-interactive --skip-skills
#    start from templates/keyword-callout.html, then: npx --yes hyperframes lint
#    npx --yes hyperframes render . --format webm -o render.webm   (transparent)
# 5. Render preview with brand subtitles
$env:VIDEO_USE_FONTS_DIR = "C:\Users\PARAS ARORA\AI_Editor\fonts"
$env:VIDEO_USE_SUB_STYLE = "FontName=Inter,FontSize=16,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H000F0E0C,BackColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=60"
uv run --project $VU python "$VU\helpers\render.py" "<edit>\edl.json" -o "<edit>\preview.mp4" --preview --build-subtitles
```

Filler removal = keep EDL ranges that skip `um/uh/umm/hmm`, false starts and silences ≥ 0.4s;
snap every edge to word boundaries with 30–200ms padding (video-use hard rules 6–7).
Overlay `start_in_output` = payoff word's output time minus the reveal time, so the
graphic lands on the spoken word. Output time = sum of prior range lengths + (word.start − range.start).

Screen recordings: speaker-zoom/face beats don't apply; callouts, keyword cards, captions do.

## Reels playbook (Vibha's "Let Claude Edit Your Reels" guide, adapted)

Paras films on these lines: one landscape 16:9 tripod take, spoken requests ("zoom in on my hand"),
pause after each, holds still where an effect lands, keeps flubs. Language is **Hinglish**.

1. **Eyes + ears.** `transcribe_local.py <take> --hinglish --model medium --names "Paras,Claude,Exponential World,..."`
   then pull 1 frame/sec (`ffmpeg -i take.mp4 -vf fps=1 edit/frames/%04d.jpg`) and look. Fix misheard
   names in the transcript JSON before planning (Whisper writes "Claude" as "clod").
   Hinglish captions stay Roman-script; correct transliteration by hand where Whisper drifts.
   Hindi fillers to cut too: toh, matlab, haan, achha, na, basically (only when used as filler).
2. **Storyboard first ("Clauditing", Vibha 2026-10-18).** In ONE message offer 3 edit directions + 3 hook-text
   options. After the pick, write `edit/storyboard.html` (opens by double-click): one NUMBERED row per beat with
   time, exact words, layout (split / full-screen demo + face circle / face only), on-screen file, a still frame with
   every planned caption/graphic box drawn at its real 1080×1920 position, SFX, and one line on why. Paras replies
   by beat number ("Beat 4: full screen"); update and re-show; render only on "approved". Nothing renders before that.
   Reels default: 9:16, top half = edited, bottom half = ORIGINAL take (`vstack` of two scaled
   16:9 strips). For tool/website talk: top = screen recording, bottom = face; full-screen demos keep the face in a
   circle bubble (`reel_compose.py` "bubble"). Name screen files in speaking order (`01-website.mp4`, `02-github.png`).
   **IG safe zone (measured on the Equal ad):** keep text/logos inside x 90–930, y 200–1560; the right rail
   (x > 930, y 1000–1700) and the bottom (y > 1560) are covered by IG UI. Never over the face, mic or phone in hand.
   **Retention rules (Dhananjay prompt):** hook text on screen within 1 s; no static shot held > ~3 s (punch-in
   10–20 %, layout change or B-roll); captions ≤ 3 words with ONE keyword highlighted; end on the CTA or loop to the start.
   **Deliverables per reel:** final MP4, `.srt`, cover frame, post caption + hashtags (first comment on IG).
3. **Cuts:** pauses > 0.25s + flubbed/repeated lines, never inside a word; report new length.
4. **Grade** only the edited half (`helpers/grade.py`), original untouched.
5. **Cut-outs** (text behind subject, documentary B&W, orbit-behind):
   `npx --yes hyperframes remove-background <clip> -o cut.webm --device cpu` on the effect window only
   (~0.36 s/frame on this CPU = ~11 s per second of 30fps footage).
6. **Graphics:** render on a TRANSPARENT background, then layer room footage underneath with
   ffmpeg (render.py overlays). HyperFrames flattens transparency when normal video is in the same comp.
   Fake 3D in 2D, dim instead of blur — CSS 3D / blur / blend modes / animated crops break alpha.
7. **Captions:** word-by-word, pop in on the word, hidden while big text is on screen.
   Brand override: guide mixes italic serif + bold sans — we use **Inter only** (bold + italic), never serif.
8. **Notes loop:** Paras gives one change per line with a timestamp; apply, re-render preview.
9. **Render safety:** one render at a time, `--workers 1`, preview closed, ≥15 GB free disk.
   iPhone footage is HDR — render SDR (`-vf zscale=t=linear,tonemap=hable,zscale=t=bt709,format=yuv420p` or ask HyperFrames for SDR).
   Post with Instagram "Upload at highest quality" on.

Reel covers + view counts for an "orbit" effect: Apify Instagram scraper (Apify MCP connected).

## Lessons from reel #1 (2026-10-02, Desktop\edit — the reference build)

Reusable tools now in `tools/`: `sync_offset.py` (external WAV ↔ camera), `force_align.py` (MMS_FA),
`reel_compose.py` (9:16 split compose: cut → overlays/cut-outs/bubble/labels/captions → ducked mix → -14 LUFS),
`captions_ass.py`. Per-job scripts (build_edl.py, make_reel_cfg.py, render_all.ps1) live in the job's `edit\` folder — copy them.

- **Hinglish transcription that works:** Whisper long-form in `hi` loops/hallucinates; `en` translates. Do:
  English pass for phrase timing → `large-v3-turbo` `hi` per-phrase chunks (beam 5) for content →
  I write Roman Hinglish per line → `force_align.py` for word times → cross-check vs loudness (stretched or
  silent words = misaligned window; tighten the window to exclude neighbour speech).
- Snap every segment length to whole frames (0.04 s @25) or effect/caption cues drift ~0.4 s by the end.
- Snap cut edges to the quietest 10 ms near the word boundary; verify joins ≤ -30 dBFS within ±5 ms.
- ffmpeg: never `-ss`-seek an alpha webm (alpha drops); `hue`/colour filters on a cut-out need `format=rgba` first.
- PowerShell 5 `ConvertTo-Json` flattens nested arrays and `Set-Content -Encoding utf8` adds a BOM → write JSON from Python.
- Mix check = effects' added level per section (mix vs voice-only stem); keep ≤ +3 dB at impacts.
- Self-review: contact sheet at every effect moment over the real frames + re-transcribe the output in short chunks.

## Lessons from reel #3 (2026-10-19, shorts\reel-03 — Flow hook + avatar + staircase gfx; first kit-validated reel)

- **Portrait HeyGen looks don't fit a bottom-half crop.** The face (~650 px tall at 1080 wide) puts the chin under
  the IG caption zone. Use the **presenter card**: avatar at 82 % (886 wide) in a 28 px glass card at (97,975), crop
  y 214, so the hair sits at ~1015 and the chin at ~1549. `edit/compose.py` builds it with alphamerge + a border PNG.
  The crop height must be even for yuv420.
- **Cuts land on spoken anchors.** Kit `validate-plan` needs each scene start within −0.15/+0.2 s of a word onset,
  and visual events no more than 2.2 s apart (or a `holdReason`). Export with `edit/kit_export.py`, then run
  `validate-plan.mjs` + `validate-footage.mjs` on `kit/`. Both passed on reel-03.
- **Captions:** seam style for split beats (baseline 1000). Full-frame beats use a boxed low style (BorderStyle 3,
  baseline 1440), so white text stays readable on a white t-shirt. Hide captions under big payoff text.
- **One composition, full timeline:** the HyperFrames `#stage` is the top half, grows to 1920 for the payoff,
  then shrinks back. The camera moves through a persistent world (`#world`). Contact-sheet every beat over gray
  before composing; reel-03 caught 5 overlaps that way.
- **Mobile QA of guide pages:** use Playwright at 390 px (`resources-build/shots.py` pattern). Chrome
  `--headless --window-size=390` renders at a ~500 px minimum and fakes an overflow.

## Cut check — no repeated words at any cut (from the long-form, 2026-10-07)

Paras caught words repeating at camera changes. Causes, all fixed in `inbox\longform-ai-editor\edit\body_edl.py`:
- **Whisper deletes restarts** ("और… और यहाँ तक", "बट | But"), so a transcript-based cut list keeps both takes.
  Removing the pause between them then glues the false start to the restart, and the angle change on that
  joint makes it obvious.
- **Lone 1-word pieces (< 1 s) are almost always false starts** ("तो", "कि", "और", "अब अगर"). Drop them.
- **Cut edges inside running speech** must sit on the real word gap: an energy valley (`wordgap.py`) plus
  letter timing (`ctc_chars.py`, MMS_FA greedy). Never pad them. Padding at a normal edge must stop 30 ms
  short of the neighbouring word's onset. Both rules are in `body_edl.py` (`DROP` list, mid-speech rule, onset clamp).
- **Camera splits inside a take** land on phrase pauses, never between two identical words (`make_longform.py`).
- **Verify before rendering:**
  1. `piece_tx.py` transcribes every kept piece on its own (separate calls can't merge a repeat; cached by edges;
     no prompt, because a prompt full of repeats makes Whisper loop).
  2. `review_joints.py` prints last words || first words for every joint. Read all of them, not just the flags.

## 4K export (long-form, 2026-10-07)

1. `python make_longform.py final` sets `out_scale: 2` (layout stays in 1920 space and renders at 3840x2160),
   the native 4K camera (`px 2.0`) and the `gfx4k` overlays.
2. Render the graphics first: `python tools/gfx_batch.py gfx_spec.json gfx4k --res landscape-4k` (Chrome at
   2x DPR, so text stays crisp). Takes about 30 s to 2 min each.
3. Compose `segments`, then `mix`. The mix reuses `music_score.wav`, since the timeline is unchanged.

Timing: about 2.5 h for 13 min of video. Segments render at 6–16 s per second of video. Long alpha overlays (the
16 s rule panel) are the slow part, because an alpha webm is decoded from frame 0 and can't be seeked.

Running the graphics batch in parallel with the segments is fine: segments wait for each overlay's `.rendered` stamp.

Disk: about 10 GB peak. Delete the `seg_*.mkv` files after the join.

The screen recording and the intro are 1080p sources, so they get upscaled.

## Music — original scores only (from the long-form, 2026-10-07)

- **Never ship a track whose licence isn't verified** (the bundled `bg-feelgood-builder.mp3` is unverified —
  Content ID risk). Default: `tools/score_music.py` composes + synthesizes an original score to picture
  (no samples → royalty-free by construction). Paid alternatives (Runway Lyria, YouTube Audio Library) only with Paras's OK.
- The job planner writes `cfg["music"]["score"]`: blocks (one cue per section, downbeat on each card/cut,
  riser/roll into the next hit, tape-stop for punchlines), events (bells, filter dips, lifts) and duck levels
  vs. the voice (body -18 LU in speech, intro/outro -15). Cues: hook (house 118), story (lo-fi 88), build
  (tech-pop 110, a layer per step), reflect (80), numbers (104), outro.
- Order: compose `segments` → `python tools/score_music.py lf.json` (needs base.mkv for the voice
  automation) → compose `mix`. Re-score only if the timeline changes; preview and final share it.
- Verify: hit onsets vs. card times, music-in-speech LU per section, speech-band (1–4 kHz) voice/music
  ≥ 20 dB mean. Don't trust `showspectrumpic fscale=log` bands — confirm tones with a Welch spectrum.
- Master = static gain → 2:1 comp → limiter (`longform_compose.py`). loudnorm silently falls back to
  dynamic AGC when peaks block linear gain (pumps the music). Trim louder sources first (`voice_gain`:
  the reel intro audio ran ~6 dB hotter than the long-form voice).

## Brand (Constitution §3 — never violate)

Void `#0C0E0F` · Blue `#1A9FD1` primary · Blue-bright `#3AB0D8` · Navy `#11324C` ·
Text `#FFFFFF` / muted `#DFDDDF` · **Inter** (TTFs in `fonts/`, also installed per-user) ·
glass panels, 28px radius. Violet/purple and Fraunces are retired. CTA hub: skool.com/exponential-world-ai-2398.

## Gates

- Confirm the cut strategy in plain English before touching the cut (video-use rule 11).
- Preview only until Paras approves; final render (`render.py` without `--preview`) after.
- Never publish/upload anything. Spoken claims must pass the compliance rules (education only,
  no income/return claims) — flag, don't silently cut.

## Local patches to video-use (re-apply if the repo is updated)

`helpers/render.py`: subtitle path uses `as_posix()` (Windows ffmpeg filter fix);
`VIDEO_USE_SUB_STYLE` / `VIDEO_USE_FONTS_DIR` env overrides; `.webm` overlays decoded with
`libvpx-vp9` so alpha survives.

## Known limits

- Hinglish via local Whisper is untested on real footage (no Hindi TTS voice to fake a test). First real
  take = the test; if word timing or transliteration is poor, ElevenLabs Scribe handles code-switching better.
- No ElevenLabs key → local Whisper. To use Scribe (better fillers, diarization), Paras adds
  `ELEVENLABS_API_KEY=` to `C:\Users\PARAS ARORA\Developer\video-use\.env` directly, then use `helpers/transcribe.py`.
- `hyperframes doctor` reports low free RAM (~0.7 GB) — close apps before long renders.
- The older `video-edit` / `video-cut-aligned` skills (BuildLoop-branded, Mac-built) still exist; prefer video-use here.

## Pronunciation gate — BEFORE every HeyGen avatar render (Paras, 2026-10-10)

HeyGen reads Roman Hinglish by guessing ("Maine" -> "main", "Meta" -> "metta", "zyada" -> "jaayda"). Never send
the Roman script to HeyGen. Per job:
1. `script.txt` stays Roman Hinglish (captions come from it). Write `script_tts.txt`: Hindi words in Devanagari,
   English words in Latin, numbers spelled out in English, voice-mangled words pinned `{Shown|बोला}`
   (`{Claude|क्लॉड}`, `{Meta|मेटा}`, `{ad|ऐड}`).
2. `python tools/pron_check.py script_tts.txt --tts` -> the exact text for HeyGen. `create_speech` with the same voice
   (audio only), then `python tools/pron_check.py script_tts.txt preview.wav --out report.md`.
3. Whisper is biased ("Claude" always comes out "Cloud"): settle doubtful words with `tools/verbatim_ctc.py`
   (letter-level, no language model). CTC can't tell "meta" from "metta"; that is Paras's ear.
4. Paras listens to the flagged moments and approves; only then render the avatar with that exact text.

## Two exports per reel: Instagram + YouTube CTA
One avatar render with both CTAs; cut two versions: **Instagram** = "follow + comment KEYWORD, link in DM";
**YouTube** = "channel ke description mein di gayi link se WhatsApp channel join karo" (no comment-to-DM there).

## Avatar rotation (Paras, 2026-10-10)
Every new video uses a **random recent avatar**: `python tools/pick_avatar.py <job>` picks from
`shorts/avatar_rotation.json` (never the previous look) and logs it. Render with `audioUrl` = the
pronunciation-approved preview WAV (not the script), so the look's default voice never changes the audio.
Landscape looks drop into the 16:9 split crop as-is (set `crop_x` from `tools/face_track.py`); portrait looks
need a portrait crop. Any generated hook/skit must reference the SAME look (face frame + a speaking clip).
