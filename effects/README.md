# Effects catalog

One folder per effect, described by `effect.json`. A job uses an effect by name, time and parameters:

```json
"effects": [{"effect": "kw", "at": 19.30, "dur": 2.6, "params": {"KICK": "Edited by", "MAIN": "Claude <span class=\"hl\">Opus</span>"}}]
```

`python -m aie effects` lists what's here; `python -m aie validate <job>` rejects unknown effects, missing or unknown
parameters, values of the wrong type or outside `choices`, a format the effect wasn't built for, Paras-only
(`"brand": "own"`) effects in client jobs, and a stage effect placed over a full-frame beat. The `effects` stage renders
each placement on its own (transparent webm, cached by its filled HTML) and the `picture` stage lays it over the video
at `at`; a placement with `"variants": ["youtube"]` shows in those variants only.

## What's here

| Family | Format | Effects |
|---|---|---|
| Long-form cards (2026-10-07) | 16:9 | `kw`, `section`, `chip`, `lower`, `subscribe` |
| Reel stage (reel-05, the top half of a split layout) | 9:16 | `reel-chat`, `reel-reveal`, `reel-connect`, `reel-counter`, `reel-step`, `reel-terminal`, `reel-prompt`, `reel-code`, `reel-rule`, `reel-guide`, `reel-cta-comment`, `reel-cta-channel` |
| Reel full frame (over footage) | 9:16 | `reel-hook`, `reel-label`, `reel-bubble`, `reel-big-number`, `reel-stamp` |

Every effect has a `preview.jpg` (frames at 20%, 50% and 85%) rendered from its `example`. After changing a template,
rerun `python tools/effect_preview.py <name>`: it renders, checks that something is drawn, that stage effects stay in
the top half and full-frame ones inside Instagram's safe zone, and rewrites the preview.

The reel effects share `templates/reel/reel.css` (the brand tokens) and `reel.js` (pop, slam, type, press), so a style
change lands in all of them. Their timings are fractions of the effect's length, taken from the shipped beat, so a
longer placement slows the same choreography down rather than leaving dead air. Client styles (reel-04's pink accent,
for instance) are Phase 1 style packs; until then these carry Paras's brand and are marked `"brand": "own"`.

Not ported, and why: reel-03's staircase world and reel-04's frame-by-frame picture effects (paper cut, sticker,
text-behind, crash zoom) are woven through one composition or one Python compositor; they stay job code until a
`picture` engine exists. reel-04's graphics are in the client's style, not ours.

## effect.json

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Same as the folder name |
| `title`, `description` | title yes | What it looks like, in plain words |
| `kind` | yes | `overlay` (graphics over the picture), `picture` (changes the frame), `transition`, `caption`, `sound` |
| `engine` | yes | `hyperframes-template`, `hyperframes-composition`, `ffmpeg`, `python`, `synth` |
| `source` | yes | The file that implements it, relative to the repo or this folder |
| `params` | no | `{NAME: {required, default, choices, description, type}}`; a required param has no default. `type`: `text` (default, HTML allowed), `list` (JSON, for the template's script), `number`, `color` (`#RRGGBB`), `file` (a file in the job folder, e.g. a real logo, copied next to the render as `asset_<name><ext>`) |
| `derived` | no | `{SLOT: {"from": PARAM, "map": {value: text}}}`: a slot filled from another parameter's value |
| `files` | no | Shared files the template loads (`templates/reel/reel.css`), copied next to it |
| `zone` | no | `stage` (top half of a split layout) or `full` (over the whole frame) |
| `example` | yes | Parameter values for the preview and the tests |
| `duration` | no | `{default, min, max}` in seconds |
| `formats` | no | `16:9`, `9:16`, `1:1` it was built and tested for |
| `brand` | no | `"own"` = carries Paras's brand; never used in client jobs |
| `origin`, `license` | yes | Where it came from, and its licence (`own`, `MIT`, ...) |
| `tags`, `preview` | no | Search words; the preview strip (`preview.jpg`) |

Herk Edit Kit code is MIT. Nate Herk's brand (AIS logo, colours, tokens) is not licensed for us and never enters this
catalog.

## Not in the catalog

`templates/lf_compare.html`, `lf_end.html` and `lf_rule.html` have the long-form's own text written into them (the cost
table, the next-video card, the 10·80·10 rule), so they are one-offs, not effects. `templates/keyword-callout.html` is a
starting point that gets copied and edited by hand.
