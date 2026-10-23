"""Connections: every API key, MCP server, app and tool the tool can use, each "not set", "set", "tested OK" or
"failed". Without them the app still runs end to end in placeholder mode: the pipeline renders, and whatever needs a
key (the agent team, avatar renders, generated shots, style learning) waits and says which key it waits for.

Values live in secrets.local.json at the repo root (or the file AIE_SECRETS names) (git-ignored; the session's safety hook won't read it). The API
never returns a secret, only its last four characters.
"""
import importlib.util
import json
import os
import shutil
from pathlib import Path

from ..settings import REPO



def secrets_path() -> Path:
    return Path(os.environ.get("AIE_SECRETS") or REPO / "secrets.local.json")

# kind: api (key + optional test call), mcp (a server the agent team connects to), app (a path on this PC),
# tool (found on this PC, nothing to enter)
REGISTRY = [
    {"id": "anthropic", "kind": "api", "name": "Claude API", "for": "The agent team: Producer, Story Editor, QA Auditor and the lanes",
     "fields": [{"key": "ANTHROPIC_API_KEY", "label": "API key", "secret": True, "hint": "sk-ant-..."}],
     "docs": "https://console.anthropic.com/settings/keys"},
    {"id": "heygen", "kind": "api", "name": "HeyGen", "for": "Avatar mode: pronunciation previews and avatar renders",
     "fields": [{"key": "HEYGEN_API_KEY", "label": "API key", "secret": True}],
     "docs": "https://app.heygen.com/settings?nav=API"},
    {"id": "higgsfield", "kind": "api", "name": "Higgsfield", "for": "Generated shots: hooks, hero shots, B-roll (Seedance, Kling, Nano Banana)",
     "fields": [{"key": "HIGGSFIELD_API_KEY", "label": "API key", "secret": True},
                {"key": "HIGGSFIELD_CREDIT_CAP", "label": "Credit cap per reel", "secret": False, "hint": "e.g. 120"}],
     "docs": "https://higgsfield.ai"},
    {"id": "google_flow", "kind": "api", "name": "Google Flow / Veo", "for": "Hooks with the 'Me' avatar (Veo through the Gemini API)",
     "fields": [{"key": "GEMINI_API_KEY", "label": "Gemini API key", "secret": True}],
     "docs": "https://aistudio.google.com/apikey"},
    {"id": "elevenlabs", "kind": "api", "name": "ElevenLabs", "for": "Scribe transcription (better on Hinglish than local Whisper)",
     "fields": [{"key": "ELEVENLABS_API_KEY", "label": "API key", "secret": True}],
     "docs": "https://elevenlabs.io/app/settings/api-keys"},
    {"id": "apify", "kind": "api", "name": "Apify", "for": "Style Learner: scrapes a profile's top reels",
     "fields": [{"key": "APIFY_TOKEN", "label": "API token", "secret": True}],
     "docs": "https://console.apify.com/settings/integrations"},
    {"id": "composio", "kind": "api", "name": "Composio", "for": "Publisher: Drive delivery and posting after approval",
     "fields": [{"key": "COMPOSIO_API_KEY", "label": "API key", "secret": True}],
     "docs": "https://app.composio.dev/settings"},
    {"id": "ghl", "kind": "api", "name": "GoHighLevel", "for": "Publisher: post copy and client delivery in GHL",
     "fields": [{"key": "GHL_API_KEY", "label": "Private integration token", "secret": True},
                {"key": "GHL_LOCATION_ID", "label": "Location ID", "secret": False}],
     "docs": "https://marketplace.gohighlevel.com/docs/"},
    {"id": "mcp_heygen", "kind": "mcp", "name": "HeyGen MCP", "for": "Avatar Producer's tools",
     "fields": [{"key": "MCP_HEYGEN_URL", "label": "Server URL", "secret": False, "hint": "https://..."},
                {"key": "MCP_HEYGEN_TOKEN", "label": "Auth token", "secret": True}]},
    {"id": "mcp_higgsfield", "kind": "mcp", "name": "Higgsfield MCP", "for": "Generator's tools",
     "fields": [{"key": "MCP_HIGGSFIELD_URL", "label": "Server URL", "secret": False},
                {"key": "MCP_HIGGSFIELD_TOKEN", "label": "Auth token", "secret": True}]},
    {"id": "mcp_apify", "kind": "mcp", "name": "Apify MCP", "for": "Style Learner's tools",
     "fields": [{"key": "MCP_APIFY_URL", "label": "Server URL", "secret": False, "hint": "https://mcp.apify.com"},
                {"key": "MCP_APIFY_TOKEN", "label": "Auth token", "secret": True}]},
    {"id": "mcp_composio", "kind": "mcp", "name": "Composio MCP", "for": "Publisher's tools (Drive, GHL)",
     "fields": [{"key": "MCP_COMPOSIO_URL", "label": "Server URL", "secret": False},
                {"key": "MCP_COMPOSIO_TOKEN", "label": "Auth token", "secret": True}]},
    {"id": "drive", "kind": "app", "name": "Google Drive folder", "for": "Deliveries are copied here (Drive for desktop syncs them)",
     "fields": [{"key": "DRIVE_FOLDER", "label": "Folder", "secret": False, "hint": "G:\\My Drive\\Edits"}]},
    {"id": "resolve", "kind": "app", "name": "DaVinci Resolve", "for": "NLE bridge: grade and finish (external scripting needs Studio)",
     "fields": [{"key": "RESOLVE_PATH", "label": "Resolve.exe", "secret": False,
                 "hint": "C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\Resolve.exe"},
                {"key": "RESOLVE_EDITION", "label": "Edition (Studio or Free)", "secret": False}]},
    {"id": "premiere", "kind": "app", "name": "Premiere Pro", "for": "NLE bridge: hand-finish, client handoff (UXP panel)",
     "fields": [{"key": "PREMIERE_PATH", "label": "Adobe Premiere Pro.exe", "secret": False}]},
    {"id": "after_effects", "kind": "app", "name": "After Effects", "for": "NLE bridge: template renders with aerender",
     "fields": [{"key": "AERENDER_PATH", "label": "aerender.exe", "secret": False,
                 "hint": "C:\\Program Files\\Adobe\\Adobe After Effects 2026\\Support Files\\aerender.exe"}]},
]
TOOLS = [("ffmpeg", "Renders and audio", "exe"), ("ffprobe", "Media checks", "exe"), ("npx", "HyperFrames graphics", "exe"),
         ("faster_whisper", "Transcription and the QA words check", "module"), ("torchaudio", "Letter timings (CTC)", "module"),
         ("cv2", "reel-04's frame-by-frame compositor", "module"), ("playwright", "Mobile QA of pages", "module")]


def load() -> dict:
    try:
        return json.loads(secrets_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(values: dict):
    secrets_path().write_text(json.dumps(values, indent=1), encoding="utf-8")
    try:
        os.chmod(secrets_path(), 0o600)
    except OSError:
        pass


def get(key: str) -> str | None:
    """A value for the code that uses it (the agent runtime, a test call); the environment wins over the file."""
    return os.environ.get(key) or load().get(key) or None


def _mask(v: str) -> str:
    return "••••" + v[-4:] if len(v) > 8 else "••••"


def listing(tests: dict) -> list:
    vals = load()
    out = []
    for c in REGISTRY:
        fields = []
        for f in c["fields"]:
            v = os.environ.get(f["key"]) or vals.get(f["key"]) or ""
            fields.append({**f, "set": bool(v), "value": (_mask(v) if f["secret"] else v) if v else "",
                           "from_env": bool(os.environ.get(f["key"]))})
        need = [f for f in fields if f["secret"] or f["key"].endswith(("_PATH", "_URL", "FOLDER"))]
        is_set = all(f["set"] for f in (need or fields))
        t = tests.get(c["id"])
        status = "not set" if not is_set else ("tested OK" if t and t["ok"] else ("failed" if t else "set"))
        out.append({**{k: c[k] for k in ("id", "kind", "name", "for")}, "docs": c.get("docs"), "fields": fields,
                    "status": status, "test": t})
    for name, why, kind in TOOLS:
        found = shutil.which(name) if kind == "exe" else importlib.util.find_spec(name)
        out.append({"id": f"tool_{name}", "kind": "tool", "name": name, "for": why, "fields": [],
                    "status": "found" if found else "missing", "test": None,
                    "docs": None, "where": str(found) if kind == "exe" and found else None})
    return out


def update(cid: str, values: dict):
    c = next((c for c in REGISTRY if c["id"] == cid), None)
    if c is None:
        raise KeyError(cid)
    allowed = {f["key"] for f in c["fields"]}
    bad = set(values) - allowed
    if bad:
        raise ValueError(f"{cid} has no field {sorted(bad)}")
    cur = load()
    for k, v in values.items():
        v = (v or "").strip()
        if v:
            cur[k] = v
        else:
            cur.pop(k, None)
    save(cur)


def _http(url: str, headers: dict) -> tuple:
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "aie-app", **headers})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.reason
    except (urllib.error.URLError, OSError) as e:
        return 0, str(getattr(e, "reason", e))


# One cheap, read-only call per service: proves the key works without spending credits.
CALLS = {
    "anthropic": lambda v: ("https://api.anthropic.com/v1/models",
                            {"x-api-key": v["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"}),
    "heygen": lambda v: ("https://api.heygen.com/v2/user/remaining_quota", {"X-Api-Key": v["HEYGEN_API_KEY"]}),
    "google_flow": lambda v: (f"https://generativelanguage.googleapis.com/v1beta/models?key={v['GEMINI_API_KEY']}", {}),
    "elevenlabs": lambda v: ("https://api.elevenlabs.io/v1/user", {"xi-api-key": v["ELEVENLABS_API_KEY"]}),
    "apify": lambda v: ("https://api.apify.com/v2/users/me", {"Authorization": f"Bearer {v['APIFY_TOKEN']}"}),
    "ghl": lambda v: (f"https://services.leadconnectorhq.com/locations/{v.get('GHL_LOCATION_ID', '')}",
                      {"Authorization": f"Bearer {v['GHL_API_KEY']}", "Version": "2021-07-28"}),
}


def test(cid: str, http=None) -> tuple:
    """(ok, message) for one connection."""
    http = http or _http
    c = next((c for c in REGISTRY if c["id"] == cid), None)
    if c is None:
        raise KeyError(cid)
    v = {f["key"]: get(f["key"]) for f in c["fields"]}
    missing = [f["label"] for f in c["fields"] if not v[f["key"]] and (f["secret"] or f["key"].endswith(("_PATH", "_URL", "FOLDER")))]
    if missing:
        return False, f"not set: {', '.join(missing)}"
    if c["kind"] == "app":
        p = Path(next(x for k, x in v.items() if x and k.endswith(("_PATH", "FOLDER"))))
        if not p.exists():
            return False, f"{p} isn't there"
        if c["id"] == "drive" and not os.access(p, os.W_OK):
            return False, f"{p} isn't writable"
        if c["id"] == "resolve" and (v.get("RESOLVE_EDITION") or "").lower().startswith("free"):
            return True, "found; the free edition only runs scripts from its own console, so the bridge hands you a script"
        return True, f"found {p.name}"
    if c["kind"] == "mcp":
        url = next(x for k, x in v.items() if k.endswith("_URL"))
        code, why = http(url, {"Authorization": f"Bearer {v[next(k for k in v if k.endswith('_TOKEN'))]}"}
                         if any(k.endswith("_TOKEN") and v[k] for k in v) else {})
        return (code != 0, f"reachable (HTTP {code}); the agent runtime connects on start" if code else f"unreachable: {why}")
    if cid not in CALLS:
        return True, "saved; checked on first use (no free read-only call to test it with)"
    url, headers = CALLS[cid](v)
    code, why = http(url, headers)
    if 200 <= code < 300:
        return True, "key works"
    if code in (401, 403):
        return False, f"rejected (HTTP {code}): check the key"
    return False, f"HTTP {code} {why}".strip() if code else f"couldn't reach the service: {why}"


def placeholder_summary(items: list) -> dict:
    cons = [c for c in items if c["kind"] in ("api", "mcp", "app")]
    ready = [c for c in cons if c["status"] in ("set", "tested OK")]
    return {"set": len(ready), "total": len(cons), "agents": any(c["id"] == "anthropic" and c["status"] in ("set", "tested OK")
                                                                   for c in cons)}
