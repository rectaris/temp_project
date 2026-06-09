#!/usr/bin/env python3
"""Select and run validation commands from changed files."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path.cwd()


def git(args: list[str]) -> list[str]:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def changed_files(all_changes: bool) -> list[str]:
    staged = git(["diff", "--cached", "--name-only"])
    if staged and not all_changes:
        return staged
    paths = set(staged)
    paths.update(git(["diff", "--name-only"]))
    paths.update(git(["ls-files", "--others", "--exclude-standard"]))
    return sorted(paths)


def existing(path: str) -> bool:
    return (ROOT / path).exists()


def select_commands(paths: list[str]) -> list[list[str]]:
    commands: list[list[str]] = [["git", "diff", "--check"]]
    if any(path.endswith(".sh") for path in paths):
        for path in paths:
            if path.endswith(".sh") and existing(path):
                commands.append(["sh", "-n", path])
    py_files = [path for path in paths if path.endswith(".py") and existing(path)]
    if py_files:
        commands.append(["python3", "-m", "py_compile", *py_files])
    if any(path.startswith("docs/plan/") or path.startswith("scripts/") for path in paths) and existing("scripts/lint-plan-docs.py"):
        commands.append(["python3", "scripts/lint-plan-docs.py"])
    if any(path.startswith(".github/") or path.startswith("scripts/") for path in paths) and existing("scripts/security-static-check.py"):
        commands.append(["python3", "scripts/security-static-check.py"])
    if any(path in {"AGENTS.md", "docs/agent/spec-index.yaml"} or path.startswith("docs/agent/") for path in paths) and existing("scripts/structure-map.py"):
        commands.append(["python3", "scripts/structure-map.py", "--check"])
    return commands


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--print-only", action="store_true")
    args = parser.parse_args()
    paths = changed_files(args.all)
    commands = select_commands(paths)
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
    raise SystemExit(main())
