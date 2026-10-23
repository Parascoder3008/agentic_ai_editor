"""Picture track for the Equal ad: one ordered list of shots covering the whole timeline, rendered at
1080x1920 / 25 fps and concatenated into base_video.mkv.
  ai   = Flow clip (native audio dropped)          cam = 4K camera crop (static per shot, zoom per shot)
  img  = Play Store screenshot with a settle-in + slow push        end = black (end card is drawn by gfx)
Cutaways replace the camera picture inside a segment; the voice keeps running underneath.
"""
import json
import subprocess
import sys
from pathlib import Path

ED = Path(__file__).resolve().parent
SRC = Path(r"C:\Users\PARAS ARORA\Desktop\equal ai")
CAM = SRC / "C7054.MP4"
PLAY = ED / "play"
AI = {"meet": SRC / "Man_pitching_while_assistant_works_20261012122430.mp4",
      "tread": SRC / "Man_running_on_treadmill_1080p_20261012122408.mp4",
      "night": SRC / "Two_men_working_late_at_20261012122322.mp4"}
FPS = 25
E = json.loads((ED / "edl.json").read_text(encoding="utf-8"))
FACES = json.loads((ED / "faces.json").read_text())
SEG = {s["id"]: s for s in E["body"]}

# camera zoom per segment, plus hard punch-ins at an output time: (t, zoom)
ZOOM = {"s1": 1.0, "s2": 1.12, "s3": 1.0, "s4": 1.0, "s5": 1.15, "s6": 1.0, "s7": 1.0, "s8": 1.15, "s9": 1.0,
        "s10": 1.15, "s11": 1.0, "s12": 1.18, "s13": 1.0, "s14": 1.15, "s15": 1.0}
PUNCH = {"s2": [(13.88, 1.32)], "s13": [(58.36, 1.15)], "s15": [(65.46, 1.28)]}
XSHIFT = {"s7": -330}                      # keep the phone he holds up inside the crop
# cutaways on the output timeline: (t0, t1, kind, source, src_in)
CUT = [
    (18.40, 19.99, "img", "ss2.png", 0),   # Equal answers your calls      ("Equal AI call uthata hai")
    (19.99, 21.95, "img", "ss4.png", 0),   # Live transcript               ("meri jagah pe baat karta hai")
    (23.80, 26.50, "img", "ss3.png", 0),   # Live green card               ("kisne call kiya, kyun kiya")
    (26.50, 28.235, "img", "ss5.png", 0),  # Call summary + recording      ("summary aur transcription")
    (28.76, 32.48, "img", "ss6.png", 0),   # Post-call actions             ("call back ... WhatsApp reply")
    (42.45, 45.57, "img", "ss7.png", 0),   # Known, unknown, delivery, bank ("delivery wale call ...")
    (47.30, 50.45, "img", "ss8.png", 0),   # 9+ Indian languages           ("9 se zyada languages")
    (56.40, 58.36, "ai", "meet", 2.55),    # "apne call ke liye ek assistant rakhte hain" -> the assistant
    (66.05, 67.59, "ai", "night", 2.95),   # "mera assistant handle kar lega" -> the assistant takes it
]
NIGHT_FIX = "delogo=x=2:y=1006:w=56:h=108"   # partial laptop-maker logo the model drew on the lid
INTRO = [(0.0, 2.55, "meet", 1.25), (2.55, 5.10, "tread", 1.45), (5.10, E["intro_end"], "night", 1.35)]


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        sys.exit(" ".join(map(str, cmd))[:500] + "\n" + p.stderr[-1500:])


def face(sid):
    a, b = SEG[sid]["cam"]
    pts = [FACES[f"{t:.2f}"] for t in (a + 0.15, (a + b) / 2, b - 0.15) if f"{t:.2f}" in FACES]
    return sum(p[0] for p in pts) / len(pts) * 2, sum(p[1] for p in pts) / len(pts) * 2   # 4K space


def crop(sid, z):
    fx, fy = face(sid)
    fx += XSHIFT.get(sid, 0)
    ch = 2160 / z; cw = ch * 9 / 16
    x = min(max(fx - cw / 2, 0), 3840 - cw)
    y = min(max(fy - 0.36 * ch, 0), 2160 - ch)
    return f"crop={int(cw)}:{int(ch)}:{int(x)}:{int(y)}"


shots = [("ai", a, b, {"clip": c, "in": i}) for a, b, c, i in INTRO]
for sid, s in SEG.items():
    a, b = s["out"]
    marks = sorted({a, b} | {t for t, _ in PUNCH.get(sid, [])} | {t for c in CUT for t in c[:2] if a < t < b})
    for t0, t1 in zip(marks, marks[1:]):
        cut = next((c for c in CUT if c[0] <= t0 + 1e-6 and t1 <= c[1] + 1e-6), None)
        if cut:
            kind, srcname, src_in = cut[2], cut[3], cut[4]
            if kind == "img":
                shots.append(("img", t0, t1, {"file": PLAY / srcname, "first": abs(t0 - cut[0]) < 1e-6,
                                             "into": t0 - cut[0], "len": cut[1] - cut[0]}))
            else:
                shots.append(("ai", t0, t1, {"clip": srcname, "in": src_in + (t0 - cut[0])}))
        else:
            z = ZOOM[sid]
            for t, pz in PUNCH.get(sid, []):
                if t0 >= t - 1e-6:
                    z = pz
            shots.append(("cam", t0, t1, {"sid": sid, "src": s["cam"][0] + (t0 - a), "z": z}))
shots.append(("end", E["end_card"][0], E["end_card"][1], {}))

wd = ED / "shots"; wd.mkdir(exist_ok=True)
ENC = ["-an", "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p", "-r", str(FPS)]
files, t_out = [], 0.0
for i, (kind, a, b, p) in enumerate(shots):
    n = round((b - a) * FPS)                       # whole frames so cues never drift
    d = n / FPS
    f = wd / f"{i:03d}_{kind}.mkv"
    if kind == "ai":
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{p['in']:.3f}", "-i", str(AI[p["clip"]]), "-frames:v", str(n),
             "-vf", f"fps={FPS},scale=1080:1920:flags=lanczos,{NIGHT_FIX if p['clip'] == 'night' else 'null'},setsar=1", *ENC, str(f)])
    elif kind == "cam":
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{p['src']:.3f}", "-i", str(CAM), "-frames:v", str(n),
             "-vf", f"fps={FPS},{crop(p['sid'], p['z'])},scale=1080:1920:flags=lanczos,eq=contrast=1.04:saturation=1.06,setsar=1",
             *ENC, str(f)])
    elif kind == "img":
        L = round(p["len"] * FPS); o = round(p["into"] * FPS)
        # settle 1.06 -> 1.0 over 6 frames on entry, then a slow push to ~1.04 across the whole cutaway
        z = f"if(lt(on+{o},6),1.06-0.01*(on+{o}),1+0.04*(on+{o}-6)/{max(L - 6, 1)})"
        run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(p["file"]), "-frames:v", str(n), "-vf",
             f"scale=2160:3840,zoompan=z='{z}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps={FPS},setsar=1",
             *ENC, str(f)])
    else:
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:r={FPS}", "-frames:v", str(n), *ENC, str(f)])
    files.append(f)
    print(f"  {i:02d} {kind:4s} {a:6.2f}-{b:6.2f} ({n} fr) {p.get('sid', p.get('clip', Path(str(p.get('file', ''))).name))}"
          + (f" z{p['z']}" if kind == "cam" else ""), flush=True)
    t_out += d

(wd / "concat.txt").write_text("".join(f"file '{f.as_posix()}'\n" for f in files), encoding="utf-8")
run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(wd / "concat.txt"), "-c", "copy",
     str(ED / "base_video.mkv")])
json.dump([[k, a, b] for k, a, b, _ in shots], open(ED / "shots.json", "w"), indent=0)
print(f"base_video.mkv {t_out:.2f}s from {len(files)} shots")
