#!/usr/bin/env python3
"""Deterministic Stop-hook gate for completion and user-communication review."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


HIGH_RISK_PREFIXES = ("src/", "scripts/", ".codex/", ".github/", "docs/agent/")
HIGH_RISK_EXACT = {"package.json", "pyproject.toml", "uv.lock", "package-lock.json"}
JAPANESE_MESSAGE_MARKERS = (
    "完了",
    "変更",
    "修正",
    "実装",
    "対応",
    "追加",
    "更新",
    "削除",
    "提案",
    "調査",
    "確認",
    "原因",
    "検証",
)
ENGLISH_MESSAGE_MARKER_RE = re.compile(
    r"\b(?:complete|completed|implemented|fixed|changed|updated|added|removed|"
    r"proposal|propose|investigated|confirmed|validated|blocked)\b",
    re.IGNORECASE,
)
LONG_MESSAGE_CHARS = 120
MARKED_MESSAGE_CHARS = 12


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


def needs_communication_review(message: object) -> bool:
    if message is None:
        return True
    if not isinstance(message, str):
        return True
    if not message.strip():
        return False
    compact = re.sub(r"\s+", "", message)
    if len(compact) >= LONG_MESSAGE_CHARS:
        return True
    if len(compact) >= MARKED_MESSAGE_CHARS and (
        any(marker in message for marker in JAPANESE_MESSAGE_MARKERS)
        or ENGLISH_MESSAGE_MARKER_RE.search(message)
    ):
        return True
    return len(re.findall(r"(?m)^\s*[-*+]\s+", message)) >= 2


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}
    if payload.get("stop_hook_active"):
        print("{}")
        return 0

    repo = repo_root()
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
    paths = sorted(
        set(
            git(["diff", "--name-only"], repo)
            + git(["diff", "--cached", "--name-only"], repo)
            + git(["ls-files", "--others", "--exclude-standard"], repo)
        )
    )
    risky = [path for path in paths if is_high_risk(path)]
    reasons: list[str] = []
    if risky or len(paths) >= 3:
        shown = "\n".join(f"- {path}" for path in (risky or paths)[:10])
        reasons.append(
            "Run a final implementation review before answering. Check correctness, regressions, "
            "validation gaps, security-sensitive issues, and spec conflicts.\n\n"
            f"Relevant changed paths:\n{shown}"
        )
    if needs_communication_review(payload.get("last_assistant_message")):
        reasons.append(
            "Read docs/agent/SPEC_USER_COMMUNICATION.md directly and use the write-for-reader "
            "workflow to review the proposed user-facing message before answering. Revise any "
            "violation, preserve correct content and uncertainty, and do not add empty sections."
        )
    if reasons:
        json.dump({"decision": "block", "reason": "\n\n".join(reasons)}, sys.stdout)
        sys.stdout.write("\n")
    else:
        print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
