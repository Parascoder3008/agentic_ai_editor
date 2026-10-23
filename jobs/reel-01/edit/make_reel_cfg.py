import json, sys
E = r"C:\Users\PARAS ARORA\Desktop\edit\edit"
A = E + r"\animations"
M = E + r"\assets\.media\audio\sfx"
V = r"C:\Users\PARAS ARORA\.claude\skills\video-edit\sfx"
final = len(sys.argv) > 1 and sys.argv[1] == "final"

whoosh, bass, click_q, pop, glass = M + r"\sfx_001.mp3", M + r"\sfx_002.mp3", M + r"\sfx_005.mp3", M + r"\sfx_004.mp3", E + r"\assets\glass_shatter.wav"
boom, swoosh, click, cpop, flare, rise = (V + "\\" + n for n in ("hook-boom.wav", "hook-whoosh.wav", "click.wav", "card-pop.wav", "flare-hit.mp3", "timeline-rise.wav"))
PEAK = {whoosh: 0.162, bass: 0.126, pop: 0.119, glass: 0.038, swoosh: 0.19, boom: 0.004, click: 0.003, cpop: 0.003, flare: 0.004, click_q: 0.072}
def hit(f, t, db):  # start the file so its peak lands on t
    return {"file": f, "at": round(max(0, t - PEAK.get(f, 0)), 3), "gain_db": db}

sfx = [
    hit(bass, 2.02, -17), hit(boom, 2.02, -19), hit(whoosh, 3.15, -20),                       # hook slam + exit
    hit(whoosh, 7.62, -20), {"file": rise, "at": 8.55, "gain_db": -24}, hit(cpop, 11.65, -20),  # editing timeline
    hit(pop, 16.97, -16), hit(whoosh, 18.40, -19), hit(swoosh, 22.85, -16),                    # logo appear, spin, fly
    hit(glass, 23.03, -15), hit(bass, 23.03, -23), hit(glass, 24.13, -23),                     # impact, shards fall
    hit(whoosh, 26.95, -20), hit(click, 30.66, -18), hit(click, 31.89, -18), hit(click, 33.87, -18),  # workflow + tabs
    hit(cpop, 34.50, -21), hit(cpop, 37.41, -21), hit(cpop, 39.10, -21), hit(cpop, 40.90, -21), hit(cpop, 42.82, -21),
    hit(whoosh, 53.06, -19), hit(click, 59.19, -15), hit(pop, 61.06, -12), hit(pop, 62.13, -12),   # reels, click, boops
    hit(flare, 67.72, -26), hit(bass, 67.72, -28), hit(click, 68.07, -23), hit(click, 68.52, -23), hit(click, 68.97, -23),  # documentary
    hit(cpop, 74.64, -18), hit(pop, 75.47, -15),                                               # CTA
    hit(cpop, 81.69, -20), hit(cpop, 85.07, -20), hit(cpop, 89.50, -20),                     # end chips
]
cfg = {
    "source": E + (r"\src_final.mkv" if final else r"\src_preview.mkv"),
    "ranges": json.load(open(E + r"\edl_ranges.json")),
    "fps": 25, "crf": 16 if final else 18, "crop_x": 313,
    "grade": "eq=contrast=1.08:saturation=1.06:brightness=0.01,colorbalance=rs=-0.01:bs=0.04:rm=0.035:gm=-0.012:bm=-0.02,vignette=angle=0.42",
    "overlays": [
        {"file": A + r"\slot_hook\render.webm", "start": 0.0, "cutout": E + r"\cutouts\hook_cut.webm"},
        {"file": A + r"\slot_timeline\render.webm", "start": 7.55},
        {"file": A + r"\slot_glass\render.webm", "start": 16.70},
        {"file": A + r"\slot_workflow\render.webm", "start": 26.90},
        {"file": A + r"\slot_reels\render.webm", "start": 52.70},
        {"file": A + r"\slot_doc_back\render.webm", "start": 67.72, "cutout": E + r"\cutouts\doc_cut.webm",
         "cutout_filter": "format=rgba,hue=s=0", "front": [A + r"\slot_doc_front\render.webm"]},
        {"file": A + r"\slot_cta\render.webm", "start": 74.64},
        {"file": A + r"\slot_end\render.webm", "start": 81.50},
    ],
    "bubble": {"start": 26.90, "end": 48.62, "src_cx": 930, "src_cy": 400, "src_size": 560, "x": 716, "y": 300, "d": 320},
    "captions": E + r"\captions.ass", "fontsdir": r"C:\Users\PARAS ARORA\AI_Editor\fonts",
    "fontfile": r"C:\Users\PARAS ARORA\AI_Editor\fonts\Inter-Bold.ttf",
    "labels": {"bottom_y": 1480, "bottom": "ORIGINAL TAKE"},
    "sfx": sfx,
    "music": {"file": r"C:\Users\PARAS ARORA\.claude\skills\video-edit\music\bg-feelgood-builder.mp3", "gain_db": -21},
    "preset": "medium" if final else "veryfast", "out_crf": 17 if final else 20,
    "out": E + (r"\reel_final.mp4" if final else r"\reel_preview.mp4"),
}
json.dump(cfg, open(E + r"\reel.json", "w"), indent=1)
print(f"{len(sfx)} sfx, {len(cfg['overlays'])} overlay groups -> reel.json ({'final' if final else 'preview'})")
