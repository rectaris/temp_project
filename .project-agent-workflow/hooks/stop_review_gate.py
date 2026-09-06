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

GUARD_CANDIDATES = (
    ".project-agent-workflow/scripts/worktree_guard.py",
    "scripts/project_workflow/worktree_guard.py",
)


def block(reason: str) -> int:
    json.dump({"decision": "block", "reason": reason}, sys.stdout)
    sys.stdout.write("\n")
    return 0


def unretired_task(repo: Path) -> str | None:
    """Report the task worktree that still owes publication and retirement.

    A success response requires the accepted commit on its source branch and
    the task worktree and temporary branch gone. While a live binding remains,
    the task is unfinished, so this reports the exact remaining action. A
    stopped task is still not a success: the agent reports its retained state
    on the forced continuation rather than retiring anything here.
    """

    guard = None
    for candidate in GUARD_CANDIDATES:
        resolved = repo / candidate
        if resolved.is_file():
            guard = resolved
            break
    if guard is None:
        return None
    result = subprocess.run(
        ["python3", str(guard), "outstanding"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    manager = ".project-agent-workflow/scripts/manage-plan-worktrees.py"
    if not (repo / manager).is_file():
        manager = "scripts/manage-plan-worktrees.py"
    if result.returncode != 0:
        # A shipped guard that cannot answer leaves retained state unknown, and
        # an unknown answer is not evidence of a retired task.
        detail = (result.stderr or "").strip().splitlines()
        return (
            "The task-worktree guard could not report retained state"
            + (f": {detail[-1]}" if detail else ".")
            + " A success response requires no task worktree to remain. Resolve the "
            f"guard failure, then run `python3 {manager} publish` for a completed task."
        )
    try:
        entries = json.loads(result.stdout or "{}").get("outstanding")
    except ValueError:
        entries = None
    if not isinstance(entries, list):
        return (
            "The task-worktree guard returned no readable retained-state report. A "
            "success response requires no task worktree to remain."
        )
    if not entries:
        return None
    first = entries[0]
    remainder = (
        f" {len(entries) - 1} further task worktree(s) also remain." if len(entries) > 1 else ""
    )
    return (
        f"This repository still owns the task worktree for {first.get('task')} at "
        f"{first.get('worktree_path')}. A success response requires its accepted commit "
        f"on {first.get('source_ref')} and this worktree and its temporary branch "
        f"absent. Run `python3 {manager} publish` to publish and retire the completed "
        "task, or report the exact retained state and blocker if the work is not "
        "complete." + remainder
    )


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
    pending = unretired_task(repo)
    if pending is not None:
        return block(pending)
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
