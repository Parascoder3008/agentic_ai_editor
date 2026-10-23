# DaVinci Resolve — Beginner Guide (BuildLoop Shorts)

You've never used Resolve. That's fine — for our workflow you only really touch **2 of the 7 pages** (Edit + Deliver). This walks you from install to a published 9:16 Short.

---

## 1. Install (free)
- Go to **blackmagicdesign.com/products/davinciresolve** → big **Download** button → pick **DaVinci Resolve** (the FREE one, *not* "Studio"). Mac version.
- Install, open. The free version does everything we need: FCPXML import, auto-captions, 9:16, H.264 export. You do **not** need Studio.
- First launch may ask about a "Project Library / Database" — just accept the default **Local Database**. Skip the tutorials popup.

---

## 2. How Resolve thinks (this trips up everyone)
Resolve is **not** like opening a `.mov` in QuickTime. It works like this:
- Everything lives inside a **Project** (stored in Resolve's internal database, not as a loose file).
- A Project holds: a **Media Pool** (your clips), one or more **Timelines** (your edits), and settings.
- Along the bottom are **7 Pages**: *Media, Cut, Edit, Fusion, Color, Fairlight, Deliver.*
  - You'll use **Edit** (build the short) and **Deliver** (export). Ignore Fusion/Color/Fairlight for now.

So you don't "open a video file" — you **open/create a Project, then import media or a timeline into it.**

---

## 3. Opening one of my timelines (your main flow)

Your shorts come as `.fcpxml` files in each session's `4_TIMELINES/` folder.

1. Open Resolve → you land on the **Project Manager** (home screen with project tiles).
2. Double-click empty space → **New Project** → name it, e.g. `Prompt Machine — Shorts`.
3. Top menu: **File → Import → Timeline → Import AAF, EDL, XML…**
4. Navigate to the session's `4_TIMELINES/` and pick e.g. `SHORT13_ALIGNED.fcpxml`.
5. A dialog appears about media/frame rate — just click OK (it's 50 fps). Resolve auto-finds `Luuk Alleman-2.mp4` because it's in `1_RAW/` on the same drive.
6. If any clip shows red **"Media Offline"**: in the **Media Pool** (top-left), right-click the offline clip → **Relink Selected Clips** → point to the session's `1_RAW/` folder.
7. You're now on the **Edit** page looking at the timeline = my cut. Press **Spacebar** to play.

> Tip: if the `.fcpxml` ever gives trouble, use the `.edl` in the same folder the same way (File → Import → Timeline).

---

## 4. Starting fresh from a raw file (alternative)
1. New Project → name it.
2. **Media** page (bottom-left) → drag a file from `1_RAW/` into the **Media Pool**.
3. Drag that clip down onto the **timeline**. Now edit.

---

## 5. The Edit page — only what you need
- **Timeline** = your video left→right. The **playhead** (white vertical line) is where you are. Click the ruler to move it; **Spacebar** plays/pauses.
- **Tools** (top-left of timeline): **Selection** arrow (shortcut `A`) for moving/trimming; **Blade** (`B`) to slice a clip where you click.
- **Trim**: hover a clip's edge → drag to shorten/lengthen. Drag the clip's middle to move it.
- **Delete**: select a clip → `Delete` leaves a gap. **Ripple-delete** (`Shift+Delete`) removes it AND closes the gap. (Use ripple-delete most of the time.)
- **Swap a take** (use a different delivery of a line): double-click `Luuk Alleman-2.mp4` in the Media Pool to load it in the **Source viewer** (top-left). Scrub to a better take, press `I` (mark in) and `O` (mark out), then drag it onto the timeline or press the overwrite key.
- **Undo** = `Cmd+Z` (use it freely). **Zoom** timeline = `Cmd +` / `Cmd -`.

---

## 6. Make it a vertical Short (9:16)
Your footage is 16:9 horizontal; Shorts are 1080×1920 vertical.

1. **Timeline menu → Timeline Settings** → untick "Use Project Settings" → set **Resolution = 1080 × 1920 (Vertical)** → Save. (Or set the Project to 1080×1920 *before* importing.)
2. Now clips sit in a vertical frame with empty sides. To fill it with your face: click a clip → top-right **Inspector** → **Transform** → raise **Zoom** (~1.7–1.9) and adjust **Position** so you're framed.
3. **Apply to all clips fast**: right-click the clip you set → **Copy**. Select all other clips (click first, Shift-click last) → right-click → **Paste Attributes** → tick **Transform** → OK.

---

## 7. Captions (do this — biggest retention boost on Shorts)
- **Timeline menu → Create Subtitles from Audio** (yes, the free version has this). It auto-transcribes your voice into caption clips on a Subtitle track.
- Style them: click the Subtitle track / a caption → **Inspector** → set **Font, Size (big), Position (centered, lower-third), Background/stroke**. Bold + centered = the Shorts look.
- Read through and fix any mis-heard word by double-clicking the caption.

---

## 8. Music & audio
- Your shorts already have **mastered voice** (clean, leveled), so you just add a music bed.
- Drag a music file into the Media Pool → onto an **audio track below** your clips.
- Lower its volume so it sits under the voice: click the music clip → Inspector → **Volume** ~ **-20 dB** (or drag the white volume line down).

---

## 9. Export (Deliver page)
1. Click **Deliver** (bottom bar).
2. Top-left: pick the **YouTube** preset (or "H.264 Master").
3. Set: **Resolution 1080×1920**, **Format MP4**, **Codec H.264**, Quality "Best"/~15–20 Mbps.
4. Set **Location** to the session's `6_EXPORTS/` and name the file.
5. **Add to Render Queue** (bottom of that panel) → **Render All** (right side). Done — your finished Short is in `6_EXPORTS/`.

---

## 10. Saving / backup
- Resolve **auto-saves** to its database (Live Save is on by default) — you won't lose work.
- For a portable backup file: **File → Export Project…** → save the `.drp` into the session's `5_DAVINCI/`.

---

## Cheat sheet
| Do this | Shortcut / where |
|---|---|
| Play/pause | `Spacebar` |
| Slice clip | `B`, then click |
| Remove clip + close gap | `Shift+Delete` |
| Mark in / out (source) | `I` / `O` |
| Undo | `Cmd+Z` |
| Import my timeline | File → Import → Timeline → XML |
| Auto-captions | Timeline → Create Subtitles from Audio |
| Export | Deliver page → YouTube preset → Render |

## Golden rules
1. **Never move files in `1_RAW/`** after importing (causes Media Offline).
2. One Resolve **Project per recording session**; put each short as a separate **Timeline** inside it.
3. Export finals to `6_EXPORTS/`, back up the `.drp` to `5_DAVINCI/`.
