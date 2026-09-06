#!/usr/bin/env python3
"""Deterministic pre-tool gate for risky agent commands."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[2] / "template/.project-agent-workflow/scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import security_rules

RULES = (
    (re.compile(r"^\s*git\s+reset\s+--hard\b"), "hard reset discards work"),
    (re.compile(r"^\s*git\s+clean\b.*\s-f"), "git clean can delete untracked files"),
    (re.compile(r"^\s*git\s+push\b.*\s(--force|-f)(\s|$)"), "force push rewrites history"),
    (security_rules.SUDO_COMMAND, "privilege escalation is not autonomous work"),
    (security_rules.REMOTE_SCRIPT_PIPE, "remote script piped to shell"),
    (re.compile(r"\b(cat|less|more|head|tail|grep|rg|awk|sed)\b.*(\.env|id_rsa|id_ed25519|\.pem|\.key)", re.I), "secret-bearing file read"),
)

# Commands whose first repository effect is a write. The authoritative
# fail-closed surfaces are the lifecycle commands and the pre-commit hook; this
# gate reports the required worktree action before the effect happens rather
# than trying to classify every possible shell string.
WRITE_COMMANDS = (
    re.compile(r"^\s*git\s+(?:-[cC]\s+\S+\s+)*(?:commit|merge|rebase|cherry-pick|revert|am|apply|stash|update-ref|mv|rm|restore|switch|checkout)\b"),
    re.compile(r"^\s*git\s+(?:-[cC]\s+\S+\s+)*add\b"),
    re.compile(r"^\s*git\s+(?:-[cC]\s+\S+\s+)*(?:branch|tag)\s+(?!-{0,2}(?:l|list|show-current|contains)\b)"),
    re.compile(r"\b(?:create|complete|finalize|shelve|promote)-plan\.(?:sh|py)\b"),
    re.compile(r"\brestructure-plan\.py\b"),
    re.compile(r"\bplan_authoring\.py\s+write\b"),
)


class GuardUnavailable(RuntimeError):
    """A shipped task-worktree guard could not be loaded."""


def guard_module():
    """Load the shared task-worktree guard, or return None when unavailable."""

    import importlib.util

    if "worktree_guard" in sys.modules:
        return sys.modules["worktree_guard"]
    try:
        root = Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=True,
            ).stdout.strip()
        )
    except Exception:
        return None
    for candidate in (
        ".project-agent-workflow/scripts/worktree_guard.py",
        "scripts/project_workflow/worktree_guard.py",
    ):
        path = root / candidate
        if not path.is_file():
            continue
        # The guard is shipped here, so a load failure is a broken boundary
        # rather than an ungoverned repository. Raise it to the caller, which
        # blocks, instead of reporting the same None as "ships no guard".
        spec = importlib.util.spec_from_file_location("worktree_guard", path)
        if spec is None or spec.loader is None:
            raise GuardUnavailable(f"{candidate} could not be loaded")
        module = importlib.util.module_from_spec(spec)
        sys.modules["worktree_guard"] = module
        spec.loader.exec_module(module)
        return module
    return None


def worktree_refusal(command: str) -> str | None:
    """Report why this write must move into a task worktree, if it must.

    A repository that ships no guard keeps its previous behavior. A shipped
    guard that refuses or fails blocks the write, so a broken boundary never
    silently allows one.
    """

    if not any(pattern.search(command) for pattern in WRITE_COMMANDS):
        return None
    try:
        guard = guard_module()
        if guard is None:
            return None
        guard.require_task_worktree(action="this repository write")
    except Exception as error:
        return f"{error}"
    return None


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
    for container_key in ("arguments", "tool_input"):
        args = payload.get(container_key)
        if not isinstance(args, dict):
            continue
        for key in ("command", "cmd", "shell_command"):
            value = args.get(key)
            if isinstance(value, str):
                out.append(value)
    return out


def main() -> int:
    payload = load_payload()
    commands = candidate_commands(payload)
    for command in commands:
        for pattern, reason in RULES:
            if pattern.search(command):
                json.dump({"decision": "block", "reason": reason}, sys.stdout)
                sys.stdout.write("\n")
                return 0
    for command in commands:
        reason = worktree_refusal(command)
        if reason is not None:
            json.dump({"decision": "block", "reason": reason}, sys.stdout)
            sys.stdout.write("\n")
            return 0
    json.dump({}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
