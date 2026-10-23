# Runway motion prompts: final, after the deep check (2026-10-12)

## RESULT: all 3 shots usable on the first render (144 credits; 108 left)
- **Gotcha:** Runway rejects Higgsfield image URLs ("URL hostname is not in allowed hostnames"). Upload start frames with init_upload, then PUT, then complete_upload. The failed task was refunded.
- **Shot 1, meeting** (`clips/shot1_meeting.mp4`, task 45467f3c): camera and phone stay rock-steady. He gestures, looks down and stops. After about 2.3 s he breaks into a big happy grin (the model overplays "smile"). **Use 0.0–2.2 s.**
- **Shot 2, gym** (`clips/shot2_gym.mp4`, task 43f54997): he lowers the dumbbell, looks at the phone, then gives a strong irritated scowl. At 3.5 s he starts curling again. **Use 0.5–3.2 s.**
- **Shot 3, late night** (`clips/shot3_night.mp4`, task c0103b8f): he types, stops and gives the phone an irritated look. His hands flail and blur at 1.3–2.3 s, then he tilts his head back and sighs. **Use 0.0–1.3 s, then a punch-in jump cut to 2.6–4.0 s** (crop to 90% anchored top-left).
- **Prompt lesson:** never write "smile" for an annoyed beat. Use "irritated, tight-lipped".
- **Preview:** `clips/INTRO_preview_silent.mp4` (7.6 s, 1080×1920, lanczos upscale, unsharp filter and light grain).

**Model:** Gen-4.5 image-to-video.
- Ratio 720:1280: the only 9:16 option for this model in Runway's API documentation. The start frames are exactly 9:16 (1152×2048), so nothing is cropped.
- 4 s per shot, silent, 12 credits/s, so 48 per shot and 144 in total. The account holds 252.
- **Order:** render shot 1, check it, then shots 2 and 3, so a prompt-style problem only costs one shot.
- **After rendering:** upscale (4K upscaling is included free in the Pro plan), then add grain and colour to match Paras's real footage.

**Rules applied** (Runway's Gen-4 guide and Gen-4.5 notes):
- Positive phrasing only; no "no X".
- Camera instruction first.
- Describe motion only, not what's already in the image.
- One action chain at natural real-time speed, ending in "then holds".
- Name what must stay stable (the phone, the colleagues).

**Risk removed:** in shot 3, hands-on-face with glasses is where AI warps. Replaced with a head tilt and sigh.

## 1 · Meeting: start frame `stills/s12.png`
Locked-off tripod shot; the camera stays perfectly still. At natural real-time speed, the man finishes his sentence with a small hand gesture, then his eyes drop to the phone lying on the table in the foreground. He pauses mid-word, lowers his hands to the table and gives his two colleagues a brief, awkward, polite smile, then holds. The two colleagues sit still, listening. The phone stays exactly where it is, its screen glowing evenly. Natural documentary realism.

## 2 · Gym: start frame `stills/s21.png`
Locked-off tripod shot; the camera stays perfectly still. At natural real-time speed, the man slowly lowers the dumbbell from his shoulder down to his side, then glances down at the phone on the bench beside his thigh. He lets out a frustrated breath and gives a small shake of his head, then holds. The gym behind him stays calm. The phone stays exactly where it is, its screen glowing evenly. Natural documentary realism.

## 3 · Late night: start frame `stills/s33.png`
Locked-off tripod shot; the camera stays perfectly still. At natural real-time speed, the man stops typing and glances down at the phone on the desk. He lifts his hands slightly off the keyboard, closes his eyes, tilts his head back and lets out a long tired sigh, then holds. The phone stays exactly where it is, its screen glowing evenly. The warm lamp light stays steady. Natural low-light documentary realism.
