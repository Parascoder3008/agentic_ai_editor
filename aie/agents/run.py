"""One agent's turn on one job. The Claude API Tool Runner drives the role's tools (aie/agents/tools.py) until the model
is done, its turn cap is reached, or the dispatch's budget runs out (Constitution section 5: a spent budget pauses and
asks). The runner, rather than the Agent SDK, because every tool an agent has is ours and guarded, and it needs no
Claude Code CLI on the PC.
"""
import json
import threading
from pathlib import Path

from .roster import HAIKU, ROLES, cost

PRIMER = Path(__file__).with_name("primer.md").read_text(encoding="utf-8")
MAX_TOKENS = 16000


class Budget:
    """The dollars one dispatch may spend, shared by the lanes that run at the same time."""

    def __init__(self, limit: float):
        self.limit, self.spent, self._lock = float(limit), 0.0, threading.Lock()

    def add(self, usd: float) -> bool:
        """Count a response; False once the limit is reached."""
        with self._lock:
            self.spent += usd
            return self.spent < self.limit

    def left(self) -> bool:
        with self._lock:
            return self.spent < self.limit


def client(api_key: str):
    try:
        import anthropic
    except ImportError:
        raise RuntimeError('the agents need the Claude API package: pip install "anthropic>=2.2"') from None
    return anthropic.Anthropic(api_key=api_key, max_retries=3)


def request(role: str) -> dict:
    """The request settings for a role. Thinking is left at the model's default (always on for Opus 5.5, adaptive for
    Sonnet 5.5); effort is set explicitly. The primer is the same for every role, so it is cached; a refusal is re-run
    on Anthropic's recommended fallback model (not offered for Haiku)."""
    spec = ROLES[role]
    kw = {"model": spec["model"], "max_tokens": MAX_TOKENS, "max_iterations": spec["iterations"],
          "system": [{"type": "text", "text": PRIMER, "cache_control": {"type": "ephemeral"}},
                     {"type": "text", "text": f"You are the {role}. {spec['brief']}"}],
          "output_config": {"effort": spec["effort"]}, "cache_control": {"type": "ephemeral"}}
    if spec["model"] != HAIKU:
        kw.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    return kw


def _calls(message) -> list:
    return [f"{b.name}({json.dumps(b.input, ensure_ascii=False)[:300]})" for b in message.content if b.type == "tool_use"]


def run_agent(role: str, task: str, toolbox, api, budget: Budget | None = None, log=None) -> dict:
    """Run `role` on `task` with `toolbox`'s tools through `api` (an anthropic client). Returns what happened:
    status (done, refused, over budget, turn cap, cut off, error), its last words, the dollars spent, and how many
    changes it made to job.json."""
    log = log or (lambda line: None)
    out = {"role": role, "model": ROLES[role]["model"], "status": "done", "text": "", "cost": 0.0, "turns": 0}
    if budget is not None and not budget.left():
        out["status"] = "over budget"
        return out
    import anthropic
    runner = api.beta.messages.tool_runner(tools=toolbox.tools(), messages=[{"role": "user", "content": task}],
                                           **request(role))
    last = None
    try:
        for message in runner:
            last = message
            out["turns"] += 1
            usd = cost(getattr(message, "model", None) or out["model"], message.usage)
            out["cost"] += usd
            text = "".join(b.text for b in message.content if b.type == "text").strip()
            if text:
                out["text"] = text
            for c in _calls(message):
                log(f"{role}: {c}")
            if message.stop_reason == "refusal":           # the whole fallback chain declined
                out["status"] = "refused"
                break
            if budget is not None and not budget.add(usd):
                out["status"] = "over budget"              # leaving the loop runs none of this turn's tool calls
                break
        else:
            if last is not None and last.stop_reason == "tool_use":
                out["status"] = "turn cap"
            elif last is not None and last.stop_reason == "max_tokens":
                out["status"] = "cut off"
    except anthropic.APIError as e:
        out["status"], out["text"] = "error", f"{type(e).__name__}: {getattr(e, 'message', e)}"
    finally:
        runner.close()
    out["cost"] = round(out["cost"], 4)
    out["changes"] = toolbox.changes
    log(f"{role}: {out['status']} after {out['turns']} turn(s), ${out['cost']:.3f}, {toolbox.changes} change(s)"
        + (f": {out['text'][:400]}" if out["text"] else ""))
    return out
