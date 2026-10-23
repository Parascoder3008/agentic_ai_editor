"""Graphics layer (HyperFrames, transparent 1080x1920) for the Equal ad. Times come from edl.json + words_fa.json.
Writes gfx/index.html; render with: npx --yes hyperframes render . --format webm -o gfx.webm  (inside gfx/)."""
import json
import shutil
from pathlib import Path

ED = Path(__file__).resolve().parent
G = ED / "gfx"; (G / "assets").mkdir(parents=True, exist_ok=True)
shutil.copy(ED / "play" / "icon.png", G / "assets" / "icon.png")
for f in ("hyperframes.json",):
    shutil.copy(Path(r"C:\Users\PARAS ARORA\AI_Editor\shorts\pilot-01\gfx\top") / f, G / f)
(G / "meta.json").write_text(json.dumps({"id": "equal_ad", "name": "equal_ad", "createdAt": "2026-10-12T08:00:00.000Z"}))

E = json.loads((ED / "edl.json").read_text(encoding="utf-8"))
W = json.loads((ED / "words_fa.json").read_text(encoding="utf-8"))
SEG = {s["id"]: s for s in E["body"]}
L = E["length"]


def w(sid, text, n=1):
    """start of the n-th word `text` in line sid"""
    k = 0
    for x in W[sid]:
        if x["text"].strip(",.?!").lower() == text.lower():
            k += 1
            if k == n:
                return x["start"]
    raise KeyError((sid, text, n))


T = {
    # intro: phone lights at clip ~2.1 s -> output 0.96 / 3.22 / 5.87; the assistant reacts ~0.7 s later
    "c1_in": 0.96, "c1_eq": 1.66, "c1_out": 2.45,
    "c2_in": 3.20, "c2_eq": 3.95, "c2_out": 5.00,
    "c3_in": 5.88, "c3_eq": 6.55, "c3_msg": 7.55, "c3_out": E["intro_end"] - 0.12,
    "logo": w("s2", "Equal"), "logo_out": SEG["s2"]["out"][1] - 0.05,
    "salary": w("s1", "salary"), "salary_x": w("s1", "nahi"), "salary_out": SEG["s1"]["out"][1],
    "ai_in": SEG["s8"]["out"][0], "ai_out": SEG["s8"]["out"][1],
    "ins_in": w("s9", "instruction"), "ins_type": w("s9", "kaun"), "ins_out": 42.40,
    "cnt_in": w("s12", "India") - 0.1, "cnt_out": SEG["s12"]["out"][1] - 0.05,
    "pa_in": w("s13", "phone"), "pa_out": SEG["s13"]["out"][1] - 0.05,
    "play": w("s14", "Play"), "apple": w("s14", "App", 1) if False else 62.92, "badges_out": SEG["s14"]["out"][1],
    "r_in": w("s15", "phir") - 0.15, "r_eq": w("s15", "koi"), "r_out": E["end_card"][0],
    "end": E["end_card"][0],
}
AI_WORDS = [(x["text"], x["start"]) for x in W["s8"]]

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800;900&display=block" rel="stylesheet" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 1080px; height: 1920px; overflow: hidden; background: transparent; }
#root { position: relative; width: 1080px; height: 1920px; font-family: Poppins, sans-serif; color: #fff; }
.abs { position: absolute; }
/* incoming-call banner (top of screen, like a real notification) */
.ban { left: 50px; width: 980px; top: 235px; height: 190px; border-radius: 40px; overflow: hidden;
  box-shadow: 0 18px 50px rgba(0,0,0,.45); }
.ban .st { position: absolute; inset: 0; padding: 34px 38px; display: flex; align-items: center; gap: 28px; }
.ban .call { background: rgba(22,24,27,.94); }
.ban .eq { background: linear-gradient(135deg, #12B347 0%, #3B9802 100%); opacity: 0; }
.av { width: 112px; height: 112px; border-radius: 50%; flex: none; display: flex; align-items: center; justify-content: center; }
.call .av { background: #3A3F45; font-size: 58px; font-weight: 700; color: #C9CED4; }
.eq .av { background: #fff; }
.eq .av img { width: 112px; height: 112px; border-radius: 50%; }
.tx { flex: 1; min-width: 0; }
.k { font-size: 27px; font-weight: 600; opacity: .8; letter-spacing: .02em; }
.n { font-size: 44px; font-weight: 800; line-height: 1.15; white-space: nowrap; }
.btns { display: flex; gap: 22px; }
.btn { width: 84px; height: 84px; border-radius: 50%; }
.btn.r { background: #FF3B30; } .btn.g { background: #34C759; }
.dots span { display: inline-block; width: 14px; height: 14px; border-radius: 50%; background: #fff; margin-left: 8px; }
.msg { position: absolute; left: 50px; width: 980px; top: 445px; padding: 30px 40px 34px; border-radius: 34px;
  background: #fff; color: #0E2A12; box-shadow: 0 18px 50px rgba(0,0,0,.35); }
.msg .k { color: #12B347; opacity: 1; font-weight: 700; }
.msg .m { font-size: 42px; font-weight: 700; line-height: 1.25; margin-top: 6px; }
/* stickers / pills */
.pill { display: inline-flex; align-items: center; gap: 18px; padding: 18px 34px 20px; border-radius: 999px;
  background: #12B347; font-weight: 800; font-size: 44px; box-shadow: 0 14px 40px rgba(0,0,0,.35); white-space: nowrap; }
#logo { left: 425px; top: 1000px; width: 230px; height: 230px; border-radius: 56px; overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,.45); }
#logo img { width: 230px; height: 230px; }
#salary { left: 0; right: 0; top: 1010px; text-align: center; }
#salary .s { position: relative; display: inline-block; font-size: 120px; font-weight: 900; letter-spacing: -.02em;
  padding: 0 34px; background: rgba(14,16,18,.82); border-radius: 30px; }
#salary .x { position: absolute; left: 20px; top: 50%; height: 16px; width: 0; border-radius: 8px; background: #FF3B30; }
/* AI voice card */
#ai { left: 100px; width: 830px; top: 1060px; padding: 34px 40px 40px; border-radius: 40px;
  background: linear-gradient(135deg, #12B347 0%, #3B9802 100%); box-shadow: 0 20px 60px rgba(0,0,0,.45); }
#ai .hd { display: flex; align-items: center; gap: 18px; font-size: 32px; font-weight: 700; }
#ai .hd img { width: 64px; height: 64px; border-radius: 16px; }
#ai .wave { display: flex; gap: 8px; align-items: center; height: 60px; margin-left: auto; }
#ai .wave i { display: block; width: 10px; height: 20px; border-radius: 5px; background: #fff; }
#ai .q { font-size: 52px; font-weight: 800; line-height: 1.2; margin-top: 22px; }
#ai .q span { opacity: .25; }
/* instruction card */
#ins { left: 100px; width: 830px; top: 960px; padding: 30px 38px 36px; border-radius: 36px; background: #fff; color: #10251A;
  box-shadow: 0 20px 60px rgba(0,0,0,.4); }
#ins .k { color: #12B347; opacity: 1; font-weight: 800; font-size: 30px; }
#ins .t { font-size: 44px; font-weight: 700; line-height: 1.25; margin-top: 10px; min-height: 110px; }
#ins .cur { display: inline-block; width: 4px; height: 46px; background: #12B347; vertical-align: -8px; margin-left: 4px; }
/* counter */
#cnt { left: 0; right: 0; top: 960px; text-align: center; }
#cnt .num { display: inline-block; font-size: 150px; font-weight: 900; letter-spacing: -.03em; padding: 0 40px;
  background: #12B347; border-radius: 36px; line-height: 1.15; box-shadow: 0 20px 60px rgba(0,0,0,.4); }
#cnt .sub { margin-top: 22px; font-size: 46px; font-weight: 800; display: inline-block; padding: 10px 30px;
  background: rgba(14,16,18,.82); border-radius: 22px; }
/* store badges */
.badge { top: 1060px; height: 130px; padding: 0 42px; border-radius: 30px; background: #000; display: flex; align-items: center; gap: 22px;
  border: 3px solid rgba(255,255,255,.85); box-shadow: 0 16px 44px rgba(0,0,0,.45); }
.badge .sm { font-size: 24px; font-weight: 600; opacity: .85; line-height: 1; }
.badge .lg { font-size: 46px; font-weight: 800; line-height: 1.1; }
#bp { left: 70px; } #ba { left: 520px; }
/* personal-assistant lower third */
#pa { left: 0; right: 0; top: 1080px; text-align: center; }
/* end card */
#endc { left: 0; top: 0; width: 1080px; height: 1920px; background: radial-gradient(ellipse at 50% 30%, #A6E22A 0%, #12B347 45%, #0B6E2C 100%);
  text-align: center; }
#endc .ic { position: absolute; left: 340px; top: 430px; width: 400px; height: 400px; border-radius: 90px; overflow: hidden;
  box-shadow: 0 30px 80px rgba(0,40,10,.45); }
#endc .ic img { width: 400px; height: 400px; }
#endc .h { position: absolute; left: 0; right: 0; top: 930px; font-size: 92px; font-weight: 900; line-height: 1.05; letter-spacing: -.02em; }
#endc .sub { position: absolute; left: 0; right: 0; top: 1150px; font-size: 46px; font-weight: 600; opacity: .95; }
#endc .cta { position: absolute; left: 190px; width: 700px; top: 1290px; height: 130px; border-radius: 999px; background: #fff;
  color: #0B6E2C; font-size: 54px; font-weight: 900; line-height: 130px; box-shadow: 0 20px 50px rgba(0,40,10,.35); }
#endc .st { position: absolute; left: 0; right: 0; top: 1470px; font-size: 38px; font-weight: 700; opacity: .95; }
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="__LEN__" data-width="1080" data-height="1920">
__BODY__
</div>
<script>
const tl = gsap.timeline({ paused: true });
const pop = (s, t, d = 0.3) => tl.fromTo(s, { opacity: 0, scale: 0.8, y: 30 }, { opacity: 1, scale: 1, y: 0, duration: d, ease: "back.out(2)" }, t);
const out = (s, t) => tl.to(s, { opacity: 0, y: -24, duration: 0.18, ease: "power2.in" }, t);
const drop = (s, t) => tl.fromTo(s, { opacity: 0, y: -160 }, { opacity: 1, y: 0, duration: 0.34, ease: "back.out(1.6)" }, t);
const swap = (b, t) => { tl.to(b + " .call", { opacity: 0, duration: 0.18 }, t).to(b + " .eq", { opacity: 1, duration: 0.18 }, t); };
const dots = (b, t0, t1) => tl.fromTo(b + " .dots span", { opacity: 0.3 }, { opacity: 1, duration: 0.25, stagger: 0.12, repeat: Math.max(1, Math.floor((t1 - t0) / 0.6)), yoyo: true }, t0);
__JS__
window.__timelines = window.__timelines || {};
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""


def banner(i, name, sub, t0, t1):
    return (f'<div id="b{i}" class="abs ban clip" data-start="{t0:.3f}" data-duration="{t1 - t0:.3f}" data-track-index="{i}">'
            f'<div class="st call"><div class="av">?</div><div class="tx"><div class="k">Incoming call</div>'
            f'<div class="n">{name}</div></div><div class="btns"><div class="btn r"></div><div class="btn g"></div></div></div>'
            f'<div class="st eq"><div class="av"><img src="assets/icon.png"></div><div class="tx"><div class="k">{sub}</div>'
            f'<div class="n">Equal AI is answering<span class="dots"><span></span><span></span><span></span></span></div></div></div></div>')


body, js = [], []
for i, (a, e_, z) in enumerate([("c1_in", "c1_eq", "c1_out"), ("c2_in", "c2_eq", "c2_out"), ("c3_in", "c3_eq", "c3_out")], 1):
    body.append(banner(i, "Unknown number", "Equal AI · on it", T[a], T[z]))
    js += [f'drop("#b{i}", {T[a]:.3f}); swap("#b{i}", {T[e_]:.3f}); dots("#b{i}", {T[e_]:.3f}, {T[z]:.3f}); out("#b{i}", {T[z] - 0.2:.3f});']
body.append(f'<div id="m3" class="abs msg clip" data-start="{T["c3_msg"]:.3f}" data-duration="{T["c3_out"] - T["c3_msg"]:.3f}" data-track-index="4">'
            f'<div class="k">Caller intent</div><div class="m">Delivery agent is at the gate with your parcel.</div></div>')
js.append(f'pop("#m3", {T["c3_msg"]:.3f}); out("#m3", {T["c3_out"] - 0.2:.3f});')

body.append(f'<div id="salary" class="abs clip" data-start="{T["salary"]:.3f}" data-duration="{T["salary_out"] - T["salary"]:.3f}" data-track-index="5">'
            f'<span class="s">Salary<span class="x"></span></span></div>')
js.append(f'pop("#salary", {T["salary"]:.3f}); tl.to("#salary .x", {{ width: 360, duration: 0.22, ease: "power2.out" }}, {T["salary_x"]:.3f});'
          f' out("#salary", {T["salary_out"] - 0.2:.3f});')

body.append(f'<div id="logo" class="abs clip" data-start="{T["logo"]:.3f}" data-duration="{T["logo_out"] - T["logo"]:.3f}" data-track-index="6"><img src="assets/icon.png"></div>')
js.append(f'tl.fromTo("#logo", {{ opacity: 0, scale: 0.3, rotation: -14 }}, {{ opacity: 1, scale: 1, rotation: 0, duration: 0.4, ease: "back.out(2.4)" }}, {T["logo"]:.3f});'
          f' out("#logo", {T["logo_out"] - 0.18:.3f});')

spans = "".join(f'<span id="aw{i}">{t} </span>' for i, (t, _) in enumerate(AI_WORDS))
bars = "".join("<i></i>" for _ in range(9))
body.append(f'<div id="ai" class="abs clip" data-start="{T["ai_in"]:.3f}" data-duration="{T["ai_out"] - T["ai_in"]:.3f}" data-track-index="7">'
            f'<div class="hd"><img src="assets/icon.png">Equal AI is speaking<div class="wave">{bars}</div></div><div class="q">{spans}</div></div>')
js.append(f'pop("#ai", {T["ai_in"]:.3f});')
js += [f'tl.to("#aw{i}", {{ opacity: 1, duration: 0.08 }}, {t:.3f});' for i, (_, t) in enumerate(AI_WORDS)]
js.append(f'tl.fromTo("#ai .wave i", {{ scaleY: 0.4 }}, {{ scaleY: 2.2, duration: 0.16, stagger: {{ each: 0.05, repeat: -1, yoyo: true }}, ease: "sine.inOut" }}, {T["ai_in"]:.3f});'
          f' out("#ai", {T["ai_out"] - 0.2:.3f});')

ins = "Delivery wala call kare &rarr; bolo parcel reception pe chhod do"
body.append(f'<div id="ins" class="abs clip" data-start="{T["ins_in"]:.3f}" data-duration="{T["ins_out"] - T["ins_in"]:.3f}" data-track-index="8">'
            f'<div class="k">TELL EQUAL</div><div class="t"><span id="inst"></span><span class="cur"></span></div></div>')
js.append(f'pop("#ins", {T["ins_in"]:.3f});'
          f' (() => {{ const full = "Delivery wala call kare → bolo parcel reception pe chhod do"; const o = {{ n: 0 }};'
          f' tl.to(o, {{ n: full.length, duration: 1.9, ease: "none", onUpdate: () => {{ document.getElementById("inst").textContent = full.slice(0, Math.round(o.n)); }} }}, {T["ins_type"]:.3f}); }})();'
          f' out("#ins", {T["ins_out"] - 0.2:.3f});')

body.append(f'<div id="cnt" class="abs clip" data-start="{T["cnt_in"]:.3f}" data-duration="{T["cnt_out"] - T["cnt_in"]:.3f}" data-track-index="9">'
            f'<div class="num"><span id="cn">0</span> Lakh+</div><br><div class="sub">log roz use karte hain</div></div>')
js.append(f'pop("#cnt", {T["cnt_in"]:.3f}); (() => {{ const o = {{ n: 0 }}; tl.to(o, {{ n: 10, duration: 0.9, ease: "power2.out",'
          f' onUpdate: () => {{ document.getElementById("cn").textContent = Math.round(o.n); }} }}, {T["cnt_in"] + 0.15:.3f}); }})();'
          f' out("#cnt", {T["cnt_out"] - 0.2:.3f});')

body.append(f'<div id="pa" class="abs clip" data-start="{T["pa_in"]:.3f}" data-duration="{T["pa_out"] - T["pa_in"]:.3f}" data-track-index="10">'
            f'<span class="pill"><img src="assets/icon.png" style="width:70px;height:70px;border-radius:18px">Your Personal AI Assistant</span></div>')
js.append(f'pop("#pa", {T["pa_in"]:.3f}); out("#pa", {T["pa_out"] - 0.2:.3f});')

play_svg = '<svg width="64" height="70" viewBox="0 0 32 35"><path d="M2 2 L30 17.5 L2 33 Z" fill="#34C759"/></svg>'
apple_svg = '<svg width="60" height="70" viewBox="0 0 30 35"><circle cx="15" cy="20" r="13" fill="#fff"/><circle cx="20" cy="5" r="4" fill="#fff"/></svg>'
for bid, t0, sm, lg, ic in (("bp", T["play"], "GET IT ON", "Play Store", play_svg), ("ba", T["apple"], "DOWNLOAD ON THE", "App Store", apple_svg)):
    body.append(f'<div id="{bid}" class="abs badge clip" data-start="{t0:.3f}" data-duration="{T["badges_out"] - t0:.3f}" data-track-index="11">'
                f'{ic}<div><div class="sm">{sm}</div><div class="lg">{lg}</div></div></div>')
    js.append(f'pop("#{bid}", {t0:.3f}); out("#{bid}", {T["badges_out"] - 0.2:.3f});')

body.append(banner(12, "Unknown number", "Equal AI · on it", T["r_in"], T["r_out"]).replace('id="b12"', 'id="b12"'))
js.append(f'drop("#b12", {T["r_in"]:.3f}); swap("#b12", {T["r_eq"]:.3f}); dots("#b12", {T["r_eq"]:.3f}, {T["r_out"]:.3f}); out("#b12", {T["r_out"] - 0.2:.3f});')

e0 = T["end"]
body.append(f'<div id="endc" class="abs clip" data-start="{e0:.3f}" data-duration="{L - e0:.3f}" data-track-index="13">'
            f'<div class="ic"><img src="assets/icon.png"></div><div class="h">Your Personal<br>AI Assistant</div>'
            f'<div class="sub">for your calls and more</div><div class="cta">Download Equal AI</div>'
            f'<div class="st">Search &ldquo;Equal AI&rdquo; on Play Store &amp; App Store</div></div>')
js.append(f'tl.fromTo("#endc", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.2 }}, {e0:.3f});'
          f' tl.fromTo("#endc .ic", {{ scale: 0.4, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.45, ease: "back.out(2)" }}, {e0 + 0.08:.3f});'
          f' tl.fromTo(["#endc .h", "#endc .sub"], {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.3, stagger: 0.1, ease: "power3.out" }}, {e0 + 0.3:.3f});'
          f' tl.fromTo("#endc .cta", {{ scale: 0.7, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.35, ease: "back.out(2)" }}, {e0 + 0.6:.3f});'
          f' tl.to("#endc .cta", {{ scale: 1.05, duration: 0.3, yoyo: true, repeat: 3, ease: "sine.inOut" }}, {e0 + 1.0:.3f});'
          f' tl.fromTo("#endc .st", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, {e0 + 0.8:.3f});')

html = HTML.replace("__LEN__", f"{L:.3f}").replace("__BODY__", "\n".join(body)).replace("__JS__", "\n".join(js))
(G / "index.html").write_text(html, encoding="utf-8")
json.dump(T, open(ED / "gfx_times.json", "w"), indent=1)
print("gfx/index.html written;", len(body), "elements; length", L)
