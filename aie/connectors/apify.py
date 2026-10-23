"""Instagram reels of a profile through Apify's official reel scraper (apify/instagram-reel-scraper), for the Style
Learner. One synchronous run per learn; Apify bills about $0.0026 a reel. Only teaching data: nothing scraped is ever
used in an edit."""
import json
import urllib.error
import urllib.request

from ..app import connections

ACTOR = "apify~instagram-reel-scraper"
URL = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"


class ApifyError(RuntimeError):
    pass


def reels(handles: list, per_profile: int = 30, timeout: float = 330) -> list:
    """[{url, owner, plays, seconds, caption, video, cover, posted}] for each profile's recent reels (pinned ones skipped)."""
    token = connections.get("APIFY_TOKEN")
    if not token:
        raise ApifyError("the Apify token isn't set (Connections)")
    body = json.dumps({"username": [h.lstrip("@") for h in handles], "resultsLimit": int(per_profile),
                       "skipPinnedPosts": True}).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            items = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ApifyError(f"Apify answered {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None
    out = []
    for it in items if isinstance(items, list) else []:
        if it.get("error") or not it.get("videoUrl"):
            continue
        out.append({"url": it.get("url"), "owner": it.get("ownerUsername"), "plays": it.get("videoPlayCount") or 0,
                    "seconds": it.get("videoDuration") or 0, "caption": (it.get("caption") or "")[:600],
                    "video": it["videoUrl"], "cover": it.get("displayUrl"), "posted": it.get("timestamp")})
    return out
