"""The Publisher: the post copy for each delivered variant, in one call to Haiku. Instagram gets the caption with the
comment keyword and the hashtags for the first comment; YouTube gets a title and a description with the WhatsApp
channel line. It writes; it never posts. The copy passes the same claims screen as every edit (Constitution section
4): copy with a claim is not saved, and Paras is told which phrase.
"""
import json
from pathlib import Path

from ..qa import claims
from .roster import HAIKU, cost

SYSTEM = """You write the post copy for Paras Arora's reels (Exponential World, AI education for Indian entrepreneurs).
Voice: friendly, clear Hinglish in Roman script, like the reel itself; no hype. Education only: no income claims, no
return or profit promises, no guarantees, no "get rich" language. Use only what the reel says; never invent numbers,
tools or results. Write exactly the sections asked for, as Markdown, nothing before or after."""

CTA = {"instagram": "Instagram: follow + comment the keyword {kw}; the link comes in DM. Hashtags go in the first comment, "
                    "not in the caption.",
       "youtube": "YouTube: the CTA is \"channel ke description mein di gayi link se WhatsApp channel join karo\"; "
                  "no comment-to-DM there."}
FORMAT = {"instagram": "## Instagram\n**Caption:** (3-6 short lines, ends with the comment CTA)\n**First comment:** "
                       "(8-15 hashtags, mixed reach)",
          "youtube": "## YouTube\n**Title:** (under 70 characters)\n**Description:** (2-4 lines, then the WhatsApp "
                     "channel line)"}


class PublishError(RuntimeError):
    pass


def spoken(d: Path) -> str:
    """What the reel says: the caption words if built, else the script."""
    w = d / "build/words.json"
    if w.exists():
        return " ".join(x["text"] for x in json.loads(w.read_text(encoding="utf-8"))["words"])
    s = d / "script.txt"
    if s.exists():
        return s.read_text(encoding="utf-8").strip()
    raise PublishError("nothing to write from yet: build the captions (or add script.txt) first")


def write(d: Path, job: dict, api) -> dict:
    """build/publish/<PREFIX>_post.md, or PublishError (nothing saved)."""
    brief = json.loads((d / "brief.json").read_text(encoding="utf-8")) if (d / "brief.json").exists() else {}
    kinds = [v for v in ("instagram", "youtube") if v in job.get("variants", {})] or ["instagram"]
    kw = brief.get("cta") or "the keyword"
    ask = (f"Title: {brief.get('title') or job.get('title', d.name)}\nTopic: {brief.get('topic', '')}\n"
           f"What the reel says:\n{spoken(d)[:6000]}\n\n" + "\n".join(CTA[k].format(kw=kw) for k in kinds) +
           "\n\nWrite these sections:\n\n" + "\n\n".join(FORMAT[k] for k in kinds))
    msg = api.messages.create(model=HAIKU, max_tokens=2000, system=SYSTEM, output_config={"effort": "low"},
                              messages=[{"role": "user", "content": ask}])
    if msg.stop_reason == "refusal":
        raise PublishError("the model declined to write this copy; write it by hand")
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    if not text:
        raise PublishError("the model wrote nothing; try again")
    hits = claims([("post copy", text)], job.get("qa", {}).get("cleared", []))
    if hits:
        raise PublishError("not saved: " + "; ".join(f'"{h["phrase"]}"' for h in hits) +
                           " reads as an income/return claim (Constitution section 4). Write again, or clear the phrase "
                           "in qa.cleared if it is education")
    prefix = job.get("package", {}).get("prefix", job.get("id", d.name).upper().replace("-", ""))
    out = d / "build/publish" / f"{prefix}_post.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    return {"file": str(out), "text": text, "cost": round(cost(HAIKU, msg.usage), 5)}
