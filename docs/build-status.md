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
| 0.4 | SFX, music, sound mix | |
| 0.5 | Picture, mux, variants; reel effects into the catalog | |
| 0.6 | QA, kit export, `run all`, render lock | |
| 0.7 | Herk Edit Kit cards into the catalog, re-coloured | |
| 1 | Style library: pack format, built packs, Style Learner | |
| 2 | Agent team (Claude Agent SDK) + tool servers, budgets, gates | |
| 3 | Local web app: 7 screens, review player, notes to agents | |
| 4 | Avatar mode (HeyGen) + generated shots (Higgsfield, Flow) | |
| 5 | Resolve, Premiere, After Effects bridges (OTIO) | |

## Unproven until the PC run

Things the cloud session cannot exercise. Each says what to run and what "pass" looks like.

1. **Long-form cut from the WAV.** `python -m unittest discover -s tests` on the PC must show 0 skipped;
   `test_cutter_rebuilds_body_pieces_exactly` compares against `jobs/longform-ai-editor/edit/body_pieces.json`.
2. **Whisper verify.** `python -m aie run jobs\longform-ai-editor verify` (faster-whisper + model download).

## Decisions taken without Paras (to confirm at the check)

- Database: the plan says Postgres; the app uses SQLite (built into Python, nothing to install or run on one PC).
  Same data model.
