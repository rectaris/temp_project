#!/usr/bin/env python3
"""Lint generic plan files and allocate plan ids."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path.cwd()
PLAN = ROOT / "docs/plan/plan.md"
CHECKED = ROOT / "docs/plan/checked.md"
PLAN_DIRS = [ROOT / "docs/plan/active", ROOT / "docs/plan/backlog", ROOT / "docs/plan/checked"]
REQUIRED_FIELDS = ("status:", "review_class:", "target_files:", "required_specs:", "validation:", "acceptance:")


def fail(message: str) -> None:
    print(f"plan lint failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def plan_ids() -> set[int]:
    ids: set[int] = set()
    for directory in PLAN_DIRS:
        if not directory.exists():
            continue
        for path in directory.glob("[0-9][0-9][0-9]-*.md"):
            ids.add(int(path.name[:3]))
    if CHECKED.exists():
        for line in CHECKED.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^(\d{3})\s+", line)
            if match:
                ids.add(int(match.group(1)))
    return ids


def next_id() -> str:
    ids = plan_ids()
    value = 1
    while value in ids:
        value += 1
    return f"{value:03d}"


def lint_plan_index() -> None:
    if not PLAN.is_file():
        fail("missing docs/plan/plan.md")
    text = PLAN.read_text(encoding="utf-8")
    if not text.startswith("# Active Plan\n"):
        fail("docs/plan/plan.md must start with '# Active Plan'")
    if "No active development items." in text:
        return
    if "id\tpath\tstatus" not in text:
        fail("active plan index must contain TSV header: id path status")
    for line in text.splitlines():
        if re.match(r"^\d{3}\t", line):
            parts = line.split("\t")
            if len(parts) != 3:
                fail(f"bad active index row: {line}")
            if not (ROOT / parts[1]).is_file():
                fail(f"active index points to missing file: {parts[1]}")


def lint_checked_index() -> None:
    if not CHECKED.is_file():
        fail("missing docs/plan/checked.md")
    text = CHECKED.read_text(encoding="utf-8")
    if not text.startswith("# Checked Plan Index\n"):
        fail("docs/plan/checked.md must start with '# Checked Plan Index'")
    if "id\tpath" not in text:
        fail("checked index must contain TSV header: id path")
    for line in text.splitlines():
        if re.match(r"^\d{3}\t", line):
            parts = line.split("\t")
            if len(parts) != 2:
                fail(f"bad checked index row: {line}")
            if not (ROOT / parts[1]).is_file():
                fail(f"checked index points to missing file: {parts[1]}")


def lint_manifest(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for field in REQUIRED_FIELDS:
        if field not in text:
            fail(f"{path} missing field: {field}")
    review = re.search(r"^review_class:\s*([ABC])\s*$", text, re.MULTILINE)
    if not review:
        fail(f"{path} review_class must be A, B, or C")


def lint_manifests() -> None:
    for directory in (ROOT / "docs/plan/active", ROOT / "docs/plan/backlog"):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("[0-9][0-9][0-9]-*.md")):
            lint_manifest(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--next-id", action="store_true", help="print the next available plan id")
    args = parser.parse_args()
    if args.next_id:
        print(next_id())
        return 0
    lint_plan_index()
    lint_checked_index()
    lint_manifests()
    print("plan docs lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
