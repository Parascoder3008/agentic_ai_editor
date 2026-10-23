# Herk Edit Kit (vendored copy)

Copied from `C:\Users\PARAS ARORA\Developer\herk-edit-kit` on 2026-10-23 as source material for the effects catalog.
Reference only: the pipeline doesn't run anything from this folder, and the copy installed on the PC (junctioned into
`~/.claude/skills`) is the one the skills use.

## Licence

`LICENSE` (MIT, Nate Herk) and `licenses/PIPELINE-USE-PERMISSION.txt` allow use, modification and commercial videos;
keep both notices. `THIRD_PARTY_NOTICES.md` overrides them for third-party parts (HyperFrames is Apache-2.0, GSAP
has its own licence, fonts keep their publishers' licences).

## Not copied or removed

- Not copied: `node_modules/`, `video-projects/`, `.git/`, all video and audio (including `examples/showcase/*.mp4`,
  so `scripts/check-kit.mjs` reports those as missing).
- Removed: `DESIGN.ais-example.md` and `docs/images/ais-live-ad.jpg`, Nate Herk's AI Automation Society brand
  identity and ad. His brand is not licensed for our videos.

## Brand rule for imports

Both styles in `style-library/` (Vox explainer, Kallaway) use the AIS palette (accent `#37BDF8`), and 47 cards mention
AIS in comments or sample text such as "AIS PILOT PROGRAM DATA 2026". A card enters `effects/` only:

- re-coloured with our tokens (Inter, `#0C0E0F` / `#1A9FD1` / `#3AB0D8` / `#11324C`), including colours written into
  its script, not just `tokens.css`;
- with every text slot required, so no sample text can reach a render.
