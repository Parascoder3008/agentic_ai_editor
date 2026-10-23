# BuildLoop Video Editing — Fable 5 setup

The two Claude Code skills I use to edit my YouTube videos, plus the DaVinci
Resolve guide. This is the full pipeline: cut the raw take, tweak it in Resolve
if you want, then one-shot the finished edit.

## What's inside

| Skill | What it does |
|-------|--------------|
| **video-cut-aligned** | Cuts a raw talking-head recording down to the best/last takes using forced alignment (Descript-grade, $0, fully local). Outputs a rendered MP4 **and** an editable **DaVinci Resolve timeline** (FCPXML + EDL) that references your raw footage, so you can re-tweak takes by hand. |
| **video-edit** | Edits a *pre-cut* video end to end: captions, the brand motion library + template overlays, zoom punch-ins, b-roll, and a full audio score (music bed + timed SFX). Three modes — Shorts (9:16), Intro (16:9, ≤30s), Longform (16:9, multi-minute). Remotion-based. |
| **DAVINCI_RESOLVE_GUIDE.md** | How to import the cut timeline into DaVinci Resolve and finish by hand. |

## The pipeline

```
  raw recording ──▶ video-cut-aligned ──▶ cut MP4 + Resolve timeline
                                            │
                          (optional) open the timeline in DaVinci Resolve,
                          re-tweak takes by hand — see the guide
                                            │
                                            ▼
                    video-edit ──▶ captions + motion + b-roll + music/SFX
                                            │
                                            ▼
                                    finished video
```

You can also skip Resolve entirely: `video-cut-aligned` gives you a ready MP4,
and `video-edit` takes it from there.

## Install

1. Copy both skill folders into your `~/.claude/skills/` directory.
2. **video-edit** needs its Remotion deps:
   `cd video-edit/remotion && npm install`
   (node_modules was stripped to keep this download small — `package.json` is
   included.)
3. Python scripts need `ffmpeg` / `ffprobe` on your PATH, plus
   `pip install faster-whisper numpy` (and `opencv-python` for video-edit). The
   `.venv` was stripped — install into your own environment.
4. For the cut skill's forced alignment, follow the model download note at the
   top of `video-cut-aligned/SKILL.md`.

## Music

`video-edit/music/` ships with **one** on-brand default bed
(`bg-feelgood-builder.mp3`) so the audio score works out of the box. The rest of
my library was left out to keep this lean and to avoid redistributing licensed
tracks — drop your own royalty-free `.mp3`s into `video-edit/music/` to expand
the rotation. All the SFX in `video-edit/sfx/` are included.

## Not included (on purpose)

- `node_modules/` and `.venv/` — reinstallable from `package.json` / pip.
- Render workdirs and source-footage archives — those were multi-GB job
  inputs/outputs, not part of the skill.
- Most of the background-music library (see Music above).
- Any credentials or personal footage — this bundle is safe to share.

## A note on brand

These skills are wired to the BuildLoop look (fonts, LUTs, motion style, the
lime accent). Swap the assets in `video-edit/assets/`, the LUTs, and the brand
constants to make it yours.
