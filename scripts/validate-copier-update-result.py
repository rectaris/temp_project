#!/usr/bin/env python3
"""Validate Copier destination state for conflict-safe updates."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

START_MARKER = re.compile(r"^<<<<<<<")
MIDDLE_MARKER = re.compile(r"^=======")
END_MARKER = re.compile(r"^>>>>>>>")


def run_git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def is_repository(repository: Path) -> bool:
    return (repository / ".git").is_dir() and bool(run_git(repository, "rev-parse", "--is-inside-work-tree").strip())


def has_complete_conflict_block(text: str) -> bool:
    in_block = False
    saw_separator = False
    for line in text.splitlines():
        if not in_block:
            if START_MARKER.match(line):
                in_block = True
                saw_separator = False
            continue

        if END_MARKER.match(line):
            if saw_separator:
                return True
            in_block = False
            saw_separator = False
            continue

        if MIDDLE_MARKER.match(line):
            saw_separator = True
            continue

        if START_MARKER.match(line):
            saw_separator = False
            continue

    return False


def conflict_scanned_paths(repository: Path) -> list[Path]:
    output = run_git(
        repository,
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    ).split("\0")
    paths: list[Path] = []
    for raw_path in output:
        if not raw_path:
            continue
        path = Path(raw_path)
        full_path = repository / path
        if path.name.endswith(".rej"):
            paths.append(path)
            continue
        if not full_path.is_file():
            continue
        if full_path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            content = full_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if has_complete_conflict_block(content):
            paths.append(path)
    return sorted(set(paths))


def validate_update_result(repository: Path) -> list[str]:
    problems: list[str] = []

    if run_git(repository, "ls-files", "-u").strip():
        problems.append("unresolved index conflicts")

    conflict_paths = conflict_scanned_paths(repository)
    if conflict_paths:
        printable = ", ".join(str(path) for path in conflict_paths)
        problems.append(f"inline conflict blocks or rejection files: {printable}")

    deleted = [
        path.strip()
        for path in run_git(repository, "diff", "--diff-filter=D", "--name-only").splitlines()
        if path.strip()
    ]
    allowed_deletions = {
        ".github/workflows/codex-ci-autofix.yml",
        "scripts/skillspector-scan.sh",
    }
    unexpected = sorted(path for path in deleted if path not in allowed_deletions)
    if unexpected:
        problems.append("unclassified tracked-file deletion: " + ", ".join(unexpected))

    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", default=".", help="Path to the copier destination")
    args = parser.parse_args(argv)

    destination = Path(args.destination).resolve()
    if not is_repository(destination):
        return 0

    issues = validate_update_result(destination)
    if issues:
        print("copier update post-render safety check failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
