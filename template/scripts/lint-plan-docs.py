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
REQUIRED_FIELDS = (
    "status:",
    "task_type:",
    "review_class:",
    "human_design_required:",
    "human_approval_status:",
    "target_files:",
    "required_specs:",
    "validation:",
    "acceptance:",
    "expected_output:",
    "checked_summary_ja:",
)
HUMAN_DESIGN_VALUES = {"yes", "no"}
HUMAN_APPROVAL_VALUES = {"not_required", "pending", "approved"}


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
    design = re.search(r"^human_design_required:\s*(\S+)\s*$", text, re.MULTILINE)
    if not design or design.group(1) not in HUMAN_DESIGN_VALUES:
        fail(f"{path} human_design_required must be yes or no")
    approval = re.search(r"^human_approval_status:\s*(\S+)\s*$", text, re.MULTILINE)
    if not approval or approval.group(1) not in HUMAN_APPROVAL_VALUES:
        fail(f"{path} human_approval_status must be not_required, pending, or approved")
    if review.group(1) == "C" and approval.group(1) != "approved":
        fail(f"{path} class C work requires human_approval_status: approved before implementation")
    summary = re.search(r"^checked_summary_ja:\s*(.+)\s*$", text, re.MULTILINE)
    if not summary or not summary.group(1).strip():
        fail(f"{path} checked_summary_ja must be non-empty")


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
