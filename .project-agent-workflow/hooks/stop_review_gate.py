#!/usr/bin/env python3
"""Deterministic Stop-hook gate for incomplete plan lifecycle state.

One adapter serves the Codex `Stop` event and the Copilot `agentStop` event.
Both surfaces read a decision object from stdout and treat a non-zero exit as
a hook error, so every path here exits zero and prints exactly one object.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


GATE_CANDIDATES = (
    ".project-agent-workflow/scripts/check-agent-completion.sh",
    "scripts/check-agent-completion.sh",
)

MISSING_GATE_REASON = (
    "This repository ships no plan completion gate at "
    ".project-agent-workflow/scripts/check-agent-completion.sh or "
    "scripts/check-agent-completion.sh. Restore the managed gate, then report "
    "the plan lifecycle state before finishing this turn."
)

FALLBACK_REASON = (
    "The plan completion gate failed without a diagnostic. Run "
    "check-agent-completion.sh --plans-only from the repository root, resolve "
    "the reported plan lifecycle state, and report the result."
)


def block(reason: str) -> int:
    json.dump({"decision": "block", "reason": reason}, sys.stdout)
    sys.stdout.write("\n")
    return 0


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip())
    return Path.cwd()


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}
    if payload.get("stop_hook_active"):
        print("{}")
        return 0

    repo = repo_root()
    completion_script = None
    for candidate in GATE_CANDIDATES:
        resolved = repo / candidate
        if resolved.is_file():
            completion_script = resolved
            break
    if completion_script is None:
        return block(MISSING_GATE_REASON)

    completion = subprocess.run(
        ["sh", str(completion_script), "--plans-only"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completion.returncode != 0:
        return block(completion.stderr.strip() or FALLBACK_REASON)
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
