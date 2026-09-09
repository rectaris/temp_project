#!/usr/bin/env python3
"""Deterministic pre-tool gate for risky agent commands."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


for script_dir in (
    Path(__file__).resolve().parents[1] / "scripts",
    Path(__file__).resolve().parents[2] / "scripts",
):
    if script_dir.is_dir():
        sys.path.insert(0, str(script_dir))
        break
import security_rules
import tool_command_context

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


GUARDS: dict = {}


def guard_module(cwd: Path):
    """Load the task-worktree guard of the repository that owns `cwd`.

    The guard is loaded for the directory the write actually runs in, so a
    command aimed at a governed repository is judged by that repository's guard
    rather than by whichever repository the hook process happens to sit in.
    Returns None when that directory belongs to no repository, or to one that
    ships no guard.
    """

    import importlib.util

    try:
        root = Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=cwd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=True,
            ).stdout.strip()
        )
    except Exception:
        return None
    if root in GUARDS:
        return GUARDS[root]
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
        sys.modules[f"worktree_guard_{abs(hash(root))}"] = module
        spec.loader.exec_module(module)
        GUARDS[root] = module
        return module
    GUARDS[root] = None
    return None


def recognized_writes(command: str) -> list[tuple[str, ...]] | None:
    """Return the `-C` directories of each recognized write in this command.

    An empty list means the command was read and writes nothing, so a lifecycle
    file name that is only read or counted no longer looks like a write. A
    command the interpreter cannot read falls back to the previous patterns,
    which classify text rather than invocations and therefore stay
    conservative.
    """

    try:
        return [write.directories for write in tool_command_context.repository_writes(command)]
    except tool_command_context.Unparsed:
        return [()] if any(pattern.search(command) for pattern in WRITE_COMMANDS) else []


def worktree_refusal(
    command: str,
    workdir: str | None,
    context_error: str | None,
    context_candidates: tuple[str, ...] = (),
) -> str | None:
    """Report why this write must move into a task worktree, if it must.

    A repository that ships no guard keeps its previous behavior. A shipped
    guard that refuses or fails blocks the write, so a broken boundary never
    silently allows one. Directory context that the payload contradicts or
    malforms blocks a governed write too, because the alternative would be to
    judge the write against a directory it does not run in. A rejected context
    is therefore checked against every directory the payload named, not against
    the hook's own process directory alone.
    """

    directories = recognized_writes(command)
    if not directories:
        return None
    base = Path.cwd()
    try:
        if context_error is not None:
            for value in (base, *context_candidates):
                candidate = Path(value)
                if not candidate.is_dir():
                    return context_error
                guard = guard_module(candidate)
                if guard is None:
                    continue
                try:
                    refusal = guard.require_task_worktree(
                        cwd=candidate, action="this repository write"
                    )
                except Exception:
                    # A guard that refuses this directory settles the question:
                    # the rejected context governs a write and must be reported.
                    return context_error
                if refusal is not None:
                    return context_error
            return None
        for entry in directories:
            cwd = tool_command_context.effective_directory(base, workdir, entry)
            guard = guard_module(cwd)
            if guard is None:
                continue
            guard.require_task_worktree(cwd=cwd, action="this repository write")
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
    try:
        workdir = tool_command_context.payload_workdir(payload)
        context_error = None
        context_candidates: tuple[str, ...] = ()
    except tool_command_context.ContextError as error:
        workdir, context_error = None, f"{error}"
        context_candidates = error.candidates
    for command in commands:
        reason = worktree_refusal(command, workdir, context_error, context_candidates)
        if reason is not None:
            json.dump({"decision": "block", "reason": reason}, sys.stdout)
            sys.stdout.write("\n")
            return 0
    json.dump({}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
