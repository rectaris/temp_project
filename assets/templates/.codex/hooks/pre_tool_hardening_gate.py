#!/usr/bin/env python3
"""Deterministic pre-tool gate for risky agent commands."""

from __future__ import annotations

import json
import re
import sys


RULES = (
    (re.compile(r"^\s*git\s+reset\s+--hard\b"), "hard reset discards work"),
    (re.compile(r"^\s*git\s+clean\b.*\s-f"), "git clean can delete untracked files"),
    (re.compile(r"^\s*git\s+push\b.*\s(--force|-f)(\s|$)"), "force push rewrites history"),
    (re.compile(r"^\s*sudo\b"), "privilege escalation is not autonomous work"),
    (re.compile(r"\b(curl|wget)\b.*\|\s*(sh|bash|zsh)\b"), "remote script piped to shell"),
    (re.compile(r"\b(cat|less|more|head|tail|grep|rg|awk|sed)\b.*(\.env|id_rsa|id_ed25519|\.pem|\.key)", re.I), "secret-bearing file read"),
)


def load_payload() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def candidate_commands(payload: dict) -> list[str]:
    out: list[str] = []
    for key in ("command", "cmd", "input"):
        value = payload.get(key)
        if isinstance(value, str):
            out.append(value)
    args = payload.get("arguments")
    if isinstance(args, dict):
        for key in ("command", "cmd", "shell_command"):
            value = args.get(key)
            if isinstance(value, str):
                out.append(value)
    return out


def main() -> int:
    payload = load_payload()
    for command in candidate_commands(payload):
        for pattern, reason in RULES:
            if pattern.search(command):
                json.dump({"decision": "block", "reason": reason}, sys.stdout)
                sys.stdout.write("\n")
                return 0
    json.dump({}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

