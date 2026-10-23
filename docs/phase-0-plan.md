# Phase 0: package the pipeline

Status: **draft for Paras's approval.** Branch: `phase-0`. Nothing on `main` changes until this is approved and tested.

Phase 0 of the [Agentic Editing Tool plan](https://claude.ai/artifact/Ct4Tz6T4pCBCEaXaid5JAR). Exit test, from the plan:
**a new reel runs from one `job.json`, with no scripts copied from an earlier job.**

Agents, the web app, the style library, the NLE bridges and AI generation are later phases and are not in this one.
Phase 0 is the base they all call.

## What the code does today

Read from the 8 jobs in this repo (`shorts/`, `clients/`, `ads/`, `jobs/`).

- **Every job already has the same shape.** A planner script holds the editorial decisions (what to keep, which graphic
  lands on which word, which SFX, the music cues) and writes a config; shared tools render from that config. Example: the
  long-form's `make_longform.py` writes `lf.json`, which `tools/longform_compose.py` renders. Phase 0 makes that shape official.
- **Some tools are already shared:** `score_music`, `captions_ass`, `gfx_batch`, `storyboard`, `transcribe_local`,
  `transcribe_hinglish`, `force_align`, `verbatim_ctc`, `pron_check`, `pick_avatar`, `reel_compose`, `longform_compose`.
- **The rest were copied per job, and the copies drifted apart:**

  | Script | Copies | Lines in common between any two copies |
  |---|---|---|
  | `sfx.py` | 6 | 19–64% |
  | `compose.py` | 5 | 21–56% |
  | `captions.py` | 4 | 31–73% |
  | `qa_final.py` | 3 | 23–97% |
  | `kit_export.py` | 3 | 27–45% |

  So this is not deleting duplicates. Each shared module takes the best version and turns its job-specific numbers into
  `job.json` settings.
- **Every script has machine paths written into it** (`C:\Users\PARAS ARORA\AI_Editor\...`, `D:\october videos\...`,
  `Downloads\DJI_...`). That ties the code to one PC and one folder.
- **There are three timeline formats:**
  - long-form: keep/drop spans on a master WAV, with camera and screen-recording offsets (`body_edl.py`);
  - camera reels: measured pieces per take, with Instagram and YouTube tails (reel-04 `edl.py`);
  - avatar reels: segments with a layout per segment, plus per-variant ranges and a freeze (reel-05 `plan.py`).

## Design

### Layout

```
aie/                     the package: python -m aie <job> <stage>
  config.py              loads + validates job.json; machine paths come from aie.local.json
  timeline.py            pieces/segments, master <-> output time, frame snapping, variants (IG / YT)
  audio.py               10 ms loudness envelope, speech islands, cut-edge snapping, onset clamp
  cuts.py                keep/drop spans or measured pieces -> pieces.json
  verify.py              each kept piece transcribed alone, joint review, repeated-word check
  transcribe.py          local Whisper, Hinglish chunks, forced alignment, letter-level CTC
  captions.py            word-by-word ASS: seam style on split beats, low boxed style on full frame, hide windows
  sfx.py                 synthesized SFX library + cue placement + ducking under the voice
  music.py               original score (score_music, unchanged logic)
  graphics.py            templated HyperFrames batch + per-job HyperFrames compositions
  picture.py             layouts: split, face, b-roll/full, presenter card, screen + face bubble, 16:9 camera
  sound.py               voice + sfx + score -> limiter -> two-pass loudnorm per variant
  qa.py                  sync, word masking, loudness, joints, contact sheets
  package.py             SRT per variant, cover frame
  kit.py                 Herk Edit Kit export + its validators
  storyboard.py          storyboard.html for the approval gate
  runner.py              stages in order, skip unchanged stages, one heavy render at a time
jobs/<slug>/job.json     one file per job: every editorial decision
jobs/<slug>/custom/      effects only this job needs (e.g. reel-04's frame-by-frame paper cut)
tests/                   regression tests against outputs already in this repo
aie.local.example.json   template for machine paths (the real aie.local.json is git-ignored)
```

### `job.json`

One file holds everything that is a decision. Everything else is computed from it. A sketch for an avatar reel (reel-05):

```json
{
  "id": "reel-05",
  "mode": "avatar",
  "fps": 25,
  "size": [1080, 1920],
  "sources": {
    "avatar": {"path": "avatar.mp4", "voice_offset": 0.24},
    "hook":   {"path": "hook/hook_video.mp4"},
    "woman":  {"path": "broll/woman_1080.mp4"}
  },
  "script": "script.txt",
  "timeline": [
    {"t": [0.00, 5.40], "layout": "hook",  "src": "hook",   "in": 0.00},
    {"t": [5.40, 6.56], "layout": "broll", "src": "woman",  "in": 1.20, "note": "typing in the dark"},
    {"t": [9.08, 11.80], "layout": "split", "src": "avatar", "in": 9.32}
  ],
  "variants": {
    "instagram": {"ranges": [[0.0, 53.80]], "freeze": 0.6, "mute_voice_after": 53.80},
    "youtube":   {"ranges": [[0.0, 49.04], [53.80, 58.00]], "freeze": 0.4}
  },
  "captions": {"hide": [[0.0, 5.40]]},
  "graphics": {"composition": "gfx/index.html"},
  "sfx": [{"kind": "whoosh_into", "word_t": 5.40, "gain_db": -28}],
  "music": {"score": {"blocks": [], "events": []}},
  "custom": [],
  "gates": {"storyboard_approved": false, "final_approved": false}
}
```

Camera footage uses a `cut` section instead of a hand-written timeline: either keep/drop spans that the cutter measures
and snaps (long-form style), or pieces whose edges were already measured (reel-04 style):

```json
"cut": {"mode": "spans", "source": "a", "gap": 0.40, "pad_in": 0.08, "pad_out": 0.12,
        "keep": [[9.10, 22.61, "open"]], "drop": [[21.95, 22.85, "lone fragment"]]}
```

Machine paths (fonts, video-use, the Herk kit, the SFX library, footage folders) live in `aie.local.json` on each
machine. The code never contains `C:\Users\...`, so the same code runs on your PC and in a cloud session.

### Stages

`python -m aie jobs/<slug> <stage>`, or `all` to run them in order:

`transcribe -> align -> cut -> verify -> storyboard -> graphics -> sfx -> music -> picture -> sound -> mux -> qa -> package -> kit`

- A stage is skipped when its inputs haven't changed since the last run.
- Heavy renders (`picture`, `graphics`, background removal) take a lock, so only one runs at a time (your render-safety rule).
- **Your gates stay:** the run stops after `storyboard` until `gates.storyboard_approved` is true, and only previews render
  until `gates.final_approved` is true. Nothing is ever published by the runner.

### What stays per job

Effects only one video needs stay as small scripts in `jobs/<slug>/custom/`, run by the runner with standard arguments:
reel-04's frame-by-frame base layer, the long-form intro builder. Turning those into general features is Phase 2+ work,
once a second job needs the same thing.

## Which version each module starts from

| Module | Starts from | Why |
|---|---|---|
| `audio`, `cuts` | long-form `body_edl.py` | Most refined cut rules: islands from the audio, quiet-10 ms snap, never padding into the next word |
| `timeline` | reel-04 `edl.py` + reel-05 `plan.py` | Multi-take pieces, IG/YT variants, freeze, voice offset |
| `verify` | long-form `piece_tx.py`, `review_joints.py`, `check_repeats.py`; reel-04 `qa_joints.py` | The restart checks that caught "time \| time" and "maine na poori ek" |
| `transcribe` | `tools/transcribe_*`, `force_align`, `verbatim_ctc` | Already shared; paths only |
| `captions` | `tools/captions_ass.py` + reel-05 `captions.py` | Newest seam/low styles, hide windows, script-text matching |
| `sfx` | reel-05 `sfx.py` | Newest synth library; cues move into `job.json` |
| `music` | `tools/score_music.py` | Already config-driven |
| `picture`, `sound` | reel-05 `compose.py` + `tools/longform_compose.py` + `tools/reel_compose.py` | Picture and sound rendered separately then muxed (fixed the 0.77 s drift); covers 9:16 and 16:9 |
| `qa` | reel-05 `qa_final.py` + `qa_sheet.py` | Sync, masking, loudness, contact sheets |
| `package`, `kit` | reel-05 `package.py`, `kit_export.py` | Newest |
| `storyboard`, `graphics` | `tools/storyboard.py`, `tools/gfx_batch.py` | Already shared; paths only |

## Build order

Each step ends with a test. "Cloud" means it can be proven here without footage; "PC" means it needs your footage and renders.

| Step | Builds | Proven by | Where |
|---|---|---|---|
| 1 | Package skeleton, `job.json` schema + validator, `aie.local.json`, shared `tools/` moved in with paths taken from config (no behaviour change) | Validator accepts reel-04 and reel-05 written as `job.json`; tools still produce their old outputs | Cloud |
| 2 | `timeline`, `audio`, `cuts`, `verify` | reel-04 from `job.json` reproduces `timeline.json` + `words_master.json` exactly; the long-form keep/drop reproduces `body_pieces.json` | Cloud + PC (the long-form needs its WAV) |
| 3 | `captions`, `package` | reel-05 from `job.json` reproduces `captions.ass` and `REEL05_instagram.srt` exactly | Cloud |
| 4 | `sfx`, `music`, `sound` | reel-05 re-mixed: loudness, true peak and sync match its `qa/final_qa.json` | PC |
| 5 | `picture`, `mux`, variants | reel-05 re-rendered; frames match the shipped reel at the QA timestamps | PC |
| 6 | `qa`, `kit`, runner `all`, render lock | **Exit test:** your next reel runs from `job.json` end to end, no copied scripts, QA passes | PC |

"Exactly" is testable: re-running reel-05's `captions.py` in a cloud session already reproduces the committed
`captions.ass` and `words_master.json` byte for byte. Any difference a new module introduces is either explained and
accepted by you, or reverted.

## Risks

- **Merging drifted scripts can change output in small ways.** The byte-for-byte tests above catch it.
- **Transcription and alignment can't run in the cloud yet.** The environment blocks `huggingface.co`
  (Network access settings). Until it's allowed, those modules are tested on the PC only.
- **Windows vs Linux.** Paths via `pathlib`, no PowerShell in the package. ffmpeg is 8.1 on the PC and 6.1 in the cloud;
  the filters the pipeline uses (`zscale`, `loudnorm`, `subtitles`, VP9 alpha) exist in both.
- **Time.** The plan gives Phase 0 one week. With five script families to merge, [Guessing] two to three weeks of daily
  sessions is more realistic.

## Decisions for Paras

1. **Working folder.** Recommended: work from the repo folder (`C:\Users\PARAS ARORA\Developer\agentic_ai_editor`).
   The design works either way, because paths come from `aie.local.json`.
2. **Per-job effects stay per job** (`custom/`) until a second job needs the same effect. OK?
3. **Exit-test reel:** the next reel you record goes through the runner instead of the old scripts.
