#!/usr/bin/env python3
"""Lint generic plan files and allocate plan ids."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import planlib


ROOT = planlib.ROOT
PLAN = planlib.PLAN
CHECKED = planlib.CHECKED
HUMAN_DESIGN_VALUES = {"yes", "no"}
HUMAN_APPROVAL_VALUES = {"not_required", "pending", "approved"}
OPEN_STATUS_VALUES = {"in_progress", "deferred", "ready_to_archive", "backlog"}
MATRIX_MARKER_RE = re.compile(r"^\s*(A|B|C|推奨|理由|Recommended|Reason)\s*[:：]")
APPROACH_MARKERS = {"A", "B", "C"}
RATIONALE_MARKERS = {"推奨", "理由", "Recommended", "Reason"}
MATRIX_WINDOW_LINES = 20


def fail(message: str) -> None:
    print(f"plan lint failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def plan_ids() -> set[int]:
    return planlib.plan_ids()


def next_id() -> str:
    return planlib.next_id()


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
    try:
        values = planlib.require_manifest_fields(path)
    except planlib.PlanError as exc:
        fail(str(exc))
    review_value = planlib.manifest_scalar(values, "review_class")
    if review_value not in {"A", "B", "C"}:
        fail(f"{path} review_class must be A, B, or C")
    design_value = planlib.manifest_scalar(values, "human_design_required")
    if design_value not in HUMAN_DESIGN_VALUES:
        fail(f"{path} human_design_required must be yes or no")
    approval_value = planlib.manifest_scalar(values, "human_approval_status")
    if approval_value not in HUMAN_APPROVAL_VALUES:
        fail(f"{path} human_approval_status must be not_required, pending, or approved")
    if review_value == "C" and approval_value != "approved":
        fail(f"{path} class C work requires human_approval_status: approved before implementation")
    status_value = planlib.manifest_scalar(values, "status")
    if status_value not in OPEN_STATUS_VALUES:
        fail(f"{path} status must be in_progress, deferred, ready_to_archive, or backlog")
    if not planlib.manifest_scalar(values, "checked_summary_ja").strip():
        fail(f"{path} checked_summary_ja must be non-empty")


def lint_active_plan_body(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    markers: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = MATRIX_MARKER_RE.match(line)
        if match:
            markers.append((lineno, match.group(1)))

    for index, (lineno, marker) in enumerate(markers):
        if marker not in APPROACH_MARKERS:
            continue
        window = [
            candidate
            for candidate_lineno, candidate in markers[index:]
            if candidate_lineno - lineno <= MATRIX_WINDOW_LINES
        ]
        approach_count = len({candidate for candidate in window if candidate in APPROACH_MARKERS})
        has_rationale = any(candidate in RATIONALE_MARKERS for candidate in window)
        if approach_count >= 2 and has_rationale:
            fail(f"{path} contains an option-analysis matrix; keep full deliberation outside active plans")


def lint_manifests() -> None:
    for directory in planlib.OPEN_PLAN_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("[0-9][0-9][0-9]-*.md")):
            lint_manifest(path)
            if directory == planlib.ACTIVE_DIR:
                lint_active_plan_body(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--next-id", action="store_true", help="print the next available plan id")
    parser.add_argument("--print-context", metavar="PLAN", help="print shell context for a plan manifest")
    parser.add_argument("--add-active", nargs=2, metavar=("ID", "PATH"), help="add or replace an active index row")
    parser.add_argument("--remove-active", metavar="ID", help="remove an active index row")
    parser.add_argument("--append-checked", nargs=2, metavar=("ID", "PATH"), help="append a checked index row")
    args = parser.parse_args()
    if args.next_id:
        print(next_id())
        return 0
    if args.print_context:
        try:
            print("\n".join(planlib.context_lines(Path(args.print_context))))
        except planlib.PlanError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0
    if args.add_active:
        planlib.add_active(args.add_active[0], args.add_active[1])
        return 0
    if args.remove_active:
        planlib.remove_active(args.remove_active)
        return 0
    if args.append_checked:
        planlib.append_checked(args.append_checked[0], args.append_checked[1])
        return 0
    lint_plan_index()
    lint_checked_index()
    lint_manifests()
    print("plan docs lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
