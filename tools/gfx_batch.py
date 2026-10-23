"""Batch-render templated HyperFrames graphics to transparent webm.

spec JSON: [{"id": "kw01", "tpl": "kw", "dur": 1.8, "vars": {"MAIN": "...", "KICK": "...", "SIDE": "right"}}, ...]
Templates live in AI_Editor/templates/lf_<tpl>.html with {{VAR}} placeholders.
Already-rendered items are skipped unless their HTML changed (cache = html hash).

Usage: python gfx_batch.py <spec.json> <out_dir> [--only id1,id2] [--lint-only] [--res landscape-4k]
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

TPL = Path(r"C:\Users\PARAS ARORA\AI_Editor\templates")
BASE_FILES = ["package.json", "hyperframes.json", "meta.json"]
HF = ["npx", "--yes", "hyperframes@0.8.111"]

SIDES = {
    "right": "right: 80px; text-align: left;",
    "left": "left: 80px; text-align: left;",
    "center": "left: 660px; text-align: center;",
}
DEFAULTS = {"kw": {"KICK": "", "SIDE": "right", "TOP": "330", "SIZE": "84"},
            "section": {"SUB": "", "STEP": "STEP"},
            "lower": {"ROLE": ""}}


def build(item, out: Path, base: Path) -> Path:
    d = out / item["id"]
    d.mkdir(parents=True, exist_ok=True)
    for f in BASE_FILES:
        if not (d / f).exists():
            shutil.copy(base / f, d / f)
    v = {**DEFAULTS.get(item["tpl"], {}), **item.get("vars", {}), "DUR": str(item["dur"])}
    if "SIDE" in v:
        v["SIDECSS"] = SIDES[v["SIDE"]]
    html = (TPL / f"lf_{item['tpl']}.html").read_text(encoding="utf-8")
    for k, val in v.items():
        html = html.replace("{{" + k + "}}", str(val))
    if "{{" in html:
        raise SystemExit(f"{item['id']}: unfilled placeholder near {html[html.index('{{'):html.index('{{') + 30]}")
    (d / "index.html").write_text(html, encoding="utf-8")
    return d


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=True, encoding="utf-8", errors="replace")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--base", default=r"C:\Users\PARAS ARORA\Desktop\edit\edit\animations\_base")
    ap.add_argument("--only")
    ap.add_argument("--lint-only", action="store_true")
    ap.add_argument("--res", help="HyperFrames --resolution preset, e.g. landscape-4k (same layout, rendered at 2x DPR)")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    only = set(a.only.split(",")) if a.only else None
    out = Path(a.out)
    for item in spec:
        if only and item["id"] not in only:
            continue
        d = build(item, out, Path(a.base))
        lint = run(" ".join(HF + ["lint"]), d)
        errs = [l for l in (lint.stdout + lint.stderr).splitlines() if "error(s)" in l or "errors," in l]
        bad = [l for l in (lint.stdout + lint.stderr).splitlines() if l.strip().startswith("✗")]
        if bad:
            print(f"{item['id']}: LINT ERRORS\n  " + "\n  ".join(bad))
            continue
        if a.lint_only:
            print(f"{item['id']}: lint ok")
            continue
        h = hashlib.sha1((d / "index.html").read_bytes()).hexdigest()[:12]
        stamp = d / ".rendered"
        if (d / "render.webm").exists() and stamp.exists() and stamp.read_text() == h:
            print(f"{item['id']}: cached")
            continue
        res = ["--resolution", a.res] if a.res else []
        r = run(" ".join(HF + ["render", ".", "--format", "webm", "--fps", "25", "--workers", "1", "--quality", "looks", *res, "-o", "render.webm"]), d)
        ok = (d / "render.webm").exists() and r.returncode == 0
        if ok:
            stamp.write_text(h)
        print(f"{item['id']}: {'rendered' if ok else 'RENDER FAILED: ' + (r.stderr or r.stdout)[-300:]}", flush=True)
