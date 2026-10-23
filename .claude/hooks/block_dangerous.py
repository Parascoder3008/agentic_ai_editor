#!/usr/bin/env python3
"""Paras AI OS — PreToolUse safety hook for Bash.
Blocks destructive commands, secret leaks, and un-approved outbound sends.
Approved sends: set AI_OS_ALLOW_SEND=1 inline for that one command.
Exit 2 = block (reason shown to Claude); exit 0 = allow.
"""
import sys, json, re, os

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

if (data.get("tool_name") or data.get("tool") or "") not in ("Bash", ""):
    sys.exit(0)

cmd = ((data.get("tool_input") or {}).get("command") or "")
low = cmd.lower()

# 1) Destructive / system-dangerous commands — always blocked
DANGEROUS = [
    r"rm\s+-rf\s+[/~]", r"rm\s+-rf\s+\*", r":\(\)\s*\{.*\};:",
    r"\bmkfs\b", r"\bdd\s+if=", r"curl[^\n|]*\|\s*(sh|bash)",
    r"wget[^\n|]*\|\s*(sh|bash)", r"git\s+push\b[^\n]*--force",
    r"git\s+reset\s+--hard", r"chmod\s+-r\s+777\s+/",
]
for p in DANGEROUS:
    if re.search(p, low):
        print(f"[AI-OS safety] Blocked dangerous command (matched: {p}). If truly intended, run it yourself in a terminal.", file=sys.stderr)
        sys.exit(2)

# 2) Secret-leak guard — don't print credentials into the transcript
SECRETS = [r"cat\s+[^\n]*\.env", r"type\s+[^\n]*\.env",
           r"echo\s+\$(ghl|aisensy|anthropic|n8n|razorpay|api)", r"printenv"]
for p in SECRETS:
    if re.search(p, low):
        print(f"[AI-OS safety] Blocked a command that could print secrets (matched: {p}). Read specific values you need without dumping the whole env/.env.", file=sys.stderr)
        sys.exit(2)

# 3) Outbound send / money guard — draft always, fire only on explicit approval
if os.environ.get("AI_OS_ALLOW_SEND") != "1":
    SENDS = [r"backend\.aisensy\.com/campaign", r"conversations\s+send\b",
             r"api\.razorpay\.com/v1/payment", r"/messages\b[^\n]*whatsapp"]
    for p in SENDS:
        if re.search(p, low):
            print(f"[AI-OS safety] Outbound/paid action blocked (matched: {p}). Compliance gate: drafts only. Test to Paras's own number first, get approval, then re-run with AI_OS_ALLOW_SEND=1 for that single send.", file=sys.stderr)
            sys.exit(2)

sys.exit(0)
