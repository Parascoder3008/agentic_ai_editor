"""Clauditing storyboard: beats.json -> storyboard.html (double-click to open). One numbered row per beat with a
9:16 mock at true 1080x1920 positions (graphic zone, caption at the seam, avatar crop, IG UI zones hatched),
the words, layout, visual, SFX and why. Click a row to hear that beat in the preview audio.
Usage: python storyboard.py <beats.json> <out.html>
beats.json: {"title","audio","look","look_y0","hooks":[...],"directions":[{"name","pitch"}],"beats":[{n,t0,t1,words,
             layout: split|face|full, text, visual, caption, sfx, why}]}"""
import html
import json
import sys
from pathlib import Path

S = 0.25                                    # mock scale: 1080x1920 -> 270x480
SEAM = 960                                  # top graphic zone / avatar boundary (px, 1080x1920 space)
LOOK_W = 1216                               # HeyGen portrait look preview width


def px(v):
    return f"{v * S:.0f}px"


def mock(b, look, look_y0):
    k = 1080 / LOOK_W * S                   # look scaled to frame width
    y0 = 0 if b["layout"] == "face" else look_y0
    face = f"background:url({look}) 0 {-y0 * k:.0f}px/100% auto no-repeat"     # unquoted: lives inside style='...'
    gfx = (f"<div class=gfx style='top:{px(200)};height:{px(SEAM - 260)}'><b>{html.escape(b.get('text', ''))}</b>"
           f"<i>{html.escape(b.get('visual', ''))}</i></div>")
    if b.get("still"):                      # a real frame (e.g. a generated hook shot) instead of a sketch
        layers = f"<div class=av style='top:0;height:100%;background:url({b['still']}) center/cover'></div>"
    elif b["layout"] == "face":
        layers = f"<div class=av style='top:0;height:100%;{face}'></div>"
    elif b["layout"] == "full":
        layers = (f"<div class=bg></div>{gfx}<div class=bubble style='left:{px(690)};top:{px(220)};width:{px(220)};"
                  f"height:{px(220)};{face.replace('100% auto', '220% auto')}'></div>")
    else:
        layers = f"<div class=bg style='height:{px(SEAM)}'></div>{gfx}<div class=av style='top:{px(SEAM)};height:{px(1920 - SEAM)};{face}'></div>"
    cap = b.get("caption")
    full_frame = b["layout"] == "face" or b.get("still")
    cap_y = 1380 if full_frame else SEAM - 50       # full-frame shots: captions below the face, above IG UI
    caption = f"<div class=cap style='top:{px(cap_y)}'>{html.escape(cap)}</div>" if cap else ""
    ui = (f"<div class=ui style='left:0;top:0;width:100%;height:{px(200)}'></div>"
          f"<div class=ui style='left:{px(930)};top:{px(1000)};width:{px(150)};height:{px(700)}'></div>"
          f"<div class=ui style='left:0;top:{px(1560)};width:100%;height:{px(360)}'></div>")
    return f"<div class=frame>{layers}{caption}{ui}</div>"


def build(spec):
    rows = "".join(
        f"<tr onclick='play({b['t0']},{b['t1']})'><td class=n>{b['n']}</td><td>{mock(b, spec['look'], spec.get('look_y0', 0))}</td>"
        f"<td><div class=t>{b['t0']:.1f}–{b['t1']:.1f}s · {b['layout']}</div><p class=w>“{html.escape(b['words'])}”</p>"
        f"<p><span>Visual</span>{html.escape(b['visual'])}</p><p><span>SFX</span>{html.escape(b.get('sfx', '—'))}</p>"
        f"<p><span>Why</span>{html.escape(b['why'])}</p></td></tr>" for b in spec["beats"])
    hooks = "".join(f"<li>{html.escape(h)}</li>" for h in spec.get("hooks", []))
    dirs = "".join(f"<li><b>{html.escape(d['name'])}</b> {html.escape(d['pitch'])}</li>" for d in spec.get("directions", []))
    return f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{html.escape(spec['title'])}</title><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel=stylesheet>
<style>
:root{{--void:#0C0E0F;--blue:#1A9FD1;--bright:#3AB0D8;--navy:#11324C;--text:#fff;--muted:#DFDDDF}}
body{{margin:0;background:var(--void);color:var(--text);font:15px/1.5 Inter,system-ui,sans-serif;padding:24px 16px}}
.wrap{{max-width:980px;margin:auto}} h1{{font-weight:800;margin:0 0 4px}} .sub{{color:var(--muted);margin:0 0 20px}}
.panel{{background:rgba(17,50,76,.35);border:1px solid rgba(58,176,216,.25);border-radius:28px;padding:18px 22px;margin:0 0 18px}}
.panel ol,.panel ul{{margin:6px 0 0;padding-left:20px}} audio{{width:100%;margin-top:8px}}
table{{width:100%;border-collapse:separate;border-spacing:0 14px}} tr{{cursor:pointer}}
td{{vertical-align:top;background:rgba(17,50,76,.25);padding:14px}} td:first-child{{border-radius:28px 0 0 28px}} td:last-child{{border-radius:0 28px 28px 0}}
.n{{font:800 34px Inter;color:var(--bright);width:40px;text-align:center}} .t{{color:var(--bright);font-weight:600}}
.w{{font-size:17px;font-weight:600;margin:6px 0}} p span{{display:inline-block;min-width:54px;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}}
.frame{{position:relative;width:270px;height:480px;overflow:hidden;border-radius:14px;background:#000}}
.frame>div{{position:absolute}} .bg{{left:0;top:0;width:100%;height:100%;background:radial-gradient(circle at 50% 30%,#11324C,#0C0E0F 70%)}}
.av{{left:0;width:100%}} .gfx{{left:{px(90)};width:{px(840)};display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:6px}}
.gfx b{{font:800 20px Inter;color:#fff;text-shadow:0 0 12px rgba(26,159,209,.6)}} .gfx i{{font:400 10px Inter;color:var(--muted);font-style:normal}}
.cap{{left:{px(90)};width:{px(840)};text-align:center;font:800 15px Inter;color:#fff;text-shadow:0 2px 4px #000}}
.bubble{{border-radius:50%;border:2px solid var(--bright)}} .ui{{background:repeating-linear-gradient(45deg,rgba(255,80,80,.18) 0 4px,transparent 4px 9px)}}
tr.on td{{background:rgba(26,159,209,.25)}} @media(max-width:640px){{td{{display:block;border-radius:28px!important}} tr{{display:block}}}}
</style></head><body><div class=wrap>
<h1>{html.escape(spec['title'])}</h1><p class=sub>Nothing is rendered yet. Reply with beat numbers ("Beat 4: …"). Click a row to hear it. Red hatching = Instagram UI.</p>
<div class=panel><b>Preview audio</b><audio id=a controls src="{html.escape(spec['audio'])}"></audio></div>
<div class=panel><b>Directions</b><ol>{dirs}</ol></div>
<div class=panel><b>Hook options</b><ol>{hooks}</ol></div>
<table>{rows}</table></div>
<script>let stop=0;const a=document.getElementById('a');a.ontimeupdate=()=>{{if(stop&&a.currentTime>=stop){{a.pause();stop=0}}}};
function play(t0,t1){{a.currentTime=t0;stop=t1;a.play();document.querySelectorAll('tr').forEach(r=>r.classList.remove('on'));event.currentTarget.classList.add('on')}}</script>
</body></html>"""


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = build(spec)
    assert out.count("<tr ") == len(spec["beats"]), "one row per beat"
    Path(sys.argv[2]).write_text(out, encoding="utf-8")
    print(f"{len(spec['beats'])} beats -> {sys.argv[2]}")
