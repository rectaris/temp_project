#!/usr/bin/env python3
"""Maintain a bounded parent-owned execution budget for one active plan."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import secrets
import shlex
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 4
MAX_BYTES = 65_536
CANDIDATE_MANIFEST_MAX_BYTES = 1024 * 1024
MAX_EVENTS = 64
MAX_CORRECTIONS = 2
MAX_PARENT_REMEDIATIONS = 2
MAX_DIAGNOSIS_ATTEMPTS = 3
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
PLAN_RE = re.compile(r"docs/plan/active/[0-9]{3}-[a-z0-9][a-z0-9-]*\.md")
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
REASON_CODES = {
    "scope_drift",
    "spec_drift",
    "security_boundary_drift",
    "multiple_independent_invariants",
    "post_authoritative_design_change",
    "candidate_correction_budget_exhausted",
    "parent_remediation_budget_exhausted",
}
REPAIR_REASON_CODES = {"independent_repair_required"}
REVIEW_REASON_CODES = {
    "acceptance_unmet",
    "out_of_scope_change",
    "required_spec_missed",
    "integration_contract_mismatch",
    "focused_validation_failed",
    "evidence_incomplete",
    "multiple_invariants_coupled",
}
MODES = {"candidate", "parent_direct"}
ATTEMPT_KINDS = {"initial", "correction"}
REVIEW_OUTCOMES = {"accepted", "correction_requested", "rejected"}
EVENT_TYPES = {
    "candidate_generation",
    "correction_rejected",
    "parent_review",
    "focused_validation",
    "authoritative_validation",
    "authoritative_failure",
    "failure_diagnosis",
    "scope_drift",
    "spec_drift",
    "security_boundary_drift",
    "post_authoritative_design_change",
    "repair_classification",
    "elapsed_checkpoint",
    "writable_attempt_started",
    "attempt_closed",
    "successor_claimed",
}
RECORD_EVENT_TYPES = EVENT_TYPES - {"writable_attempt_started", "attempt_closed"}
EXACT_KEYS = {
    "schema_version", "run_id", "plan_path", "plan_digest", "source_head",
    "primary_invariant_digest", "candidate_lifecycle_identity_digest", "state",
    "implementation_mode", "candidate_generations", "correction_rounds",
    "parent_direct_remediation_rounds", "focused_validation_events",
    "authoritative_validation_events", "repair_reason_codes", "replan_reason_codes",
    "predecessor_plan_digest", "predecessor_accepted_candidate_digest",
    "predecessor_closing_event_digest", "predecessor_accepted_source_head",
    "writable_attempt_starts",
    "writable_attempt_closures", "open_attempt_id", "accepted_candidate_digest",
    "accepted_closing_event_digest", "accepted_source_head", "successor_claim_digest",
    "review_reason_codes", "last_monotonic_ns", "genesis_digest", "event_chain_digest", "events",
}
EVENT_KEYS = {
    "sequence", "event_id", "event_type", "implementation_mode", "invariant_digests",
    "finding_severities", "independent_review_receipt_digest", "repair_classification",
    "repair_evidence_digest",
    "candidate_lifecycle_digest",
    "attempt_id", "attempt_kind", "candidate_digest", "review_outcome",
    "review_reason_code", "review_author", "review_evidence_digest",
    "predecessor_plan_digest", "predecessor_accepted_candidate_digest",
    "predecessor_closing_event_digest", "predecessor_accepted_source_head",
    "accepted_source_head", "successor_run_id", "successor_plan_digest",
    "successor_source_head", "successor_primary_invariant_digest", "successor_genesis_digest",
    "elapsed_seconds", "monotonic_ns", "previous_event_digest", "event_digest",
}
LEGACY_EVENT_KEYS = EVENT_KEYS - {"successor_genesis_digest"}
DIAGNOSIS_EVENT_KEYS = EVENT_KEYS | {
    "failure_evidence", "failure_evidence_digest", "diagnosis_evidence",
    "diagnosis_evidence_digest",
}
REPAIR_CLASSIFICATION_KEYS = {
    "schema_version", "plan_path", "plan_digest", "source_head", "primary_invariant_digest",
    "affected_invariant_digests", "candidate_lifecycle_identity_digest", "candidate_lifecycle_digest",
    "independent_review_receipt_digest", "bounded_write_scope", "bounded_validation_scope",
    "source_scope_unchanged", "validation_authority_unchanged",
    "invariant_boundaries_unchanged", "source_acceptance_unchanged",
    "safety_conditions_unchanged", "external_effect_authority_unchanged",
    "independent_invariant_count",
}
FAILURE_EVIDENCE_KEYS = {
    "schema_version", "plan_path", "plan_digest", "source_head",
    "implementation_mode",
    "candidate_lifecycle_identity_digest", "candidate_lifecycle_digest",
    "candidate_manifest_digest", "validation_report_digest",
    "failed_operation_digest", "observed_exit_status",
}
DIAGNOSIS_EVIDENCE_KEYS = {
    "schema_version", "plan_path", "plan_digest", "source_head",
    "candidate_lifecycle_identity_digest", "candidate_lifecycle_digest",
    "authoritative_failure_event_digest", "failure_evidence_digest",
    "failed_operation_digest", "observed_exit_status", "affected_invariant_digest",
    "independent_review_receipt_digest", "reproduction_evidence_digest",
    "diagnosis_result",
}
DIAGNOSIS_RESULTS = {"confirmed", "inconclusive", "disputed"}
VALIDATION_FAILURE_KINDS = {
    "command", "dependency_integrity", "runtime_integrity",
    "head_immutability", "ref_immutability", "runner_setup", "source_integrity",
}
CANDIDATE_LIFECYCLE_KEYS = {
    "schema_version", "orchestration_run_id", "current_manifest_digest",
    "current_patch_digest", "correction_round", "candidate_generations", "phase",
    "focused_required", "focused_validation_count", "authoritative_validation_count",
    "parent_review_rejections",
    "plan_execution_attempt_id",
}
EMPTY_CHAIN_DIGEST = digest(b"") if "digest" in globals() else "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class StateError(ValueError):
    pass


def sanitized_git_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def digest(data: bytes | str) -> str:
    raw = data.encode() if isinstance(data, str) else data
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def file_digest(path: Path) -> str:
    reject_symlink_ancestors(path, include_target=True)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise StateError("candidate lifecycle must be a regular file")
        hasher = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 65_536)
            if not chunk:
                break
            hasher.update(chunk)
        return "sha256:" + hasher.hexdigest()
    finally:
        os.close(descriptor)


def lifecycle_identity_digest(run_id: str, lifecycle_path: Path) -> str:
    return digest(f"{run_id}\0{lifecycle_path.resolve()}")


def reject_symlink_ancestors(path: Path, *, include_target: bool) -> None:
    absolute = path.absolute()
    parts = absolute.parts
    current = Path(parts[0])
    limit = len(parts) if include_target else len(parts) - 1
    for part in parts[1:limit]:
        current /= part
        if current.is_symlink():
            raise StateError(f"symlink path component is not allowed: {current}")


def repository_root() -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=sanitized_git_environment(),
    )
    if completed.returncode != 0:
        raise StateError("current directory is not a Git repository")
    return Path(completed.stdout.strip()).resolve()


def git_output(root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", *arguments], cwd=root, check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=sanitized_git_environment(),
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise StateError(detail or f"git {' '.join(arguments)} failed")
    return completed.stdout


def current_head(root: Path) -> str:
    return git_output(root, "rev-parse", "HEAD").decode().strip()


def require_clean_repository(root: Path) -> None:
    if git_output(root, "status", "--porcelain=1", "--untracked-files=all"):
        raise StateError("accepted closure requires a clean repository")


def require_repository_baseline(state: dict[str, Any]) -> None:
    root = repository_root()
    if current_head(root) != state["source_head"]:
        raise StateError("repository source HEAD differs from the execution baseline")
    plan = root / state["plan_path"]
    reject_symlink_ancestors(plan, include_target=True)
    try:
        plan_bytes = plan.read_bytes()
    except OSError as exc:
        raise StateError("execution plan is unavailable") from exc
    if digest(plan_bytes) != state["plan_digest"]:
        raise StateError("repository plan digest differs from the execution baseline")
    try:
        plan_text = plan_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StateError("execution plan must be UTF-8") from exc
    invariants = re.findall(r"^primary_invariant: (.+)$", plan_text, flags=re.MULTILINE)
    if len(invariants) != 1 or digest(invariants[0]) != state["primary_invariant_digest"]:
        raise StateError("repository primary invariant differs from the execution baseline")


def state_genesis_digest(value: dict[str, Any]) -> str:
    identity_keys = (
        "schema_version", "run_id", "plan_path", "plan_digest", "source_head",
        "primary_invariant_digest", "candidate_lifecycle_identity_digest",
        "implementation_mode", "predecessor_plan_digest",
        "predecessor_accepted_candidate_digest", "predecessor_closing_event_digest",
        "predecessor_accepted_source_head",
    )
    identity = {key: value[key] for key in identity_keys}
    return digest(json.dumps(identity, sort_keys=True, separators=(",", ":")))


def require_outside_repository(path: Path, label: str) -> None:
    root = repository_root()
    absolute = path.absolute()
    try:
        absolute.relative_to(root)
    except ValueError:
        return
    raise StateError(f"{label} must be outside the repository")


def require_digest(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if allow_empty and value == "":
        return ""
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise StateError(f"{label} must be sha256:<64 lowercase hex>")
    return value


def open_read(path: Path) -> tuple[int, bytes]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise StateError("execution state must be a regular file")
        data = os.read(descriptor, MAX_BYTES + 1)
        return metadata.st_mode & 0o777, data
    finally:
        os.close(descriptor)


def read_external_artifact(
    path: Path, label: str, maximum_bytes: int = MAX_BYTES
) -> bytes:
    require_outside_repository(path, label)
    reject_symlink_ancestors(path, include_target=True)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise StateError(f"{label} must be a regular file")
        data = os.read(descriptor, maximum_bytes + 1)
        if len(data) > maximum_bytes:
            raise StateError(f"{label} exceeds size limit")
        return data
    finally:
        os.close(descriptor)


def classify_repair(value: dict[str, Any]) -> str:
    if not value["source_scope_unchanged"] or not value["bounded_write_scope"]:
        return "scope_drift"
    if (
        not value["validation_authority_unchanged"]
        or not value["source_acceptance_unchanged"]
        or not value["bounded_validation_scope"]
    ):
        return "spec_drift"
    if not value["safety_conditions_unchanged"] or not value["external_effect_authority_unchanged"]:
        return "security_boundary_drift"
    if not value["invariant_boundaries_unchanged"] or value["independent_invariant_count"] != 1:
        return "multiple_independent_invariants"
    return "independent_repair_required"


def validate_repair_classification(
    value: Any,
    state: dict[str, Any],
    invariants: list[str],
    receipt: str,
    lifecycle_digest: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REPAIR_CLASSIFICATION_KEYS:
        raise StateError("repair classification evidence has an invalid exact schema")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise StateError("repair classification evidence has an invalid schema version")
    if type(value["independent_invariant_count"]) is not int or value["independent_invariant_count"] < 1:
        raise StateError("repair classification evidence has an invalid invariant count")
    boolean_keys = {
        "bounded_write_scope", "bounded_validation_scope", "source_acceptance_unchanged",
        "source_scope_unchanged", "validation_authority_unchanged",
        "invariant_boundaries_unchanged", "safety_conditions_unchanged",
        "external_effect_authority_unchanged",
    }
    if any(type(value[key]) is not bool for key in boolean_keys):
        raise StateError("repair classification evidence has a non-boolean condition")
    expected_identity = {
        "plan_path": state["plan_path"],
        "plan_digest": state["plan_digest"],
        "source_head": state["source_head"],
        "primary_invariant_digest": state["primary_invariant_digest"],
        "affected_invariant_digests": invariants,
        "candidate_lifecycle_identity_digest": state["candidate_lifecycle_identity_digest"],
        "candidate_lifecycle_digest": lifecycle_digest,
        "independent_review_receipt_digest": receipt,
    }
    if any(value[key] != expected for key, expected in expected_identity.items()):
        raise StateError("repair classification evidence does not match the execution baseline")
    if value["independent_invariant_count"] != len(invariants):
        raise StateError("repair classification invariant count does not match affected invariants")
    return value


def load_repair_classification(
    path: Path,
    state: dict[str, Any],
    invariants: list[str],
    receipt: str,
    lifecycle_digest: str,
) -> tuple[dict[str, Any], str]:
    data = read_external_artifact(path, "repair classification evidence")
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError("repair classification evidence is invalid JSON") from exc
    classification = validate_repair_classification(value, state, invariants, receipt, lifecycle_digest)
    canonical = (json.dumps(classification, sort_keys=True, indent=2) + "\n").encode()
    if data != canonical:
        raise StateError("repair classification evidence is not canonical JSON")
    return classification, digest(data)


def validation_operation_digest(
    *, suite: str, kind: str, command_index: int, argv: list[str]
) -> str:
    identity = {
        "suite": suite,
        "kind": kind,
        "command_index": command_index,
        "argv": argv,
    }
    return digest(json.dumps(identity, sort_keys=True, separators=(",", ":")))


def authoritative_plan_commands(plan_path: Path) -> list[list[str]]:
    commands: list[list[str]] = []
    in_validation = False
    for line in plan_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            break
        if line == "validation:":
            in_validation = True
            continue
        if in_validation:
            if line.startswith("  - "):
                try:
                    argv = shlex.split(line[4:], posix=True)
                except ValueError as exc:
                    raise StateError("execution plan has an invalid authoritative command") from exc
                if not argv:
                    raise StateError("execution plan has an empty authoritative command")
                commands.append(argv)
                continue
            if line and not line.startswith(" "):
                break
    if not commands:
        raise StateError("execution plan has no authoritative validation commands")
    return commands


def load_authoritative_failure(
    path: Path,
    state: dict[str, Any],
    lifecycle_path: Path,
    lifecycle_digest: str,
) -> tuple[dict[str, Any], str]:
    data = read_external_artifact(
        path, "authoritative validation report", CANDIDATE_MANIFEST_MAX_BYTES
    )
    try:
        report = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError("authoritative validation report is invalid JSON") from exc
    if not isinstance(report, dict):
        raise StateError("authoritative validation report must be a JSON object")
    if report.get("suite") != "authoritative" or report.get("passed") is not False:
        raise StateError("diagnosis requires a failed authoritative validation report")
    if report.get("plan_path") != state["plan_path"]:
        raise StateError("authoritative validation report does not match the execution plan")
    if report.get("implementation_mode") != state["implementation_mode"]:
        raise StateError("authoritative validation report has the wrong implementation mode")
    if report.get("plan_digest") != state["plan_digest"]:
        raise StateError("authoritative validation report does not match the plan digest")
    if report.get("source_head") != state["source_head"]:
        raise StateError("authoritative validation report does not match the source HEAD")
    failure = report.get("failure")
    if not isinstance(failure, dict) or set(failure) != {
        "kind", "command_index", "operation_digest", "observed_exit_status"
    }:
        raise StateError("authoritative validation report lacks exact failure identity")
    kind = failure["kind"]
    command_index = failure["command_index"]
    observed_exit_status = failure["observed_exit_status"]
    if kind not in VALIDATION_FAILURE_KINDS:
        raise StateError("authoritative validation report has an unknown failure kind")
    if type(command_index) is not int or command_index < 0:
        raise StateError("authoritative validation report has an invalid command index")
    if type(observed_exit_status) is not int or not -255 <= observed_exit_status <= 255:
        raise StateError("authoritative validation report has an invalid observed exit status")
    commands = report.get("commands")
    if not isinstance(commands, list) or command_index >= len(commands):
        raise StateError("authoritative validation report failure does not identify one command")
    if len(commands) != command_index + 1:
        raise StateError("authoritative validation report contains operations after the failure")
    command = commands[command_index]
    if not isinstance(command, dict) or not isinstance(command.get("argv"), list) or any(
        not isinstance(item, str) for item in command.get("argv", [])
    ):
        raise StateError("authoritative validation report has an invalid failed command")
    command_status = command.get("returncode")
    if type(command_status) is not int or not -255 <= command_status <= 255:
        raise StateError("authoritative validation report has an invalid command status")
    for index, item in enumerate(commands):
        if not isinstance(item, dict) or item.get("index") != index:
            raise StateError("authoritative validation report command sequence is inconsistent")
        prior_status = item.get("returncode")
        if type(prior_status) is not int or not -255 <= prior_status <= 255:
            raise StateError("authoritative validation report has an invalid command status")
        if index < command_index and prior_status != 0:
            raise StateError("authoritative validation report continues after an earlier failure")
    if kind == "command":
        if command_status == 0 or observed_exit_status != command_status:
            raise StateError("authoritative command failure status is inconsistent")
    elif command_status != 0 or observed_exit_status != 1:
        raise StateError("authoritative safety-check failure must use exit status 1")
    plan_commands = authoritative_plan_commands(repository_root() / state["plan_path"])
    if len(plan_commands) <= command_index or any(
        not isinstance(item, dict)
        or item.get("argv") != plan_commands[index]
        for index, item in enumerate(commands)
    ):
        raise StateError("authoritative validation report operation differs from plan authority")
    expected_operation = validation_operation_digest(
        suite="authoritative",
        kind=kind,
        command_index=command_index,
        argv=command["argv"],
    )
    if failure["operation_digest"] != expected_operation:
        raise StateError("authoritative failed-operation identity is inconsistent")
    candidate_manifest_digest = ""
    if state["implementation_mode"] == "candidate":
        lifecycle_data = read_external_artifact(lifecycle_path, "candidate lifecycle")
        try:
            lifecycle = json.loads(lifecycle_data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StateError("candidate lifecycle is invalid JSON") from exc
        if not isinstance(lifecycle, dict) or set(lifecycle) != CANDIDATE_LIFECYCLE_KEYS:
            raise StateError("candidate lifecycle state has an invalid exact schema")
        if lifecycle.get("schema_version") != 2 or lifecycle.get(
            "orchestration_run_id"
        ) != state["run_id"]:
            raise StateError("candidate lifecycle run identity mismatch")
        attempt_id = state["open_attempt_id"]
        if not attempt_id or lifecycle.get("plan_execution_attempt_id") != attempt_id:
            raise StateError("failed candidate lifecycle attempt identity mismatch")
        for key in ("current_manifest_digest", "current_patch_digest"):
            if not isinstance(lifecycle[key], str) or not re.fullmatch(
                r"[0-9a-f]{64}", lifecycle[key]
            ):
                raise StateError(f"candidate lifecycle state has an invalid digest: {key}")
        for key in (
            "correction_round", "candidate_generations", "focused_validation_count",
            "authoritative_validation_count", "parent_review_rejections",
        ):
            value = lifecycle[key]
            if type(value) is not int or not 0 <= value <= 3:
                raise StateError(f"candidate lifecycle state has an invalid counter: {key}")
        if lifecycle["candidate_generations"] != lifecycle["correction_round"] + 1 or lifecycle[
            "parent_review_rejections"
        ] != lifecycle["correction_round"]:
            raise StateError("candidate lifecycle state has inconsistent correction lineage")
        if (
            lifecycle["candidate_generations"] != state["candidate_generations"]
            or lifecycle["correction_round"] != state["correction_rounds"]
            or lifecycle["focused_validation_count"] != state["focused_validation_events"]
            or lifecycle["authoritative_validation_count"]
            != state["authoritative_validation_events"]
        ):
            raise StateError("failed candidate lifecycle lineage differs from the execution ledger")
        if type(lifecycle["focused_required"]) is not bool:
            raise StateError("candidate lifecycle focused_required must be boolean")
        if lifecycle.get("phase") != "authoritative_failed" or lifecycle.get(
            "authoritative_validation_count"
        ) != 1 or (lifecycle["focused_required"] and lifecycle["focused_validation_count"] != 1):
            raise StateError("diagnosis requires one completed authoritative_failed lifecycle")
        raw_candidate_digest = report.get("candidate_manifest_digest")
        if not isinstance(raw_candidate_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", raw_candidate_digest
        ):
            raise StateError("authoritative validation report has an invalid candidate digest")
        if lifecycle.get("current_manifest_digest") != raw_candidate_digest:
            raise StateError("validation report does not match the failed candidate lifecycle")
        raw_patch_digest = report.get("candidate_patch_digest")
        if not isinstance(raw_patch_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", raw_patch_digest
        ) or lifecycle["current_patch_digest"] != raw_patch_digest:
            raise StateError("validation report patch does not match the failed candidate lifecycle")
        if report.get("plan_execution_attempt_id") != attempt_id:
            raise StateError("validation report attempt does not match the failed candidate lifecycle")
        candidate_manifest_digest = "sha256:" + raw_candidate_digest
    elif report.get("candidate_manifest_digest") not in {None, ""}:
        raise StateError("parent-direct failure cannot claim a candidate manifest")
    evidence = {
        "schema_version": 1,
        "plan_path": state["plan_path"],
        "plan_digest": state["plan_digest"],
        "source_head": state["source_head"],
        "implementation_mode": state["implementation_mode"],
        "candidate_lifecycle_identity_digest": state["candidate_lifecycle_identity_digest"],
        "candidate_lifecycle_digest": lifecycle_digest,
        "candidate_manifest_digest": candidate_manifest_digest,
        "validation_report_digest": digest(data),
        "failed_operation_digest": expected_operation,
        "observed_exit_status": observed_exit_status,
    }
    return evidence, digest(json.dumps(evidence, sort_keys=True, separators=(",", ":")))


def authoritative_failure_event(state: dict[str, Any]) -> dict[str, Any] | None:
    failures = [event for event in state["events"] if event["event_type"] == "authoritative_failure"]
    if len(failures) > 1:
        raise StateError("execution state contains multiple authoritative failures")
    return failures[0] if failures else None


def confirmed_diagnosis_invariant(state: dict[str, Any]) -> str:
    confirmed = [
        event for event in state["events"]
        if event["event_type"] == "failure_diagnosis"
        and event["diagnosis_evidence"]["diagnosis_result"] == "confirmed"
    ]
    if len(confirmed) > 1:
        raise StateError("execution state contains multiple confirmed diagnoses")
    return confirmed[0]["invariant_digests"][0] if confirmed else ""


def validate_diagnosis_evidence(
    value: Any,
    state: dict[str, Any],
    invariants: list[str],
    receipt: str,
    lifecycle_digest: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != DIAGNOSIS_EVIDENCE_KEYS:
        raise StateError("failure diagnosis evidence has an invalid exact schema")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise StateError("failure diagnosis evidence has an invalid schema version")
    failure_event = authoritative_failure_event(state)
    if failure_event is None:
        raise StateError("failure diagnosis lacks an authoritative failure")
    failure = failure_event["failure_evidence"]
    if lifecycle_digest != failure["candidate_lifecycle_digest"]:
        raise StateError("failure diagnosis lifecycle differs from authoritative failure")
    expected_identity = {
        "plan_path": state["plan_path"],
        "plan_digest": state["plan_digest"],
        "source_head": state["source_head"],
        "candidate_lifecycle_identity_digest": state["candidate_lifecycle_identity_digest"],
        "candidate_lifecycle_digest": failure["candidate_lifecycle_digest"],
        "authoritative_failure_event_digest": failure_event["event_digest"],
        "failure_evidence_digest": failure_event["failure_evidence_digest"],
        "failed_operation_digest": failure["failed_operation_digest"],
        "observed_exit_status": failure["observed_exit_status"],
        "independent_review_receipt_digest": receipt,
    }
    if any(value[key] != expected for key, expected in expected_identity.items()):
        raise StateError("failure diagnosis evidence does not match the authoritative failure")
    require_digest(value["reproduction_evidence_digest"], "reproduction_evidence_digest")
    result = value["diagnosis_result"]
    if result not in DIAGNOSIS_RESULTS:
        raise StateError("failure diagnosis evidence has an invalid result")
    affected = value["affected_invariant_digest"]
    if result == "confirmed":
        if len(invariants) != 1 or affected != invariants[0]:
            raise StateError("confirmed diagnosis must identify exactly one affected invariant")
        require_digest(affected, "affected_invariant_digest")
    elif invariants or affected != "":
        raise StateError("unconfirmed diagnosis cannot claim an affected invariant")
    return value


def load_diagnosis_evidence(
    path: Path,
    state: dict[str, Any],
    invariants: list[str],
    receipt: str,
    lifecycle_digest: str,
) -> tuple[dict[str, Any], str]:
    data = read_external_artifact(path, "failure diagnosis evidence")
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError("failure diagnosis evidence is invalid JSON") from exc
    evidence = validate_diagnosis_evidence(value, state, invariants, receipt, lifecycle_digest)
    canonical = (json.dumps(evidence, sort_keys=True, indent=2) + "\n").encode()
    if data != canonical:
        raise StateError("failure diagnosis evidence is not canonical JSON")
    return evidence, digest(data)


def validate_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != EXACT_KEYS:
        raise StateError("execution state has an invalid exact schema")
    if value["schema_version"] != SCHEMA_VERSION or isinstance(value["schema_version"], bool):
        raise StateError("execution state schema version mismatch")
    if not isinstance(value["run_id"], str) or not ID_RE.fullmatch(value["run_id"]):
        raise StateError("invalid run_id")
    if not isinstance(value["plan_path"], str) or not PLAN_RE.fullmatch(value["plan_path"]):
        raise StateError("invalid plan_path")
    require_digest(value["plan_digest"], "plan_digest")
    if not isinstance(value["source_head"], str) or not re.fullmatch(r"[0-9a-f]{40}", value["source_head"]):
        raise StateError("invalid source_head")
    require_digest(value["primary_invariant_digest"], "primary_invariant_digest")
    require_digest(value["candidate_lifecycle_identity_digest"], "candidate_lifecycle_identity_digest")
    predecessor_fields = (
        "predecessor_plan_digest",
        "predecessor_accepted_candidate_digest",
        "predecessor_closing_event_digest",
    )
    predecessor_values = [
        require_digest(value[key], key, allow_empty=True) for key in predecessor_fields
    ]
    if any(predecessor_values) and not all(predecessor_values):
        raise StateError("predecessor acceptance digests must be all present or all absent")
    predecessor_source = value["predecessor_accepted_source_head"]
    if not isinstance(predecessor_source, str) or (
        predecessor_source and not re.fullmatch(r"[0-9a-f]{40}", predecessor_source)
    ):
        raise StateError("invalid predecessor accepted source HEAD")
    if bool(predecessor_source) != bool(any(predecessor_values)):
        raise StateError("predecessor accepted source HEAD must accompany predecessor digests")
    accepted_fields = ("accepted_candidate_digest", "accepted_closing_event_digest")
    accepted_values = [
        require_digest(value[key], key, allow_empty=True) for key in accepted_fields
    ]
    if any(accepted_values) and not all(accepted_values):
        raise StateError("accepted candidate and closing-event digests must be paired")
    accepted_source = value["accepted_source_head"]
    if not isinstance(accepted_source, str) or (
        accepted_source and not re.fullmatch(r"[0-9a-f]{40}", accepted_source)
    ):
        raise StateError("invalid accepted source HEAD")
    if bool(accepted_source) != bool(any(accepted_values)):
        raise StateError("accepted source HEAD must accompany accepted candidate evidence")
    require_digest(value["successor_claim_digest"], "successor_claim_digest", allow_empty=True)
    if value["state"] not in {
        "active", "accepted", "rejected", "diagnosis_required",
        "repair_required", "replan_required"
    }:
        raise StateError("invalid state")
    if value["implementation_mode"] not in MODES:
        raise StateError("invalid implementation_mode")
    counter_keys = (
        "candidate_generations", "correction_rounds", "parent_direct_remediation_rounds",
        "focused_validation_events", "authoritative_validation_events",
        "writable_attempt_starts", "writable_attempt_closures", "last_monotonic_ns",
    )
    for key in counter_keys:
        item = value[key]
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise StateError(f"{key} must be a nonnegative integer")
    reasons = value["replan_reason_codes"]
    if not isinstance(reasons, list) or len(reasons) != len(set(reasons)) or any(
        not isinstance(reason, str) or reason not in REASON_CODES | REVIEW_REASON_CODES
        for reason in reasons
    ):
        raise StateError("invalid replan_reason_codes")
    if value["state"] == "replan_required" and not reasons:
        raise StateError("replan_required state needs a reason")
    repair_reasons = value["repair_reason_codes"]
    if not isinstance(repair_reasons, list) or len(repair_reasons) != len(set(repair_reasons)) or any(
        not isinstance(reason, str) or reason not in REPAIR_REASON_CODES for reason in repair_reasons
    ):
        raise StateError("invalid repair_reason_codes")
    if value["state"] == "repair_required" and not repair_reasons:
        raise StateError("repair_required state needs a reason")
    if value["state"] == "active" and (reasons or repair_reasons):
        raise StateError("active state cannot have stop reasons")
    review_reasons = value["review_reason_codes"]
    if not isinstance(review_reasons, list) or len(review_reasons) != len(set(review_reasons)) or any(
        not isinstance(reason, str) or reason not in REVIEW_REASON_CODES
        for reason in review_reasons
    ):
        raise StateError("invalid review_reason_codes")
    if not isinstance(value["open_attempt_id"], str) or (
        value["open_attempt_id"] and not ID_RE.fullmatch(value["open_attempt_id"])
    ):
        raise StateError("invalid open_attempt_id")
    if value["state"] == "accepted" and not all(accepted_values):
        raise StateError("accepted state requires accepted candidate evidence")
    if value["state"] != "accepted" and any(accepted_values):
        raise StateError("only accepted state may retain accepted candidate evidence")
    if reasons and repair_reasons:
        raise StateError("repair and replan reasons cannot be combined")
    events = value["events"]
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise StateError("invalid event list")
    seen_ids: set[str] = set()
    seen_review_receipts: set[str] = set()
    validated_events: list[dict[str, Any]] = []
    previous_ns = 0
    require_digest(value["genesis_digest"], "genesis_digest")
    if value["genesis_digest"] != state_genesis_digest(value):
        raise StateError("execution-state genesis identity digest mismatch")
    previous_digest = value["genesis_digest"]
    for index, event in enumerate(events, start=1):
        allowed_event_keys = {
            frozenset(EVENT_KEYS), frozenset(LEGACY_EVENT_KEYS),
            frozenset(DIAGNOSIS_EVENT_KEYS),
        }
        if not isinstance(event, dict) or frozenset(event) not in allowed_event_keys:
            raise StateError("event has an invalid exact schema")
        successor_genesis_digest = event.get("successor_genesis_digest", "")
        if event["sequence"] != index or isinstance(event["sequence"], bool):
            raise StateError("event sequence mismatch")
        if not isinstance(event["event_id"], str) or not ID_RE.fullmatch(event["event_id"]):
            raise StateError("invalid event_id")
        if event["event_id"] in seen_ids:
            raise StateError("duplicate event_id")
        seen_ids.add(event["event_id"])
        if event["event_type"] not in EVENT_TYPES or event["implementation_mode"] not in MODES:
            raise StateError("invalid event classification")
        prior_summary = derive_summary(validated_events)
        if prior_summary["state"] != "active":
            successor_is_allowed = (
                prior_summary["state"] == "accepted"
                and event["event_type"] == "successor_claimed"
                and not prior_summary["successor_claim_digest"]
            )
            diagnosis_is_allowed = (
                prior_summary["state"] == "diagnosis_required"
                and event["event_type"] in {"failure_diagnosis", "repair_classification"}
            )
            if not successor_is_allowed and not diagnosis_is_allowed:
                raise StateError("event history continues after a terminal execution state")
        invariants = event["invariant_digests"]
        if not isinstance(invariants, list) or len(invariants) != len(set(invariants)) or any(
            not isinstance(item, str) or not DIGEST_RE.fullmatch(item) for item in invariants
        ):
            raise StateError("invalid invariant_digests")
        severities = event["finding_severities"]
        if not isinstance(severities, list) or len(severities) != len(set(severities)) or any(
            severity not in {"High", "Medium", "Low"} for severity in severities
        ):
            raise StateError("invalid finding_severities")
        require_digest(
            event["independent_review_receipt_digest"],
            "independent_review_receipt_digest",
            allow_empty=True,
        )
        receipt_digest = event["independent_review_receipt_digest"]
        receipt_required = event["event_type"] in {
            "repair_classification", "failure_diagnosis"
        } or (
            event["event_type"] == "parent_review" and event["implementation_mode"] == "parent_direct"
        )
        if receipt_required:
            if not receipt_digest:
                raise StateError("event is missing an independent review receipt")
            if receipt_digest in seen_review_receipts:
                raise StateError("independent review receipt replay is not allowed")
            seen_review_receipts.add(receipt_digest)
        require_digest(event["repair_evidence_digest"], "repair_evidence_digest", allow_empty=True)
        classification = event["repair_classification"]
        if not isinstance(classification, dict):
            raise StateError("invalid repair classification")
        require_digest(event["candidate_lifecycle_digest"], "candidate_lifecycle_digest", allow_empty=True)
        attempt_id = event["attempt_id"]
        if not isinstance(attempt_id, str) or (attempt_id and not ID_RE.fullmatch(attempt_id)):
            raise StateError("invalid attempt_id")
        if event["attempt_kind"] not in ATTEMPT_KINDS | {""}:
            raise StateError("invalid attempt_kind")
        require_digest(event["candidate_digest"], "candidate_digest", allow_empty=True)
        if event["review_outcome"] not in REVIEW_OUTCOMES | {""}:
            raise StateError("invalid review_outcome")
        if event["review_reason_code"] not in REVIEW_REASON_CODES | {""}:
            raise StateError("invalid review_reason_code")
        if event["review_author"] not in {"", "parent"}:
            raise StateError("review outcome reason must be parent-authored")
        require_digest(event["review_evidence_digest"], "review_evidence_digest", allow_empty=True)
        event_predecessors = [
            require_digest(event[key], key, allow_empty=True) for key in predecessor_fields
        ]
        if any(event_predecessors) and not all(event_predecessors):
            raise StateError("event predecessor digests must be all present or all absent")
        event_predecessor_source = event["predecessor_accepted_source_head"]
        if not isinstance(event_predecessor_source, str) or (
            event_predecessor_source
            and not re.fullmatch(r"[0-9a-f]{40}", event_predecessor_source)
        ):
            raise StateError("event has an invalid predecessor accepted source HEAD")
        if bool(event_predecessor_source) != bool(any(event_predecessors)):
            raise StateError("event predecessor source HEAD is incomplete")
        event_accepted_source = event["accepted_source_head"]
        if not isinstance(event_accepted_source, str) or (
            event_accepted_source and not re.fullmatch(r"[0-9a-f]{40}", event_accepted_source)
        ):
            raise StateError("event has an invalid accepted source HEAD")
        successor_run_id = event["successor_run_id"]
        if not isinstance(successor_run_id, str) or (
            successor_run_id and not ID_RE.fullmatch(successor_run_id)
        ):
            raise StateError("event has an invalid successor run id")
        for key in ("successor_plan_digest", "successor_primary_invariant_digest"):
            require_digest(event[key], key, allow_empty=True)
        require_digest(successor_genesis_digest, "successor_genesis_digest", allow_empty=True)
        successor_source = event["successor_source_head"]
        if not isinstance(successor_source, str) or (
            successor_source and not re.fullmatch(r"[0-9a-f]{40}", successor_source)
        ):
            raise StateError("event has an invalid successor source HEAD")
        if event["event_type"] == "writable_attempt_started":
            if not attempt_id or not event["attempt_kind"]:
                raise StateError("writable attempt start is missing its identifier or kind")
            if any((event["candidate_digest"], event["review_outcome"], event["review_reason_code"],
                    event["review_author"], event["review_evidence_digest"],
                    event_accepted_source, successor_run_id, event["successor_plan_digest"],
                    successor_source, event["successor_primary_invariant_digest"],
                    successor_genesis_digest)):
                raise StateError("writable attempt start contains review outcome data")
            if event_predecessors != predecessor_values:
                raise StateError("writable attempt start predecessor evidence differs from its run")
            if event_predecessor_source != predecessor_source:
                raise StateError("writable attempt start predecessor source differs from its run")
        elif event["event_type"] == "attempt_closed":
            if not attempt_id or event["attempt_kind"] or not event["review_outcome"]:
                raise StateError("attempt closure has invalid attempt identity fields")
            if event["review_author"] != "parent" or not event["review_evidence_digest"]:
                raise StateError("attempt closure requires parent review evidence")
            if not invariants:
                raise StateError("attempt closure must identify affected invariants")
            if event["review_outcome"] == "accepted":
                if (not event["candidate_digest"] or event["review_reason_code"]
                        or not event_accepted_source):
                    raise StateError("accepted attempt closure has invalid candidate or reason data")
            elif not event["review_reason_code"] or event_accepted_source:
                raise StateError("non-accepted attempt closure requires a review reason code")
            if any(event_predecessors) or event_predecessor_source:
                raise StateError("attempt closure cannot restate predecessor evidence")
            if any((successor_run_id, event["successor_plan_digest"], successor_source,
                    event["successor_primary_invariant_digest"],
                    successor_genesis_digest)):
                raise StateError("attempt closure cannot contain successor identity")
        elif event["event_type"] == "successor_claimed":
            successor_values = (
                successor_run_id, event["successor_plan_digest"], successor_source,
                event["successor_primary_invariant_digest"], successor_genesis_digest,
            )
            if not all(successor_values):
                raise StateError("successor claim has incomplete child identity")
            if any((attempt_id, event["attempt_kind"], event["candidate_digest"],
                    event["review_outcome"], event["review_reason_code"],
                    event["review_author"], event["review_evidence_digest"],
                    *event_predecessors, event_predecessor_source, event_accepted_source)):
                raise StateError("successor claim contains unrelated attempt data")
        elif any((attempt_id, event["attempt_kind"], event["candidate_digest"],
                  event["review_outcome"], event["review_reason_code"],
                  event["review_author"], event["review_evidence_digest"], *event_predecessors,
                  event_predecessor_source, event_accepted_source, successor_run_id,
                  event["successor_plan_digest"], successor_source,
                  event["successor_primary_invariant_digest"], successor_genesis_digest)):
            raise StateError("non-attempt event contains writable-attempt data")
        diagnosis_keys_present = frozenset(event) == frozenset(DIAGNOSIS_EVENT_KEYS)
        failure_evidence = event.get("failure_evidence", {})
        failure_evidence_digest = event.get("failure_evidence_digest", "")
        diagnosis_evidence = event.get("diagnosis_evidence", {})
        diagnosis_evidence_digest = event.get("diagnosis_evidence_digest", "")
        if event["event_type"] == "authoritative_failure":
            if not diagnosis_keys_present or set(failure_evidence) != FAILURE_EVIDENCE_KEYS:
                raise StateError("authoritative failure event has an invalid exact schema")
            if diagnosis_evidence or diagnosis_evidence_digest:
                raise StateError("authoritative failure event contains diagnosis evidence")
            if failure_evidence["schema_version"] != 1:
                raise StateError("authoritative failure evidence has an invalid schema version")
            expected_failure_identity = {
                "plan_path": value["plan_path"],
                "plan_digest": value["plan_digest"],
                "source_head": value["source_head"],
                "implementation_mode": value["implementation_mode"],
                "candidate_lifecycle_identity_digest": value["candidate_lifecycle_identity_digest"],
                "candidate_lifecycle_digest": event["candidate_lifecycle_digest"],
            }
            if any(failure_evidence[key] != expected for key, expected in expected_failure_identity.items()):
                raise StateError("authoritative failure evidence does not match the execution baseline")
            require_digest(
                failure_evidence["candidate_manifest_digest"],
                "candidate_manifest_digest",
                allow_empty=value["implementation_mode"] == "parent_direct",
            )
            for key in ("validation_report_digest", "failed_operation_digest"):
                require_digest(failure_evidence[key], key)
            if value["implementation_mode"] == "candidate" and not failure_evidence[
                "candidate_manifest_digest"
            ]:
                raise StateError("candidate failure evidence lacks a candidate manifest")
            if value["implementation_mode"] == "parent_direct" and failure_evidence[
                "candidate_manifest_digest"
            ]:
                raise StateError("parent-direct failure evidence contains a candidate manifest")
            status = failure_evidence["observed_exit_status"]
            if type(status) is not int or not -255 <= status <= 255:
                raise StateError("authoritative failure evidence has an invalid exit status")
            require_digest(failure_evidence_digest, "failure_evidence_digest")
            expected_failure_digest = digest(
                json.dumps(failure_evidence, sort_keys=True, separators=(",", ":"))
            )
            if failure_evidence_digest != expected_failure_digest:
                raise StateError("authoritative failure evidence digest mismatch")
            if invariants or receipt_digest or severities:
                raise StateError("authoritative failure cannot pre-claim diagnosis results")
        elif event["event_type"] == "failure_diagnosis":
            if not diagnosis_keys_present or failure_evidence or failure_evidence_digest:
                raise StateError("failure diagnosis event has an invalid exact schema")
            if not receipt_digest or severities:
                raise StateError("failure diagnosis requires one independent review receipt")
            validate_diagnosis_evidence(
                diagnosis_evidence, value, invariants, receipt_digest,
                event["candidate_lifecycle_digest"],
            )
            require_digest(diagnosis_evidence_digest, "diagnosis_evidence_digest")
            canonical_diagnosis = (
                json.dumps(diagnosis_evidence, sort_keys=True, indent=2) + "\n"
            ).encode()
            if diagnosis_evidence_digest != digest(canonical_diagnosis):
                raise StateError("failure diagnosis evidence digest mismatch")
        elif diagnosis_keys_present:
            raise StateError("non-diagnosis event contains diagnosis evidence fields")
        if event["event_type"] == "repair_classification":
            if not invariants:
                raise StateError("repair classification event must affect at least one invariant")
            if not event["independent_review_receipt_digest"] or not event["repair_evidence_digest"]:
                raise StateError("repair classification event is missing evidence")
            if not event["candidate_lifecycle_digest"]:
                raise StateError("repair classification event is missing candidate lifecycle evidence")
            if severities:
                raise StateError("repair classification event cannot contain unresolved findings")
            validate_repair_classification(
                classification,
                value,
                invariants,
                event["independent_review_receipt_digest"],
                event["candidate_lifecycle_digest"],
            )
            canonical_classification = (json.dumps(classification, sort_keys=True, indent=2) + "\n").encode()
            if event["repair_evidence_digest"] != digest(canonical_classification):
                raise StateError("repair evidence digest does not match embedded classification")
        elif event["repair_evidence_digest"] or classification:
            raise StateError("non-repair event contains repair classification evidence")
        elapsed = event["elapsed_seconds"]
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
            raise StateError("elapsed_seconds must be finite and nonnegative")
        monotonic_ns = event["monotonic_ns"]
        if isinstance(monotonic_ns, bool) or not isinstance(monotonic_ns, int) or monotonic_ns <= previous_ns:
            raise StateError("event monotonic_ns must increase")
        previous_ns = monotonic_ns
        if event["previous_event_digest"] != previous_digest:
            raise StateError("event hash-chain predecessor mismatch")
        require_digest(event["event_digest"], "event_digest")
        unsigned = {key: value for key, value in event.items() if key != "event_digest"}
        expected_event_digest = digest(json.dumps(unsigned, sort_keys=True, separators=(",", ":")))
        if event["event_digest"] != expected_event_digest:
            raise StateError("event hash-chain digest mismatch")
        previous_digest = event["event_digest"]
        validated_events.append(event)
    if events and value["last_monotonic_ns"] != events[-1]["monotonic_ns"]:
        raise StateError("last_monotonic_ns mismatch")
    if value["event_chain_digest"] != previous_digest:
        raise StateError("event_chain_digest mismatch")
    derived = derive_summary(events)
    for key, expected in derived.items():
        if value[key] != expected:
            raise StateError(f"{key} does not match the immutable event history")
    return value


def derive_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_generations = 0
    correction_rounds = 0
    parent_rounds = 0
    focused_events = 0
    authoritative_events = 0
    attempt_starts = 0
    attempt_closures = 0
    open_attempt_id = ""
    last_attempt_kind = ""
    last_review_outcome = ""
    accepted_candidate_digest = ""
    accepted_closing_event_digest = ""
    accepted_source_head = ""
    successor_claim_digest = ""
    terminal_rejection = False
    review_reason_codes: list[str] = []
    reasons: list[str] = []
    repair_reasons: list[str] = []
    authoritative_failure_seen = False
    diagnosis_attempts = 0
    confirmed_invariant = ""

    def add_reason(reason: str) -> None:
        if reason not in reasons:
            reasons.append(reason)

    for event in events:
        event_type = event["event_type"]
        if event_type == "candidate_generation":
            if candidate_generations != 0:
                raise StateError("initial candidate generation already recorded")
            candidate_generations += 1
        elif event_type == "correction_rejected":
            if candidate_generations != correction_rounds + 1:
                raise StateError("correction event is out of order")
            correction_rounds += 1
            candidate_generations += 1
            if correction_rounds >= MAX_CORRECTIONS:
                add_reason("candidate_correction_budget_exhausted")
        elif event_type == "parent_review":
            if len(event["invariant_digests"]) > 1:
                add_reason("multiple_independent_invariants")
            if event["implementation_mode"] == "parent_direct" and set(
                event["finding_severities"]
            ) & {"High", "Medium"}:
                parent_rounds += 1
                if parent_rounds >= MAX_PARENT_REMEDIATIONS:
                    add_reason("parent_remediation_budget_exhausted")
        elif event_type == "focused_validation":
            focused_events += 1
        elif event_type == "authoritative_validation":
            authoritative_events += 1
        elif event_type == "authoritative_failure":
            if authoritative_events != 1 or authoritative_failure_seen:
                raise StateError("authoritative failure is out of order")
            authoritative_failure_seen = True
        elif event_type == "failure_diagnosis":
            if not authoritative_failure_seen or confirmed_invariant:
                raise StateError("failure diagnosis is out of order")
            diagnosis_attempts += 1
            if diagnosis_attempts > MAX_DIAGNOSIS_ATTEMPTS:
                raise StateError("failure diagnosis attempt budget is exhausted")
            if event["diagnosis_evidence"]["diagnosis_result"] == "confirmed":
                confirmed_invariant = event["invariant_digests"][0]
        elif event_type in {
            "scope_drift", "spec_drift", "security_boundary_drift", "post_authoritative_design_change"
        }:
            add_reason(event_type)
        elif event_type == "repair_classification":
            if not confirmed_invariant or event["invariant_digests"] != [confirmed_invariant]:
                raise StateError("repair classification requires the confirmed affected invariant")
            classification_result = classify_repair(event["repair_classification"])
            if classification_result == "independent_repair_required":
                repair_reasons.append(classification_result)
            else:
                add_reason(classification_result)
        elif event_type == "writable_attempt_started":
            if open_attempt_id:
                raise StateError("writable attempts overlap")
            attempt_kind = event["attempt_kind"]
            if attempt_kind == "initial":
                if attempt_starts:
                    raise StateError("initial writable attempt may start only once")
            elif last_review_outcome != "correction_requested":
                raise StateError("correction attempt lacks a parent correction decision")
            if attempt_kind == "correction" and correction_rounds >= MAX_CORRECTIONS:
                raise StateError("candidate correction budget is exhausted")
            attempt_starts += 1
            candidate_generations += 1
            if attempt_kind == "correction":
                correction_rounds += 1
            open_attempt_id = event["attempt_id"]
            last_attempt_kind = attempt_kind
            last_review_outcome = ""
        elif event_type == "attempt_closed":
            if not open_attempt_id or event["attempt_id"] != open_attempt_id:
                raise StateError("attempt closure does not match the open writable attempt")
            attempt_closures += 1
            open_attempt_id = ""
            outcome = event["review_outcome"]
            last_review_outcome = outcome
            reason = event["review_reason_code"]
            if reason:
                repeated = reason in review_reason_codes
                if not repeated:
                    review_reason_codes.append(reason)
                if repeated:
                    add_reason(reason)
                if reason == "multiple_invariants_coupled":
                    add_reason(reason)
            if outcome == "accepted":
                if last_attempt_kind not in ATTEMPT_KINDS:
                    raise StateError("accepted closure lacks a writable attempt")
                accepted_candidate_digest = event["candidate_digest"]
                accepted_closing_event_digest = event["event_digest"]
                accepted_source_head = event["accepted_source_head"]
            elif outcome == "rejected":
                if correction_rounds >= MAX_CORRECTIONS:
                    add_reason("candidate_correction_budget_exhausted")
                else:
                    terminal_rejection = True
            elif correction_rounds >= MAX_CORRECTIONS:
                add_reason("candidate_correction_budget_exhausted")
        elif event_type == "successor_claimed":
            if not accepted_candidate_digest or successor_claim_digest:
                raise StateError("successor claim is not attached to one accepted leaf")
            successor_claim_digest = event["event_digest"]
    if reasons:
        state = "replan_required"
    elif repair_reasons:
        state = "repair_required"
    elif accepted_candidate_digest:
        state = "accepted"
    elif terminal_rejection:
        state = "rejected"
    elif authoritative_failure_seen:
        state = "diagnosis_required"
    else:
        state = "active"
    return {
        "state": state,
        "candidate_generations": candidate_generations,
        "correction_rounds": correction_rounds,
        "parent_direct_remediation_rounds": parent_rounds,
        "focused_validation_events": focused_events,
        "authoritative_validation_events": authoritative_events,
        "writable_attempt_starts": attempt_starts,
        "writable_attempt_closures": attempt_closures,
        "open_attempt_id": open_attempt_id,
        "accepted_candidate_digest": accepted_candidate_digest,
        "accepted_closing_event_digest": accepted_closing_event_digest,
        "accepted_source_head": accepted_source_head,
        "successor_claim_digest": successor_claim_digest,
        "review_reason_codes": review_reason_codes,
        "repair_reason_codes": repair_reasons,
        "replan_reason_codes": reasons,
    }


def read_state(path: Path) -> dict[str, Any]:
    reject_symlink_ancestors(path, include_target=True)
    _, data = open_read(path)
    if len(data) > MAX_BYTES:
        raise StateError("execution state exceeds size limit")
    try:
        return validate_state(json.loads(data))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError(f"invalid execution state JSON: {exc}") from exc


def predecessor_acceptance_from_state(predecessor: dict[str, Any]) -> dict[str, str]:
    if predecessor["state"] != "accepted" or predecessor["open_attempt_id"]:
        raise StateError("predecessor execution state lacks an accepted closing transition")
    return {
        "predecessor_plan_digest": predecessor["plan_digest"],
        "predecessor_accepted_candidate_digest": predecessor["accepted_candidate_digest"],
        "predecessor_closing_event_digest": predecessor["accepted_closing_event_digest"],
        "predecessor_accepted_source_head": predecessor["accepted_source_head"],
    }


def read_predecessor_acceptance(path: Path) -> dict[str, str]:
    require_outside_repository(path, "predecessor execution state")
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
        predecessor = read_state(path)
    return predecessor_acceptance_from_state(predecessor)


def successor_identity(state: dict[str, Any]) -> dict[str, str]:
    return {
        "successor_run_id": state["run_id"],
        "successor_plan_digest": state["plan_digest"],
        "successor_source_head": state["source_head"],
        "successor_primary_invariant_digest": state["primary_invariant_digest"],
        "successor_genesis_digest": state["genesis_digest"],
    }


def claim_predecessor_for_successor(
    predecessor_path: Path,
    expected: dict[str, str],
    successor: dict[str, Any],
    elapsed_seconds: float,
) -> None:
    require_outside_repository(predecessor_path, "predecessor execution state")
    with with_lock(predecessor_path) as predecessor_lock:
        fcntl.flock(predecessor_lock.fileno(), fcntl.LOCK_EX)
        predecessor = read_state(predecessor_path)
        observed = predecessor_acceptance_from_state(predecessor)
        if observed != expected:
            raise StateError("predecessor acceptance proof is stale or mismatched")
        identity = successor_identity(successor)
        prior_claims = [
            event for event in predecessor["events"]
            if event["event_type"] == "successor_claimed"
        ]
        if prior_claims:
            prior = prior_claims[0]
            if any(prior[key] != value for key, value in identity.items()):
                raise StateError("accepted predecessor is already claimed by another successor")
            return
        monotonic_ns = max(time.monotonic_ns(), predecessor["last_monotonic_ns"] + 1)
        event = {
            "sequence": len(predecessor["events"]) + 1,
            "event_id": f"successor:{successor['run_id']}",
            "event_type": "successor_claimed",
            "implementation_mode": predecessor["implementation_mode"],
            "invariant_digests": [],
            "finding_severities": [],
            "independent_review_receipt_digest": "",
            "repair_classification": {},
            "repair_evidence_digest": "",
            "candidate_lifecycle_digest": "",
            "attempt_id": "",
            "attempt_kind": "",
            "candidate_digest": "",
            "review_outcome": "",
            "review_reason_code": "",
            "review_author": "",
            "review_evidence_digest": "",
            "predecessor_plan_digest": "",
            "predecessor_accepted_candidate_digest": "",
            "predecessor_closing_event_digest": "",
            "predecessor_accepted_source_head": "",
            "accepted_source_head": "",
            **identity,
            "elapsed_seconds": elapsed_seconds,
            "monotonic_ns": monotonic_ns,
            "previous_event_digest": predecessor["event_chain_digest"],
        }
        event["event_digest"] = digest(
            json.dumps(event, sort_keys=True, separators=(",", ":"))
        )
        predecessor["events"].append(event)
        predecessor["last_monotonic_ns"] = monotonic_ns
        predecessor["event_chain_digest"] = event["event_digest"]
        for key, value in derive_summary(predecessor["events"]).items():
            predecessor[key] = value
        validate_state(predecessor)
        atomic_write(predecessor_path, predecessor)


def require_predecessor_ancestry(accepted_source_head: str, successor_source_head: str) -> None:
    root = repository_root()
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", accepted_source_head, successor_source_head],
        cwd=root, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise StateError("successor source HEAD is not based on the accepted predecessor source")


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    reject_symlink_ancestors(path, include_target=False)
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    if len(data) > MAX_BYTES:
        raise StateError("execution state exceeds size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    directory_descriptor = os.open(path.parent, directory_flags)
    temporary_name = f".{path.name}.{secrets.token_hex(16)}.tmp"
    descriptor = -1
    try:
        descriptor = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_descriptor,
        )
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(
            temporary_name, path.name,
            src_dir_fd=directory_descriptor, dst_dir_fd=directory_descriptor,
        )
        os.fsync(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary_name, dir_fd=directory_descriptor)
        except FileNotFoundError:
            pass
        os.close(directory_descriptor)


def with_lock(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    reject_symlink_ancestors(lock_path, include_target=True)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    directory_descriptor = os.open(
        lock_path.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        descriptor = os.open(
            lock_path.name,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_descriptor,
        )
    finally:
        os.close(directory_descriptor)
    return os.fdopen(descriptor, "a", encoding="utf-8")


def init_state(args: argparse.Namespace) -> None:
    path = Path(args.state)
    lifecycle_path = Path(args.lifecycle_state)
    require_outside_repository(path, "execution state")
    require_outside_repository(lifecycle_path, "candidate lifecycle state")
    if path.exists() or path.is_symlink():
        raise StateError("execution state already exists")
    plan = Path(args.plan)
    plan_bytes = plan.read_bytes()
    if digest(plan_bytes) != args.plan_digest:
        raise StateError("plan digest mismatch")
    invariant_digest = require_digest(args.primary_invariant_digest, "primary_invariant_digest")
    plan_text = plan_bytes.decode("utf-8")
    invariant_matches = re.findall(r"^primary_invariant: (.+)$", plan_text, flags=re.MULTILINE)
    if len(invariant_matches) > 1 or (invariant_matches and digest(invariant_matches[0]) != invariant_digest):
        raise StateError("primary invariant digest mismatch")
    actual_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, env=sanitized_git_environment()
    ).strip()
    if actual_head != args.source_head:
        raise StateError("source HEAD mismatch")
    predecessor = {
        "predecessor_plan_digest": "",
        "predecessor_accepted_candidate_digest": "",
        "predecessor_closing_event_digest": "",
        "predecessor_accepted_source_head": "",
    }
    if args.predecessor_state:
        predecessor = read_predecessor_acceptance(Path(args.predecessor_state))
        require_predecessor_ancestry(
            predecessor["predecessor_accepted_source_head"], args.source_head
        )
    state = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "plan_path": args.plan,
        "plan_digest": args.plan_digest,
        "source_head": args.source_head,
        "primary_invariant_digest": invariant_digest,
        "candidate_lifecycle_identity_digest": lifecycle_identity_digest(args.run_id, lifecycle_path),
        "state": "active",
        "implementation_mode": args.implementation_mode,
        "candidate_generations": 0,
        "correction_rounds": 0,
        "parent_direct_remediation_rounds": 0,
        "focused_validation_events": 0,
        "authoritative_validation_events": 0,
        **predecessor,
        "writable_attempt_starts": 0,
        "writable_attempt_closures": 0,
        "open_attempt_id": "",
        "accepted_candidate_digest": "",
        "accepted_closing_event_digest": "",
        "accepted_source_head": "",
        "successor_claim_digest": "",
        "review_reason_codes": [],
        "repair_reason_codes": [],
        "replan_reason_codes": [],
        "last_monotonic_ns": 0,
        "genesis_digest": "",
        "event_chain_digest": "",
        "events": [],
    }
    state["genesis_digest"] = state_genesis_digest(state)
    state["event_chain_digest"] = state["genesis_digest"]
    validate_state(state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if path.exists() or path.is_symlink():
            raise StateError("execution state already exists")
        atomic_write(path, state)


def trigger(state: dict[str, Any], reason: str) -> None:
    state["state"] = "replan_required"
    if reason not in state["replan_reason_codes"]:
        state["replan_reason_codes"].append(reason)


def require_independent_repair(state: dict[str, Any]) -> None:
    state["state"] = "repair_required"
    if "independent_repair_required" not in state["repair_reason_codes"]:
        state["repair_reason_codes"].append("independent_repair_required")


def stopped_message(state: dict[str, Any]) -> str:
    if state["state"] == "replan_required":
        return "plan execution is stopped for restructuring"
    if state["state"] == "accepted":
        return "plan execution is closed with an accepted candidate"
    if state["state"] == "rejected":
        return "plan execution is closed with a rejected candidate"
    if state["state"] == "diagnosis_required":
        return "plan execution is stopped pending confirmed failure diagnosis"
    return "plan execution is stopped for an independent repair"


def record_event(args: argparse.Namespace) -> None:
    path = Path(args.state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        if state["run_id"] != args.run_id:
            raise StateError("run_id mismatch")
        if state["implementation_mode"] != args.implementation_mode:
            raise StateError("event implementation mode differs from the execution ledger")
        if state["state"] == "active":
            if args.event_type == "failure_diagnosis":
                raise StateError("failure diagnosis requires an authoritative failure")
            if args.event_type == "repair_classification":
                raise StateError("repair classification requires a confirmed failure diagnosis")
        elif state["state"] == "diagnosis_required":
            if args.event_type not in {"failure_diagnosis", "repair_classification"}:
                raise StateError(stopped_message(state))
            if args.event_type == "failure_diagnosis" and confirmed_diagnosis_invariant(state):
                raise StateError("confirmed failure diagnosis already exists")
            diagnosis_attempts = sum(
                event["event_type"] == "failure_diagnosis" for event in state["events"]
            )
            if args.event_type == "failure_diagnosis" and diagnosis_attempts >= MAX_DIAGNOSIS_ATTEMPTS:
                raise StateError("failure diagnosis attempt budget is exhausted")
            if args.event_type == "repair_classification" and not confirmed_diagnosis_invariant(state):
                raise StateError("repair classification requires a confirmed failure diagnosis")
        else:
            raise StateError(stopped_message(state))
        if any(event["event_id"] == args.event_id for event in state["events"]):
            raise StateError("event replay is not allowed")
        if len(state["events"]) >= MAX_EVENTS:
            raise StateError("event budget exhausted")
        invariants = args.invariant_digest or []
        if len(invariants) != len(set(invariants)):
            raise StateError("invariant digests must be unique")
        for invariant in invariants:
            require_digest(invariant, "invariant_digest")
        severities = args.finding_severity or []
        receipt = args.independent_review_receipt_digest or ""
        repair_classification: dict[str, Any] = {}
        repair_evidence = ""
        failure_evidence: dict[str, Any] = {}
        failure_evidence_digest = ""
        diagnosis_evidence: dict[str, Any] = {}
        diagnosis_evidence_digest = ""
        lifecycle = args.candidate_lifecycle_digest or ""
        if args.implementation_mode == "parent_direct" and args.event_type == "parent_review":
            require_digest(receipt, "independent_review_receipt_digest")
            if any(event["independent_review_receipt_digest"] == receipt for event in state["events"]):
                raise StateError("independent review receipt replay is not allowed")
        if args.event_type == "repair_classification":
            if not invariants:
                raise StateError("repair classification requires at least one affected invariant")
            require_digest(receipt, "independent_review_receipt_digest")
            if not args.repair_evidence_file:
                raise StateError("repair classification requires an evidence file")
            if any(event["independent_review_receipt_digest"] == receipt for event in state["events"]):
                raise StateError("independent review receipt replay is not allowed")
            if severities:
                raise StateError("repair classification cannot carry unresolved findings")
        elif args.repair_evidence_file:
            raise StateError("repair evidence is only valid for independent repair")
        if args.event_type == "authoritative_failure":
            if not args.validation_report:
                raise StateError("authoritative failure requires a validation report")
            if invariants or severities or receipt:
                raise StateError("authoritative failure cannot pre-claim diagnosis results")
            if state["authoritative_validation_events"] != 1:
                raise StateError("authoritative failure requires exactly one authoritative event")
        elif args.validation_report:
            raise StateError("validation report is only valid for authoritative failure")
        if args.event_type == "failure_diagnosis":
            require_digest(receipt, "independent_review_receipt_digest")
            if not args.diagnosis_evidence_file:
                raise StateError("failure diagnosis requires an evidence file")
            if severities:
                raise StateError("failure diagnosis cannot carry unresolved findings")
            if any(event["independent_review_receipt_digest"] == receipt for event in state["events"]):
                raise StateError("independent review receipt replay is not allowed")
        elif args.diagnosis_evidence_file:
            raise StateError("diagnosis evidence is only valid for failure diagnosis")
        if args.event_type in {
            "parent_review", "scope_drift", "spec_drift", "security_boundary_drift",
            "post_authoritative_design_change",
        } and not invariants:
            raise StateError("this event requires at least one affected invariant digest")
        if args.event_type in {
            "candidate_generation", "correction_rejected", "focused_validation",
            "authoritative_validation", "authoritative_failure", "failure_diagnosis",
            "repair_classification",
        }:
            require_digest(lifecycle, "candidate_lifecycle_digest")
            if lifecycle != file_digest(Path(args.lifecycle_state)):
                raise StateError("candidate lifecycle content digest mismatch")
        if args.event_type in {
            "authoritative_failure", "failure_diagnosis", "repair_classification"
        }:
            require_repository_baseline(state)
        if args.event_type == "repair_classification":
            confirmed = confirmed_diagnosis_invariant(state)
            if invariants != [confirmed]:
                raise StateError("repair classification must use the confirmed affected invariant")
            confirmed_event = next(
                event for event in state["events"]
                if event["event_type"] == "failure_diagnosis"
                and event["diagnosis_evidence"]["diagnosis_result"] == "confirmed"
            )
            if lifecycle != confirmed_event["candidate_lifecycle_digest"]:
                raise StateError("repair classification lifecycle differs from confirmed diagnosis")
            repair_classification, repair_evidence = load_repair_classification(
                Path(args.repair_evidence_file), state, invariants, receipt, lifecycle,
            )
        elif args.event_type == "authoritative_failure":
            failure_evidence, failure_evidence_digest = load_authoritative_failure(
                Path(args.validation_report), state, Path(args.lifecycle_state), lifecycle,
            )
        elif args.event_type == "failure_diagnosis":
            diagnosis_evidence, diagnosis_evidence_digest = load_diagnosis_evidence(
                Path(args.diagnosis_evidence_file), state, invariants, receipt, lifecycle,
            )
        monotonic_ns = time.monotonic_ns()
        if monotonic_ns <= state["last_monotonic_ns"]:
            monotonic_ns = state["last_monotonic_ns"] + 1
        event = {
            "sequence": len(state["events"]) + 1,
            "event_id": args.event_id,
            "event_type": args.event_type,
            "implementation_mode": args.implementation_mode,
            "invariant_digests": invariants,
            "finding_severities": severities,
            "independent_review_receipt_digest": receipt,
            "repair_classification": repair_classification,
            "repair_evidence_digest": repair_evidence,
            "candidate_lifecycle_digest": lifecycle,
            "attempt_id": "",
            "attempt_kind": "",
            "candidate_digest": "",
            "review_outcome": "",
            "review_reason_code": "",
            "review_author": "",
            "review_evidence_digest": "",
            "predecessor_plan_digest": "",
            "predecessor_accepted_candidate_digest": "",
            "predecessor_closing_event_digest": "",
            "predecessor_accepted_source_head": "",
            "accepted_source_head": "",
            "successor_run_id": "",
            "successor_plan_digest": "",
            "successor_source_head": "",
            "successor_primary_invariant_digest": "",
            "successor_genesis_digest": "",
            "elapsed_seconds": args.elapsed_seconds,
            "monotonic_ns": monotonic_ns,
            "previous_event_digest": state["event_chain_digest"],
        }
        if args.event_type in {"authoritative_failure", "failure_diagnosis"}:
            event.update(
                {
                    "failure_evidence": failure_evidence,
                    "failure_evidence_digest": failure_evidence_digest,
                    "diagnosis_evidence": diagnosis_evidence,
                    "diagnosis_evidence_digest": diagnosis_evidence_digest,
                }
            )
        event["event_digest"] = digest(
            json.dumps(event, sort_keys=True, separators=(",", ":"))
        )
        state["events"].append(event)
        state["last_monotonic_ns"] = monotonic_ns
        state["event_chain_digest"] = event["event_digest"]
        if args.event_type == "post_authoritative_design_change" and not state[
            "authoritative_validation_events"
        ]:
            raise StateError("post-authoritative design change requires an authoritative event")
        for key, value in derive_summary(state["events"]).items():
            state[key] = value
        validate_state(state)
        atomic_write(path, state)


def require_lifecycle_identity(state: dict[str, Any], run_id: str, lifecycle_path: Path) -> None:
    if state["candidate_lifecycle_identity_digest"] != lifecycle_identity_digest(
        run_id, lifecycle_path
    ):
        raise StateError("candidate lifecycle identity mismatch")


def record_writable_attempt_start(args: argparse.Namespace) -> None:
    path = Path(args.state)
    lifecycle_path = Path(args.lifecycle_state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        if state["run_id"] != args.run_id:
            raise StateError("run_id mismatch")
        if state["plan_path"] != args.plan:
            raise StateError("plan path mismatch")
        if state["state"] != "active":
            raise StateError(stopped_message(state))
        if state["implementation_mode"] != "candidate":
            raise StateError("writable attempt start requires candidate implementation mode")
        require_repository_baseline(state)
        require_lifecycle_identity(state, args.run_id, lifecycle_path)
        if state["open_attempt_id"]:
            raise StateError("a writable attempt is already open in this dependency chain")
        if any(event["attempt_id"] == args.attempt_id for event in state["events"]):
            raise StateError("attempt identifier replay is not allowed")
        prior_candidate_digest = args.prior_candidate_digest or ""
        if args.attempt_kind == "correction":
            require_digest(prior_candidate_digest, "prior_candidate_digest")
            closures = [
                event for event in state["events"] if event["event_type"] == "attempt_closed"
            ]
            if (
                not closures
                or closures[-1]["review_outcome"] != "correction_requested"
                or closures[-1]["candidate_digest"] != prior_candidate_digest
            ):
                raise StateError("correction start is not bound to the parent-rejected candidate")
        elif prior_candidate_digest:
            raise StateError("only a correction start may bind a prior candidate")
        predecessor = {
            "predecessor_plan_digest": state["predecessor_plan_digest"],
            "predecessor_accepted_candidate_digest": state[
                "predecessor_accepted_candidate_digest"
            ],
            "predecessor_closing_event_digest": state["predecessor_closing_event_digest"],
            "predecessor_accepted_source_head": state["predecessor_accepted_source_head"],
        }
        if args.attempt_kind == "initial" and any(predecessor.values()):
            if not args.predecessor_state:
                raise StateError("dependent writable start requires predecessor execution state")
            predecessor_path = Path(args.predecessor_state)
            if predecessor_path.absolute() == path.absolute():
                raise StateError("predecessor execution state cannot be the current ledger")
            require_predecessor_ancestry(
                predecessor["predecessor_accepted_source_head"], state["source_head"]
            )
            claim_predecessor_for_successor(
                predecessor_path, predecessor, state, args.elapsed_seconds
            )
        elif args.predecessor_state:
            raise StateError("predecessor execution state is valid only for an initial dependent start")
        monotonic_ns = max(time.monotonic_ns(), state["last_monotonic_ns"] + 1)
        event = {
            "sequence": len(state["events"]) + 1,
            "event_id": f"start:{args.attempt_id}",
            "event_type": "writable_attempt_started",
            "implementation_mode": "candidate",
            "invariant_digests": [],
            "finding_severities": [],
            "independent_review_receipt_digest": "",
            "repair_classification": {},
            "repair_evidence_digest": "",
            "candidate_lifecycle_digest": "",
            "attempt_id": args.attempt_id,
            "attempt_kind": args.attempt_kind,
            "candidate_digest": "",
            "review_outcome": "",
            "review_reason_code": "",
            "review_author": "",
            "review_evidence_digest": "",
            **predecessor,
            "accepted_source_head": "",
            "successor_run_id": "",
            "successor_plan_digest": "",
            "successor_source_head": "",
            "successor_primary_invariant_digest": "",
            "successor_genesis_digest": "",
            "elapsed_seconds": args.elapsed_seconds,
            "monotonic_ns": monotonic_ns,
            "previous_event_digest": state["event_chain_digest"],
        }
        event["event_digest"] = digest(
            json.dumps(event, sort_keys=True, separators=(",", ":"))
        )
        state["events"].append(event)
        state["last_monotonic_ns"] = monotonic_ns
        state["event_chain_digest"] = event["event_digest"]
        for key, value in derive_summary(state["events"]).items():
            state[key] = value
        validate_state(state)
        atomic_write(path, state)


def load_candidate_lifecycle_for_close(
    path: Path, run_id: str, attempt_id: str, lifecycle_digest: str, candidate_digest: str
) -> dict[str, Any]:
    require_digest(lifecycle_digest, "candidate_lifecycle_digest")
    raw = read_external_artifact(path, "candidate lifecycle state")
    if digest(raw) != lifecycle_digest:
        raise StateError("candidate lifecycle content digest mismatch")
    try:
        lifecycle = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError("candidate lifecycle state is invalid JSON") from exc
    if not isinstance(lifecycle, dict) or set(lifecycle) != CANDIDATE_LIFECYCLE_KEYS:
        raise StateError("candidate lifecycle state has an invalid exact schema")
    if lifecycle["schema_version"] != 2 or lifecycle["orchestration_run_id"] != run_id:
        raise StateError("candidate lifecycle run identity mismatch")
    if lifecycle["plan_execution_attempt_id"] != attempt_id:
        raise StateError("candidate lifecycle attempt identity mismatch")
    for key in ("current_manifest_digest", "current_patch_digest"):
        if not isinstance(lifecycle[key], str) or not re.fullmatch(r"[0-9a-f]{64}", lifecycle[key]):
            raise StateError(f"candidate lifecycle state has an invalid digest: {key}")
    for key in (
        "correction_round", "candidate_generations", "focused_validation_count",
        "authoritative_validation_count", "parent_review_rejections",
    ):
        value = lifecycle[key]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 3:
            raise StateError(f"candidate lifecycle state has an invalid counter: {key}")
    if lifecycle["candidate_generations"] != lifecycle["correction_round"] + 1 or lifecycle[
        "parent_review_rejections"
    ] != lifecycle["correction_round"]:
        raise StateError("candidate lifecycle state has inconsistent correction lineage")
    if not isinstance(lifecycle["focused_required"], bool):
        raise StateError("candidate lifecycle focused_required must be boolean")
    phase = lifecycle["phase"]
    if phase not in {
        "admitted", "focused_passed", "focused_failed", "focused_running",
        "authoritative_passed", "authoritative_failed", "authoritative_running",
        "applying", "applied",
    }:
        raise StateError("candidate lifecycle state has an invalid phase")
    focused_count = lifecycle["focused_validation_count"]
    authoritative_count = lifecycle["authoritative_validation_count"]
    if phase == "admitted" and (focused_count or authoritative_count):
        raise StateError("candidate lifecycle admitted phase has validation events")
    if phase.startswith("focused_") and (focused_count != 1 or authoritative_count != 0):
        raise StateError("candidate lifecycle focused phase has inconsistent counters")
    if phase in {
        "authoritative_running", "authoritative_passed", "authoritative_failed",
        "applying", "applied",
    } and (authoritative_count != 1 or (lifecycle["focused_required"] and focused_count != 1)):
        raise StateError("candidate lifecycle authoritative phase has inconsistent counters")
    manifest_digest = lifecycle["current_manifest_digest"]
    if candidate_digest != f"sha256:{manifest_digest}":
        raise StateError("candidate identifier differs from the lifecycle manifest")
    return lifecycle


def load_candidate_manifest_for_close(
    path: Path,
    state: dict[str, Any],
    attempt_id: str,
    candidate_digest: str,
    lifecycle: dict[str, Any],
) -> dict[str, Any]:
    raw = read_external_artifact(
        path, "candidate manifest", CANDIDATE_MANIFEST_MAX_BYTES
    )
    if digest(raw) != candidate_digest:
        raise StateError("candidate manifest digest mismatch")
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError("candidate manifest is invalid JSON") from exc
    if not isinstance(manifest, dict):
        raise StateError("candidate manifest must be a JSON object")
    expected = {
        "orchestration_run_id": state["run_id"],
        "plan_path": state["plan_path"],
        "plan_digest": state["plan_digest"].removeprefix("sha256:"),
        "source_head": state["source_head"],
        "plan_execution_attempt_id": attempt_id,
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise StateError("candidate manifest differs from the ledger run baseline or attempt")
    patch_digest = manifest.get("patch_digest")
    if not isinstance(patch_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", patch_digest):
        raise StateError("candidate manifest has an invalid patch digest")
    if lifecycle["current_manifest_digest"] != candidate_digest.removeprefix("sha256:"):
        raise StateError("candidate manifest is not the current lifecycle leaf")
    if lifecycle["current_patch_digest"] != patch_digest:
        raise StateError("candidate manifest patch differs from the lifecycle leaf")
    return manifest


def require_accepted_candidate_commit(
    state: dict[str, Any], manifest: dict[str, Any], accepted_source_head: str
) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", accepted_source_head):
        raise StateError("accepted source HEAD must be a full Git object id")
    root = repository_root()
    require_clean_repository(root)
    if current_head(root) != accepted_source_head:
        raise StateError("accepted source HEAD differs from the current clean repository")
    require_predecessor_ancestry(state["source_head"], accepted_source_head)
    commit_line = git_output(
        root, "rev-list", "--parents", "-n", "1", accepted_source_head
    ).decode().strip().split()
    if commit_line != [accepted_source_head, state["source_head"]]:
        raise StateError("accepted source must be exactly one non-merge commit after the ledger baseline")
    patch = git_output(
        root, "diff", "--binary", "--full-index", state["source_head"], accepted_source_head, "--"
    )
    if hashlib.sha256(patch).hexdigest() != manifest["patch_digest"]:
        raise StateError("accepted source commit does not exactly contain the admitted candidate")


def record_attempt_close(args: argparse.Namespace) -> None:
    path = Path(args.state)
    lifecycle_path = Path(args.lifecycle_state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        if state["run_id"] != args.run_id:
            raise StateError("run_id mismatch")
        if state["state"] != "active":
            raise StateError(stopped_message(state))
        require_lifecycle_identity(state, args.run_id, lifecycle_path)
        if not state["open_attempt_id"] or state["open_attempt_id"] != args.attempt_id:
            raise StateError("attempt closure does not match the open writable attempt")
        if args.review_author != "parent":
            raise StateError("review outcome reason must be parent-authored")
        evidence_digest = require_digest(args.review_evidence_digest, "review_evidence_digest")
        reason = args.review_reason_code or ""
        if args.outcome == "accepted":
            if reason:
                raise StateError("accepted attempt closure cannot include a review reason code")
        elif reason not in REVIEW_REASON_CODES:
            raise StateError("unknown review reason code")
        invariants = args.invariant_digest or []
        if len(invariants) != len(set(invariants)):
            raise StateError("invariant digests must be unique")
        for invariant in invariants:
            require_digest(invariant, "invariant_digest")
        if reason == "multiple_invariants_coupled":
            if len(invariants) < 2 or state["primary_invariant_digest"] not in invariants:
                raise StateError(
                    "multiple_invariants_coupled requires the primary and another affected invariant"
                )
        elif invariants != [state["primary_invariant_digest"]]:
            raise StateError("attempt closure must bind the primary invariant")
        candidate_digest = args.candidate_digest or ""
        lifecycle_digest = args.candidate_lifecycle_digest or ""
        lifecycle: dict[str, Any] | None = None
        manifest: dict[str, Any] | None = None
        if candidate_digest:
            require_digest(candidate_digest, "candidate_digest")
            if any(
                event["candidate_digest"] == candidate_digest
                for event in state["events"]
                if event["candidate_digest"]
            ):
                raise StateError("candidate identifier replay is not allowed")
            lifecycle = load_candidate_lifecycle_for_close(
                lifecycle_path, args.run_id, args.attempt_id, lifecycle_digest, candidate_digest
            )
            if args.candidate_manifest:
                manifest = load_candidate_manifest_for_close(
                    Path(args.candidate_manifest), state, args.attempt_id, candidate_digest, lifecycle
                )
        elif lifecycle_digest or args.candidate_manifest:
            raise StateError("candidate lifecycle and manifest require a candidate identifier")
        accepted_source_head = args.accepted_source_head or ""
        if args.outcome == "accepted":
            if lifecycle is None or lifecycle.get("phase") != "applied":
                raise StateError("accepted attempt closure requires an applied candidate lifecycle")
            if manifest is None or not accepted_source_head:
                raise StateError("accepted closure requires candidate and source-commit evidence")
            require_accepted_candidate_commit(state, manifest, accepted_source_head)
        else:
            if accepted_source_head:
                raise StateError("only an accepted closure may record an accepted source HEAD")
            require_repository_baseline(state)
        monotonic_ns = max(time.monotonic_ns(), state["last_monotonic_ns"] + 1)
        event = {
            "sequence": len(state["events"]) + 1,
            "event_id": f"close:{args.attempt_id}",
            "event_type": "attempt_closed",
            "implementation_mode": "candidate",
            "invariant_digests": invariants,
            "finding_severities": [],
            "independent_review_receipt_digest": "",
            "repair_classification": {},
            "repair_evidence_digest": "",
            "candidate_lifecycle_digest": lifecycle_digest,
            "attempt_id": args.attempt_id,
            "attempt_kind": "",
            "candidate_digest": candidate_digest,
            "review_outcome": args.outcome,
            "review_reason_code": reason,
            "review_author": "parent",
            "review_evidence_digest": evidence_digest,
            "predecessor_plan_digest": "",
            "predecessor_accepted_candidate_digest": "",
            "predecessor_closing_event_digest": "",
            "predecessor_accepted_source_head": "",
            "accepted_source_head": accepted_source_head,
            "successor_run_id": "",
            "successor_plan_digest": "",
            "successor_source_head": "",
            "successor_primary_invariant_digest": "",
            "successor_genesis_digest": "",
            "elapsed_seconds": args.elapsed_seconds,
            "monotonic_ns": monotonic_ns,
            "previous_event_digest": state["event_chain_digest"],
        }
        event["event_digest"] = digest(
            json.dumps(event, sort_keys=True, separators=(",", ":"))
        )
        state["events"].append(event)
        state["last_monotonic_ns"] = monotonic_ns
        state["event_chain_digest"] = event["event_digest"]
        for key, value in derive_summary(state["events"]).items():
            state[key] = value
        validate_state(state)
        atomic_write(path, state)


def check_gate(args: argparse.Namespace) -> None:
    state = read_state(Path(args.state))
    if state["run_id"] != args.run_id:
        raise StateError("run_id mismatch")
    repair_plan = args.operation == "repair_plan"
    diagnosis_read = (
        state["state"] == "diagnosis_required" and args.operation == "diagnosis_read"
    )
    repair_plan_allowed = state["state"] == "repair_required" and repair_plan
    if state["state"] != "active" and not diagnosis_read and not repair_plan_allowed:
        raise StateError(stopped_message(state))
    if repair_plan and state["state"] != "repair_required":
        raise StateError("repair-plan gate requires a confirmed independent repair classification")
    if args.plan and state["plan_path"] != args.plan:
        raise StateError("plan path mismatch")
    if args.open_attempt_id and state["open_attempt_id"] != args.open_attempt_id:
        raise StateError("plan execution attempt is no longer the exact open writable attempt")
    require_repository_baseline(state)
    if args.lifecycle_state and state["candidate_lifecycle_identity_digest"] != lifecycle_identity_digest(
        args.run_id, Path(args.lifecycle_state)
    ):
        raise StateError("candidate lifecycle identity mismatch")
    latest_start = max(
        (
            index for index, event in enumerate(state["events"])
            if event["event_type"] == "writable_attempt_started"
        ),
        default=-1,
    )
    recorded_lifecycle_digests = [
        event["candidate_lifecycle_digest"]
        for event in state["events"][latest_start + 1:]
        if event["candidate_lifecycle_digest"]
    ]
    if recorded_lifecycle_digests:
        if not args.lifecycle_state:
            raise StateError("candidate lifecycle is required after a lifecycle-bound event")
        if file_digest(Path(args.lifecycle_state)) != recorded_lifecycle_digests[-1]:
            raise StateError("candidate lifecycle changed after the latest budget event")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("state")
    init.add_argument("--run-id", required=True)
    init.add_argument("--plan", required=True)
    init.add_argument("--plan-digest", required=True)
    init.add_argument("--source-head", required=True)
    init.add_argument("--primary-invariant-digest", required=True)
    init.add_argument("--lifecycle-state", required=True)
    init.add_argument("--predecessor-state")
    init.add_argument("--implementation-mode", choices=sorted(MODES), required=True)
    init.set_defaults(handler=init_state)
    record = sub.add_parser("record")
    record.add_argument("state")
    record.add_argument("--run-id", required=True)
    record.add_argument("--event-id", required=True)
    record.add_argument("--event-type", choices=sorted(RECORD_EVENT_TYPES), required=True)
    record.add_argument("--implementation-mode", choices=sorted(MODES), required=True)
    record.add_argument("--invariant-digest", action="append")
    record.add_argument("--finding-severity", action="append", choices=("High", "Medium", "Low"))
    record.add_argument("--independent-review-receipt-digest")
    record.add_argument("--repair-evidence-file")
    record.add_argument("--validation-report")
    record.add_argument("--diagnosis-evidence-file")
    record.add_argument("--candidate-lifecycle-digest")
    record.add_argument("--lifecycle-state", required=True)
    record.add_argument("--elapsed-seconds", type=float, default=0.0)
    record.set_defaults(handler=record_event)
    start = sub.add_parser("start")
    start.add_argument("state")
    start.add_argument("--run-id", required=True)
    start.add_argument("--plan", required=True)
    start.add_argument("--attempt-id", required=True)
    start.add_argument("--attempt-kind", choices=sorted(ATTEMPT_KINDS), required=True)
    start.add_argument("--predecessor-state")
    start.add_argument("--prior-candidate-digest")
    start.add_argument("--lifecycle-state", required=True)
    start.add_argument("--elapsed-seconds", type=float, default=0.0)
    start.set_defaults(handler=record_writable_attempt_start)
    close = sub.add_parser("close")
    close.add_argument("state")
    close.add_argument("--run-id", required=True)
    close.add_argument("--attempt-id", required=True)
    close.add_argument("--outcome", choices=sorted(REVIEW_OUTCOMES), required=True)
    close.add_argument("--review-author", required=True)
    close.add_argument("--review-reason-code")
    close.add_argument("--review-evidence-digest", required=True)
    close.add_argument("--invariant-digest", action="append", required=True)
    close.add_argument("--candidate-digest")
    close.add_argument("--candidate-manifest")
    close.add_argument("--candidate-lifecycle-digest")
    close.add_argument("--accepted-source-head")
    close.add_argument("--lifecycle-state", required=True)
    close.add_argument("--elapsed-seconds", type=float, default=0.0)
    close.set_defaults(handler=record_attempt_close)
    check = sub.add_parser("check")
    check.add_argument("state")
    check.add_argument("--run-id", required=True)
    check.add_argument("--plan")
    check.add_argument("--lifecycle-state")
    check.add_argument("--open-attempt-id")
    check.add_argument(
        "--operation",
        choices=("execution", "completion", "archive", "repair_plan", "diagnosis_read"),
        default="execution",
    )
    check.set_defaults(handler=check_gate)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        args.handler(args)
    except (OSError, UnicodeError, StateError) as exc:
        print(f"plan execution state failed: {exc}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
