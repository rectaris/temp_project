#!/usr/bin/env python3
"""Select and run generic validation commands from changed files."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

import plan_validation_commands


ROOT = Path.cwd()


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
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def changed_files(mode: str) -> tuple[list[str], str]:
    staged = git(["diff", "--cached", "--name-only"])
    if mode == "staged":
        return staged, "staged"
    if mode == "auto" and staged:
        return staged, "staged"
    paths = set(staged)
    paths.update(git(["diff", "--name-only"]))
    paths.update(git(["ls-files", "--others", "--exclude-standard"]))
    return sorted(paths), "all"


def existing(path: str) -> bool:
    return (ROOT / path).exists()


def add_command(commands: list[list[str]], command: list[str]) -> None:
    if command not in commands:
        commands.append(command)


def select_commands(paths: list[str], diff_mode: str) -> list[list[str]]:
    commands: list[list[str]] = []
    add_command(commands, ["git", "diff", "--cached", "--check"] if diff_mode == "staged" else ["git", "diff", "--check"])

    shell_paths = [path for path in paths if path.endswith(".sh") and existing(path)]
    for path in shell_paths:
        add_command(commands, ["sh", "-n", path])

    py_files = [path for path in paths if path.endswith(".py") and existing(path)]
    if py_files:
        add_command(commands, ["python3", "-m", "py_compile", *py_files])

    if any(path.endswith(".toml") or path.startswith(".codex/") for path in paths) and existing("scripts/check-codex-toml.py"):
        add_command(commands, ["python3", "scripts/check-codex-toml.py"])

    if any(path.startswith("docs/plan/") or path.startswith("scripts/") for path in paths) and existing("scripts/lint-plan-docs.py"):
        add_command(commands, ["python3", "scripts/lint-plan-docs.py"])

    if any(path.startswith("docs/plan/") for path in paths) and existing("scripts/format-plan-docs.py"):
        add_command(commands, ["python3", "scripts/format-plan-docs.py", "--check"])

    if any(path.startswith(".github/") or path.startswith("scripts/") for path in paths) and existing("scripts/security-static-check.py"):
        add_command(commands, ["python3", "scripts/security-static-check.py"])

    if any(path in {"AGENTS.md", "docs/agent/spec-index.yaml"} or path.startswith("docs/agent/") for path in paths) and existing("scripts/structure-map.py"):
        add_command(commands, ["python3", "scripts/structure-map.py", "--check"])

    return commands


def validate_selected_commands(commands: list[list[str]]) -> None:
    raw_commands = [shlex.join(command) for command in commands]
    plan_validation_commands.parse_validation_commands(raw_commands)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="inspect staged, unstaged, and untracked files")
    parser.add_argument("--staged", action="store_true", help="inspect staged files only")
    parser.add_argument("--print-only", action="store_true", help="print selected commands without running them")
    args = parser.parse_args(argv)

    if args.all and args.staged:
        parser.error("--all and --staged are mutually exclusive")

    mode = "staged" if args.staged else "all" if args.all else "auto"
    paths, diff_mode = changed_files(mode)
    if not paths:
        print("no changed files detected")
        return 0

    commands = select_commands(paths, diff_mode)
    validate_selected_commands(commands)
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
