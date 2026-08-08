#!/usr/bin/env python3
"""Restore and report active referent contracts without blocking the turn."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


MAX_SHOWN = 5


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


def load_payload() -> dict[str, Any]:
    try:
        value = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def active_contracts(root: Path) -> list[tuple[Path, str, str]]:
    contract_root = root / ".agent-artifacts/referent-contracts"
    if not contract_root.is_dir():
        return []
    active: list[tuple[Path, str, str]] = []
    for path in sorted(contract_root.glob("**/contract.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            active.append((path, "invalid", "unknown"))
            continue
        if isinstance(value, dict) and value.get("active") is True:
            active.append((path, str(value.get("state", "unknown")), str(value.get("mode", "unknown"))))
    return active


def main() -> int:
    payload = load_payload()
    if payload.get("stop_hook_active"):
        print("{}")
        return 0
    root = repo_root()
    checker = ".project-agent-workflow/scripts/referent-contract.py"
    if not (root / checker).is_file():
        checker = "scripts/referent-contract.py"
    active = active_contracts(root)
    if not active:
        print("{}")
        return 0
    lines = [
        "Referent-first advisory: reread and complete active semantic contracts before relying on labels or compressed context."
    ]
    for path, state, mode in active[:MAX_SHOWN]:
        relative = path.relative_to(root)
        lines.append(f"- {relative} (state: {state}, mode: {mode})")
        lines.append(f"  Check: python3 {checker} check {relative}")
    if len(active) > MAX_SHOWN:
        lines.append(f"- {len(active) - MAX_SHOWN} additional active contract(s) not shown")
    json.dump({"continue": True, "systemMessage": "\n".join(lines)}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
