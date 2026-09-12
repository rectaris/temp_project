#!/usr/bin/env python3
"""Lint generic plan files and allocate plan ids."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import planlib
import plan_validation_commands


ROOT = planlib.ROOT
PLAN = planlib.PLAN
CHECKED = planlib.CHECKED
REPLANNED = planlib.REPLANNED
HUMAN_DESIGN_VALUES = {"yes", "no"}
IMPLEMENTATION_TIER_VALUES = {"0", "1", "2"}
HUMAN_APPROVAL_VALUES = {"not_required", "pending", "approved"}
OPEN_STATUS_VALUES = {
    "in_progress",
    "deferred",
    "replan_required",
    "ready_to_archive",
    "backlog",
    "shelved",
}
SHELVED_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
# An archive written before these fields existed cannot supply them, and a
# completed record's review history cannot be reconstructed after the fact.
# Judge each of them only when the record actually carries it.
ARCHIVE_VINTAGE_OPTIONAL_FIELDS = (
    "status",
    "review_class",
    "human_design_required",
    "human_approval_status",
    "acceptance",
)
# Copier updates must continue to read archives produced before checked became
# the terminal manifest value. New finalization is tested to emit checked.
CLOSED_STATUS_VALUES = {"checked", "completed", "ready_to_archive"}
REPLANNED_STATUS_VALUES = {"replanned"}
REPLAN_REASON_CODES = {
    "scope_drift",
    "spec_drift",
    "security_boundary_drift",
    "multiple_independent_invariants",
    "post_authoritative_design_change",
    "candidate_correction_budget_exhausted",
    "parent_remediation_budget_exhausted",
}
SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
SUCCESSOR_PLAN_RE = re.compile(r"docs/plan/active/[0-9]{3}-[a-z0-9][a-z0-9-]*\.md")
REPLAN_SOURCE_RE = re.compile(
    r"docs/plan/(?:active/[0-9]{3}-[a-z0-9][a-z0-9-]*\.md|"
    r"replanned/[0-9]{4}/[0-9]{2}/(?:01-15|16-31)/[0-9]{3}-[a-z0-9][a-z0-9-]*\.md)"
)
REPLAN_CONTRACT_RE = re.compile(r"docs/plan/replanned/contracts/[0-9]{3}-[a-z0-9][a-z0-9-]*\.json")
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
    try:
        rows = planlib.parse_active_index(planlib.read_active_index(PLAN))
    except planlib.ActiveIndexError as exc:
        fail(str(exc))
    for plan_id, path, status in rows:
        indexed_path = ROOT / path
        if indexed_path.parent != planlib.ACTIVE_DIR:
            fail(f"active index path is outside active plan directory: {path}")
        if not indexed_path.is_file():
            fail(f"active index points to missing file: {path}")
        try:
            values = planlib.parse_manifest(indexed_path)
        except planlib.PlanError as exc:
            fail(str(exc))
        if planlib.manifest_scalar(values, "status") != status:
            fail(f"active index status does not match manifest: {path}")


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


def lint_replanned_index() -> None:
    if not REPLANNED.is_file():
        fail("missing docs/plan/replanned.md")
    text = REPLANNED.read_text(encoding="utf-8")
    if not text.startswith("# Replanned Plan Index\n"):
        fail("docs/plan/replanned.md must start with '# Replanned Plan Index'")
    if "id\tpath\tcontract" not in text:
        fail("replanned index must contain TSV header: id path contract")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    seen_contracts: set[str] = set()
    for line in text.splitlines():
        if not re.match(r"^\d{3}\t", line):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            fail(f"bad replanned index row: {line}")
        plan_id, path, contract = parts
        if plan_id in seen_ids or path in seen_paths or contract in seen_contracts:
            fail(f"duplicate replanned index identity: {line}")
        seen_ids.add(plan_id)
        seen_paths.add(path)
        seen_contracts.add(contract)
        archive = ROOT / path
        contract_path = ROOT / contract
        if not Path(path).name.startswith(plan_id + "-"):
            fail(f"replanned index id does not match filename: {line}")
        if planlib.REPLANNED_DIR not in archive.parents or not archive.is_file():
            fail(f"replanned index points outside the replanned archive or to a missing file: {path}")
        if contract_path.parent != planlib.REPLANNED_DIR / "contracts" or not contract_path.is_file():
            fail(f"replanned index points outside the contract directory or to a missing file: {contract}")
        if planlib.manifest_scalar(planlib.parse_manifest(archive), "status") != "replanned":
            fail(f"replanned index archive status mismatch: {path}")
    verifier = Path(__file__).with_name("restructure-plan.py")
    completed = subprocess.run(
        [sys.executable, str(verifier), "--verify"], cwd=ROOT, check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if completed.returncode != 0:
        fail(completed.stderr.strip() or "replanned contract verification failed")


def lint_manifest(path: Path) -> None:
    if not path.is_absolute():
        path = planlib.ROOT / path
    text = path.read_text(encoding="utf-8")
    parsed = planlib.parse_manifest(path)
    is_checked = planlib.CHECKED_DIR in path.parents
    is_replanned = planlib.REPLANNED_DIR in path.parents
    is_legacy_checked = bool(
        is_checked
        and not parsed.get("task_types")
        and planlib.manifest_scalar(parsed, "task_type")
    )
    declares = {
        field: bool(re.search(rf"^{field}:", text, flags=re.MULTILINE))
        for field in ARCHIVE_VINTAGE_OPTIONAL_FIELDS
    }
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
        if is_legacy_checked:
            fields = tuple(
                field
                for field in fields
                if field not in ARCHIVE_VINTAGE_OPTIONAL_FIELDS or declares[field]
            )
        values = planlib.require_manifest_fields(path, fields)
    except planlib.PlanError as exc:
        fail(str(exc))
    judges = {
        field: not is_legacy_checked or declares[field]
        for field in ARCHIVE_VINTAGE_OPTIONAL_FIELDS
    }
    review_value = planlib.manifest_scalar(values, "review_class")
    if judges["review_class"] and review_value not in {"A", "B", "C"}:
        fail(f"{path} review_class must be A, B, or C")
    design_value = planlib.manifest_scalar(values, "human_design_required")
    if judges["human_design_required"] and design_value not in HUMAN_DESIGN_VALUES:
        fail(f"{path} human_design_required must be yes or no")
    tier_value = planlib.manifest_scalar(values, "implementation_tier").strip()
    if tier_value and tier_value not in IMPLEMENTATION_TIER_VALUES:
        fail(f"{path} implementation_tier must be 0, 1, or 2")
    if is_legacy_checked:
        task_types = [planlib.manifest_scalar(values, "task_type")]
    else:
        task_types = values["task_types"]
        assert isinstance(task_types, list)
    if len(task_types) != len(set(task_types)):
        fail(f"{path} task_types must not contain duplicates")
    required_specs = values["required_specs"]
    assert isinstance(required_specs, list)
    legacy_route_specs = planlib.required_specs_for(task_types, planlib.LEGACY_SPEC_INDEX)
    is_pre_v1_open = bool(
        not is_checked
        and not is_replanned
        and planlib.has_pre_v1_adoption_provenance()
        and not any(spec.startswith(".project-agent-workflow/docs/agent/") for spec in required_specs)
        and set(required_specs) & legacy_route_specs
    )
    spec_index = planlib.LEGACY_SPEC_INDEX if is_pre_v1_open else planlib.SPEC_INDEX
    if not is_checked and not is_replanned:
        unknown_task_types = sorted(set(task_types) - planlib.task_type_values(spec_index))
        if unknown_task_types:
            fail(
                f"{path} task_types must match route keys from {spec_index.relative_to(ROOT)}: "
                f"{', '.join(unknown_task_types)}"
            )
    approval_value = planlib.manifest_scalar(values, "human_approval_status")
    if judges["human_approval_status"] and approval_value not in HUMAN_APPROVAL_VALUES:
        fail(f"{path} human_approval_status must be not_required, pending, or approved")
    status_value = planlib.manifest_scalar(values, "status")
    if is_legacy_checked and not declares["status"]:
        status_value = "checked"
    if is_replanned:
        allowed_statuses = REPLANNED_STATUS_VALUES
    else:
        allowed_statuses = CLOSED_STATUS_VALUES if is_checked else OPEN_STATUS_VALUES
    if status_value not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        fail(f"{path} status must be one of: {allowed}")
    if path.parent == planlib.ACTIVE_DIR and status_value not in {
        "in_progress", "deferred", "replan_required", "ready_to_archive"
    }:
        fail(
            f"{path} active plan status must be in_progress, deferred, "
            "replan_required, or ready_to_archive"
        )
    if path.parent == planlib.BACKLOG_DIR and status_value not in {"backlog", "deferred"}:
        fail(f"{path} backlog plan status must be backlog or deferred")
    if path.parent == planlib.SHELVED_DIR and status_value != "shelved":
        fail(f"{path} shelved plan status must be shelved")
    if status_value == "shelved":
        if path.parent != planlib.SHELVED_DIR:
            fail(f"{path} status: shelved is written only under docs/plan/shelved")
        if not planlib.manifest_scalar(values, "shelved_reason").strip():
            fail(f"{path} status: shelved requires shelved_reason")
        if not SHELVED_DATE_RE.fullmatch(
            planlib.manifest_scalar(values, "shelved_at").strip()
        ):
            fail(f"{path} status: shelved requires shelved_at as YYYY-MM-DD")
    if not is_legacy_checked and review_value == "C" and approval_value not in {"pending", "approved"}:
        fail(f"{path} class C plan requires human_approval_status: pending or approved")
    if (
        judges["human_approval_status"]
        and review_value == "C"
        and status_value in {"in_progress", "ready_to_archive"}
        and approval_value != "approved"
    ):
        fail(f"{path} class C implementation requires human_approval_status: approved")
    if not is_legacy_checked and design_value == "yes" and review_value != "C":
        fail(f"{path} human_design_required: yes requires review_class: C")
    if status_value == "deferred" and not planlib.manifest_scalar(values, "completion_deferred_reason").strip():
        fail(f"{path} status: deferred requires completion_deferred_reason")
    try:
        planlib.validate_predecessor_list(values, str(path))
    except planlib.PlanError as exc:
        fail(str(exc))
    lint_replan_fields(path, values, status_value)
    if not is_checked and not is_replanned:
        try:
            if is_pre_v1_open:
                plan_validation_commands.check_legacy_plan_for_lint(path, ROOT)
            else:
                plan_validation_commands.check_plan(path)
        except plan_validation_commands.ValidationCommandError as exc:
            fail(f"{path} validation command is invalid: {exc}")
        missing_specs = sorted(
            planlib.required_specs_for(task_types, spec_index) - set(required_specs)
        )
        if missing_specs:
            fail(f"{path} required_specs is missing routed specs: {', '.join(missing_specs)}")
    if not is_legacy_checked:
        write_scope = values["write_scope"]
        context_files = values["context_files"]
        assert isinstance(write_scope, list)
        assert isinstance(context_files, list)
        overlap = sorted((set(write_scope) - {"none"}) & (set(context_files) - {"none"}))
        if overlap:
            fail(f"{path} write_scope and context_files overlap: {', '.join(overlap)}")
    if not planlib.manifest_scalar(values, "checked_summary_ja").strip():
        fail(f"{path} checked_summary_ja must be non-empty")
    if not is_checked and not is_replanned and planlib.has_admission_record(values):
        try:
            planlib.validate_admission_record(values)
        except planlib.PlanError as exc:
            fail(f"{path} admission record is invalid: {exc}")


ADMISSION_REVISION_HINT = (
    "revise the plan in place to declare plan_purpose: implementation, bounded "
    "feasibility_evidence, completion_conditions, and a completion_witness_map "
    "bound to declared focused_validation commands; do not create another plan "
    "to carry that metadata"
)


def check_admission(path: Path) -> None:
    """Refuse to admit a numbered plan that cannot start bounded implementation."""

    if not path.is_absolute():
        path = planlib.ROOT / path
    try:
        values = planlib.parse_manifest(path)
    except planlib.PlanError as exc:
        fail(str(exc))
    if not planlib.has_admission_record(values):
        fail(
            f"{path} has no executable admission record: {ADMISSION_REVISION_HINT}"
        )
    try:
        planlib.validate_admission_record(values)
    except planlib.PlanError as exc:
        fail(f"{path} admission record is invalid: {exc}; {ADMISSION_REVISION_HINT}")


def lint_replan_fields(
    path: Path,
    values: dict[str, str | list[str]],
    status_value: str,
) -> None:
    primary_invariant = planlib.manifest_scalar(values, "primary_invariant").strip()
    replan_source = planlib.manifest_scalar(values, "replan_source").strip()
    replan_contract = planlib.manifest_scalar(values, "replan_contract").strip()
    integration_gates = values["integration_gates"]
    successor_plans = values["successor_plans"]
    inherited_digests = values["inherited_acceptance_digests"]
    reason_codes = values["replan_reason_codes"]
    assert isinstance(integration_gates, list)
    assert isinstance(successor_plans, list)
    assert isinstance(inherited_digests, list)
    assert isinstance(reason_codes, list)

    list_fields = {
        "integration_gates": integration_gates,
        "successor_plans": successor_plans,
        "inherited_acceptance_digests": inherited_digests,
        "replan_reason_codes": reason_codes,
    }
    for field, items in list_fields.items():
        if len(items) != len(set(items)):
            fail(f"{path} {field} must not contain duplicates")
        if any(not item.strip() for item in items):
            fail(f"{path} {field} must not contain blank values")

    unknown_reasons = sorted(set(reason_codes) - REPLAN_REASON_CODES)
    if unknown_reasons:
        fail(f"{path} has unknown replan_reason_codes: {', '.join(unknown_reasons)}")
    if len(reason_codes) > len(REPLAN_REASON_CODES):
        fail(f"{path} replan_reason_codes exceeds the bounded reason set")
    if status_value == "replan_required" and not reason_codes:
        fail(f"{path} status: replan_required requires replan_reason_codes")

    lineage_present = bool(
        primary_invariant
        or replan_source
        or replan_contract
        or integration_gates
        or successor_plans
        or inherited_digests
    )
    if status_value == "replanned" and not lineage_present:
        fail(f"{path} status: replanned requires complete replan lineage")
    if not lineage_present:
        return
    if not primary_invariant or len(primary_invariant) > 200:
        fail(f"{path} replan lineage requires primary_invariant of at most 200 characters")
    if not REPLAN_SOURCE_RE.fullmatch(replan_source):
        fail(f"{path} replan_source must identify a normalized active or replanned plan path")
    if not REPLAN_CONTRACT_RE.fullmatch(replan_contract):
        fail(f"{path} replan_contract must identify a normalized replanned contract path")
    if not integration_gates:
        fail(f"{path} replan lineage requires at least one integration_gates entry")
    if not successor_plans:
        fail(f"{path} replan lineage requires at least one successor_plans entry")
    if any(not SUCCESSOR_PLAN_RE.fullmatch(item) for item in successor_plans):
        fail(f"{path} successor_plans must contain normalized active-plan paths")
    if any(not SHA256_RE.fullmatch(item) for item in inherited_digests):
        fail(f"{path} inherited_acceptance_digests must contain sha256:<64 lowercase hex> values")
    if not inherited_digests:
        fail(f"{path} replan lineage requires inherited_acceptance_digests")


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


def load_parallel_group_module():
    """Load the shared group-description authority used by root and generated lint."""

    path = Path(__file__).with_name("parallel-plan-state.py")
    if not path.is_file():
        fail("parallel-plan-state.py is required for execution group policy")
    spec = importlib.util.spec_from_file_location("generated_parallel_group", path)
    if spec is None or spec.loader is None:
        fail("could not load the parallel plan group authority")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def execution_group_members() -> dict[str, str]:
    """Return every enrolled member plan path mapped to its group description."""

    module = load_parallel_group_module()
    try:
        groups = module.load_group_descriptions(ROOT)
    except module.GroupError as exc:
        fail(f"invalid execution group description: {exc}")
    enrolled: dict[str, str] = {}
    for label, group in groups.items():
        for plan_path in group["members"]:
            enrolled[plan_path] = label
    return enrolled


def lint_execution_groups() -> None:
    directory = ROOT / "docs/plan/execution-groups"
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            if path.is_dir() or path.suffix != ".json":
                fail(
                    "docs/plan/execution-groups may contain only group description "
                    f"JSON files: {path.relative_to(ROOT)}"
                )
    enrolled = execution_group_members()
    if planlib.ACTIVE_DIR.exists():
        for path in sorted(planlib.ACTIVE_DIR.glob("[0-9][0-9][0-9]-*.md")):
            relative = str(path.relative_to(ROOT))
            try:
                values = planlib.parse_manifest(path)
            except planlib.PlanError as exc:
                fail(str(exc))
            declared = planlib.manifest_scalar(values, "execution_group")
            if not declared:
                continue
            if enrolled.get(relative) != declared:
                fail(
                    f"{relative} declares execution_group {declared!r}, which does "
                    "not name a validated group description enrolling this plan"
                )
    for plan_path in sorted(enrolled):
        if not (ROOT / plan_path).is_file():
            fail(f"execution group enrolls a missing plan: {plan_path}")


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
    if planlib.REPLANNED_DIR.exists():
        for path in sorted(planlib.REPLANNED_DIR.glob("**/[0-9][0-9][0-9]-*.md")):
            lint_manifest(path)


def render_admission_block() -> str:
    """Render the admission manifest block from bounded environment inputs."""

    def entries(name: str) -> list[str]:
        raw = os.environ.get(name, "")
        return [line for line in raw.split("\n") if line.strip()]

    purpose = os.environ.get("PLAN_ADMISSION_PURPOSE", "").strip()
    if purpose not in planlib.PLAN_PURPOSE_VALUES:
        fail("plan creation requires --purpose implementation")
    write_scope = entries("PLAN_ADMISSION_WRITE_SCOPE")
    completions = entries("PLAN_ADMISSION_COMPLETIONS")
    witnesses = entries("PLAN_ADMISSION_WITNESSES")
    feasibility = entries("PLAN_ADMISSION_FEASIBILITY")
    if len(completions) != len(witnesses):
        fail("each --completion condition needs exactly one --witness command")

    evidence_records: list[dict[str, str]] = []
    for item in feasibility:
        kind, separator, evidence = item.partition(":")
        if not separator:
            fail(f"--feasibility must use <kind>:<evidence>: {item}")
        evidence_records.append({"kind": kind.strip(), "evidence": evidence.strip()})

    values: dict[str, str | list[str]] = {
        "plan_purpose": purpose,
        "write_scope": write_scope,
        "focused_validation": list(dict.fromkeys(witnesses)),
        "feasibility_evidence": [
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for record in evidence_records
        ],
        "completion_conditions": completions,
        "completion_witness_map": [
            json.dumps(
                {
                    "condition_sha256": planlib.acceptance_digest(condition),
                    "witness": witness,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for condition, witness in zip(completions, witnesses)
        ],
    }
    try:
        planlib.validate_admission_record(values)
    except planlib.PlanError as exc:
        fail(f"plan creation admission inputs are invalid: {exc}")

    lines = [f"plan_purpose: {purpose}"]
    for field in (
        "write_scope",
        "focused_validation",
        "feasibility_evidence",
        "completion_conditions",
        "completion_witness_map",
    ):
        lines.append(f"{field}:")
        items = values[field]
        assert isinstance(items, list)
        lines.extend(f"  - {item}" for item in items)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--next-id", action="store_true", help="print the next available plan id")
    parser.add_argument("--check-manifest", metavar="PLAN", help="validate one plan manifest")
    parser.add_argument(
        "--render-admission",
        action="store_true",
        help="render the admission manifest block from bounded environment inputs",
    )
    parser.add_argument(
        "--check-admission",
        metavar="PLAN",
        help="require the executable admission record of one plan",
    )
    parser.add_argument("--print-context", metavar="PLAN", help="print shell context for a plan manifest")
    parser.add_argument("--add-active", nargs=2, metavar=("ID", "PATH"), help="add or replace an active index row")
    parser.add_argument("--remove-active", metavar="ID", help="remove an active index row")
    parser.add_argument("--append-checked", nargs=2, metavar=("ID", "PATH"), help="append a checked index row")
    parser.add_argument(
        "--check-active-index",
        action="store_true",
        help="validate the whole active plan index document",
    )
    parser.add_argument("--check-active-mapping", nargs=3, metavar=("ID", "PATH", "STATUS"))
    parser.add_argument("--set-active-status", nargs=4, metavar=("ID", "PATH", "OLD", "NEW"))
    parser.add_argument("--check-promotion", nargs=3, metavar=("ID", "SOURCE", "DESTINATION"))
    parser.add_argument("--check-archive-target", nargs=2, metavar=("ID", "DESTINATION"))
    parser.add_argument("--rewrite-status", nargs=2, metavar=("PATH", "STATUS"))
    parser.add_argument("--copy-status-exclusive", nargs=3, metavar=("SOURCE", "DESTINATION", "STATUS"))
    parser.add_argument("--complete-transition", nargs=3, metavar=("ID", "PATH", "OLD_STATUS"))
    parser.add_argument(
        "--check-execution-groups",
        action="store_true",
        help="validate committed parallel execution group descriptions",
    )
    args = parser.parse_args()
    if args.next_id:
        print(next_id())
        return 0
    if args.check_manifest:
        lint_manifest(Path(args.check_manifest))
        return 0
    if args.render_admission:
        print(render_admission_block())
        return 0
    if args.check_admission:
        check_admission(Path(args.check_admission))
        return 0
    if args.print_context:
        try:
            print("\n".join(planlib.context_lines(Path(args.print_context))))
        except planlib.PlanError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0
    if args.add_active:
        try:
            planlib.add_active(args.add_active[0], args.add_active[1])
        except planlib.PlanError as exc:
            fail(str(exc))
        return 0
    if args.remove_active:
        try:
            planlib.remove_active(args.remove_active)
        except planlib.PlanError as exc:
            fail(str(exc))
        return 0
    if args.append_checked:
        try:
            planlib.append_checked(args.append_checked[0], args.append_checked[1])
        except planlib.PlanError as exc:
            fail(str(exc))
        return 0
    if args.check_active_index:
        try:
            planlib.read_active_rows()
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
    if args.check_execution_groups:
        lint_execution_groups()
        print("execution group lint passed")
        return 0
    lint_plan_index()
    lint_checked_index()
    lint_replanned_index()
    lint_manifests()
    lint_execution_groups()
    try:
        planlib.validate_active_plan_predecessors()
    except planlib.PlanError as exc:
        fail(str(exc))
    print("plan docs lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
