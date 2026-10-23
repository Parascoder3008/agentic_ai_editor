# Voice upgrade (2026-10-22)

**Source audio:** Paras's lav-mic course lectures, mono 44.1 kHz WAV, already uploaded to HeyGen.
| Asset | Asset ID | Length |
|---|---|---|
| Lecture 1, intro | `bf3e00c685534997b894a62d11b12a23` | 20.6 min |
| Lecture 2, offer | `65e52d468b7a41579a31d23ec765056f` | 30.3 min |
| 2-minute sample (lecture 1, 290–410 s) | `420d1bff73ee4b06af69c626ece0e0fb` | 2.0 min |

**Instant voice v2:** `84c9815d67de40faab36511444541c7f`, "Paras Arora - Instant v2 (lecture mic)". HeyGen's model-backed instant voice, cloned from the 2-minute sample with similarity set to max and no denoise. Status ACTIVE. `create_speech` uses the `orca` engine.
- **Preview:** `preview_instant_v2.wav`, 58.2 s, URL in `preview_instant_v2_url.txt`.
- **Pronunciation report:** `report_instant_v2.md`.

**Professional voice is blocked.** `create_model_audio_voice` failed: "No professional voice slots are available. Purchase another slot." Once a slot is bought, run it on the two lecture assets above, named "Paras Arora - Pro (lectures 1-2)". The audio is already uploaded, so training can start right away.
