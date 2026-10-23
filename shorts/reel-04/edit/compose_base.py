"""Base layer of reel-04, frame by frame on the master timeline (1080x1920 @30). Everything the voice asks for that changes
the PICTURE lives here; text/UI graphics are the HyperFrames overlay on top.
  0-5.65    hook push-in            7.95-8.55  -> top-left card (he asked: "top left corner")
  10.45     his reel slides in below ("neeche laga de meri poori reel")       13.87-14.37  card -> full ("aage aa jaun")
  15.31     title rises BEHIND him (matte cut1), 17.30 morphs cinematic ("font cinematic"), out 19.50-19.75
  29.40     paper-cut world: white-border cut-out, stop-motion 10 fps (matte cut2)
  31.19     cut-out shrinks to a corner sticker ("ek side mein"), 32.07 product B-roll fills the screen ("screen par … B-roll")
  35.80     sticker grows back to full ("finally main aaun"), 36.86 punch-in on "bye"
Usage: python compose_base.py [t0 t1]   (optional range for a quick test render -> base_test.mp4)"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ED = Path(__file__).resolve().parent
JOB = ED.parent
TL = json.loads((ED / "timeline.json").read_text())
W, H, FPS = 1080, 1920, 30
N = int(round(TL["length"] * FPS))
HX, HY = 440, 760
FONTS = Path(r"C:\Users\PARAS ARORA\AI_Editor\fonts")
CR = JOB / "client_reels"                                # the client's own reels (@venomstech)
REEL = CR / "rtx5090_pc.mp4"
BRIGHT = np.array([240, 106, 140], np.float32)          # client style (Clauditing ref): pink accent
CORAL = np.array([242, 162, 126], np.float32)

# ---- beat times (master seconds, from words_master.json)
PUSH = (0.0, 5.65)
PIP_IN, PIP_OUT = (7.95, 8.55), (13.87, 14.37)
PIP = (70, 360, 380, 676)                       # x, y, w, h of the face card
RC = (500, 790, 420, 747)                       # reel card
REEL_IN, REEL_OFF = (10.45, 10.85), 34.5        # his 12-lakh product cards land on 'graphics'
TB_IN, TB_MORPH, TB_OUT = 15.31, 17.30, (19.50, 19.75)
M1 = (15.0, 19.75)                              # cut1.webm covers this master window
PAPER, SIDE, BROLL, BACK, BACK_END = 29.40, (31.19, 31.64), 32.07, (35.80, 36.06), 36.10
M2 = (29.2, 36.1)                               # cut2.webm
STICK = (0.47, 60, 1010)                        # sticker scale and where the frame's top-left lands
BYE = 36.86
PANELS = [(100, 400, 880, 460, CR / "ddr5_ram.mp4", 32.3, 0.50, 32.07, 1.0),        # x, y, w, h, clip, start, crop-centre y,
          (100, 990, 880, 460, CR / "laptop_vs_pc.mp4", 32.05, 0.50, 32.25, 0.75)]  # in, speed: renders from his own reels
WIPE = (29.40, 29.80)                                   # before/after wipe into the paper world (line drawn in gfx)
PUNCH = [(4.37, 0.16), (46.05, 0.12), (54.37, 0.12)]    # crash zooms on the pitch-drop hits (time, amount)

ease = lambda u: 3 * u * u - 2 * u * u * u
clamp = lambda u: min(1.0, max(0.0, u))
prog = lambda t, a, b: ease(clamp((t - a) / (b - a)))


def frames(path, t0=0.0, dur=None, size=None, alpha=False, speed=1.0):
    cmd = ["ffmpeg", "-v", "error"] + (["-c:v", "libvpx-vp9"] if alpha else []) + ["-ss", f"{t0:.4f}", "-i", str(path)]
    vf = (f"setpts=PTS/{speed}," if speed != 1.0 else "") + f"fps={FPS}" + (f",scale={size[0]}:{size[1]}" if size else "")
    cmd += (["-t", f"{dur * speed:.4f}"] if dur else []) + ["-vf", vf,
                                                    "-f", "rawvideo", "-pix_fmt", "rgba" if alpha else "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    w, h = size or (W, H); c = 4 if alpha else 3
    while True:
        b = p.stdout.read(w * h * c)
        if len(b) < w * h * c:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w, c)


def rounded(w, h, r):
    m = np.zeros((h, w), np.uint8); cv2.rectangle(m, (r, 0), (w - r, h), 255, -1); cv2.rectangle(m, (0, r), (w, h - r), 255, -1)
    for cx, cy in ((r, r), (w - r - 1, r), (r, h - r - 1), (w - r - 1, h - r - 1)):
        cv2.circle(m, (cx, cy), r, 255, -1, cv2.LINE_AA)
    return m.astype(np.float32)[..., None] / 255


def paste(dst, src, x, y, a=None):
    """alpha-paste src (h,w,3) at (x,y) with alpha a (h,w,1 float), clipped to the frame"""
    h, w = src.shape[:2]; x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32)
    if a is None:
        dst[y0:y1, x0:x1] = s
    else:
        aa = a[y0 - y:y1 - y, x0 - x:x1 - x]
        dst[y0:y1, x0:x1] = dst[y0:y1, x0:x1] * (1 - aa) + s * aa


def zoom_about(img, z, cx=HX, cy=HY):
    if abs(z - 1) < 1e-4:
        return img
    M = np.float32([[z, 0, cx - z * cx], [0, z, cy - z * cy]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def filmstrip(w, h):
    """black film strip around a card: 34 px side rails with sprocket holes, 14 px top/bottom"""
    fs = np.zeros((h + 28, w + 68, 4), np.float32); fs[..., 3] = 1
    for yy in range(18, h + 10, 38):
        for xx in (10, w + 44):
            cv2.rectangle(fs, (xx, yy), (xx + 14, yy + 20), (243, 237, 228, 1), -1, cv2.LINE_AA)
    return fs


def card(dst, img, x, y, w, h, r, glow=1.0, strip=False):
    """face/reel card: shadow, 3 px bright-blue rim, rounded corners"""
    w, h = max(2, int(round(w))), max(2, int(round(h)))
    sm = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    if strip:
        fs = filmstrip(w, h)
        paste(dst, fs[..., :3], x - 34, y - 14, fs[..., 3:])
        paste(dst, sm, x, y)
        return
    m = rounded(w, h, max(1, int(r)))
    if glow > 0:
        sh = np.zeros((h + 80, w + 80), np.float32); sh[40:40 + h, 40:40 + w] = m[..., 0]
        sh = cv2.GaussianBlur(sh, (0, 0), 18)[..., None] * 0.55 * glow
        paste(dst, np.zeros((h + 80, w + 80, 3)), x - 40 + 8, y - 40 + 14, sh)
        rim = rounded(w + 6, h + 6, int(r) + 3) * glow
        paste(dst, np.broadcast_to(BRIGHT, (h + 6, w + 6, 3)), x - 3, y - 3, rim * 0.9)
    paste(dst, sm, x, y, m)


# ---- text-behind title: heavy white "AI EDITOR" -> on "cinematic" a serif italic "AI editor." in coral->pink with glow
F_BLACK = ImageFont.truetype(str(FONTS / "Inter-Black.ttf"), 205)
F_SERIF = ImageFont.truetype(r"C:\Windows\Fonts\SitkaVF-Italic.ttf", 236)
try:
    F_SERIF.set_variation_by_name("Banner Italic")
except Exception:
    pass


def _text_alpha(font, text, baseline, track=0.0):
    im = Image.new("L", (W, H), 0); d = ImageDraw.Draw(im)
    widths = [font.getlength(c) for c in text]
    x = (W - sum(widths) - track * (len(text) - 1)) / 2
    for c, cw in zip(text, widths):
        d.text((x, baseline), c, font=font, fill=255, anchor="ls"); x += cw + track
    return np.array(im, np.float32)[..., None] / 255


_A = {}


def title_layer(t):
    """(RGBA float layer, glow) or None. Baseline ~700: his head covers the middle letters."""
    if not (TB_IN <= t < TB_OUT[1]):
        return None
    if not _A:
        _A["black"] = _text_alpha(F_BLACK, "AI EDITOR", 700, -6)
        _A["serif"] = _text_alpha(F_SERIF, "AI editor.", 700)
    rise = ease(clamp((t - TB_IN) / 0.45)); m = ease(clamp((t - TB_MORPH) / 0.5)); fade = 1 - prog(t, *TB_OUT)
    dy = int((1 - rise) * 160)
    shift = lambda a: np.roll(a, dy, 0) if dy else a
    a = (shift(_A["black"]) * (1 - m) + shift(_A["serif"]) * m) * rise * fade
    g = np.clip((np.arange(H, dtype=np.float32) - 520) / 200, 0, 1)[:, None, None]
    col = 255 * (1 - m) + (CORAL * (1 - g) + BRIGHT * g) * m
    col = np.ascontiguousarray(np.broadcast_to(col, (H, W, 3)), dtype=np.float32)
    glow = cv2.GaussianBlur(a[..., 0], (0, 0), 26)[..., None] * 0.6 * m
    return np.concatenate([col, np.clip(a, 0, 1)], 2), glow


# ---- cut-out (paper-cut + sticker): white border + shadow, any affine
KER = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (29, 29))


def cutout_layers(rgba):
    a = rgba[..., 3].astype(np.float32) / 255
    border = cv2.GaussianBlur(cv2.dilate((a > 0.45).astype(np.uint8) * 255, KER), (0, 0), 1.2).astype(np.float32) / 255
    rgb = rgba[..., :3].astype(np.float32)
    col = rgb * a[..., None] + 255 * (1 - a[..., None])         # person over white = the paper border
    return col, border


def draw_cutout(dst, col, border, s, rot, tx, ty):
    M = cv2.getRotationMatrix2D((HX, HY), rot, s); M[0, 2] += tx; M[1, 2] += ty
    c = cv2.warpAffine(col, M, (W, H), flags=cv2.INTER_LINEAR)
    b = cv2.warpAffine(border, M, (W, H), flags=cv2.INTER_LINEAR)[..., None]
    sh = cv2.GaussianBlur(cv2.warpAffine(border, M, (W, H)), (0, 0), 14)
    sh = np.roll(np.roll(sh, int(16 * s + 4), 0), int(10 * s + 3), 1)[..., None] * 0.5
    dst[:] = dst * (1 - sh)
    dst[:] = dst * (1 - b) + c * b


def main():
    t_lo, t_hi = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) > 2 else (0.0, TL["length"])
    k0, k1 = int(round(t_lo * FPS)), min(N, int(round(t_hi * FPS)))
    bg_pip = np.array(Image.open(JOB / "assets" / "bg_pip.png").convert("RGB"), np.float32)
    paper = np.array(Image.open(JOB / "assets" / "paper_bg.png").convert("RGB"), np.float32)
    cream = np.array(Image.open(JOB / "assets" / "cream_bg.png").convert("RGB"), np.float32)
    span = BACK[1] - BROLL + 0.4
    pclips = []
    for (px, py, pw, ph, clip, st, cy, _, spd) in PANELS:        # crop each 720x1280 clip to the panel's aspect, then scale
        ch = int(720 * ph / pw) // 2 * 2; y0 = int(1280 * cy - ch / 2)
        pclips.append([np.ascontiguousarray(fr[y0:y0 + ch]) for fr in frames(clip, st, span, (720, 1280), speed=spd)])
    reel = list(frames(REEL, REEL_OFF, PIP_OUT[1] - REEL_IN[0] + 0.2, (RC[2], RC[3])))
    cut1 = list(frames(ED / "matte" / "cut1.webm", alpha=True))
    cut2 = list(frames(ED / "matte" / "cut2.webm", alpha=True))
    print("reel", len(reel), "cut1", len(cut1), "cut2", len(cut2), flush=True)
    out = ED / ("base_test.mp4" if len(sys.argv) > 2 else "base_video.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", str(out)],
                           stdin=subprocess.PIPE)
    cache2 = {}
    for k, face in enumerate(frames(ED / "base_face.mp4", t_lo, (k1 - k0) / FPS), start=k0):
        if k >= k1:
            break
        t = k / FPS
        f = face.astype(np.float32)
        # hook push-in + bye punch (zoom about the head)
        z = 1 + 0.05 * prog(t, *PUSH) if t < PIP_IN[0] else 1.0
        if BYE <= t < 37.37:
            z = 1 + 0.09 * ease(clamp((t - BYE) / 0.14))
        for pt, amt in PUNCH:                                   # crash zoom: in over 2 frames, settle over 0.5 s
            if pt <= t < pt + 0.6:
                u = t - pt
                z *= 1 + amt * (min(1.0, u / 0.07) if u < 0.07 else max(0.0, 1 - (u - 0.07) / 0.5) ** 2)
        if z != 1.0:
            f = zoom_about(f, z)
        frame = f
        # ---- card layout: he goes to the top-left corner, his reel plays below
        if PIP_IN[0] <= t < PIP_OUT[1]:
            u = prog(t, *PIP_IN) * (1 - prog(t, *PIP_OUT))
            frame = bg_pip.copy()
            x, y = PIP[0] * u, PIP[1] * u
            w, h = W + (PIP[2] - W) * u, H + (PIP[3] - H) * u
            if t >= REEL_IN[0]:
                v = prog(t, *REEL_IN) * (1 - prog(t, PIP_OUT[0], PIP_OUT[0] + 0.3))
                ri = min(len(reel) - 1, int((t - REEL_IN[0]) * FPS))
                card(frame, reel[ri].astype(np.float32), RC[0], RC[1] + (1 - v) * 1150, RC[2], RC[3], 30, strip=True)
            card(frame, f, x, y, w, h, 34 * u, glow=u)
        # ---- title behind him
        tl = title_layer(t)
        if tl is not None and M1[0] <= t < M1[1]:
            (lay, glow) = tl
            i = min(len(cut1) - 1, int(round((t - M1[0]) * FPS)))
            pa = cut1[i][..., 3:4].astype(np.float32) / 255
            under = f * (1 - glow) + BRIGHT * glow
            under = under * (1 - lay[..., 3:]) + lay[..., :3] * lay[..., 3:]
            frame = f * pa + under * (1 - pa)
        # ---- paper cut -> sticker over product B-roll -> back
        if PAPER <= t < BACK_END:
            stop = t < SIDE[0]
            tk = PAPER + int((t - PAPER) * 10) / 10 if stop else t          # stop-motion: pose held 3 frames
            i = min(len(cut2) - 1, int(round((tk - M2[0]) * FPS)))
            if i not in cache2:
                cache2.clear(); cache2[i] = cutout_layers(cut2[i])
            col, border = cache2[i]
            step = int((t - PAPER) * 10)
            rot = (1.3 if step % 2 else -1.1) if stop else 0.0
            jx, jy = ((step * 37) % 7 - 3, (step * 53) % 7 - 3) if stop else (0, 0)
            pop = 1 + 0.05 * (1 - ease(clamp((t - PAPER) / 0.18)))
            sv = prog(t, *SIDE) * (1 - prog(t, *BACK))
            s = pop * (1 + (STICK[0] - 1) * sv)
            tx = STICK[1] * sv - (s - 1) * 0
            ty = (STICK[2] - HY * (1 - STICK[0]) * 0) * sv
            canvas = paper.copy()
            if t >= BROLL - 0.2:
                bv = prog(t, BROLL - 0.2, BROLL) * (1 - prog(t, *BACK))
                br = cream.copy()
                for (px, py, pw, ph, _, _, _, tin, _), clip in zip(PANELS, pclips):
                    if t < tin:
                        continue
                    pv = ease(clamp((t - tin) / 0.3))
                    fi = min(len(clip) - 1, int((t - BROLL) * FPS))
                    sc = 0.86 + 0.14 * pv
                    w2, h2 = pw * sc, ph * sc
                    xx, yy = px + (pw - w2) / 2, py + (ph - h2) / 2 + (1 - pv) * 60
                    m = rounded(int(w2) + 16, int(h2) + 16, 30)
                    paste(br, np.full((int(h2) + 16, int(w2) + 16, 3), 255.0), xx - 8, yy - 8, m * pv)      # white frame
                    card(br, clip[fi].astype(np.float32), xx, yy, w2, h2, 24, glow=0)
                canvas = canvas * (1 - bv) + br * bv
            # sticker geometry: scale about the head, then move so the head sits bottom-left
            hx_t, hy_t = 230, 1390
            mx = (hx_t - HX) * sv; my = (hy_t - HY) * sv
            draw_cutout(canvas, col, border, s, rot, mx + jx, my + jy)
            frame = canvas
            if t < WIPE[1]:                                               # wipe: paper revealed right -> left
                xl = int(W * (1 - prog(t, *WIPE)))
                frame = canvas.copy(); frame[:, :xl] = f[:, :xl]
            if t >= BACK[1]:                                              # hand back to the real frame
                frame = canvas * (1 - prog(t, BACK[1], BACK_END)) + f * prog(t, BACK[1], BACK_END)
        enc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
        if k % 150 == 0:
            print(f"  {t:6.2f}s", flush=True)
    enc.stdin.close(); enc.wait()
    print("->", out)


if __name__ == "__main__":
    main()
