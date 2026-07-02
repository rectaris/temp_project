#!/usr/bin/env python3
"""Validate plan manifest validation commands without invoking a shell."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import shlex
import subprocess
import sys


class ValidationCommandError(ValueError):
    pass


SHELL_METACHARS = frozenset(";|&<>`$\\\n\r")
UNSUPPORTED_CHARS = frozenset("\"'~*?[]{}()")
ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

EXACT_COMMANDS = {
    ("git", "diff", "--check"),
    ("git", "diff", "--cached", "--check"),
    ("python3", "scripts/check-codex-toml.py"),
    ("python3", "scripts/lint-plan-docs.py"),
    ("python3", "scripts/format-plan-docs.py", "--check"),
    ("python3", "scripts/security-static-check.py"),
    ("python3", "scripts/structure-map.py", "--check"),
    ("python3", "scripts/validate-changes.py"),
    ("python3", "scripts/validate-changes.py", "--all"),
    ("python3", "scripts/validate-changes.py", "--print-only"),
    ("python3", "scripts/plan_validation_commands.py", "--self-test"),
    ("sh", "scripts/lint-plan-docs.sh"),
    ("sh", "scripts/format-plan-docs.sh", "--check"),
    ("sh", "scripts/check-agent-completion.sh"),
    ("npm", "run", "build"),
    ("npm", "run", "test"),
    ("npm", "run", "test:unit"),
    ("npm", "run", "lint"),
    ("npm", "run", "verify"),
    ("pytest",),
    ("uv", "run", "pytest"),
}


@dataclass(frozen=True)
class ValidationCommand:
    raw: str
    argv: tuple[str, ...]


def extract_validation_commands(plan_path: Path) -> list[str]:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    commands: list[str] = []
    in_validation = False
    for line in lines:
        if line.startswith("# "):
            break
        if line == "validation:":
            in_validation = True
            continue
        if in_validation:
            if line.startswith("  - "):
                commands.append(line[4:])
                continue
            if line and not line.startswith(" "):
                break
    if not commands:
        raise ValidationCommandError(f"validation list is empty in {plan_path}")
    return commands


def parse_validation_command(command: str) -> ValidationCommand:
    if not command.strip():
        raise ValidationCommandError("validation command must not be empty")
    if command != command.strip():
        raise ValidationCommandError(f"validation command has surrounding whitespace: {command!r}")

    bad_shell = sorted({char for char in command if char in SHELL_METACHARS})
    if bad_shell:
        raise ValidationCommandError(
            f"shell metacharacter is not allowed in validation command: {''.join(bad_shell)!r}"
        )

    bad_unsupported = sorted({char for char in command if char in UNSUPPORTED_CHARS})
    if bad_unsupported:
        raise ValidationCommandError(
            f"unsupported character is not allowed in validation command: {''.join(bad_unsupported)!r}"
        )

    try:
        argv = tuple(shlex.split(command, posix=True))
    except ValueError as exc:
        raise ValidationCommandError(f"could not parse validation command: {exc}") from exc

    if not argv:
        raise ValidationCommandError("validation command must not be empty")
    if ENV_ASSIGNMENT_RE.match(argv[0]):
        raise ValidationCommandError("environment assignment is not allowed in validation command")

    validate_argv(argv, command)
    return ValidationCommand(raw=command, argv=argv)


def validate_argv(argv: tuple[str, ...], command: str) -> None:
    if argv in EXACT_COMMANDS:
        return
    if is_script_syntax_check(argv):
        return
    if is_python_compile(argv):
        return
    if is_pytest_path_check(argv):
        return
    raise ValidationCommandError(f"validation command is not allowlisted: {command}")


def is_script_syntax_check(argv: tuple[str, ...]) -> bool:
    if len(argv) != 3 or argv[:2] not in {("sh", "-n"), ("bash", "-n")}:
        return False
    script = Path(argv[2])
    if script.is_absolute() or ".." in script.parts or script.suffix != ".sh":
        return False
    return script.parts[0] in {"scripts", "tests"} or script.parts[:2] == ("template", "scripts")


def is_python_compile(argv: tuple[str, ...]) -> bool:
    if len(argv) < 4 or argv[:3] != ("python3", "-m", "py_compile"):
        return False
    for raw_path in argv[3:]:
        path = Path(raw_path)
        if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
            return False
        if path.parts[0] not in {"scripts", "tests", ".codex"} and path.parts[:2] != ("template", "scripts"):
            return False
    return True


def is_pytest_path_check(argv: tuple[str, ...]) -> bool:
    if len(argv) < 2:
        return False
    if argv[0] == "pytest":
        paths = argv[1:]
    elif len(argv) >= 4 and argv[:3] == ("uv", "run", "pytest"):
        paths = argv[3:]
    else:
        return False
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "tests":
            return False
    return True


def parse_validation_commands(commands: list[str]) -> list[ValidationCommand]:
    return [parse_validation_command(command) for command in commands]


def check_plan(path: Path) -> list[ValidationCommand]:
    return parse_validation_commands(extract_validation_commands(path))


def run_plan(path: Path) -> None:
    for command in check_plan(path):
        print(f"+ {shlex.join(command.argv)}", flush=True)
        subprocess.run(command.argv, check=True)


def self_test() -> None:
    parse_validation_command("git diff --check")
    parse_validation_command("python3 -m py_compile scripts/example.py tests/example.py")
    parse_validation_command("sh -n scripts/example.sh")
    for bad in ("git diff --check; rm -rf .", "FOO=1 pytest", "python3 - <<EOF"):
        try:
            parse_validation_command(bad)
        except ValidationCommandError:
            continue
        raise ValidationCommandError(f"self-test accepted unsafe command: {bad}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")

    check_parser = subparsers.add_parser("check-plan")
    check_parser.add_argument("plan_path", type=Path)

    run_parser = subparsers.add_parser("run-plan")
    run_parser.add_argument("plan_path", type=Path)

    commands_parser = subparsers.add_parser("check-commands")
    commands_parser.add_argument("commands", nargs="+")

    parser.add_argument("--self-test", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.self_test:
            self_test()
        elif args.command == "check-plan":
            check_plan(args.plan_path)
        elif args.command == "run-plan":
            run_plan(args.plan_path)
        elif args.command == "check-commands":
            parse_validation_commands(args.commands)
        else:
            parser.print_help()
            return 2
    except ValidationCommandError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
