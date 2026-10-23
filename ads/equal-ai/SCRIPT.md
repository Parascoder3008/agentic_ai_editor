# Equal AI ad: "Interruptions" (draft v1, for Paras's approval)

**Format:** 9:16 reel, about 38–40 s, Hinglish.
**Structure:** AI-generated intro (0:00–0:09) → Paras on camera + real app screen recordings (0:09–0:35) → call to action + end card (0:35–0:40).
**Positioning (from the brief):** always "**your personal AI assistant**". Never call it a spam blocker, a call-screening app, a chatbot or voicemail.

## Concept
- **Their brand film:** spam callers are shown as pushy people barging into a gym session, and Equal is a guy in a green jacket who picks up the phone ("main utha lunga").
- **Our version:** the same tension, set in **your** life.
  - Three rapid interruptions: a meeting, the gym, deep work.
  - The third call is *not* spam. It's a delivery guy, which sets up the "Tell Equal" instruction payoff later.
  - Equal is never a person here; it's the **real app on your phone**. That follows the brief: "show the product, let the product do the talking".

## Script

### INTRO: AI-generated (0:00–0:09). No one speaks on screen.
| Time | Shot | Sound | On screen |
|---|---|---|---|
| 0:00–0:03 | **Meeting.** Paras presenting to 2 clients in a glass meeting room. His phone on the table lights up and buzzes. He glances at it; his smile freezes mid-sentence. | Vibration ×2, then the caller through the phone speaker: *"Sir, aapke liye pre-approved personal loan hai…"* | Clean "Unknown number" call bar (added in edit) |
| 0:03–0:06 | **Gym.** Mid-set on the bench press. The phone on the bench rings loudly; he loses the rep, racks the bar and stares at the phone. | Ringtone, barbell clank. Caller: *"Sir, sirf aaj ke liye Goa ka holiday package…"* | Call bar |
| 0:06–0:09 | **Deep work, late night.** Laptop, headphones, focused. The phone rings a third time; he drops his head on the desk. | Ringtone. Caller (a real call this time): *"Bhaiya, parcel aaya hai, gate pe aa jao!"* | Call bar. Ringtone cuts off with a whoosh |

### BODY: Paras records this (0:09–0:35)
| Time | Visual | Paras says |
|---|---|---|
| 0:09–0:12 | Talking head, phone in hand, calm | **"Ab yeh calls main khud nahi uthata. Mera personal AI assistant uthata hai: Equal."** |
| 0:12–0:16 | **Screen rec:** incoming call, Equal answers | **"Number saved ho ya unknown, Equal call uthata hai aur meri jagah baat karta hai."** |
| 0:16–0:21 | **Screen rec:** call summary, then transcript scroll, then recording play | **"Call ke baad batata hai kisne call kiya, kyun kiya, aur kya bola. Summary, transcript, recording, sab ek jagah."** |
| 0:21–0:25 | **Screen rec:** tap **Call Back**, then **Reply on WhatsApp** | **"Kisi ko call back chahiye? Ek tap. WhatsApp pe reply karna hai? Ek tap."** |
| 0:25–0:30 | **Screen rec:** Tell Equal, typing the instruction | **"Aur main Equal ko bata deta hoon kaunsi call kaise handle karni hai. Jaise, delivery wala call kare, toh parcel reception pe chhudwa do."** |
| 0:30–0:35 | Talking head + overlays "9+ Indian languages", "1M+ daily users" | **"Hindi, English aur 9 se zyada Indian languages mein baat karta hai. Aur 10 lakh se zyada log ise roz use karte hain."** |

### CTA (0:35–0:40)
| Time | Visual | Paras says |
|---|---|---|
| 0:35–0:38 | Talking head | **"Toh apni calls AI assistant ko do, aur apna kaam karo. Equal download karo: Play Store ya App Store pe."** |
| 0:38–0:40 | Brand end card: Equal logo, "Your Personal AI Assistant that manages calls and more", store badges | (music out) |

Optional, about 2 s before the end card: **gym payoff.** Paras finishes the set calmly while his phone silently shows "Equal answered" (one more AI shot).

## What you record
1. **Talking head, 9:16, phone in hand.** Eye level, lav mic, plain background. Wear black or white (Equal's green pops against it). Say each line twice with a pause between.
2. **Screen recordings on your phone, with Equal installed:**
   1. A friend calls from a number not saved in your phone, and Equal answers.
   2. Open the summary, scroll the transcript, play the recording.
   3. The Actions row: Call Back, Reply on WhatsApp.
   4. Tell Equal: type the delivery instruction.
   5. The call history list.
   Use test calls only; I'll blur any real numbers or names.
3. **Phone-in-hand B-roll:** over-the-shoulder, thumb tapping through the app (the brief asks for this).

## How the AI intro gets made (cheap, and none of reel 1's speech problems)
- **Visuals:** 3 still images with your face (about 1 credit each), each animated to a 3–5 s clip. Kling 3.0 on Higgsfield costs about 7.5 credits per clip; Runway Gen-4 Turbo costs about 25 Runway credits per clip.
- **Voices:** you never speak in the AI shots, so there's no lip-sync to go wrong. Caller voices are separate voice-overs that go through the same pronunciation check as before, played as if through a phone speaker.
- **Phone screens:** added in the edit as clean overlays, because AI scrambles on-screen text.

## Locked decisions (Paras, 2026-10-12)
- 9:16 reel. Runs as a **paid partnership with Equal**, so it needs the "Paid partnership" label.
- Face: Higgsfield Soul **"Paras New Avatar"** (soul_2 `dea58452…`, the black T-shirt photo), with different clothes per scene.
- Stills come from Higgsfield Soul 2.0; the animation is done in Runway.

## AI intro: start frames (approved by QA; Paras to confirm)
| Scene | Still | Job | QA |
|---|---|---|---|
| 1 Meeting | `stills/s12.png` | 9b38995e-5d17-49c2-9c10-c6b61e2b780b | Face matches; colleagues seen from behind (no cloned face); no laptop or logo; one phone, screen plain |
| 2 Gym | `stills/s21.png` | 8efb0249-518d-4b73-8d68-26e04782e868 | Face matches; hand on dumbbell is natural; one phone on bench |
| 3 Late night | `stills/s33.png` | 9361907a-b7ce-47d8-a061-e9ddbc4edad6 | Plain hoodie; one phone; tea cup; laptop lid not visible |

Rejected:
- s10/s11: Apple logo on the laptop, and a colleague with Paras's face.
- s20: weaker likeness.
- s30/s31: two phones on the desk, and a hoodie logo.
- s13: face too small.

## AI intro: motion prompts (Runway Gen-4.5, 4 s each, 9:16, no audio, 12 credits/s, about 144 credits in total)
1. **Meeting:** "Static locked-off camera. The man keeps explaining with small natural hand gestures; then the smartphone lying on the table in the foreground lights up and buzzes, vibrating slightly against the wood. He glances down at it, stops mid-sentence and gives his colleagues an awkward, polite smile. The colleagues stay still. The phone stays in exactly the same place with its screen plain white. Subtle, realistic motion, no camera movement, no cuts."
2. **Gym:** "Static locked-off camera. The man finishes lowering the dumbbell from the curl; the smartphone on the bench next to his thigh lights up and buzzes. He stops, rests the dumbbell on his knee, looks down at the phone and exhales in frustration with a small shake of his head. The phone stays in exactly the same place with its screen plain white. Subtle, realistic motion, no camera movement, no cuts."
3. **Late night:** "Static locked-off camera. The man is typing on the laptop; the smartphone on the desk in the foreground lights up and buzzes. He stops typing, closes his eyes and slowly drops his face into both hands in frustration. The phone stays in exactly the same place with its screen plain white. Subtle, realistic low-light motion, no camera movement, no cuts."

**What makes it look real in the edit:**
- A clean incoming-call screen placed over each phone (the camera is locked off, so the phone doesn't move).
- Each AI clip trimmed to the best 2.5–3 s.
- Grain and colour matched to Paras's real footage, plus a light handheld drift added in the edit.
- Real ambience under each scene: office murmur, gym clanks, night room tone. Phone vibration and ringtone sounds.
- Caller voices played through a phone-speaker filter, after a pronunciation check.

## Claim check (all from the agency brief)
| Claim | Brief | ✓ |
|---|---|---|
| Answers known + unknown numbers | p2 "known and unknown numbers" | ✓ |
| Who called, why, what was said; summary, transcript, recording | p2 "Users can see" list | ✓ |
| Call Back, Reply on WhatsApp | p3–4 live Actions | ✓ |
| Delivery → reception instruction | p3, the brief's own example | ✓ |
| 9+ Indian languages | p4 | ✓ |
| 1M+ daily users ("10 lakh se zyada roz") | p6 | ✓ (confirm it's still current before the final) |
| Play Store + App Store | their brand film's end card | ✓ |
