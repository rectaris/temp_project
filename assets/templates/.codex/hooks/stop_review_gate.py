#!/usr/bin/env python3
"""Deterministic Stop-hook review gate for broad or high-risk diffs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


HIGH_RISK_PREFIXES = ("src/", "scripts/", ".codex/", ".github/", "docs/agent/")
HIGH_RISK_EXACT = {"package.json", "pyproject.toml", "uv.lock", "package-lock.json"}


def git(args: list[str], repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


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


def is_high_risk(path: str) -> bool:
    return path in HIGH_RISK_EXACT or any(path.startswith(prefix) for prefix in HIGH_RISK_PREFIXES)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}
    if payload.get("stop_hook_active"):
        print("{}")
        return 0

    repo = repo_root()
    paths = sorted(set(git(["diff", "--name-only"], repo) + git(["diff", "--cached", "--name-only"], repo) + git(["ls-files", "--others", "--exclude-standard"], repo)))
    risky = [path for path in paths if is_high_risk(path)]
    if risky or len(paths) >= 3:
        shown = "\n".join(f"- {path}" for path in (risky or paths)[:10])
        reason = (
            "Run a final review pass before answering. Check correctness, regressions, "
            "validation gaps, security-sensitive issues, and spec conflicts.\n\n"
            f"Relevant changed paths:\n{shown}"
        )
        json.dump({"decision": "block", "reason": reason}, sys.stdout)
        sys.stdout.write("\n")
    else:
        print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

