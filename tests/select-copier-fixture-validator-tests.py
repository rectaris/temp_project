#!/usr/bin/env python3
"""Select Copier fixture validator test commands from Git-visible changes.

This is a root-only test-development entrypoint. It never derives an executable
word from a changed path, a diff, an environment value, or repository content:
every selectable command is a literal declared in this file and is validated
against the repository command allowlist before it runs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Bind the repository-owned allowlist by path so no earlier `sys.modules` entry
# or `sys.path` entry can substitute a different command policy.
_ALLOWLIST_SPEC = importlib.util.spec_from_file_location(
    "copier_fixture_validator_plan_commands",
    ROOT / "scripts/plan_validation_commands.py",
)
if _ALLOWLIST_SPEC is None or _ALLOWLIST_SPEC.loader is None:
    raise SystemExit("could not load scripts/plan_validation_commands.py")
plan_validation_commands = importlib.util.module_from_spec(_ALLOWLIST_SPEC)
sys.modules[_ALLOWLIST_SPEC.name] = plan_validation_commands
_ALLOWLIST_SPEC.loader.exec_module(plan_validation_commands)


OUTPUT_LIMIT = 4000

AGGREGATE_COMMAND = ["python3", "tests/test-copier-fixture-validator.py"]

# A changed domain module selects only its own literal command.
DOMAIN_COMMANDS: dict[str, list[str]] = {
    "tests/copier_fixture_validator/contract.py": [
        "python3",
        "tests/copier_fixture_validator/contract.py",
    ],
    "tests/copier_fixture_validator/inventory.py": [
        "python3",
        "tests/copier_fixture_validator/inventory.py",
    ],
    "tests/copier_fixture_validator/execution.py": [
        "python3",
        "tests/copier_fixture_validator/execution.py",
    ],
    "tests/copier_fixture_validator/grammar.py": [
        "python3",
        "tests/copier_fixture_validator/grammar.py",
    ],
    "tests/copier_fixture_validator/placement.py": [
        "python3",
        "tests/copier_fixture_validator/placement.py",
    ],
}

# Shared surfaces every domain depends on, plus the selector and its own tests.
AGGREGATE_PATHS = frozenset(
    {
        "tests/copier_fixture_validator/__init__.py",
        "tests/copier_fixture_validator/support.py",
        "tests/test-copier-fixture-validator.py",
        "tests/select-copier-fixture-validator-tests.py",
        "tests/validation_tools/changes.py",
        "tests/validation_tools/plan.py",
        "scripts/plan_validation_commands.py",
        "scripts/project_workflow/copier_fixture_validator.py",
        "scripts/project_workflow/shell_lexical.py",
        "scripts/project_workflow/shell_functions.py",
        "scripts/project_workflow/shell_execution.py",
    }
)

# An unclassified path inside a relevant boundary also selects the complete suite.
RELEVANT_PREFIXES = (
    "tests/copier_fixture_validator/",
    "scripts/project_workflow/",
)


class GitQueryError(RuntimeError):
    """A Git command needed to determine changed files failed."""


def git(args: list[str]) -> list[str]:
    argv = ["git", "-c", "core.quotePath=false", *args, "-z"]
    try:
        result = subprocess.run(
            argv,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except UnicodeDecodeError as error:
        raise GitQueryError(f"Git output was not decodable: {shlex.join(argv)}") from error
    if result.returncode != 0:
        raise GitQueryError(f"Git query failed ({result.returncode}): {shlex.join(argv)}")
    return [entry for entry in result.stdout.split("\0") if entry]


def changed_files(mode: str) -> tuple[list[str], str, list[str]]:
    """Return the inspected paths, the diff mode, and the paths left out of it.

    A relevant path that stays outside the inspected set still forces the
    complete suite, because every domain module reads the shared working-tree
    fixtures whatever the index holds.
    """
    staged = set(git(["diff", "--cached", "--name-only"]))
    working = set(git(["diff", "--name-only"]))
    working.update(git(["ls-files", "--others", "--exclude-standard"]))
    if mode == "staged" or (mode == "auto" and staged):
        return sorted(staged), "staged", sorted(working - staged)
    return sorted(staged | working), "all", []


def existing(path: str) -> bool:
    return (ROOT / path).is_file()


def is_relevant(path: str) -> bool:
    return (
        path in DOMAIN_COMMANDS
        or path in AGGREGATE_PATHS
        or any(path.startswith(prefix) for prefix in RELEVANT_PREFIXES)
    )


def select_commands(paths: list[str], deferred: list[str] | None = None) -> list[list[str]]:
    """Map changed paths to literal test commands, never to derived text."""
    if any(is_relevant(path) for path in deferred or ()):
        return [list(AGGREGATE_COMMAND)]
    relevant = [path for path in paths if is_relevant(path)]
    if not relevant:
        return []
    domain: list[list[str]] = []
    for path in relevant:
        command = DOMAIN_COMMANDS.get(path)
        if command is None or not existing(path):
            return [list(AGGREGATE_COMMAND)]
        if command not in domain:
            domain.append(list(command))
    return domain


def validate_selected_commands(commands: list[list[str]]) -> None:
    plan_validation_commands.parse_validation_commands([shlex.join(command) for command in commands])


def command_records(commands: list[list[str]]) -> list[dict[str, object]]:
    return [{"argv": command, "raw": shlex.join(command)} for command in commands]


def output_tail(value: str) -> str:
    if len(value) <= OUTPUT_LIMIT:
        return value
    return value[-OUTPUT_LIMIT:]


def print_json(value: dict[str, object]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Select Copier fixture validator tests.")
    parser.add_argument("--all", action="store_true", help="inspect staged, unstaged, and untracked files")
    parser.add_argument("--staged", action="store_true", help="inspect staged files only")
    parser.add_argument("--print-only", action="store_true", help="print selected commands without running them")
    parser.add_argument("--json", action="store_true", help="print machine-readable selection and results")
    args = parser.parse_args(argv)

    if args.all and args.staged:
        parser.error("--all and --staged are mutually exclusive")

    mode = "staged" if args.staged else "all" if args.all else "auto"
    try:
        paths, diff_mode, deferred = changed_files(mode)
    except GitQueryError as error:
        if args.json:
            print_json({"changed_files": [], "commands": [], "error": str(error), "status": "git_query_failed"})
        else:
            print(f"select-copier-fixture-validator-tests: {error}", file=sys.stderr)
        return 1

    commands = select_commands(paths, deferred)
    try:
        validate_selected_commands(commands)
    except plan_validation_commands.ValidationCommandError as error:
        if args.json:
            print_json(
                {
                    "changed_files": paths,
                    "commands": [],
                    "diff_mode": diff_mode,
                    "error": str(error),
                    "status": "command_rejected",
                }
            )
        else:
            print(f"select-copier-fixture-validator-tests: {error}", file=sys.stderr)
        return 1

    if not commands:
        if args.json:
            print_json(
                {
                    "changed_files": paths,
                    "commands": [],
                    "diff_mode": diff_mode,
                    "status": "no_matching_tests",
                }
            )
            return 0
        print("no matching Copier fixture validator test is required")
        return 0

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
