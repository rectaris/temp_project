#!/usr/bin/env python3
"""Deterministic Stop-hook gate for incomplete plan lifecycle state."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


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
    completion_script = repo / ".project-agent-workflow/scripts/check-agent-completion.sh"
    if not completion_script.is_file():
        completion_script = repo / "scripts/check-agent-completion.sh"
    if completion_script.is_file():
        completion = subprocess.run(
            ["sh", str(completion_script), "--plans-only"],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completion.returncode != 0:
            json.dump({"decision": "block", "reason": completion.stderr.strip()}, sys.stdout)
            sys.stdout.write("\n")
            return 0
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
