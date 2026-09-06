#!/usr/bin/env python3
"""Select and run generic validation commands from changed files."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import plan_validation_commands


ROOT = Path.cwd()
OUTPUT_LIMIT = 4000
EXCLUDED_CHANGE_PREFIXES = (".project-agent-workflow-migration/",)


class GitQueryError(RuntimeError):
    """A Git command needed to determine changed files failed."""


def git(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        raise GitQueryError(f"Git query failed ({result.returncode}): {shlex.join(['git', *args])}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def changed_files(mode: str) -> tuple[list[str], str]:
    staged = filter_changed_files(git(["diff", "--cached", "--name-only"]))
    if mode == "staged":
        return staged, "staged"
    if mode == "auto" and staged:
        return staged, "staged"
    paths = set(staged)
    paths.update(git(["diff", "--name-only"]))
    paths.update(git(["ls-files", "--others", "--exclude-standard"]))
    return filter_changed_files(paths), "all"


def filter_changed_files(paths: list[str] | set[str]) -> list[str]:
    return sorted(
        path
        for path in paths
        if not any(path.startswith(prefix) for prefix in EXCLUDED_CHANGE_PREFIXES)
    )


def existing(path: str) -> bool:
    return (ROOT / path).exists()


# --- active plan index grammar: keep byte-identical across enforcing commands ---
ACTIVE_INDEX_TITLE = "# Active Plan"
ACTIVE_INDEX_EMPTY_BODY = "No active development items."
ACTIVE_INDEX_HEADER = "id\tpath\tstatus"
ACTIVE_INDEX_STATUSES = ("in_progress", "ready_to_archive", "deferred", "replan_required")
ACTIVE_INDEX_ID_RE = re.compile(r"[0-9]{3}")
ACTIVE_INDEX_ROW_PATH_RE = re.compile(r"docs/plan/active/([0-9]{3})-[a-z0-9][a-z0-9-]*\.md")


class ActiveIndexError(ValueError):
    """Raised when the active plan index is not one accepted representation."""


def read_active_index(path: Path) -> str:
    """Read one active plan index without newline translation."""

    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ActiveIndexError(f"active plan index is not UTF-8 text: {exc}") from exc


def parse_active_index(text: str) -> list[tuple[str, str, str]]:
    """Return the rows of one exact accepted active plan index document.

    The empty representation is the title, one blank line, and the empty
    marker. The populated representation is the title, one blank line, the
    actual-tab header, and one or more actual-tab rows. Every other nonempty
    document is rejected whole instead of being partially parsed.
    """

    if "\r" in text or not text.endswith("\n") or text.endswith("\n\n"):
        raise ActiveIndexError("active plan index must end with exactly one trailing newline")
    lines = text.split("\n")[:-1]
    if lines[:2] != [ACTIVE_INDEX_TITLE, ""]:
        raise ActiveIndexError("active plan index must start with its title and one blank line")
    body = lines[2:]
    if not body:
        raise ActiveIndexError("active plan index must hold the empty marker or the header")
    if body[0] == ACTIVE_INDEX_EMPTY_BODY:
        if len(body) > 1:
            raise ActiveIndexError("empty active plan index must hold no other content")
        return []
    if body[0] != ACTIVE_INDEX_HEADER:
        raise ActiveIndexError(f"active plan index needs the exact tab header: {body[0]!r}")
    if len(body) == 1:
        raise ActiveIndexError("active plan index header must be followed by at least one row")
    rows: list[tuple[str, str, str]] = []
    for line in body[1:]:
        columns = line.split("\t")
        if len(columns) != 3:
            raise ActiveIndexError(f"active plan index row needs three tab columns: {line!r}")
        plan_id, path, status = columns
        if ACTIVE_INDEX_ID_RE.fullmatch(plan_id) is None:
            raise ActiveIndexError(f"active plan index row needs a three-digit id: {line!r}")
        match = ACTIVE_INDEX_ROW_PATH_RE.fullmatch(path)
        if match is None:
            raise ActiveIndexError(f"active plan index row needs a normalized path: {line!r}")
        if match.group(1) != plan_id:
            raise ActiveIndexError(f"active plan index row id does not match its file: {line!r}")
        if status not in ACTIVE_INDEX_STATUSES:
            raise ActiveIndexError(f"active plan index row status is not allowed: {line!r}")
        if any(plan_id == row[0] for row in rows):
            raise ActiveIndexError(f"duplicate active plan index id: {plan_id}")
        if any(path == row[1] for row in rows):
            raise ActiveIndexError(f"duplicate active plan index path: {path}")
        rows.append((plan_id, path, status))
    return rows


def render_active_index(rows: list[tuple[str, str, str]]) -> str:
    """Serialize fully parsed rows as the single canonical representation."""

    if rows:
        body = "\n".join("\t".join(row) for row in rows)
        text = f"{ACTIVE_INDEX_TITLE}\n\n{ACTIVE_INDEX_HEADER}\n{body}\n"
    else:
        text = f"{ACTIVE_INDEX_TITLE}\n\n{ACTIVE_INDEX_EMPTY_BODY}\n"
    if parse_active_index(text) != rows:
        raise ActiveIndexError("canonical active plan index serialization failed")
    return text
# --- end active plan index grammar ---

def managed_plan_index() -> Path | None:
    """Return the active plan index when this project manages plan documents."""

    path = ROOT / "docs/plan/plan.md"
    if not path.is_file():
        return None
    if (ROOT / "docs/plan/active").is_dir():
        return path
    try:
        text = read_active_index(path)
    except ActiveIndexError:
        return path
    return path if ACTIVE_INDEX_TITLE in text.splitlines() else None


def active_plan_index_fault() -> str | None:
    """Report one fault when a managed active plan index is not canonical."""

    path = managed_plan_index()
    if path is None:
        return None
    try:
        parse_active_index(read_active_index(path))
    except ActiveIndexError as exc:
        return str(exc)
    return None


def uses_managed_plan_format() -> bool:
    return managed_plan_index() is not None


def uses_managed_external_service_format() -> bool:
    try:
        text = (ROOT / "docs/agent/external-services.yaml").read_text(encoding="utf-8")
    except OSError:
        return False
    if "credential_env:" in text:
        return False
    version_1 = "version: 1" in text and "authentication:" in text and "credential_reference:" in text
    version_2 = (
        "version: 2" in text
        and "access_profile: task_scoped_default_allow" in text
        and "provider_requirement: runtime_configured" in text
    )
    return version_1 or version_2


def add_command(commands: list[list[str]], command: list[str]) -> None:
    if command not in commands:
        commands.append(command)


def select_commands(paths: list[str], diff_mode: str) -> list[list[str]]:
    commands: list[list[str]] = []
    if diff_mode == "staged":
        add_command(commands, ["git", "diff", "--cached", "--check"])
    else:
        add_command(commands, ["git", "diff", "--cached", "--check"])
        add_command(commands, ["git", "diff", "--check"])

    shell_paths = [path for path in paths if path.endswith(".sh") and existing(path)]
    for path in shell_paths:
        add_command(commands, ["sh", "-n", path])

    py_files = [path for path in paths if path.endswith(".py") and existing(path)]
    if py_files:
        add_command(commands, ["python3", "-m", "py_compile", *py_files])

    if any(path.endswith(".toml") or path.startswith(".codex/") for path in paths) and existing(".project-agent-workflow/scripts/check-codex-toml.py"):
        add_command(commands, ["python3", ".project-agent-workflow/scripts/check-codex-toml.py"])

    managed_plan_format = uses_managed_plan_format()
    if managed_plan_format and any(path.startswith("docs/plan/") or path.startswith(".project-agent-workflow/scripts/") for path in paths) and existing(".project-agent-workflow/scripts/lint-plan-docs.py"):
        add_command(commands, ["python3", ".project-agent-workflow/scripts/lint-plan-docs.py"])

    if managed_plan_format and any(path.startswith("docs/plan/") for path in paths) and existing(".project-agent-workflow/scripts/format-plan-docs.py"):
        add_command(commands, ["python3", ".project-agent-workflow/scripts/format-plan-docs.py", "--check"])

    if any(path.startswith(".github/") or path.startswith(".project-agent-workflow/scripts/") for path in paths) and existing(".project-agent-workflow/scripts/security-static-check.py"):
        add_command(commands, ["python3", ".project-agent-workflow/scripts/security-static-check.py", "--changed"])

    external_service_paths = {
        "docs/agent/external-services.yaml",
        ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md",
        ".project-agent-workflow/scripts/check-external-service-policy.py",
    }
    if uses_managed_external_service_format() and any(path in external_service_paths for path in paths) and existing(".project-agent-workflow/scripts/check-external-service-policy.py"):
        add_command(commands, ["python3", ".project-agent-workflow/scripts/check-external-service-policy.py", "check"])

    if any(path in {"AGENTS.md", ".project-agent-workflow/docs/agent/spec-index.yaml"} or path.startswith("docs/agent/") for path in paths) and existing(".project-agent-workflow/scripts/structure-map.py"):
        add_command(commands, ["python3", ".project-agent-workflow/scripts/structure-map.py", "--check"])

    return commands


def validate_selected_commands(commands: list[list[str]]) -> None:
    raw_commands = [shlex.join(command) for command in commands]
    plan_validation_commands.parse_validation_commands(raw_commands)


def command_records(commands: list[list[str]]) -> list[dict[str, object]]:
    return [{"argv": command, "raw": shlex.join(command)} for command in commands]


def output_tail(value: str) -> str:
    if len(value) <= OUTPUT_LIMIT:
        return value
    return value[-OUTPUT_LIMIT:]


def print_json(value: dict[str, object]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="inspect staged, unstaged, and untracked files")
    parser.add_argument("--staged", action="store_true", help="inspect staged files only")
    parser.add_argument("--print-only", action="store_true", help="print selected commands without running them")
    parser.add_argument("--json", action="store_true", help="print machine-readable validation selection and results")
    args = parser.parse_args(argv)

    if args.all and args.staged:
        parser.error("--all and --staged are mutually exclusive")

    mode = "staged" if args.staged else "all" if args.all else "auto"
    fault = active_plan_index_fault()
    if fault is not None:
        if args.json:
            print_json({"changed_files": [], "commands": [], "error": fault, "status": "invalid_active_plan_index"})
        else:
            print(f"validate-changes: {fault}", file=sys.stderr)
        return 1

    try:
        paths, diff_mode = changed_files(mode)
    except GitQueryError as error:
        if args.json:
            print_json({"changed_files": [], "commands": [], "error": str(error), "status": "git_query_failed"})
        else:
            print(f"validate-changes: {error}", file=sys.stderr)
        return 1
    if not paths:
        if args.json:
            print_json({"changed_files": [], "commands": [], "diff_mode": diff_mode, "status": "no_changes"})
            return 0
        print("no changed files detected")
        return 0

    commands = select_commands(paths, diff_mode)
    validate_selected_commands(commands)
    if args.json and args.print_only:
        print_json(
            {
                "changed_files": paths,
                "commands": command_records(commands),
                "diff_mode": diff_mode,
                "status": "selected",
            }
        )
        return 0
    if args.json:
        results = []
        status = "passed"
        exit_code = 0
        for command in commands:
            result = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if result.returncode != 0 and status == "passed":
                status = "failed"
                exit_code = result.returncode
            results.append(
                {
                    "argv": command,
                    "raw": shlex.join(command),
                    "returncode": result.returncode,
                    "stdout_tail": output_tail(result.stdout),
                    "stderr_tail": output_tail(result.stderr),
                }
            )
            if result.returncode != 0:
                break
        print_json(
            {
                "changed_files": paths,
                "commands": command_records(commands),
                "diff_mode": diff_mode,
                "results": results,
                "status": status,
            }
        )
        return exit_code
    for command in commands:
        print(shlex.join(command))
    if args.print_only:
        return 0
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
