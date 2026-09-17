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

# Credential variable names this repository's service policy declares. The
# policy sits at a fixed place inside the repository that installed this hook,
# so the names do not depend on the directory a command happens to run in.
DECLARED_CREDENTIAL_NAMES = security_rules.DeclaredCredentialNames(
    Path(__file__).resolve().parents[2]
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
    session_id: str | None = None,
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
            guard.require_task_worktree(
                cwd=cwd, action="this repository write", session_id=session_id,
            )
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


FILE_EDIT_TOOLS = {
    "apply_patch", "write", "edit", "multiedit", "create_file",
    "insert_edit_into_file", "replace_string_in_file", "str_replace_editor",
    "multi_replace_string_in_file",
}


# Envelope keys that can carry an edit's own targets at the top level, next to
# a nested `arguments`/`tool_input` section rather than instead of one.
FILE_EDIT_ENVELOPE_KEYS = (
    "patch", "input", "file_path", "filePath", "path", "replacements",
)


def file_edit_targets(tool: str, payload: dict) -> list[str]:
    """Return every path this edit can touch, refusing an ambiguous envelope.

    A runtime may carry the edit nested under `arguments` or `tool_input`, or
    directly on the payload. Deriving from one section alone would let an
    envelope that carries both hide a second target behind an innocuous one, so
    every section that carries an edit-bearing key is derived independently and
    the derived targets must agree.
    """

    nested = [payload[key] for key in ("arguments", "tool_input") if key in payload]
    if nested and any(value != nested[0] for value in nested[1:]):
        raise ValueError("file edit arguments contradict each other")
    containers = list(nested)
    if any(key in payload for key in FILE_EDIT_ENVELOPE_KEYS):
        containers.append(payload)
    if not containers:
        containers = [payload]
    derived = [file_edit_container_targets(tool, container) for container in containers]
    if any(targets != derived[0] for targets in derived[1:]):
        raise ValueError("file edit arguments contradict each other")
    return derived[0]


def file_edit_container_targets(tool: str, arguments) -> list[str]:
    if tool == "apply_patch":
        patches = [arguments] if isinstance(arguments, str) else [
            arguments[key] for key in ("patch", "input") if key in arguments
        ] if isinstance(arguments, dict) else []
        if not patches or any(patch != patches[0] for patch in patches[1:]):
            raise ValueError("file edit requires one unambiguous patch")
        patch = patches[0]
        if not isinstance(patch, str):
            raise ValueError("file edit patch must be text")
        lines = patch.strip().splitlines()
        if len(lines) < 3 or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
            raise ValueError("file edit requires a supported complete patch")
        targets = []
        can_move = False
        for line in lines[1:-1]:
            header = next((
                prefix for prefix in (
                    "*** Add File: ", "*** Update File: ", "*** Delete File: ",
                    "*** Move to: ",
                ) if line.startswith(prefix)
            ), None)
            if header is not None:
                if header == "*** Move to: " and not can_move:
                    raise ValueError("patch move has no unambiguous update source")
                targets.append(line[len(header):])
                can_move = header == "*** Update File: "
            else:
                can_move = False
                if line.startswith("*** ") and line != "*** End of File":
                    raise ValueError("file edit patch contains an unsupported header")
    else:
        if not isinstance(arguments, dict):
            raise ValueError("file edit arguments must be an object")
        if tool == "str_replace_editor" and arguments.get("command") == "view":
            return []
        entries = (
            arguments.get("replacements")
            if tool == "multi_replace_string_in_file" else [arguments]
        )
        if not isinstance(entries, list) or not entries:
            raise ValueError("file edit requires explicit target entries")
        targets = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("file edit target entry must be an object")
            paths = [entry[key] for key in ("file_path", "filePath", "path") if key in entry]
            if not paths or any(path != paths[0] for path in paths[1:]):
                raise ValueError("file edit requires one unambiguous path per target")
            targets.append(paths[0])
    if not targets or any(
        not isinstance(target, str) or not target.strip() or "\0" in target
        for target in targets
    ):
        raise ValueError("file edit targets must be nonblank paths")
    return targets


def file_edit_refusal(
    tool: str, payload: dict, workdir: str | None,
    context_error: str | None, session_id: str | None,
) -> str | None:
    if tool not in FILE_EDIT_TOOLS:
        return None
    try:
        targets = file_edit_targets(tool, payload)
        if not targets:
            return None
        if context_error is not None:
            return context_error
        base = tool_command_context.effective_directory(Path.cwd(), workdir, ())
        directories: set[Path] = set()
        for raw in targets:
            target = Path(raw)
            if not target.is_absolute():
                target = base / target
            # A tool may replace a symlink or follow it; guard both locations.
            for candidate in (target, target.resolve()):
                directory = candidate.parent
                while not directory.exists():
                    directory = directory.parent
                if not directory.is_dir():
                    raise ValueError("file edit target has a non-directory ancestor")
                directories.add(directory)
        for directory in sorted(directories):
            guard = guard_module(directory)
            if guard is not None:
                guard.require_task_worktree(
                    cwd=directory, action="this file edit", session_id=session_id,
                )
    except (ValueError, OSError, RuntimeError, ImportError, SyntaxError,
            AttributeError, TypeError, KeyError) as error:
        return f"file edit guard failed: {error}"
    return None


def main() -> int:
    payload = load_payload()
    commands = candidate_commands(payload)
    session_id = payload.get("session_id")
    if not isinstance(session_id, str):
        session_id = None
    for command in commands:
        for pattern, reason in RULES:
            if pattern.search(command):
                json.dump({"decision": "block", "reason": reason}, sys.stdout)
                sys.stdout.write("\n")
                return 0
        reason = security_rules.credential_display_refusal(
            command, DECLARED_CREDENTIAL_NAMES
        )
        if reason is not None:
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
        reason = worktree_refusal(
            command, workdir, context_error, context_candidates, session_id,
        )
        if reason is not None:
            json.dump({"decision": "block", "reason": reason}, sys.stdout)
            sys.stdout.write("\n")
            return 0
    tool = str(payload.get("tool_name") or payload.get("tool") or "").split(".")[-1].lower()
    reason = file_edit_refusal(tool, payload, workdir, context_error, session_id)
    if reason is not None:
        json.dump({"decision": "block", "reason": reason}, sys.stdout)
        sys.stdout.write("\n")
        return 0
    json.dump({}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
