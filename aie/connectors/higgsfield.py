"""Generated shots on Higgsfield, through its MCP server: the Generator agent asks for a clip, this code spends the
credits. Every request is priced first (get_cost) and refused if it would take the reel past Paras's credit cap
(Connections, "Credit cap per reel"); nothing is generated while no cap is set. Each charge is written to
build/generated.json before the wait, so an app restart can't lose what was spent. A submission is never retried:
a failed or timed-out job is reported, and Paras decides.
"""
import json
import re
import time
from pathlib import Path

from ..app import connections
from . import mcp

DEFAULT_MODEL = "seedance_2_5"
POLL, WAIT = 15.0, 20 * 60
DONE = ("completed", "complete", "succeeded", "success", "done", "finished")
FAILED = ("failed", "error", "nsfw", "cancelled", "canceled", "rejected")


def ledger(d: Path) -> dict:
    f = d / "build/generated.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"spent": 0.0, "clips": []}


def _save(d: Path, led: dict):
    (d / "build").mkdir(exist_ok=True)
    (d / "build/generated.json").write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")


def cap() -> float:
    try:
        return float(connections.get("HIGGSFIELD_CREDIT_CAP") or 0)
    except ValueError:
        return 0.0


def generate(d: Path, name: str, prompt: str, seconds: int = 5, aspect: str = "9:16", model: str = DEFAULT_MODEL,
             poll: float | None = None, wait: float | None = None) -> str:
    """One clip into raw/gen_<name>.mp4. Returns a line for the agent: what was saved, or why not."""
    poll, wait = POLL if poll is None else poll, WAIT if wait is None else wait
    if not re.fullmatch(r"[a-z0-9_-]{1,40}", name or ""):
        return "name: 1-40 lowercase letters, digits, - or _"
    why = mcp.missing("higgsfield")
    if why:
        return f"not generated: {why}"
    limit = cap()
    if limit <= 0:
        return "not generated: Paras hasn't set a credit cap per reel (Connections, Higgsfield)"
    led = ledger(d)
    params = {"model": model, "prompt": prompt, "duration": int(seconds), "aspect_ratio": aspect}
    priced = mcp.call("higgsfield", "generate_video", {"params": {**params, "get_cost": True},
                                                       "context": "B-roll for an edited reel"})
    cost = mcp.number(priced, "cost", "credits", "total_cost", "price")
    if cost is None:
        return f"not generated: Higgsfield didn't price it ({json.dumps(priced)[:200]})"
    if led["spent"] + cost > limit:
        return (f"not generated: it costs {cost:g} credits and {limit - led['spent']:g} of the {limit:g} cap are left. "
                "Ask Paras to raise the cap, or pick a shorter or cheaper shot")
    made = mcp.call("higgsfield", "generate_video", {"params": {**params, "use_unlim": False},
                                                     "context": "B-roll for an edited reel"})
    job = mcp.find(made, "job_id", "jobId", "id")
    if not job:
        return f"not generated: Higgsfield gave no job id ({json.dumps(made)[:200]})"
    led["spent"] = round(led["spent"] + cost, 3)
    clip = {"name": name, "job": job, "model": model, "prompt": prompt, "seconds": int(seconds), "credits": cost,
            "status": "submitted", "at": round(time.time())}
    led["clips"].append(clip)
    _save(d, led)
    t0, url = time.time(), None
    while time.time() - t0 < wait:
        st = mcp.call("higgsfield", "jobs_wait", {"jobs": [{"index": 0, "job_id": job}], "timeout_seconds": 15})
        state = str(mcp.find(st, "status", "state") or "").lower()
        if state in FAILED:
            clip["status"] = f"failed: {mcp.find(st, 'error', 'message', 'reason') or state}"
            break
        if state in DONE:
            url = mcp.find(st, "video_url", "result_url", "url", "raw_url")
            clip["status"] = "done" if url else "done, but no file URL"
            break
        after = mcp.number(st, "poll_after_seconds")
        time.sleep(poll if after is None else after)
    else:
        clip["status"] = "still running"
    if url:
        out = mcp.download(url, d / "raw" / f"gen_{name}.mp4")
        clip["file"] = out.relative_to(d).as_posix()
    _save(d, led)
    if not url:
        return f"{name}: {clip['status']} (job {job}, {cost:g} credits charged). Not retried; tell Paras."
    return (f"saved {clip['file']} ({cost:g} credits; {limit - led['spent']:g} of the {limit:g} cap left). Add it to "
            f"sources with \"rights\": \"generated\" and place it on the timeline; Paras checks it at the storyboard")
