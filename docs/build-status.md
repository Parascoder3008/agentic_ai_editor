# Build status: the whole Agentic Editing Tool

Branch: `agentic-editor`. Plan: the [Agentic Editing Tool artifact](https://claude.ai/artifact/Ct4Tz6T4pCBCEaXaid5JAR)
and `docs/phase-0-plan.md`. Paras asked (23 Oct) for the whole tool, frontend and backend working together, held to
9.5/10, and will check the full pipeline at the end.

How "done" is judged here: every module is proven against what the shipped jobs actually produced (byte-identical
captions, identical ffmpeg commands, identical audio stems) wherever that is possible without footage; graphics and the
UI are rendered and inspected in the cloud; anything that needs the PC, its apps, footage or API keys is listed under
"Unproven until the PC run" below.

## Phases

| Phase | What | Status |
|---|---|---|
| 0.1 | Package, job.json validator, effects catalog, machine settings | done |
| 0.2 | Cut builder, joint verification, stage runner | done (PC check pending) |
| 0.3 | Captions + SRT / cover packaging | done: reel-05 and reel-04 captions.ass, words_master.json and all four SRTs byte-identical; reel-05 cover pixel-identical |
| 0.4 | SFX, music, sound mix | done: reel-05 voice, SFX (99 traced cues) and music stems byte-identical to the shipped scripts on the same input; reel-04 piece-by-piece voice byte-identical, its SFX within 1e-3; variants delivered at the shipped lengths and -14 LUFS |
| 0.5 | Picture, mux, variants; reel effects into the catalog | done: reel-05 and reel-04 video commands identical to the shipped compose scripts (recorded), card mask/border pixel-identical; synthetic job rendered and checked frame by frame. 17 reel effects (9:16) ported from reel-05; all 22 catalog effects render in the cloud with HyperFrames, pass the preview checks and lint with 0 errors |
| 0.6 | QA, kit export, `run all`, render lock | done: `qa` stage runs the plan's 9.5 audit (length, loudness, sync, joints, words, spelling, safe zone, effects on words, rights, compliance, plus hook, still-picture, cut-anchor and footage-reuse advisories), contact sheets, score and gate; `storyboard` stage and its gate; `all`; render lock. The Herk kit's rules are QA checks rather than an export (see decisions) |
| 0.7 | Herk Edit Kit cards into the catalog, re-coloured | |
| 1 | Style library: pack format, built packs, Style Learner | |
| 2 | Agent team (Claude Agent SDK) + tool servers, budgets, gates | |
| 3 | Local web app: 7 screens, review player, notes to agents, **Connections screen** | |
| 4 | Avatar mode (HeyGen) + generated shots (Higgsfield, Flow) | |
| 5 | Resolve, Premiere, After Effects bridges (OTIO) | |

## Unproven until the PC run

Things the cloud session cannot exercise. Each says what to run and what "pass" looks like.

1. **Long-form cut from the WAV.** `python -m unittest discover -s tests` on the PC must show 0 skipped;
   `test_cutter_rebuilds_body_pieces_exactly` compares against `jobs/longform-ai-editor/edit/body_pieces.json`.
2. **Whisper verify.** `python -m aie run jobs\longform-ai-editor verify` (faster-whisper + model download).
3. **reel-05 re-delivered from job.json.** Copy `avatar.mp4`, `hook/`, `broll/` and `gfx/render.webm` into
   `shorts\reel-05` if they aren't there, then `python -m aie run shorts\reel-05 deliver`. Pass: `build\publish\
   REEL05_instagram.mp4` and `_youtube.mp4` at 54.40 s and 53.64 s, -14 LUFS, and frames at `qa\` timestamps that
   match the shipped files.
4. **reel-04 re-delivered.** `python -m aie run shorts\reel-04 deliver` (runs `edit\compose_base.py` as its custom step,
   about as long as it took before). Pass: same lengths as the shipped REEL04 files, frames match.
7. **QA words check.** `python -m aie run shorts\reel-05 qa` on the PC runs the Whisper "words" check the cloud can't
   (it shows NOT RUN here). Pass: OK, or a list of lost words matching what VERIFY.md found ("hai" 12.58, "hai" 23.31,
   "pehle" 45.40 were flagged there by forced alignment and heard clearly by Whisper).
8. **reel-04 rights.** reel-04 is a client job and its sources don't say who owns the footage yet, so QA fails the
   rights check until `"rights": "client"` (or whatever is true) is set on sources a and b. That is the check working.
6. **Reel effects on the PC.** `python tools\effect_preview.py` (no `--gsap` there; Chrome reaches the CDN). Pass:
   every line ends "ok" and the previews look like the committed ones (the cloud renders used the session's Chromium and
   system Inter, so a font difference would show here first).
5. **HyperFrames from the pipeline.** Drop `"render"` from reel-05's `graphics` for one run: the `graphics` stage
   re-renders `gfx\index.html` (about 5 min) and the result matches the shipped render.

## Requests from Paras during the build

- **(23 Oct) Placeholders for every connection.** The app has a Connections screen listing every external service
  (Claude API for the agents, HeyGen, Higgsfield, Google Flow, ElevenLabs, Apify, Google Drive, GHL, Composio, Resolve /
  Premiere / After Effects paths), each "not set / set / tested OK". Keys live only on the PC in `secrets.local.json`
  (git-ignored, and the safety hook denies reading it). Without keys the app still runs end to end in placeholder mode,
  so the whole flow can be checked before any key is added.

## Decisions taken without Paras (to confirm at the check)

- Database: the plan says Postgres; the app uses SQLite (built into Python, nothing to install or run on one PC).
  Same data model.
- One SFX library: reel-05's (the newest) is the canonical one. Older jobs' slightly different versions of the same
  sounds (reel-04's whoosh, its ticks) are expressed through settings, so reel-04's stem matches within 1e-3, not bit
  for bit.
- Mix defaults are reel-04's newer choices: gain set from the voice (about -17 LUFS into the limiter), 20 ms joint
  fades, 0.8 s tail. reel-05 keeps its own fixed +12 dB, 30 ms, 0.6 s in its job.json.
- A voice longer than the score (common with avatar renders) is cut to the score's length before the music ducks
  against it; the original scorer refused such a voice.
- Effects that only some variants show get their own master picture (`build/picture_<variant>.mp4`); the first variant's
  master is `build/picture.mp4`, which the cover is taken from.
- The Herk kit's validators needed a hand-written export per job (scene names, events copied out of the composition,
  open loops). Their rules now run inside QA on the job itself: cuts on spoken anchors, the 2.2 s event gap (measured
  on the delivered picture as "no still picture over 3 s"), and each B-roll window used once.
- A job without `gates` is treated as not approved: the storyboard must be approved before a picture renders.
- QA score: 10, minus 1 per failed check and 0.1 per warning (0.5 at most); the gate is 9.5 with no failed check. A
  check that can't run on a machine (Whisper in the cloud) is listed as NOT RUN and doesn't count.
- The compliance check is a screen, not a judge: any income, return or guarantee phrase blocks the job until Paras
  reads it; a phrase he clears goes into `qa.cleared` in job.json. On five shipped scripts it raised no false alarm and
  it catches the long-form's "80% profitability" line that was cut by hand.
- Pre-rendered graphics (`graphics.render`) are trusted as they are; only a `composition` is re-rendered when its
  files change. reel-04 and reel-05 point at their shipped renders, so re-delivering them doesn't re-render 5 minutes of
  graphics.
