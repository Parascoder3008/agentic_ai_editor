"""Avatar mode on HeyGen, through its MCP server (CLAUDE.md's pronunciation gate).

preview: the exact text HeyGen reads (tools/pron_check.py --tts) -> create_speech with the approved voice ->
    pron/preview.wav, and pron/report.md with every word that drifted. A new preview withdraws the last approval.
render:  only after Paras approved that very file (its hash is checked): upload it, render the picked look
    lip-syncing it (an audio asset, so the look's default voice never changes the words), download raw/avatar.mp4,
    and write the job. A render that is still running is polled again, never submitted twice.
"""
import hashlib
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from ..settings import REPO
from . import mcp

POLL, WAIT = 30.0, 45 * 60          # HeyGen asks for 30 s between polls; give up waiting (not the render) after 45 min
_running: set = set()
_lock = threading.Lock()


class AvatarError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_brief(d: Path) -> dict:
    f = d / "brief.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def write_brief(d: Path, b: dict):
    (d / "brief.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")


def voice_for(b: dict, rotation: Path) -> str:
    v = b.get("voice")
    if not v and rotation.exists():
        v = json.loads(rotation.read_text(encoding="utf-8")).get("voice_id")
    if not v:
        raise AvatarError('no voice: set "voice" in the brief or "voice_id" in the avatar rotation file')
    return v


def _pron(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "tools/pron_check.py"), *map(str, args)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def tts_text(d: Path) -> str:
    if not (d / "script_tts.txt").exists():
        raise AvatarError("write script_tts.txt first (Hindi in Devanagari, English in Latin, {Shown|बोला} pins)")
    r = _pron(d / "script_tts.txt", "--tts")
    if r.returncode:
        raise AvatarError((r.stderr or r.stdout).strip()[-600:])
    return r.stdout.strip()


def preview(d: Path, rotation: Path) -> dict:
    """The voice preview Paras listens to; returns what the brief now says about it."""
    b = read_brief(d)
    text, voice = tts_text(d), voice_for(b, rotation)
    res = mcp.call("heygen", "create_speech", {"text": text, "voiceId": voice})
    url = mcp.find(res, "audio_url", "audioUrl", "url")
    if not url:
        raise AvatarError(f"create_speech gave no audio URL: {json.dumps(res)[:300]}")
    ext = Path(str(url).split("?")[0]).suffix.lower() or ".mp3"
    raw = mcp.download(url, d / "pron" / f"preview_heygen{ext}")
    wav = d / "pron/preview.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-ac", "1", "-ar", "48000", str(wav)], check=True)
    rep = _pron(d / "script_tts.txt", wav, "--out", d / "pron/report.md")
    b = read_brief(d)
    b["preview"] = {"file": "pron/preview.wav", "sha": sha(wav), "voice": voice, "made": round(time.time()),
                    "report": "pron/report.md" if rep.returncode == 0 else None,
                    "report_error": None if rep.returncode == 0 else (rep.stderr or rep.stdout).strip()[-400:]}
    b["pron_approved"] = False                       # new audio, new listen
    b.pop("pron_approved_sha", None)
    write_brief(d, b)
    return b["preview"]


def approve(d: Path, value: bool) -> dict:
    """Paras's approval of the current preview, tied to its exact bytes."""
    b = read_brief(d)
    if value:
        p = b.get("preview")
        if not p or not (d / p["file"]).exists():
            raise AvatarError("make a voice preview first: the approval is for audio you have heard")
        b["pron_approved"], b["pron_approved_sha"] = True, sha(d / p["file"])
    else:
        b["pron_approved"] = False
        b.pop("pron_approved_sha", None)
    write_brief(d, b)
    return b


def check_ready(d: Path) -> dict:
    b = read_brief(d)
    p = b.get("preview")
    if not b.get("look"):
        raise AvatarError("pick the avatar look first")
    if not (b.get("pron_approved") and p and (d / p["file"]).exists()):
        raise AvatarError("approve the pronunciation preview first")
    if sha(d / p["file"]) != b.get("pron_approved_sha"):
        raise AvatarError("the preview changed since you approved it: listen again and approve")
    if (b.get("render") or {}).get("status") == "done" and (d / "raw/avatar.mp4").exists():
        raise AvatarError("this project's avatar is already rendered (raw/avatar.mp4)")
    return b


def start_render(d: Path, on_done=None) -> dict:
    """Checks the gate now, then renders on a thread; progress is in brief.json "render"."""
    check_ready(d)
    key = str(d.resolve())
    with _lock:
        if key in _running:
            return {"message": "the avatar is already rendering"}
        _running.add(key)
    threading.Thread(target=_render_thread, args=(d, on_done), daemon=True, name=f"aie-heygen-{d.name}").start()
    return {"message": "rendering on HeyGen: the job is made when it's back"}


def _render_thread(d: Path, on_done):
    try:
        render(d)
        if on_done:
            on_done()
    except Exception as e:                           # the brief says what broke; the app keeps running
        _status(d, status="failed", message=f"{type(e).__name__}: {e}")
    finally:
        with _lock:
            _running.discard(str(d.resolve()))


def _status(d: Path, **kw):
    b = read_brief(d)
    b["render"] = {**(b.get("render") or {}), **kw, "at": round(time.time())}
    write_brief(d, b)


def render(d: Path, poll: float | None = None, wait: float | None = None):
    poll, wait = POLL if poll is None else poll, WAIT if wait is None else wait
    b = check_ready(d)
    look, wav = b["look"], d / b["preview"]["file"]
    vid = (b.get("render") or {}).get("video_id")
    if vid and (b["render"].get("audio_sha") != b["pron_approved_sha"] or b["render"].get("look") != look["id"]):
        vid = None                                   # a render of other audio or another look: start a new one
    if not vid:
        _status(d, status="uploading", message="uploading the approved audio")
        up = mcp.call("heygen", "create_asset_upload", {"filename": "preview.wav", "contentType": "audio/wav",
                                                        "sizeBytes": wav.stat().st_size})
        asset, url = mcp.find(up, "asset_id", "assetId", "id"), mcp.find(up, "upload_url", "uploadUrl")
        if not (asset and url):
            raise AvatarError(f"create_asset_upload gave no asset or upload URL: {json.dumps(up)[:300]}")
        mcp.upload(url, wav, "audio/wav", mcp.find(up, "upload_headers", "headers"))
        mcp.call("heygen", "complete_asset_upload", {"assetId": asset})
        made = mcp.call("heygen", "create_video_from_avatar", {
            "avatarId": look["id"], "audioAssetId": asset, "aspectRatio": "auto", "resolution": "1080p",
            "title": f"{d.name} ({look.get('name', look['id'])})"})
        vid = mcp.find(made, "video_id", "videoId", "id")
        if not vid:
            raise AvatarError(f"create_video_from_avatar gave no video id: {json.dumps(made)[:300]}")
        _status(d, status="rendering", video_id=vid, look=look["id"], audio_sha=b["pron_approved_sha"],
                message="HeyGen is rendering")
    t0 = time.time()
    while True:
        st = mcp.call("heygen", "get_video", {"videoId": vid})
        state = str(mcp.find(st, "status") or "").lower()
        if state in ("completed", "complete", "succeeded", "success", "done"):
            url = mcp.find(st, "video_url", "videoUrl")
            break
        if state in ("failed", "error", "cancelled", "canceled"):
            raise AvatarError(f"HeyGen: {mcp.find(st, 'failure_message', 'error', 'message') or state}")
        if time.time() - t0 > wait:
            _status(d, status="rendering", message=f"still {state or 'pending'} after {int(wait // 60)} min; "
                                                   "render again to keep waiting (it isn't resubmitted)")
            return None
        after = mcp.number(st, "retry_after_seconds", "retry_after")
        time.sleep(poll if after is None else after)
    if not url:
        raise AvatarError("HeyGen says done but gave no video URL")
    mcp.download(url, d / "raw/avatar.mp4")
    from ..app.projects import avatar_job
    avatar_job(d, read_brief(d), d / "raw/avatar.mp4")
    _status(d, status="done", file="raw/avatar.mp4", message="rendered; the job is made")
    return d / "raw/avatar.mp4"
