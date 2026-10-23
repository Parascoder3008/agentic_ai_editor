"""Reel-05 master timeline (0-58.00 s, 25 fps), shared by compose.py, captions.py, sfx.py and kit_export.py.
The voice is trimmed by OFF (0.24 s of TTS lead-in) so the first word lands on frame 2; every voice-tied time below is
`aligned word time - OFF`. Every cut sits in a pause between spoken words and on the 25 fps grid."""
OFF = 0.24
END = 58.00
FPS = 25
# (t0, t1, layout, source, src_in, speed): layout hook|broll|face|split. Avatar src_in = t0 + OFF (lip-sync).
SEGMENTS = [
    (0.00, 5.40, "hook", "hook/hook_video.mp4", 0.00, 1.0),
    (5.40, 6.56, "broll", "broll/woman_1080.mp4", 1.20, 1.0),     # typing in the dark
    (6.56, 7.48, "broll", "broll/woman_1080.mp4", 3.55, 1.0),     # the 2:04 clock on "2 baje"
    (7.48, 9.08, "broll", "broll/woman_1080.mp4", 4.60, 1.0),     # close-up; her message pops on "Friday"
    (9.08, 11.80, "split", "avatar.mp4", 9.32, 1.0),
    (11.80, 13.12, "broll", "broll/salon_1080.mp4", 4.90, 1.0),   # owner grins at his phone, thumbs-up
    (13.12, 21.88, "split", "avatar.mp4", 13.36, 1.0),
    (21.88, 23.80, "face", "avatar.mp4", 22.12, 1.0),
    (23.80, 39.44, "split", "avatar.mp4", 24.04, 1.0),
    (39.44, 42.44, "broll", "broll/sleeping_1080.mp4", 5.20, 1.0),   # phone pulses while he sleeps
    (42.44, END, "split", "avatar.mp4", 42.68, 1.0),
]
FULL_FRAME = [(a, b) for a, b, lay, *_ in SEGMENTS if lay != "split"]
# variants: IG ends on "comment AGENT ... DM mein" + freeze (voice muted after the last word so the WhatsApp line
# never leaks into the freeze); YT skips the AGENT line and ends on the WhatsApp channel line
VARIANTS = {"instagram": {"ranges": [(0.0, 53.80)], "freeze": 0.6, "mute_voice_after": 53.80},   # freeze tail = music only, no "Toh channel..."
            "youtube": {"ranges": [(0.0, 49.04), (53.80, END)], "freeze": 0.4}}
