# Effects catalog

One folder per effect, described by `effect.json`. A job uses an effect by name, time and parameters:

```json
"effects": [{"effect": "kw", "at": 19.30, "dur": 2.6, "params": {"KICK": "Edited by", "MAIN": "Claude <span class=\"hl\">Opus</span>"}}]
```

`python -m aie effects` lists what's here; `python -m aie validate <job>` rejects unknown effects, missing or unknown
parameters, values outside `choices`, a format the effect wasn't built for, and Paras-only (`"brand": "own"`) effects in
client jobs.

## effect.json

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Same as the folder name |
| `title`, `description` | title yes | What it looks like, in plain words |
| `kind` | yes | `overlay` (graphics over the picture), `picture` (changes the frame), `transition`, `caption`, `sound` |
| `engine` | yes | `hyperframes-template`, `hyperframes-composition`, `ffmpeg`, `python`, `synth` |
| `source` | yes | The file that implements it, relative to the repo or this folder |
| `params` | no | `{NAME: {required, default, choices, description}}`; a required param has no default |
| `duration` | no | `{default, min, max}` in seconds |
| `formats` | no | `16:9`, `9:16`, `1:1` it was built and tested for |
| `brand` | no | `"own"` = carries Paras's brand; never used in client jobs |
| `origin`, `license` | yes | Where it came from, and its licence (`own`, `MIT`, ...) |
| `tags`, `preview` | no | Search words; a preview clip or still |

Herk Edit Kit code is MIT. Nate Herk's brand (AIS logo, colours, tokens) is not licensed for us and never enters this
catalog.

## Not in the catalog

`templates/lf_compare.html`, `lf_end.html` and `lf_rule.html` have the long-form's own text written into them (the cost
table, the next-video card, the 10·80·10 rule), so they are one-offs, not effects. `templates/keyword-callout.html` is a
starting point that gets copied and edited by hand.
