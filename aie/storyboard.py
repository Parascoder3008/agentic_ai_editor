"""The storyboard: one numbered row per beat for Paras to approve before anything renders (CLAUDE.md, "Clauditing").

Each row: the beat's time, the exact words spoken in it, its layout and source, a still framed the way the layout will
frame it with every planned caption, graphic and effect box drawn at its real position (and Instagram's UI zones), the
SFX in it, and its note. Written to build/storyboard.html (opens by double-click) and build/storyboard.json (the web
app's storyboard screen reads it).
"""
import html
import json
import subprocess
from pathlib import Path

from .captions import STYLE_DEFAULTS, zone_spans

VOID = (12, 14, 15)


def grab(src: Path, t: float):
    """One frame of a source at t seconds, as a PIL image (black when the source can't be read there)."""
    from PIL import Image
    import io
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(src), "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    try:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return None


def frame_for(layout: str, layouts: dict, im, size, zoom: float = 1.0):
    """The source frame framed by its layout at the output size: what picture.py will render, as a still."""
    from PIL import Image, ImageDraw
    W, H = size
    if im is None:
        im = Image.new("RGB", (W, H), (40, 44, 48))
    if layout == "face":
        cw, ch, cx, cy = layouts["face"]["crop"]
        return im.crop((cx, cy, cx + cw, cy + ch)).resize((W, H), Image.LANCZOS)
    if layout == "split":
        sp = layouts["split"]
        x, y, w, h = sp["card"]
        cw, ch, cx, cy = sp["crop"]
        out = Image.new("RGB", (W, H), VOID)
        card = im.crop((cx, cy, cx + cw, cy + ch)).resize((w, h), Image.LANCZOS)
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], sp.get("radius", 28), fill=255)
        out.paste(card, (x, y), mask)
        return out
    if layout == "camera":
        cam = layouts.get("camera", {})
        if cam.get("crop"):
            cw, ch, cx, cy = cam["crop"]
            im = im.crop((cx, cy, cx + cw, cy + ch))
        hx, hy = cam.get("head", (W // 2, H // 2))
        Wz, Hz = int(W * zoom) // 2 * 2, int(H * zoom) // 2 * 2
        x0, y0 = int(hx * zoom - hx), int(hy * zoom - hy)
        return im.resize((Wz, Hz), Image.LANCZOS).crop((x0, y0, x0 + W, y0 + H))
    return im.resize((W, H), Image.LANCZOS)


def beats(data: dict, pieces: list | None) -> list:
    """The beats in order: timeline segments, or the cut's pieces for a camera job."""
    if "timeline" in data:
        return [{"t": list(s["t"]), "layout": s["layout"], "src": s["src"], "in": s["in"], "speed": s.get("speed", 1.0),
                 "zoom": s.get("zoom", 1.0), "note": s.get("note", "")} for s in data["timeline"]]
    return [{"t": [p["out0"], round(p["out0"] + p["out"] - p["in"], 4)], "layout": "camera", "src": p["src"], "in": p["in"],
             "speed": 1.0, "zoom": p.get("zoom", 1.0), "note": p.get("text", p.get("note", ""))} for p in pieces]


def boxes(data: dict, beat: dict, catalog) -> list:
    """[(label, [x0, y0, x1, y1], colour)] of everything planned on screen during the beat."""
    W, H = data["size"]
    t0, t1 = beat["t"]
    out = []
    g = data.get("graphics")
    if g and beat["layout"] == "split":
        out.append(("graphics (stage)", [0, 0, W, 960], (58, 176, 216)))
    for i, p in enumerate(data.get("effects", [])):
        fx = catalog.get(p["effect"])
        if not fx:
            continue
        dur = p.get("dur", fx.data.get("duration", {}).get("default", 1.0))
        if p["at"] >= t1 or p["at"] + dur <= t0:
            continue
        vals = fx.filled(p.get("params", {}))
        text = next((str(v) for k, v in vals.items() if fx.kind_of(k) == "text" and v and k not in ("BG", "COLOR", "SIDE")), "")
        label = f"#{i + 1} {fx.data['title']} @{p['at']:.2f}" + (f": {html.unescape(text)[:28]}" if text else "")
        if fx.data.get("zone") == "stage":
            box = [0, 0, W, 960]
        else:
            y = float(vals.get("Y", 250))
            box = [90, int(y), 930, int(y) + 180]
        out.append((label, box, (255, 210, 60)))
    cap = data.get("captions") or {}
    hidden = any(a <= (t0 + t1) / 2 < b for a, b in cap.get("hide", []))
    if "words" in cap and cap.get("burn", True) and not hidden:
        style = "Cap" if "Cap" in cap.get("styles", {}) else next(iter(cap.get("styles", {})), None)
        for name, a, b, _lead in zone_spans(cap, data):
            if a <= (t0 + t1) / 2 < b:
                style = name
        st = {**STYLE_DEFAULTS, **cap.get("styles", {}).get(style, {})} if style else dict(STYLE_DEFAULTS)
        base = st.get("baseline", H - 60)
        ml, mr = st["margins"]
        out.append((f"captions ({style or 'default'})", [ml, int(base - st["size"] * 1.25), W - mr, base], (255, 255, 255)))
    return out


def draw(still, items: list, size, scale_w: int, fonts: Path | None = None):
    from PIL import Image, ImageDraw, ImageFont
    W, H = size
    k = scale_w / W
    im = still.resize((scale_w, int(H * k)), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype(str(Path(fonts) / "Inter-SemiBold.ttf"), 13)
    except (OSError, TypeError):
        font = ImageFont.load_default()
    if H > W:                                            # Instagram's UI covers these
        d.line([(0, 200 * k), (im.width, 200 * k)], fill=(230, 60, 60))
        d.line([(0, 1560 * k), (im.width, 1560 * k)], fill=(230, 60, 60))
        d.rectangle([930 * k, 1000 * k, im.width - 1, 1700 * k], outline=(230, 60, 60))
    for label, (x0, y0, x1, y1), col in items:
        d.rectangle([x0 * k, y0 * k, x1 * k - 1, y1 * k - 1], outline=col, width=2)
        tw = d.textlength(label, font=font)
        d.rectangle([x0 * k + 2, y0 * k + 2, min(im.width - 2, x0 * k + 10 + tw), y0 * k + 21], fill=(0, 0, 0))
        d.text((x0 * k + 6, y0 * k + 4), label, fill=col, font=font)
    return im


def page(data: dict, rows: list) -> str:
    """The storyboard as one HTML page in the brand (void, blue, Inter)."""
    e = html.escape
    trs = []
    for r in rows:
        fx = "".join(f"<li>{e(x)}</li>" for x in r["on_screen"]) or "<li class=m>nothing planned</li>"
        sfx = ", ".join(f"{c['kind']} @{c['t']:.2f}" for c in r["sfx"]) or "none"
        trs.append(f"""<article><img src="{e(r['still'])}" alt="beat {r['n']} still"><div>
<h2><span>{r['n']:02d}</span> {r['t'][0]:.2f}&ndash;{r['t'][1]:.2f} s <small>{r['t'][1] - r['t'][0]:.2f} s</small></h2>
<p class=w>{e(r['words']) or '<i>no words</i>'}</p>
<dl><dt>Layout</dt><dd>{e(r['layout'])}</dd><dt>Source</dt><dd>{e(r['src'])} from {r['in']:.2f} s</dd>
<dt>On screen</dt><dd><ul>{fx}</ul></dd><dt>SFX</dt><dd>{e(sfx)}</dd><dt>Why</dt><dd>{e(r['note']) or '&ndash;'}</dd></dl>
</div></article>""")
    title = e(data.get("title") or data["id"])
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Storyboard: {title}</title><style>
body{{margin:0;background:#0C0E0F;color:#fff;font:15px/1.5 Inter,system-ui,sans-serif;padding:24px 16px 60px}}
main{{max-width:1000px;margin:0 auto;display:grid;gap:18px}} h1{{margin:0;font-size:28px;letter-spacing:-.02em}}
.lede{{color:#DFDDDF;margin:0 0 6px}} article{{display:grid;grid-template-columns:270px 1fr;gap:18px;background:#12171A;
border:1px solid #22303A;border-radius:28px;padding:16px}} img{{width:100%;border-radius:16px;display:block}}
h2{{margin:0 0 6px;font-size:18px}} h2 span{{color:#3AB0D8;font-variant-numeric:tabular-nums}} small{{color:#A9B4BC;font-weight:500}}
.w{{margin:0 0 10px;font-size:17px;color:#fff}} dl{{display:grid;grid-template-columns:90px 1fr;gap:4px 12px;margin:0}}
dt{{color:#3AB0D8;font-weight:600}} dd{{margin:0;color:#DFDDDF}} ul{{margin:0;padding-left:18px}} .m{{color:#A9B4BC}}
@media(max-width:640px){{article{{grid-template-columns:1fr}}}}</style></head><body><main>
<h1>Storyboard: {title}</h1>
<p class=lede>{len(rows)} beats, {rows[-1]['t'][1]:.2f} s. Reply by beat number ("Beat 4: full screen"); nothing renders until
<code>gates.storyboard_approved</code> is true. Red lines: Instagram's UI. Yellow: effects. Blue: the graphics stage. White: captions.</p>
{''.join(trs)}</main></body></html>"""


def write(path: Path, rows: list):
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
