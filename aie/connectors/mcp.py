"""Calls to the MCP servers set in Connections, made by this code, not by a model: a call a model makes through the
API's MCP connector runs on Anthropic's side, where no budget of ours can stop it. Needs pip install "mcp>=2.3,<3".

The token goes as a bearer token; without an MCP token the service's API key is tried. Results come back as the
tool's structured content, or its text parsed as JSON. Field names vary between servers and versions, so callers
read them with find().
"""
import asyncio
import json
import shutil
import urllib.request
from pathlib import Path

from ..app import connections

SERVERS = {"heygen": ("MCP_HEYGEN_URL", "MCP_HEYGEN_TOKEN", "HEYGEN_API_KEY"),
           "higgsfield": ("MCP_HIGGSFIELD_URL", "MCP_HIGGSFIELD_TOKEN", "HIGGSFIELD_API_KEY")}
NAMES = {"heygen": "HeyGen", "higgsfield": "Higgsfield"}
TARGETS = {}                      # tests connect a server name to an in-process MCPServer here


class MCPError(RuntimeError):
    pass


def missing(server: str) -> str | None:
    """What stops calls to this server, or None."""
    if server in TARGETS:
        return None
    url, token, key = SERVERS[server]
    name = NAMES[server]
    if not connections.get(url):
        return f"the {name} MCP server URL isn't set"
    if not (connections.get(token) or connections.get(key)):
        return f"the {name} MCP token (or API key) isn't set"
    return None


def call(server: str, tool: str, args: dict, timeout: float = 120) -> dict:
    return asyncio.run(_call(server, tool, args, timeout))


async def _call(server, tool, args, timeout):
    try:
        from mcp import Client
        from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
    except ImportError:
        raise MCPError('the MCP client isn\'t installed: pip install "mcp>=2.3,<3"') from None
    why = missing(server)
    if why:
        raise MCPError(why)
    if server in TARGETS:
        async with Client(TARGETS[server], read_timeout_seconds=timeout) as c:
            res = await c.call_tool(tool, args)
    else:
        url, token, key = SERVERS[server]
        auth = connections.get(token) or connections.get(key)
        async with create_mcp_http_client(headers={"Authorization": f"Bearer {auth}"}) as http:
            async with Client(streamable_http_client(connections.get(url), http_client=http),
                              read_timeout_seconds=timeout) as c:
                res = await c.call_tool(tool, args)
    text = "\n".join(b.text for b in res.content if getattr(b, "type", "") == "text")
    if res.is_error:
        raise MCPError(f"{server} {tool}: {text[:600] or 'failed'}")
    data = res.structured_content or {}
    if data and not (list(data) == ["result"] and isinstance(data["result"], str)):
        return data
    try:                                              # JSON as text (or a str result wrapped as {"result": ...})
        out = json.loads(text)
        return out if isinstance(out, dict) else {"result": out}
    except ValueError:
        return data or {"text": text}


def find(obj, *keys):
    """The first value under any of keys (in that order of preference), searching nested dicts and lists."""
    for k in keys:
        level = [obj]
        while level:
            nxt = []
            for o in level:
                if isinstance(o, dict):
                    if o.get(k) not in (None, ""):
                        return o[k]
                    nxt += list(o.values())
                elif isinstance(o, list):
                    nxt += o
            level = nxt
    return None


def number(obj, *keys) -> float | None:
    """A number under any of keys, looking inside a nested object ({"cost": {"credits": 4}} -> 4.0)."""
    v = find(obj, *keys)
    for _ in range(3):
        if not isinstance(v, dict):
            break
        v = find(v, *keys)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def download(url: str, dst: Path, timeout: float = 600) -> Path:
    """A result file onto this PC (http or https only)."""
    if not str(url).startswith(("https://", "http://")):
        raise MCPError(f"refusing to download {url!r}: not an http(s) URL")
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    with urllib.request.urlopen(url, timeout=timeout) as r, part.open("wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    part.replace(dst)
    return dst


def upload(url: str, src: Path, content_type: str, headers: dict | None = None, timeout: float = 600):
    """PUT a file to a presigned upload URL."""
    if not str(url).startswith(("https://", "http://")):
        raise MCPError(f"refusing to upload to {url!r}: not an http(s) URL")
    data = src.read_bytes()
    req = urllib.request.Request(url, data=data, method="PUT",
                                 headers={"Content-Type": content_type, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if r.status not in (200, 201, 204):
            raise MCPError(f"upload of {src.name} answered {r.status}")
