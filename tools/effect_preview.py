"""Render catalog effects from their "example" parameters, check them, and save a preview strip next to each.

Usage: python tools/effect_preview.py [name ...] [--out DIR] [--gsap FILE]
  name        effects to render (default: every hyperframes-template effect with an "example")
  --out DIR   where the render folders go (default: a temporary folder)
  --gsap FILE serve GSAP from a local copy, for a browser that can't reach cdn.jsdelivr.net (a cloud session)

Writes effects/<name>/preview.jpg: frames at 20%, 50% and 85% of the effect, over a grey stand-in for footage.
Checks, per frame: something is drawn; stage effects stay in the top half (y < 966); full-frame effects keep their
text inside Instagram's safe zone (x 90-930, y 200-1560); the render has the format's size.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # repo root, for the aie package
from aie import ffmpeg  # noqa: E402
from aie.effects import Catalog  # noqa: E402
from aie.runner import _hyperframes  # noqa: E402
from aie.settings import REPO, load_settings  # noqa: E402

SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
CDN = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
SAFE = (90, 200, 930, 1560)
FPS = 25


def frames(webm: Path, times, size):
    """RGBA frames at the given seconds (decoded with libvpx so the alpha survives; never seeked)."""
    from PIL import Image
    w, h = size
    out = []
    for t in times:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", str(webm), "-vf",
                              f"select='gte(t\\,{t:.3f})',format=rgba", "-frames:v", "1", "-f", "rawvideo", "-"],
                             capture_output=True, check=True).stdout
        out.append(Image.frombytes("RGBA", (w, h), raw[:w * h * 4]))
    return out


def check(fx, ims) -> list:
    import numpy as np
    probs = []
    for i, im in enumerate(ims):
        a = np.asarray(im)[..., 3]
        ys, xs = np.nonzero(a > 40)
        if len(xs) < 500:
            probs.append(f"frame {i + 1}: nothing drawn")
            continue
        if fx.data.get("zone") == "stage" and ys.max() >= 966:
            probs.append(f"frame {i + 1}: draws below the stage (y {ys.max()})")
        if fx.data.get("zone") == "full":
            x0, y0, x1, y1 = SAFE
            if xs.min() < x0 - 40 or xs.max() > x1 + 40 or ys.min() < y0 or ys.max() > y1:
                probs.append(f"frame {i + 1}: outside the IG safe zone ({xs.min()}-{xs.max()}, {ys.min()}-{ys.max()})")
    return probs


def strip(ims, size, out: Path):
    from PIL import Image, ImageDraw
    w, h = size
    s = 360 / max(w, h) * (640 / 360 if h > w else 1)
    tw, th = int(w * s), int(h * s)
    sheet = Image.new("RGB", (tw * len(ims) + 8 * (len(ims) - 1), th), (12, 14, 15))
    for i, im in enumerate(ims):
        bg = Image.new("RGBA", (w, h), (74, 80, 86, 255))
        ImageDraw.Draw(bg).rectangle([0, h * 0.55, w, h], fill=(96, 104, 110, 255))     # footage stand-in
        bg.alpha_composite(im)
        sheet.paste(bg.convert("RGB").resize((tw, th), Image.LANCZOS), (i * (tw + 8), 0))
    sheet.save(out, quality=86)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--gsap")
    a = ap.parse_args()
    s = load_settings()
    cat = Catalog.load(s.path("effects"))
    names = a.names or [n for n, fx in cat.effects.items()
                        if fx.data["engine"] == "hyperframes-template" and "example" in fx.data]
    out = Path(a.out or tempfile.mkdtemp())
    bad = 0
    for name in names:
        fx = cat.get(name)
        if fx is None:
            print(f"{name}: not in the catalog")
            bad += 1
            continue
        size = SIZES[fx.formats[0]]
        dur = fx.data.get("duration", {}).get("default", 2.0)
        given = fx.data.get("example", {})
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        for f in ("package.json", "hyperframes.json", "meta.json"):
            shutil.copy(s.path("hyperframes_base") / f, d / f)
        html = fx.html(given, dur, s.path("templates"))
        if a.gsap:
            shutil.copy(a.gsap, d / "gsap.min.js")
            html = html.replace(CDN, "gsap.min.js")
        (d / "index.html").write_text(html, encoding="utf-8")
        for n, src in fx.files(given, s.path("templates")).items():
            shutil.copy(src if isinstance(src, Path) else REPO / src, d / n)
        try:
            _hyperframes(s, d, FPS, d / "render.webm")
        except Exception as e:                     # report and go on to the next effect
            print(f"{name}: RENDER FAILED {e}")
            bad += 1
            continue
        info = ffmpeg.video_info(d / "render.webm")
        probs = [] if info["size"] == list(size) else [f"rendered {info['size']}, expected {list(size)}"]
        ims = frames(d / "render.webm", [dur * f for f in (0.2, 0.5, 0.85)], size)
        probs += check(fx, ims)
        strip(ims, size, fx.dir / "preview.jpg")
        bad += bool(probs)
        print(f"{name}: " + ("; ".join(probs) if probs else "ok") + f"  -> {fx.dir / 'preview.jpg'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
