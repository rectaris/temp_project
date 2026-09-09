#!/usr/bin/env python3
"""Deterministic Stop-hook gate for incomplete plan lifecycle state.

One adapter serves the Codex `Stop` event and the Copilot `agentStop` event.
Both surfaces read a decision object from stdout and treat a non-zero exit as
a hook error, so every path here exits zero and prints exactly one object.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
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

MAX_RETAINED_BLOCKS = 3
REPETITION_STATE = "project-agent-workflow-stop-repetition.json"


def block(reason: str) -> int:
    json.dump({"decision": "block", "reason": reason}, sys.stdout)
    sys.stdout.write("\n")
    return 0


def retained_block_required(repo: Path, reason: str | None) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        if reason is None:
            return False
        raise ValueError("cannot locate the common Git directory")
    path = Path(result.stdout.strip()) / REPETITION_STATE
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
    if reason is not None:
        flags |= os.O_CREAT
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileNotFoundError:
        if reason is None:
            return False
        raise
    with os.fdopen(descriptor, "r+", encoding="utf-8") as handle:
        info = os.fstat(handle.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise ValueError("repetition state must be an owner-only single-linked regular file")
        # Keep one inode under the lock: unlinking a reset would split concurrent readers.
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = handle.read(513)
        if len(raw) > 512:
            raise ValueError("repetition state exceeds its size bound")
        state = json.loads(raw) if raw else {"reason_digest": None, "count": 0}
        if not isinstance(state, dict) or set(state) != {"reason_digest", "count"}:
            raise ValueError("invalid repetition state fields")
        previous = state["reason_digest"]
        count = state["count"]
        if (
            type(count) is not int
            or not 0 <= count <= MAX_RETAINED_BLOCKS
            or not (
                previous is None and count == 0
                or isinstance(previous, str)
                and len(previous) == 64
                and all(char in "0123456789abcdef" for char in previous)
                and count > 0
            )
        ):
            raise ValueError("invalid repetition state values")
        current = hashlib.sha256(reason.encode("utf-8")).hexdigest() if reason else None
        if current is not None and previous == current and count == MAX_RETAINED_BLOCKS:
            return False
        state = {
            "reason_digest": current,
            "count": (count + 1 if current == previous else 1) if current else 0,
        }
        handle.seek(0)
        json.dump(state, handle, sort_keys=True)
        handle.write("\n")
        handle.truncate()
        handle.flush()
        os.fsync(handle.fileno())
    return reason is not None


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
    if not first.get("worktree_present", True):
        # The record outlived the directory it names, so publication is no
        # longer possible from here. Name the one command that clears it.
        return (
            f"This repository still owns a record for {first.get('task')} whose task "
            f"worktree at {first.get('worktree_path')} is already gone, so its "
            "retirement was interrupted. A success response requires no retained task "
            f"state. Run `python3 {manager} retire` to finish that retirement." + remainder
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
    pending = None
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
        )
        if completion.returncode != 0:
            reason = completion.stderr.strip() or FALLBACK_REASON
        else:
            pending = unretired_task(repo)
            reason = pending
    try:
        keep_blocking = retained_block_required(repo, pending)
    except (OSError, ValueError) as error:
        return block(
            (reason + " " if reason else "")
            + f"The retained-task repetition counter is unavailable: {error}. "
            "Report this blocker; do not claim the task was published or retired."
        )
    if reason is not None and (pending is None or keep_blocking):
        return block(reason)
    if pending is not None:
        print(
            "The identical retained-task blocker was already reported three times. "
            "End this turn by reporting it; publication and retirement remain incomplete.",
            file=sys.stderr,
        )
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
