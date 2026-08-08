#!/usr/bin/env python3
"""Lint generic plan files and allocate plan ids."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import planlib
import plan_validation_commands


ROOT = planlib.ROOT
PLAN = planlib.PLAN
CHECKED = planlib.CHECKED
HUMAN_DESIGN_VALUES = {"yes", "no"}
HUMAN_APPROVAL_VALUES = {"not_required", "pending", "approved"}
OPEN_STATUS_VALUES = {"in_progress", "deferred", "ready_to_archive", "backlog"}
# Copier updates must continue to read archives produced before checked became
# the terminal manifest value. New finalization is tested to emit checked.
CLOSED_STATUS_VALUES = {"checked", "completed", "ready_to_archive"}
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
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for line in text.splitlines():
        if re.match(r"^\d{3}\t", line):
            parts = line.split("\t")
            if len(parts) != 3:
                fail(f"bad active index row: {line}")
            if parts[0] in seen_ids:
                fail(f"duplicate active index id: {parts[0]}")
            if parts[1] in seen_paths:
                fail(f"duplicate active index path: {parts[1]}")
            seen_ids.add(parts[0])
            seen_paths.add(parts[1])
            if not Path(parts[1]).name.startswith(parts[0] + "-"):
                fail(f"active index id does not match filename: {line}")
            indexed_path = ROOT / parts[1]
            if indexed_path.parent != planlib.ACTIVE_DIR:
                fail(f"active index path is outside active plan directory: {parts[1]}")
            if not indexed_path.is_file():
                fail(f"active index points to missing file: {parts[1]}")
            try:
                values = planlib.parse_manifest(indexed_path)
            except planlib.PlanError as exc:
                fail(str(exc))
            if planlib.manifest_scalar(values, "status") != parts[2]:
                fail(f"active index status does not match manifest: {parts[1]}")


def lint_checked_index() -> None:
    if not CHECKED.is_file():
        fail("missing docs/plan/checked.md")
    text = CHECKED.read_text(encoding="utf-8")
    if not text.startswith("# Checked Plan Index\n"):
        fail("docs/plan/checked.md must start with '# Checked Plan Index'")
    if "id\tpath" not in text:
        fail("checked index must contain TSV header: id path")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for line in text.splitlines():
        if re.match(r"^\d{3}\t", line):
            parts = line.split("\t")
            if len(parts) != 2:
                fail(f"bad checked index row: {line}")
            if parts[0] in seen_ids:
                fail(f"duplicate checked index id: {parts[0]}")
            if parts[1] in seen_paths:
                fail(f"duplicate checked index path: {parts[1]}")
            seen_ids.add(parts[0])
            seen_paths.add(parts[1])
            if not Path(parts[1]).name.startswith(parts[0] + "-"):
                fail(f"checked index id does not match filename: {line}")
            if not (ROOT / parts[1]).is_file():
                fail(f"checked index points to missing file: {parts[1]}")
            if planlib.CHECKED_DIR not in (ROOT / parts[1]).parents:
                fail(f"checked index path is outside checked archive: {parts[1]}")


def lint_manifest(path: Path) -> None:
    if not path.is_absolute():
        path = planlib.ROOT / path
    text = path.read_text(encoding="utf-8")
    parsed = planlib.parse_manifest(path)
    is_checked = planlib.CHECKED_DIR in path.parents
    is_legacy_checked = bool(
        is_checked
        and not parsed.get("task_types")
        and planlib.manifest_scalar(parsed, "task_type")
    )
    if not is_legacy_checked:
        legacy_fields = [
            field
            for field in ("task_type", "target_files", "expected_output")
            if re.search(rf"^{field}:", text, flags=re.MULTILINE)
        ]
        if legacy_fields:
            fail(f"{path} uses removed manifest fields: {', '.join(legacy_fields)}")
        inline_lists = [
            field
            for field in ("task_types", "write_scope", "context_files", "required_specs")
            if re.search(rf"^{field}:[ \t]+\S", text, flags=re.MULTILINE)
        ]
        if inline_lists:
            fail(f"{path} list fields must use indented list items: {', '.join(inline_lists)}")
    try:
        fields = planlib.LEGACY_REQUIRED_FIELDS if is_legacy_checked else planlib.REQUIRED_FIELDS
        values = planlib.require_manifest_fields(path, fields)
    except planlib.PlanError as exc:
        fail(str(exc))
    review_value = planlib.manifest_scalar(values, "review_class")
    if review_value not in {"A", "B", "C"}:
        fail(f"{path} review_class must be A, B, or C")
    design_value = planlib.manifest_scalar(values, "human_design_required")
    if design_value not in HUMAN_DESIGN_VALUES:
        fail(f"{path} human_design_required must be yes or no")
    if is_legacy_checked:
        task_types = [planlib.manifest_scalar(values, "task_type")]
    else:
        task_types = values["task_types"]
        assert isinstance(task_types, list)
    if len(task_types) != len(set(task_types)):
        fail(f"{path} task_types must not contain duplicates")
    unknown_task_types = sorted(set(task_types) - planlib.task_type_values())
    if unknown_task_types:
        fail(f"{path} task_types must match route keys from .project-agent-workflow/docs/agent/spec-index.yaml: {', '.join(unknown_task_types)}")
    approval_value = planlib.manifest_scalar(values, "human_approval_status")
    if approval_value not in HUMAN_APPROVAL_VALUES:
        fail(f"{path} human_approval_status must be not_required, pending, or approved")
    status_value = planlib.manifest_scalar(values, "status")
    allowed_statuses = CLOSED_STATUS_VALUES if is_checked else OPEN_STATUS_VALUES
    if status_value not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        fail(f"{path} status must be one of: {allowed}")
    if path.parent == planlib.ACTIVE_DIR and status_value not in {"in_progress", "deferred", "ready_to_archive"}:
        fail(f"{path} active plan status must be in_progress, deferred, or ready_to_archive")
    if path.parent == planlib.BACKLOG_DIR and status_value not in {"backlog", "deferred"}:
        fail(f"{path} backlog plan status must be backlog or deferred")
    if not is_legacy_checked and review_value == "C" and approval_value not in {"pending", "approved"}:
        fail(f"{path} class C plan requires human_approval_status: pending or approved")
    if review_value == "C" and status_value in {"in_progress", "ready_to_archive"} and approval_value != "approved":
        fail(f"{path} class C implementation requires human_approval_status: approved")
    if not is_legacy_checked and design_value == "yes" and review_value != "C":
        fail(f"{path} human_design_required: yes requires review_class: C")
    if status_value == "deferred" and not planlib.manifest_scalar(values, "completion_deferred_reason").strip():
        fail(f"{path} status: deferred requires completion_deferred_reason")
    if not is_legacy_checked:
        try:
            plan_validation_commands.check_plan(path)
        except plan_validation_commands.ValidationCommandError as exc:
            fail(f"{path} validation command is invalid: {exc}")
        required_specs = values["required_specs"]
        assert isinstance(required_specs, list)
        missing_specs = sorted(planlib.required_specs_for(task_types) - set(required_specs))
        if missing_specs:
            fail(f"{path} required_specs is missing routed specs: {', '.join(missing_specs)}")
        write_scope = values["write_scope"]
        context_files = values["context_files"]
        assert isinstance(write_scope, list)
        assert isinstance(context_files, list)
        overlap = sorted((set(write_scope) - {"none"}) & (set(context_files) - {"none"}))
        if overlap:
            fail(f"{path} write_scope and context_files overlap: {', '.join(overlap)}")
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
    if planlib.CHECKED_DIR.exists():
        for path in sorted(planlib.CHECKED_DIR.glob("**/[0-9][0-9][0-9]-*.md")):
            lint_manifest(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--next-id", action="store_true", help="print the next available plan id")
    parser.add_argument("--check-manifest", metavar="PLAN", help="validate one plan manifest")
    parser.add_argument("--print-context", metavar="PLAN", help="print shell context for a plan manifest")
    parser.add_argument("--add-active", nargs=2, metavar=("ID", "PATH"), help="add or replace an active index row")
    parser.add_argument("--remove-active", metavar="ID", help="remove an active index row")
    parser.add_argument("--append-checked", nargs=2, metavar=("ID", "PATH"), help="append a checked index row")
    parser.add_argument("--check-active-mapping", nargs=3, metavar=("ID", "PATH", "STATUS"))
    parser.add_argument("--set-active-status", nargs=4, metavar=("ID", "PATH", "OLD", "NEW"))
    parser.add_argument("--check-promotion", nargs=3, metavar=("ID", "SOURCE", "DESTINATION"))
    parser.add_argument("--check-archive-target", nargs=2, metavar=("ID", "DESTINATION"))
    parser.add_argument("--rewrite-status", nargs=2, metavar=("PATH", "STATUS"))
    parser.add_argument("--copy-status-exclusive", nargs=3, metavar=("SOURCE", "DESTINATION", "STATUS"))
    parser.add_argument("--complete-transition", nargs=3, metavar=("ID", "PATH", "OLD_STATUS"))
    args = parser.parse_args()
    if args.next_id:
        print(next_id())
        return 0
    if args.check_manifest:
        lint_manifest(Path(args.check_manifest))
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
        try:
            planlib.append_checked(args.append_checked[0], args.append_checked[1])
        except planlib.PlanError as exc:
            fail(str(exc))
        return 0
    if args.check_active_mapping:
        try:
            planlib.check_active_mapping(*args.check_active_mapping)
        except planlib.PlanError as exc:
            fail(str(exc))
        return 0
    if args.set_active_status:
        try:
            planlib.set_active_status(*args.set_active_status)
        except planlib.PlanError as exc:
            fail(str(exc))
        return 0
    if args.check_promotion:
        try:
            lint_manifest(Path(args.check_promotion[1]))
            planlib.check_promotion(*args.check_promotion)
        except planlib.PlanError as exc:
            fail(str(exc))
        return 0
    if args.check_archive_target:
        try:
            planlib.check_archive_target(*args.check_archive_target)
        except planlib.PlanError as exc:
            fail(str(exc))
        return 0
    if args.rewrite_status:
        try:
            planlib.rewrite_status(*args.rewrite_status)
        except planlib.PlanError as exc:
            fail(str(exc))
        return 0
    if args.copy_status_exclusive:
        try:
            planlib.copy_with_status_exclusive(*args.copy_status_exclusive)
        except planlib.PlanError as exc:
            fail(str(exc))
        return 0
    if args.complete_transition:
        try:
            planlib.complete_transition(*args.complete_transition)
        except planlib.PlanError as exc:
            fail(str(exc))
        return 0
    lint_plan_index()
    lint_checked_index()
    lint_manifests()
    print("plan docs lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
