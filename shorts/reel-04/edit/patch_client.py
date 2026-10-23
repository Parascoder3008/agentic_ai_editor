"""One-off: turn compose_base.py into the client (@venomstech) version — client reel + product B-roll, Clauditing palette,
film strip, before/after wipe, crash zooms, serif cinematic title. compose_base_paras.py keeps the old version."""
from pathlib import Path

p = Path(__file__).with_name("compose_base.py")
s = p.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)


rep(r'''REEL = r"C:\Users\PARAS ARORA\AI_Editor\shorts\reel-03\REEL03_instagram.mp4"
BRIGHT = np.array([58, 176, 216], np.float32)''',
    '''CR = JOB / "client_reels"                                # the client's own reels (@venomstech)
REEL = CR / "rtx5090_pc.mp4"
BRIGHT = np.array([240, 106, 140], np.float32)          # client style (Clauditing ref): pink accent
CORAL = np.array([242, 162, 126], np.float32)''')
rep("REEL_IN, REEL_OFF = (10.45, 10.85), 3.6",
    "REEL_IN, REEL_OFF = (10.45, 10.85), 34.5        # his 12-lakh product cards land on 'graphics'")
rep("SHOTS = [(32.07, 33.07, 0, 160), (33.07, 34.07, 1650, 1720), (34.07, 35.80, 3803, 6600)]   # hub page y pans",
    '''PANELS = [(100, 400, 880, 460, CR / "ps5_pc.mp4", 15.0, 0.42, 32.07),          # x, y, w, h, clip, start, crop-centre y, in
          (100, 990, 880, 460, CR / "laptop_vs_pc.mp4", 32.0, 0.50, 32.25)]   # product B-roll from his reels, on cream
WIPE = (29.40, 29.80)                                   # before/after wipe into the paper world (line drawn in gfx)
PUNCH = [(4.37, 0.16), (46.05, 0.12), (54.37, 0.12)]    # crash zooms on the pitch-drop hits (time, amount)''')
rep("def card(dst, img, x, y, w, h, r, glow=1.0):", '''def filmstrip(w, h):
    """black film strip around a card: 34 px side rails with sprocket holes, 14 px top/bottom"""
    fs = np.zeros((h + 28, w + 68, 4), np.float32); fs[..., 3] = 1
    for yy in range(18, h + 10, 38):
        for xx in (10, w + 44):
            cv2.rectangle(fs, (xx, yy), (xx + 14, yy + 20), (243, 237, 228, 1), -1, cv2.LINE_AA)
    return fs


def card(dst, img, x, y, w, h, r, glow=1.0, strip=False):''')
rep('''    w, h = max(2, int(round(w))), max(2, int(round(h)))
    sm = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)''', '''    w, h = max(2, int(round(w))), max(2, int(round(h)))
    sm = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    if strip:
        fs = filmstrip(w, h)
        paste(dst, fs[..., :3], x - 34, y - 14, fs[..., 3:])
        paste(dst, sm, x, y)
        return''')
a = s[s.index("# ---- text-behind title"):s.index("# ---- cut-out (paper-cut")]
rep(a, r'''# ---- text-behind title: heavy white "AI EDITOR" -> on "cinematic" a serif italic "AI editor." in coral->pink with glow
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


''')
rep('''            (lay, glow, lines) = tl
            i = min(len(cut1) - 1, int(round((t - M1[0]) * FPS)))
            pa = cut1[i][..., 3:4].astype(np.float32) / 255
            under = f.copy()
            if glow is not None:
                under = under * (1 - glow) + BRIGHT * glow
                under = under * (1 - lines) + 255 * lines
            under''', '''            (lay, glow) = tl
            i = min(len(cut1) - 1, int(round((t - M1[0]) * FPS)))
            pa = cut1[i][..., 3:4].astype(np.float32) / 255
            under = f * (1 - glow) + BRIGHT * glow
            under''')
rep('''    hub = np.array(Image.open(JOB / "assets" / "broll" / "hub_full.png").convert("RGB"))
    hub = np.concatenate([np.broadcast_to(hub[4:5, :, :], (380, W, 3)), hub])     # page starts below the prompt bar''',
    '''    cream = np.array(Image.open(JOB / "assets" / "cream_bg.png").convert("RGB"), np.float32)
    span = BACK[1] - BROLL + 0.4
    pclips = []
    for (px, py, pw, ph, clip, st, cy, _) in PANELS:             # crop each 720x1280 clip to the panel's aspect, then scale
        ch = int(720 * ph / pw) // 2 * 2; y0 = int(1280 * cy - ch / 2)
        pclips.append([np.ascontiguousarray(fr[y0:y0 + ch]) for fr in frames(clip, st, span, (720, 1280))])''')
rep("card(frame, reel[ri].astype(np.float32), RC[0], RC[1] + (1 - v) * 1150, RC[2], RC[3], 30)",
    "card(frame, reel[ri].astype(np.float32), RC[0], RC[1] + (1 - v) * 1150, RC[2], RC[3], 30, strip=True)")
rep('''        if BYE <= t < 37.37:
            z = 1 + 0.09 * ease(clamp((t - BYE) / 0.14))''', '''        if BYE <= t < 37.37:
            z = 1 + 0.09 * ease(clamp((t - BYE) / 0.14))
        for pt, amt in PUNCH:                                   # crash zoom: in over 2 frames, settle over 0.5 s
            if pt <= t < pt + 0.6:
                u = t - pt
                z *= 1 + amt * (min(1.0, u / 0.07) if u < 0.07 else max(0.0, 1 - (u - 0.07) / 0.5) ** 2)''')
rep('''            frame = canvas
            if t >= BACK[1]:''', '''            frame = canvas
            if t < WIPE[1]:                                               # wipe: paper revealed right -> left
                xl = int(W * (1 - prog(t, *WIPE)))
                frame = canvas.copy(); frame[:, :xl] = f[:, :xl]
            if t >= BACK[1]:''')
rep('''            if t >= BROLL - 0.2:
                bv = prog(t, BROLL - 0.2, BROLL) * (1 - prog(t, *BACK))
                sh = next((sh for sh in SHOTS if sh[0] <= t < sh[1]), SHOTS[-1] if t >= SHOTS[-1][0] else SHOTS[0])
                py = sh[2] + (sh[3] - sh[2]) * ease(clamp((t - sh[0]) / (sh[1] - sh[0])))
                br = hub[int(py):int(py) + H].astype(np.float32)
                if br.shape[0] < H:
                    br = np.pad(br, ((0, H - br.shape[0]), (0, 0), (0, 0)))
                canvas = canvas * (1 - bv) + br * bv''', '''            if t >= BROLL - 0.2:
                bv = prog(t, BROLL - 0.2, BROLL) * (1 - prog(t, *BACK))
                br = cream.copy()
                for (px, py, pw, ph, _, _, _, tin), clip in zip(PANELS, pclips):
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
                canvas = canvas * (1 - bv) + br * bv''')
p.write_text(s, encoding="utf-8")
print("compose_base.py -> client version")
