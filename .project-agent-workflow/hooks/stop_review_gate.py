#!/usr/bin/env python3
"""Read-only Stop reminders that never prevent ending a conversation turn.

One adapter serves the Codex `Stop` event and the Copilot `agentStop` event.
Both surfaces receive an empty decision on stdout and exit zero. Diagnostics
go to stderr; completion and write enforcement belong to operation boundaries.
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
    "the plan lifecycle state before claiming completion of the affected work."
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

def unretired_task(repo: Path) -> str | None:
    """Report the task worktree that still owes publication and retirement.

    This is repository-wide context, not an assignment to this session. Ending
    a turn grants no publication, retirement or completion authority.
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
        timeout=5,
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
            + " Retirement remains unverified. The owning task must resolve the "
            "guard failure before claiming completion."
        )
    try:
        entries = json.loads(result.stdout or "{}").get("outstanding")
    except ValueError:
        entries = None
    if not isinstance(entries, list):
        return (
            "The task-worktree guard returned no readable retained-state report. "
            "The owning task must verify retirement before claiming completion."
        )
    if not entries:
        return None
    first = entries[0]
    remainder = (
        f" {len(entries) - 1} further task worktree(s) also remain." if len(entries) > 1 else ""
    )
    if not first.get("worktree_present", True):
        # The record outlived the directory it names, so publication is no
        # longer possible from here. Name the one command that clears it.
        return (
            f"This repository still owns a record for {first.get('task')} whose task "
            f"worktree at {first.get('worktree_path')} is already gone, so its "
            "retirement was interrupted. That task remains incomplete. "
            f"Its owning session uses `python3 {manager} retire` to finish that retirement." + remainder
        )
    return (
        f"This repository still owns the task worktree for {first.get('task')} at "
        f"{first.get('worktree_path')}. Completing that task requires its accepted commit "
        f"on {first.get('source_ref')} and this worktree and its temporary branch "
        f"absent. Its owning session uses `python3 {manager} publish` to publish and retire the completed "
        "task; unfinished work remains recorded until its owner can complete it." + remainder
    )


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=5,
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip())
    return Path.cwd()


def main() -> int:
    # Stop is a conversation boundary, not evidence of task completion. Never
    # classify message text, require a session id, or consume shared counters.
    try:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except (ValueError, UnicodeError):
            payload = {}
        if isinstance(payload, dict) and payload.get("stop_hook_active"):
            return 0

        repo = repo_root()
        completion_script = next(
            (repo / candidate for candidate in GATE_CANDIDATES if (repo / candidate).is_file()),
            None,
        )
        if completion_script is None:
            reason = MISSING_GATE_REASON
        else:
            completion = subprocess.run(
                ["sh", str(completion_script), "--plans-only"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=5,
            )
            reason = (
                completion.stderr.strip() or FALLBACK_REASON
                if completion.returncode != 0
                else unretired_task(repo)
            )
        if reason:
            print(
                "Unfinished repository work (advisory only; this does not assign "
                "another session's task or require continuing this turn): " + reason,
                file=sys.stderr,
            )
    except Exception as error:
        # Diagnostics are best-effort; unexpected report shapes cannot turn a
        # conversation boundary into a hook error or a forced continuation.
        print(
            f"Stop reminder unavailable: {error}. Ending this turn does not "
            "establish task completion; the owning task must verify its state.",
            file=sys.stderr,
        )
    finally:
        print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
