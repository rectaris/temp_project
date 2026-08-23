#!/usr/bin/env python3
"""Maintain a bounded parent-owned execution budget for one active plan."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import re
import secrets
import shlex
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType
from typing import Any


SCHEMA_VERSION = 4
MAX_BYTES = 65_536
CANDIDATE_MANIFEST_MAX_BYTES = 1024 * 1024
MAX_EVENTS = 64
MAX_CORRECTIONS = 2
MAX_PARENT_REMEDIATIONS = 2
MAX_DIAGNOSIS_ATTEMPTS = 3
SESSION_CHECKPOINT_SCHEMA_VERSION = 1
REVIEW_RECEIPT_SCHEMA_VERSION = 1
SESSION_BOUNDARIES = {
    "checked",
    "replanned",
    "repair_required",
    "replan_required",
    "authoritative_failure",
}
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
    "session_checkpoint_emitted",
    "session_checkpoint_claimed",
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
    "review_target_digest",
    "predecessor_plan_digest", "predecessor_accepted_candidate_digest",
    "predecessor_closing_event_digest", "predecessor_accepted_source_head",
    "accepted_source_head", "successor_run_id", "successor_plan_digest",
    "successor_source_head", "successor_primary_invariant_digest", "successor_genesis_digest",
    "elapsed_seconds", "monotonic_ns", "previous_event_digest", "event_digest",
}
PRE_REVIEW_TARGET_EVENT_KEYS = EVENT_KEYS - {"review_target_digest"}
PRE_SUCCESSOR_GENESIS_EVENT_KEYS = EVENT_KEYS - {"successor_genesis_digest"}
LEGACY_EVENT_KEYS = EVENT_KEYS - {"successor_genesis_digest", "review_target_digest"}
DIAGNOSIS_EVENT_KEYS = EVENT_KEYS | {
    "failure_evidence", "failure_evidence_digest", "diagnosis_evidence",
    "diagnosis_evidence_digest",
}
PRE_REVIEW_TARGET_DIAGNOSIS_EVENT_KEYS = DIAGNOSIS_EVENT_KEYS - {"review_target_digest"}
PRE_SUCCESSOR_GENESIS_DIAGNOSIS_EVENT_KEYS = DIAGNOSIS_EVENT_KEYS - {
    "successor_genesis_digest"
}
LEGACY_DIAGNOSIS_EVENT_KEYS = DIAGNOSIS_EVENT_KEYS - {
    "successor_genesis_digest", "review_target_digest"
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
RESOURCE_METRICS = {
    "provider_input_tokens",
    "provider_cached_input_tokens",
    "provider_output_tokens",
    "provider_reasoning_tokens",
    "model_response_count",
    "compaction_count",
    "helper_turn_count",
    "tool_call_count",
}
RESOURCE_EVIDENCE_SOURCES = {
    "external_transcript": "transcript_log",
    "codex_hooks": "hook_event_log",
}
SESSION_CHECKPOINT_KEYS = {
    "schema_version", "plan_path", "plan_digest", "source_head", "run_id",
    "execution_state", "execution_event_chain_digest", "boundary",
    "root_session_identity", "resource_observations", "reviewer_session_digests",
    "checkpoint_digest", "successor_claim",
}
SUCCESSOR_CLAIM_KEYS = {
    "run_id", "plan_digest", "source_head", "primary_invariant_digest", "genesis_digest",
}
REVIEW_RECEIPT_KEYS = {
    "schema_version", "plan_digest", "review_target_digest", "admitted_diff_digest",
    "worker_receipt_digests", "applicable_specification_digests",
    "reviewer_session_digest", "inherited_turns", "inheritance_evidence",
    "inheritance_evidence_digest",
    "review_round", "packet_digest",
}
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


_SANDBOXED_WORKER_MODULE: ModuleType | None = None


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


def load_sandboxed_worker_module() -> ModuleType:
    global _SANDBOXED_WORKER_MODULE
    if _SANDBOXED_WORKER_MODULE is not None:
        return _SANDBOXED_WORKER_MODULE
    path = Path(__file__).with_name("run-sandboxed-plan-worker.py")
    spec = importlib.util.spec_from_file_location("plan_execution_state_worker", path)
    if spec is None or spec.loader is None:
        raise StateError("could not load the sandboxed plan worker verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _SANDBOXED_WORKER_MODULE = module
    return module


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


def canonical_digest(value: Any) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")))


def root_session_identity(value: str | None) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {"status": "not_observed", "digest": None}
    return {"status": "observed", "digest": digest(value)}


def resource_observations_from_manifest(path: Path) -> dict[str, Any]:
    root = repository_root()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise StateError("resource manifest must be inside the current repository") from exc
    if (
        len(relative.parts) != 3
        or relative.parts[0] != ".agent-logs"
        or relative.name != "manifest.json"
    ):
        raise StateError("resource manifest must be .agent-logs/<run-id>/manifest.json")
    checker = Path(__file__).with_name("check-agent-log-manifest.py")
    completed = subprocess.run(
        [sys.executable, os.fspath(checker), os.fspath(resolved)],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=sanitized_git_environment(),
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip()
        raise StateError(detail or "resource manifest validation failed")
    manifest = read_bounded_json(path, "resource manifest", outside_repository=False)
    if not isinstance(manifest, dict):
        raise StateError("resource manifest must be an object")
    observations = validate_resource_observations(manifest.get("resource_observations"))
    validate_resource_identity_evidence(resolved.parent, manifest, observations)
    return observations


def source_session_digests(data: bytes, source: str) -> set[str]:
    session_digests: set[str] = set()
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise StateError(f"resource {source} evidence is not UTF-8") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StateError(
                f"resource {source} evidence line {line_number} is invalid JSON"
            ) from exc
        if not isinstance(record, dict):
            raise StateError(
                f"resource {source} evidence line {line_number} must be an object"
            )
        candidates: list[Any] = []
        if source == "codex_hooks":
            payload = record.get("payload")
            if isinstance(payload, dict):
                candidates.append(payload.get("session_id"))
        else:
            metadata = record.get("metadata")
            if isinstance(metadata, dict):
                candidates.extend(
                    (metadata.get("session_id"), metadata.get("root_session_id"))
                )
        for candidate in candidates:
            if isinstance(candidate, str) and candidate:
                session_digests.add(digest(candidate))
    return session_digests


def read_bound_resource_evidence(
    run_dir: Path,
    declared_path: str,
    source: str,
    expected_digest: str,
) -> bytes:
    relative = Path(declared_path)
    if not declared_path or relative.is_absolute() or ".." in relative.parts:
        raise StateError(f"resource {source} evidence path is not safe")
    path = run_dir / relative
    try:
        path.resolve().relative_to(run_dir.resolve())
    except ValueError as exc:
        raise StateError(f"resource {source} evidence resolves outside the run directory") from exc
    reject_symlink_ancestors(path, include_target=True)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise StateError(f"resource {source} evidence must be a regular file")
        data = os.read(descriptor, CANDIDATE_MANIFEST_MAX_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(data) > CANDIDATE_MANIFEST_MAX_BYTES:
        raise StateError(f"resource {source} evidence exceeds size limit")
    if digest(data) != expected_digest:
        raise StateError(
            f"resource {source} evidence digest changed after manifest validation"
        )
    return data


def validate_resource_identity_evidence(
    run_dir: Path,
    manifest: dict[str, Any],
    observations: dict[str, Any],
) -> None:
    identity = observations["root_session_identity"]
    if identity["status"] != "observed":
        return
    evidence_digests = observations["evidence_digests"]
    derived: set[str] = set()
    for source, manifest_field in RESOURCE_EVIDENCE_SOURCES.items():
        if evidence_digests[source] is None:
            continue
        declared_path = manifest.get(manifest_field)
        if not isinstance(declared_path, str):
            raise StateError(f"resource manifest does not declare {manifest_field}")
        evidence = read_bound_resource_evidence(
            run_dir,
            declared_path,
            source,
            evidence_digests[source],
        )
        derived.update(source_session_digests(evidence, source))
    if not derived:
        raise StateError(
            "observed resource root-session identity is not derived from bound runtime evidence"
        )
    if len(derived) != 1:
        raise StateError("bound runtime evidence contains conflicting root-session identities")
    if identity["digest"] not in derived:
        raise StateError(
            "resource root-session identity does not match bound runtime evidence"
        )


def review_turn_zero_from_manifest(
    path: Path,
    reviewer_session_digest: str,
    packet_digest: str,
    inheritance_evidence_digest: str,
) -> None:
    observations = resource_observations_from_manifest(path)
    identity = observations["root_session_identity"]
    if identity != {"status": "observed", "digest": reviewer_session_digest}:
        raise StateError("reviewer session differs from bound runtime evidence")
    manifest = read_bounded_json(path, "review resource manifest", outside_repository=False)
    run_dir = path.resolve().parent
    matched_source = False
    matched_observation = False
    for source, manifest_field in RESOURCE_EVIDENCE_SOURCES.items():
        source_digest = observations["evidence_digests"][source]
        if source_digest != inheritance_evidence_digest:
            continue
        matched_source = True
        declared_path = manifest.get(manifest_field)
        if not isinstance(declared_path, str):
            raise StateError(f"review resource manifest does not declare {manifest_field}")
        evidence = read_bound_resource_evidence(
            run_dir, declared_path, source, source_digest
        )
        try:
            records = [
                json.loads(line) for line in evidence.decode("utf-8").splitlines()
                if line.strip()
            ]
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StateError("review runtime evidence is invalid JSONL") from exc
        observations_in_source = 0
        for record in records:
            if not isinstance(record, dict):
                continue
            if source == "codex_hooks":
                if record.get("event") != "ReviewPacketStart":
                    continue
                payload = record.get("payload")
            else:
                if record.get("record_type") != "review_packet_start":
                    continue
                payload = record.get("metadata")
            observations_in_source += 1
            if not isinstance(payload, dict):
                continue
            session_id = payload.get("session_id")
            inherited_turns = payload.get("inherited_turns")
            if (
                isinstance(session_id, str)
                and digest(session_id) == reviewer_session_digest
                and payload.get("review_packet_digest") == packet_digest
                and inherited_turns == 0
                and not isinstance(inherited_turns, bool)
            ):
                matched_observation = True
        if observations_in_source != 1:
            raise StateError(
                "review runtime evidence must contain exactly one packet turn observation"
            )
    if not matched_source:
        raise StateError("review inheritance evidence digest is not bound by the runtime manifest")
    if not matched_observation:
        raise StateError(
            "runtime evidence does not observe this review packet at inherited turn zero"
        )


def validate_resource_observations(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "root_session_identity", "evidence_digests", "metrics"
    }:
        raise StateError("resource observations have an invalid exact field shape")
    if value["schema_version"] != 1:
        raise StateError("resource observations have an unsupported schema version")
    evidence_digests = value["evidence_digests"]
    if (
        not isinstance(evidence_digests, dict)
        or set(evidence_digests) != set(RESOURCE_EVIDENCE_SOURCES)
    ):
        raise StateError("resource evidence digests have an invalid exact field shape")
    for source, evidence_digest in evidence_digests.items():
        if evidence_digest is not None:
            require_digest(evidence_digest, f"resource {source} evidence digest")
    has_bound_evidence = any(
        evidence_digest is not None for evidence_digest in evidence_digests.values()
    )
    identity = value["root_session_identity"]
    if not isinstance(identity, dict) or set(identity) != {"status", "digest"}:
        raise StateError("resource root-session identity has an invalid exact field shape")
    if identity["status"] == "observed":
        require_digest(identity["digest"], "resource root-session identity digest")
        if not has_bound_evidence:
            raise StateError(
                "observed resource root-session identity requires bound runtime evidence"
            )
    elif identity != {"status": "not_observed", "digest": None}:
        raise StateError("unavailable resource root-session identity must remain not_observed")
    metrics = value["metrics"]
    if not isinstance(metrics, dict) or set(metrics) != RESOURCE_METRICS:
        raise StateError("resource metrics have an invalid exact field shape")
    for name, observation in metrics.items():
        if not isinstance(observation, dict) or set(observation) != {
            "status", "value", "provenance"
        }:
            raise StateError(f"resource metric {name} has an invalid exact field shape")
        if observation["status"] == "observed":
            metric_value = observation["value"]
            if isinstance(metric_value, bool) or not isinstance(metric_value, int) or metric_value < 0:
                raise StateError(f"resource metric {name} must be a nonnegative integer")
            expected = "provider" if name.startswith("provider_") else "deterministic_proxy"
            if observation["provenance"] != expected:
                raise StateError(f"resource metric {name} has invalid provenance")
            if not has_bound_evidence:
                raise StateError(
                    f"observed resource metric {name} requires bound runtime evidence"
                )
        elif observation != {
            "status": "not_observed",
            "value": None,
            "provenance": "not_observed",
        }:
            raise StateError(f"unavailable resource metric {name} must remain not_observed")
    return value


def validate_review_receipt(value: Any, expected_plan_digest: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REVIEW_RECEIPT_KEYS:
        raise StateError("review receipt has an invalid exact field shape")
    if value["schema_version"] != REVIEW_RECEIPT_SCHEMA_VERSION:
        raise StateError("review receipt has an unsupported schema version")
    for field in (
        "plan_digest", "review_target_digest", "admitted_diff_digest",
        "reviewer_session_digest", "packet_digest",
    ):
        require_digest(value[field], field)
    if expected_plan_digest and value["plan_digest"] != expected_plan_digest:
        raise StateError("review receipt plan digest mismatch")
    if value["review_target_digest"] != value["admitted_diff_digest"]:
        raise StateError("review target must be the admitted diff digest")
    for field in ("worker_receipt_digests", "applicable_specification_digests"):
        entries = value[field]
        if not isinstance(entries, list) or len(entries) > 64 or len(entries) != len(set(entries)):
            raise StateError(f"{field} must be a bounded unique list")
        for entry in entries:
            require_digest(entry, field)
    inherited_turns = value["inherited_turns"]
    inheritance_evidence = value["inheritance_evidence"]
    inheritance_digest = value["inheritance_evidence_digest"]
    if inheritance_evidence == "observed":
        if isinstance(inherited_turns, bool) or not isinstance(inherited_turns, int):
            raise StateError("observed review inherited_turns must be an integer")
        require_digest(inheritance_digest, "inheritance_evidence_digest")
    elif (
        inheritance_evidence != "not_observed"
        or inherited_turns is not None
        or inheritance_digest is not None
    ):
        raise StateError("unavailable review inheritance must remain not_observed")
    if value["review_round"] not in {1, 2}:
        raise StateError("review_round must be one or two")
    packet = {
        key: value[key]
        for key in (
            "plan_digest", "review_target_digest", "admitted_diff_digest",
            "worker_receipt_digests", "applicable_specification_digests",
        )
    }
    if canonical_digest(packet) != value["packet_digest"]:
        raise StateError("review packet digest mismatch")
    return value


def checkpoint_payload_digest(value: dict[str, Any]) -> str:
    return canonical_digest({
        key: item for key, item in value.items()
        if key not in {"checkpoint_digest", "successor_claim"}
    })


def validate_session_checkpoint(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != SESSION_CHECKPOINT_KEYS:
        raise StateError("session checkpoint has an invalid exact field shape")
    if value["schema_version"] != SESSION_CHECKPOINT_SCHEMA_VERSION:
        raise StateError("session checkpoint has an unsupported schema version")
    if not PLAN_RE.fullmatch(value["plan_path"]):
        raise StateError("session checkpoint plan path is invalid")
    for field in ("plan_digest", "execution_event_chain_digest", "checkpoint_digest"):
        require_digest(value[field], field)
    if not re.fullmatch(r"[0-9a-f]{40}", value["source_head"]):
        raise StateError("session checkpoint source HEAD is invalid")
    if not ID_RE.fullmatch(value["run_id"]):
        raise StateError("session checkpoint run id is invalid")
    if value["boundary"] not in SESSION_BOUNDARIES:
        raise StateError("session checkpoint boundary is invalid")
    boundary_states = {
        "checked": {"active", "accepted"},
        "replanned": {"replan_required"},
        "replan_required": {"replan_required"},
        "repair_required": {"repair_required"},
        "authoritative_failure": {"diagnosis_required"},
    }
    if value["execution_state"] not in boundary_states[value["boundary"]]:
        raise StateError("session checkpoint state does not match its boundary")
    identity = value["root_session_identity"]
    if not isinstance(identity, dict) or set(identity) != {"status", "digest"}:
        raise StateError("checkpoint root-session identity has an invalid exact field shape")
    if identity["status"] == "observed":
        require_digest(identity["digest"], "checkpoint root-session identity digest")
    elif identity != {"status": "not_observed", "digest": None}:
        raise StateError("unavailable checkpoint root-session identity must remain not_observed")
    validate_resource_observations(value["resource_observations"])
    reviewers = value["reviewer_session_digests"]
    if not isinstance(reviewers, list) or len(reviewers) > 2 or len(reviewers) != len(set(reviewers)):
        raise StateError("checkpoint reviewer sessions must be a bounded unique list")
    for reviewer in reviewers:
        require_digest(reviewer, "reviewer_session_digest")
    claim = value["successor_claim"]
    if claim is not None:
        if not isinstance(claim, dict) or set(claim) != SUCCESSOR_CLAIM_KEYS:
            raise StateError("checkpoint successor claim has an invalid exact field shape")
        if not ID_RE.fullmatch(claim["run_id"]):
            raise StateError("checkpoint successor run id is invalid")
        for field in ("plan_digest", "primary_invariant_digest", "genesis_digest"):
            require_digest(claim[field], field)
        if not re.fullmatch(r"[0-9a-f]{40}", claim["source_head"]):
            raise StateError("checkpoint successor source HEAD is invalid")
    if checkpoint_payload_digest(value) != value["checkpoint_digest"]:
        raise StateError("session checkpoint digest mismatch")
    return value


def read_session_checkpoint(path: Path) -> dict[str, Any]:
    require_outside_repository(path, "session checkpoint")
    _, data = open_read(path)
    if len(data) > MAX_BYTES:
        raise StateError("session checkpoint exceeds size limit")
    try:
        return validate_session_checkpoint(json.loads(data))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError(f"invalid session checkpoint JSON: {exc}") from exc


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


def read_bounded_json(path: Path, label: str, *, outside_repository: bool) -> Any:
    if outside_repository:
        data = read_external_artifact(path, label)
    else:
        reject_symlink_ancestors(path, include_target=True)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise StateError(f"{label} must be a regular file")
            data = os.read(descriptor, MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise StateError(f"{label} exceeds size limit")
        finally:
            os.close(descriptor)
    try:
        return json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError(f"{label} is invalid JSON") from exc


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
    bounded_review_counts: dict[str, int] = {}
    candidate_attempt_reviews: dict[str, tuple[str, str, str]] = {}
    validated_events: list[dict[str, Any]] = []
    previous_ns = 0
    require_digest(value["genesis_digest"], "genesis_digest")
    if value["genesis_digest"] != state_genesis_digest(value):
        raise StateError("execution-state genesis identity digest mismatch")
    previous_digest = value["genesis_digest"]
    for index, event in enumerate(events, start=1):
        allowed_event_keys = {
            frozenset(EVENT_KEYS), frozenset(PRE_REVIEW_TARGET_EVENT_KEYS),
            frozenset(PRE_SUCCESSOR_GENESIS_EVENT_KEYS), frozenset(LEGACY_EVENT_KEYS),
            frozenset(DIAGNOSIS_EVENT_KEYS),
            frozenset(PRE_REVIEW_TARGET_DIAGNOSIS_EVENT_KEYS),
            frozenset(PRE_SUCCESSOR_GENESIS_DIAGNOSIS_EVENT_KEYS),
            frozenset(LEGACY_DIAGNOSIS_EVENT_KEYS),
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
            )
            checkpoint_event_allowed = (
                event["event_type"] == "session_checkpoint_emitted"
                and not any(
                    prior["event_type"] == "session_checkpoint_emitted"
                    for prior in validated_events
                )
            ) or (
                event["event_type"] == "session_checkpoint_claimed"
                and any(
                    prior["event_type"] == "session_checkpoint_emitted"
                    for prior in validated_events
                )
                and not any(
                    prior["event_type"] == "session_checkpoint_claimed"
                    for prior in validated_events
                )
            )
            diagnosis_is_allowed = (
                prior_summary["state"] == "diagnosis_required"
                and event["event_type"] in {"failure_diagnosis", "repair_classification"}
            )
            if not successor_is_allowed and not diagnosis_is_allowed and not checkpoint_event_allowed:
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
            event["event_type"] == "parent_review"
            and (
                event["implementation_mode"] == "parent_direct"
                or bool(event.get("review_target_digest", ""))
            )
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
        review_target_digest = event.get("review_target_digest", "")
        require_digest(review_target_digest, "review_target_digest", allow_empty=True)
        if event["event_type"] not in {
            "parent_review", "attempt_closed",
            "session_checkpoint_emitted", "session_checkpoint_claimed"
        } and review_target_digest:
            raise StateError("only a parent review may bind a review target")
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
        if event["event_type"] == "parent_review" and review_target_digest:
            if (
                not review_target_digest
                or not event["candidate_lifecycle_digest"]
                or event["review_outcome"]
                or event["review_reason_code"]
                or event["review_author"]
                or event["review_evidence_digest"]
                or event_accepted_source
                or any(event_predecessors)
                or event_predecessor_source
                or successor_run_id
                or event["successor_plan_digest"]
                or successor_source
                or event["successor_primary_invariant_digest"]
                or successor_genesis_digest
            ):
                raise StateError("parent review has invalid candidate identity data")
            if event["implementation_mode"] == "candidate":
                if not attempt_id or not event["candidate_digest"]:
                    raise StateError("candidate review lacks admitted candidate identity")
                candidate_identity = (
                    event["candidate_lifecycle_digest"],
                    event["candidate_digest"],
                    review_target_digest,
                )
                prior_identity = candidate_attempt_reviews.setdefault(
                    attempt_id, candidate_identity
                )
                if prior_identity != candidate_identity:
                    raise StateError(
                        "writable attempt reviews bind different admitted candidates"
                    )
            elif attempt_id or event["candidate_digest"]:
                raise StateError("parent-direct review cannot claim a writable candidate")
            identity = event["candidate_lifecycle_digest"]
            bounded_review_counts[identity] = bounded_review_counts.get(identity, 0) + 1
            if bounded_review_counts[identity] > 2:
                raise StateError(
                    "review budget permits one initial review and one bounded rereview"
                )
        elif event["event_type"] == "writable_attempt_started":
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
                        or not event_accepted_source or not review_target_digest):
                    raise StateError("accepted attempt closure has invalid candidate or reason data")
                accepted_identity = review_candidate_identity_digest(
                    attempt_id, event["candidate_digest"], review_target_digest
                )
                matching_reviews = [
                    prior for prior in validated_events
                    if prior["event_type"] == "parent_review"
                    and prior["candidate_lifecycle_digest"] == accepted_identity
                    and prior["attempt_id"] == attempt_id
                    and prior["candidate_digest"] == event["candidate_digest"]
                    and prior.get("review_target_digest", "") == review_target_digest
                ]
                if not matching_reviews:
                    raise StateError("accepted candidate identity lacks a bounded review")
                if set(matching_reviews[-1]["finding_severities"]) & {"High", "Medium"}:
                    raise StateError("accepted candidate review has unresolved findings")
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
        elif event["event_type"] in {
            "session_checkpoint_emitted", "session_checkpoint_claimed"
        }:
            if not event["candidate_digest"] or not review_target_digest:
                raise StateError("session checkpoint event lacks checkpoint identity")
            if any((
                attempt_id, event["attempt_kind"], event["review_outcome"],
                event["review_reason_code"], event["review_author"],
                event["review_evidence_digest"], *event_predecessors,
                event_predecessor_source, event_accepted_source,
            )):
                raise StateError("session checkpoint event contains unrelated attempt data")
            successor_values = (
                successor_run_id, event["successor_plan_digest"], successor_source,
                event["successor_primary_invariant_digest"], successor_genesis_digest,
            )
            if event["event_type"] == "session_checkpoint_emitted" and any(successor_values):
                raise StateError("checkpoint issuance cannot contain successor identity")
            if event["event_type"] == "session_checkpoint_claimed" and not all(successor_values):
                raise StateError("checkpoint claim has incomplete successor identity")
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


def read_predecessor_acceptance(path: Path) -> tuple[dict[str, str], bool]:
    require_outside_repository(path, "predecessor execution state")
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
        predecessor = read_state(path)
    checkpoint_emitted = any(
        event["event_type"] == "session_checkpoint_emitted"
        for event in predecessor["events"]
    )
    return predecessor_acceptance_from_state(predecessor), checkpoint_emitted


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
        emitted_checkpoints = [
            event for event in predecessor["events"]
            if event["event_type"] == "session_checkpoint_emitted"
        ]
        if emitted_checkpoints:
            matching_claims = [
                event for event in predecessor["events"]
                if event["event_type"] == "session_checkpoint_claimed"
                and all(
                    event[field] == value
                    for field, value in identity.items()
                )
            ]
            if len(matching_claims) != 1:
                raise StateError(
                    "issued session checkpoint is not claimed by this successor"
                )
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
            "review_target_digest": "",
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
    predecessor_checkpoint_emitted = False
    if args.predecessor_state:
        try:
            predecessor, predecessor_checkpoint_emitted = read_predecessor_acceptance(
                Path(args.predecessor_state)
            )
        except StateError:
            if not args.predecessor_checkpoint:
                raise
        if predecessor["predecessor_accepted_source_head"]:
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
    if bool(args.predecessor_checkpoint) != bool(args.root_session_manifest):
        raise StateError(
            "predecessor checkpoint and root session manifest must be supplied together"
        )
    if predecessor_checkpoint_emitted and not args.predecessor_checkpoint:
        raise StateError(
            "issued predecessor session checkpoint requires checkpoint and root-session evidence"
        )
    if args.predecessor_checkpoint:
        if not args.predecessor_state:
            raise StateError("predecessor checkpoint requires predecessor execution state")
        successor_resources = resource_observations_from_manifest(
            Path(args.root_session_manifest)
        )
        claim_session_checkpoint(
            Path(args.predecessor_checkpoint),
            Path(args.predecessor_state),
            state,
            successor_resources["root_session_identity"],
        )
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if path.exists() or path.is_symlink():
            raise StateError("execution state already exists")
        atomic_write(path, state)


def checkpoint_boundary_matches(state: dict[str, Any], boundary: str) -> bool:
    if boundary == "checked":
        return (
            state["implementation_mode"] == "parent_direct"
            and state["state"] == "active"
            and state["authoritative_validation_events"] == 1
        ) or state["state"] == "accepted"
    if boundary in {"replanned", "replan_required"}:
        return state["state"] == "replan_required"
    if boundary == "repair_required":
        return state["state"] == "repair_required"
    return state["state"] == "diagnosis_required"


def append_checkpoint_event(
    state: dict[str, Any],
    *,
    event_type: str,
    checkpoint: dict[str, Any],
    successor: dict[str, str] | None = None,
) -> None:
    successor = successor or {
        "run_id": "",
        "plan_digest": "",
        "source_head": "",
        "primary_invariant_digest": "",
        "genesis_digest": "",
    }
    monotonic_ns = max(time.monotonic_ns(), state["last_monotonic_ns"] + 1)
    event = {
        "sequence": len(state["events"]) + 1,
        "event_id": (
            f"checkpoint:{checkpoint['checkpoint_digest'][7:23]}"
            if event_type == "session_checkpoint_emitted"
            else f"checkpoint-claim:{successor['run_id']}"
        ),
        "event_type": event_type,
        "implementation_mode": state["implementation_mode"],
        "invariant_digests": [],
        "finding_severities": [],
        "independent_review_receipt_digest": "",
        "repair_classification": {},
        "repair_evidence_digest": "",
        "candidate_lifecycle_digest": "",
        "attempt_id": "",
        "attempt_kind": "",
        "candidate_digest": checkpoint["checkpoint_digest"],
        "review_outcome": "",
        "review_reason_code": "",
        "review_author": "",
        "review_evidence_digest": "",
        "review_target_digest": checkpoint["checkpoint_digest"],
        "predecessor_plan_digest": "",
        "predecessor_accepted_candidate_digest": "",
        "predecessor_closing_event_digest": "",
        "predecessor_accepted_source_head": "",
        "accepted_source_head": "",
        "successor_run_id": successor["run_id"],
        "successor_plan_digest": successor["plan_digest"],
        "successor_source_head": successor["source_head"],
        "successor_primary_invariant_digest": successor["primary_invariant_digest"],
        "successor_genesis_digest": successor["genesis_digest"],
        "elapsed_seconds": 0.0,
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


def create_session_checkpoint(args: argparse.Namespace) -> None:
    state_path = Path(args.state)
    state = read_state(state_path)
    if state["run_id"] != args.run_id:
        raise StateError("run_id mismatch")
    if any(
        event["event_type"] == "session_checkpoint_emitted"
        for event in state["events"]
    ):
        raise StateError("execution boundary already emitted a session checkpoint")
    checkpoint_source_head = state["source_head"]
    if args.boundary == "checked":
        root = repository_root()
        plan = root / state["plan_path"]
        if digest(plan.read_bytes()) != state["plan_digest"]:
            raise StateError("execution plan differs from the checkpoint baseline")
        require_clean_repository(root)
        checkpoint_source_head = current_head(root)
        if state["implementation_mode"] == "parent_direct":
            require_predecessor_ancestry(state["source_head"], checkpoint_source_head)
        elif checkpoint_source_head != state["accepted_source_head"]:
            raise StateError("accepted candidate source HEAD differs from the checkpoint source")
    else:
        require_repository_baseline(state)
    if not checkpoint_boundary_matches(state, args.boundary):
        raise StateError("execution state does not match the requested checkpoint boundary")
    if not args.resource_manifest:
        raise StateError("session checkpoint requires one resource manifest")
    resources = resource_observations_from_manifest(Path(args.resource_manifest))
    checkpoint_identity = resources["root_session_identity"]
    review_events = [
        event for event in state["events"]
        if event["event_type"] == "parent_review"
    ]
    accepted_identity = ""
    required_review_target = ""
    final_patch = b""
    if args.boundary == "checked" and state["implementation_mode"] == "candidate":
        accepted = next(
            event for event in reversed(state["events"])
            if event["event_type"] == "attempt_closed"
            and event["review_outcome"] == "accepted"
        )
        required_review_target = accepted["review_target_digest"]
        accepted_identity = review_candidate_identity_digest(
            accepted["attempt_id"],
            accepted["candidate_digest"],
            required_review_target,
        )
    elif args.boundary == "checked" and state["implementation_mode"] == "parent_direct":
        final_patch = require_commit_within_write_scope(
            root,
            state["source_head"],
            checkpoint_source_head,
            plan_write_scope(state),
        )
        required_review_target = digest(final_patch)
    reviewer_sessions: list[str] = []
    review_receipt_digests: list[str] = []
    checkpoint_review_target = ""
    for receipt_path in args.review_receipt or []:
        receipt_file = Path(receipt_path)
        receipt = validate_review_receipt(
            read_bounded_json(
                receipt_file,
                "review receipt",
                outside_repository=True,
            ),
            state["plan_digest"],
        )
        if checkpoint_review_target and receipt["review_target_digest"] != checkpoint_review_target:
            raise StateError("checkpoint review receipts must describe one accepted candidate")
        if required_review_target and receipt["review_target_digest"] != required_review_target:
            raise StateError("checkpoint review receipt differs from the checked target")
        checkpoint_review_target = receipt["review_target_digest"]
        reviewer_sessions.append(receipt["reviewer_session_digest"])
        review_receipt_digests.append(file_digest(receipt_file))
    if len(reviewer_sessions) != len(set(reviewer_sessions)):
        raise StateError("reviewer session replay is not allowed")
    if args.boundary == "checked" and not reviewer_sessions:
        raise StateError("checked checkpoint requires at least one bounded review receipt")
    recorded_review_receipts = [
        event["independent_review_receipt_digest"]
        for event in state["events"]
        if event["event_type"] == "parent_review"
        and event["independent_review_receipt_digest"]
        and (
            event["candidate_lifecycle_digest"] == accepted_identity
            if accepted_identity
            else event.get("review_target_digest", "") == checkpoint_review_target
        )
    ]
    if review_receipt_digests != recorded_review_receipts:
        raise StateError("checkpoint review receipts differ from the execution review history")
    if args.boundary == "checked" and state["implementation_mode"] == "parent_direct":
        if not review_events or digest(final_patch) != review_events[-1]["review_target_digest"]:
            raise StateError("checked parent-direct diff differs from the reviewed target")
        if set(review_events[-1]["finding_severities"]) & {"High", "Medium"}:
            raise StateError("checked parent-direct review has unresolved findings")
    if args.boundary == "checked" and state["implementation_mode"] == "candidate":
        if not any(
            event["candidate_lifecycle_digest"] == accepted_identity
            for event in review_events
        ):
            raise StateError("accepted candidate identity lacks a bounded review")
    checkpoint = {
        "schema_version": SESSION_CHECKPOINT_SCHEMA_VERSION,
        "plan_path": state["plan_path"],
        "plan_digest": state["plan_digest"],
        "source_head": checkpoint_source_head,
        "run_id": state["run_id"],
        "execution_state": state["state"],
        "execution_event_chain_digest": state["event_chain_digest"],
        "boundary": args.boundary,
        "root_session_identity": checkpoint_identity,
        "resource_observations": resources,
        "reviewer_session_digests": reviewer_sessions,
        "checkpoint_digest": "",
        "successor_claim": None,
    }
    checkpoint["checkpoint_digest"] = checkpoint_payload_digest(checkpoint)
    validate_session_checkpoint(checkpoint)
    output = Path(args.output)
    require_outside_repository(output, "session checkpoint")
    if output.exists() or output.is_symlink():
        raise StateError("session checkpoint output already exists")
    atomic_write(output, checkpoint)
    with with_lock(state_path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        current = read_state(state_path)
        if current["event_chain_digest"] != checkpoint["execution_event_chain_digest"]:
            raise StateError("execution ledger changed while issuing the session checkpoint")
        if any(
            event["event_type"] == "successor_claimed"
            for event in current["events"]
        ):
            raise StateError("execution boundary is already claimed by a successor")
        if any(
            event["event_type"] == "session_checkpoint_emitted"
            for event in current["events"]
        ):
            raise StateError("execution boundary already emitted a session checkpoint")
        append_checkpoint_event(
            current,
            event_type="session_checkpoint_emitted",
            checkpoint=checkpoint,
        )
        atomic_write(state_path, current)


def verify_session_checkpoint(args: argparse.Namespace) -> None:
    checkpoint = read_session_checkpoint(Path(args.checkpoint))
    state = read_state(Path(args.state))
    issued = [
        event for event in state["events"]
        if event["event_type"] == "session_checkpoint_emitted"
        and event["candidate_digest"] == checkpoint["checkpoint_digest"]
        and event["previous_event_digest"] == checkpoint["execution_event_chain_digest"]
    ]
    if len(issued) != 1:
        raise StateError("session checkpoint is not issued by the execution ledger")


def claim_session_checkpoint(
    path: Path,
    predecessor_state_path: Path,
    successor: dict[str, Any],
    successor_root_session: dict[str, Any],
) -> None:
    if successor_root_session["status"] != "observed":
        raise StateError("successor root-session identity is not observed")
    with with_lock(predecessor_state_path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        predecessor_state = read_state(predecessor_state_path)
        checkpoint = read_session_checkpoint(path)
        if (
            checkpoint["plan_digest"] != predecessor_state["plan_digest"]
            or checkpoint["plan_path"] != predecessor_state["plan_path"]
        ):
            raise StateError("session checkpoint differs from the predecessor execution ledger")
        predecessor_identity = checkpoint["root_session_identity"]
        if predecessor_identity["status"] != "observed":
            raise StateError("predecessor root-session identity is not observed")
        if predecessor_identity["digest"] == successor_root_session["digest"]:
            raise StateError("successor plan cannot start in the checkpointed root session")
        if checkpoint["plan_path"] == successor["plan_path"]:
            raise StateError("session checkpoint must cross a numbered-plan boundary")
        require_predecessor_ancestry(checkpoint["source_head"], successor["source_head"])
        claim = {
            "run_id": successor["run_id"],
            "plan_digest": successor["plan_digest"],
            "source_head": successor["source_head"],
            "primary_invariant_digest": successor["primary_invariant_digest"],
            "genesis_digest": successor["genesis_digest"],
        }
        checkpoint_claims = [
            event for event in predecessor_state["events"]
            if event["event_type"] == "session_checkpoint_claimed"
            and event["candidate_digest"] == checkpoint["checkpoint_digest"]
        ]
        if checkpoint_claims:
            prior = checkpoint_claims[0]
            prior_claim = {
                "run_id": prior["successor_run_id"],
                "plan_digest": prior["successor_plan_digest"],
                "source_head": prior["successor_source_head"],
                "primary_invariant_digest": prior["successor_primary_invariant_digest"],
                "genesis_digest": prior["successor_genesis_digest"],
            }
            if prior_claim != claim:
                raise StateError("session checkpoint is already claimed by another successor")
            return
        emitted = [
            event for event in predecessor_state["events"]
            if event["event_type"] == "session_checkpoint_emitted"
            and event["candidate_digest"] == checkpoint["checkpoint_digest"]
            and event["previous_event_digest"] == checkpoint["execution_event_chain_digest"]
        ]
        if len(emitted) != 1:
            raise StateError("session checkpoint lacks one ledger issuance event")
        append_checkpoint_event(
            predecessor_state,
            event_type="session_checkpoint_claimed",
            checkpoint=checkpoint,
            successor=claim,
        )
        atomic_write(predecessor_state_path, predecessor_state)


def plan_list_field(state: dict[str, Any], field: str) -> list[str]:
    plan = repository_root() / state["plan_path"]
    lines = plan.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index(f"{field}:") + 1
    except ValueError as exc:
        raise StateError(f"execution plan lacks {field}") from exc
    paths: list[str] = []
    for line in lines[start:]:
        if line.startswith("  - "):
            paths.append(line[4:])
            continue
        if line and not line.startswith(" "):
            break
        if line.strip():
            raise StateError(f"execution plan {field} has invalid structure")
    if not paths or len(paths) != len(set(paths)):
        raise StateError(f"execution plan {field} must be a nonempty unique list")
    return paths


def plan_write_scope(state: dict[str, Any]) -> list[str]:
    return plan_list_field(state, "write_scope")


def applicable_specification_digests(state: dict[str, Any]) -> list[str]:
    root = repository_root()
    return [file_digest(root / path) for path in plan_list_field(state, "required_specs")]


def path_is_in_write_scope(path: str, write_scope: list[str]) -> bool:
    return any(
        path == allowed.rstrip("/") or path.startswith(allowed.rstrip("/") + "/")
        for allowed in write_scope
    )


def require_commit_within_write_scope(
    root: Path, baseline: str, checked_head: str, write_scope: list[str]
) -> bytes:
    changed = git_output(
        root, "diff", "--name-only", "-z", baseline, checked_head, "--"
    ).decode("utf-8").split("\0")
    outside = [
        path for path in changed if path and not path_is_in_write_scope(path, write_scope)
    ]
    if outside:
        raise StateError(
            "checked parent-direct commit changes paths outside write_scope: "
            + ", ".join(outside)
        )
    return git_output(
        root, "diff", "--binary", "--full-index", baseline, checked_head, "--"
    )


def review_candidate_identity_digest(
    attempt_id: str, candidate_manifest_digest: str, admitted_diff_digest: str
) -> str:
    if not ID_RE.fullmatch(attempt_id):
        raise StateError("review candidate attempt identifier is invalid")
    require_digest(candidate_manifest_digest, "review candidate manifest digest")
    require_digest(admitted_diff_digest, "review admitted diff digest")
    return canonical_digest({
        "attempt_id": attempt_id,
        "candidate_manifest_digest": candidate_manifest_digest,
        "admitted_diff_digest": admitted_diff_digest,
    })


def parent_direct_review_identity(
    state: dict[str, Any],
) -> tuple[str, str]:
    root = repository_root()
    require_repository_baseline(state)
    patch = git_output(
        root,
        "diff",
        "--binary",
        "--full-index",
        state["source_head"],
        "--",
        *plan_write_scope(state),
    )
    if not patch:
        raise StateError("parent-direct review requires an admitted write-scope diff")
    target = digest(patch)
    identity = canonical_digest({
        "implementation_mode": "parent_direct",
        "source_head": state["source_head"],
        "admitted_diff_digest": target,
    })
    return target, identity


def candidate_review_identity(
    state: dict[str, Any], lifecycle_path: Path, manifest_path: Path
) -> tuple[str, str, str, str, list[str]]:
    attempt_id = state["open_attempt_id"]
    if not attempt_id:
        raise StateError("candidate review requires one open writable attempt")
    raw = read_external_artifact(lifecycle_path, "candidate lifecycle state")
    lifecycle_digest = digest(raw)
    try:
        candidate_digest = f"sha256:{json.loads(raw)['current_manifest_digest']}"
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError("candidate lifecycle state is invalid JSON") from exc
    lifecycle = load_candidate_lifecycle_for_close(
        lifecycle_path,
        state["run_id"],
        attempt_id,
        lifecycle_digest,
        candidate_digest,
    )
    if lifecycle["phase"] != "admitted":
        raise StateError("candidate review requires the admitted lifecycle phase")
    worker = load_sandboxed_worker_module()
    try:
        verified = worker.verify_candidate_manifest(
            repo_root=repository_root(),
            git_bin="git",
            planlib=worker.load_planlib(),
            manifest_path=manifest_path,
            expected_plan=state["plan_path"],
            require_applicable=True,
            require_clean=True,
        )
    except worker.RunnerError as exc:
        raise StateError(f"candidate manifest failed admission verification: {exc}") from exc
    if verified["manifest_digest"] != candidate_digest.removeprefix("sha256:"):
        raise StateError("verified candidate manifest differs from the lifecycle leaf")
    manifest = verified["manifest"]
    if manifest.get("plan_execution_attempt_id") != attempt_id:
        raise StateError("verified candidate manifest attempt differs from the open attempt")
    if lifecycle["current_patch_digest"] != verified["patch_digest"]:
        raise StateError("verified candidate patch differs from the lifecycle leaf")
    target = f"sha256:{verified['patch_digest']}"
    identity = review_candidate_identity_digest(
        attempt_id,
        candidate_digest,
        target,
    )
    return (
        target,
        identity,
        attempt_id,
        candidate_digest,
        [f"sha256:{verified['worker_completion_receipt_digest']}"],
    )


def record_bounded_review(args: argparse.Namespace) -> None:
    if args.implementation_mode == "candidate":
        if not args.candidate_manifest:
            raise StateError("candidate review requires the admitted candidate manifest")
    elif args.candidate_manifest:
        raise StateError("parent-direct review cannot use a candidate manifest")
    record_event(argparse.Namespace(
        state=args.state,
        run_id=args.run_id,
        event_id=args.event_id,
        event_type="parent_review",
        implementation_mode=args.implementation_mode,
        invariant_digest=args.invariant_digest,
        finding_severity=args.finding_severity,
        independent_review_receipt_digest="",
        repair_evidence_file=None,
        validation_report=None,
        diagnosis_evidence_file=None,
        candidate_lifecycle_digest="",
        review_target_digest="",
        review_attempt_id="",
        review_candidate_digest="",
        bounded_review=True,
        review_receipt=args.review_receipt,
        review_resource_manifest=args.review_resource_manifest,
        candidate_manifest=args.candidate_manifest,
        predecessor_checkpoint=args.predecessor_checkpoint,
        lifecycle_state=args.lifecycle_state,
        elapsed_seconds=args.elapsed_seconds,
    ))


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
        if getattr(args, "bounded_review", False):
            receipt_path = Path(args.review_receipt)
            review_receipt = validate_review_receipt(
                read_bounded_json(
                    receipt_path,
                    "review receipt",
                    outside_repository=True,
                ),
                state["plan_digest"],
            )
            if (
                review_receipt["inheritance_evidence"] != "observed"
                or review_receipt["inherited_turns"] != 0
            ):
                raise StateError("staged review requires observed zero inherited turns")
            review_turn_zero_from_manifest(
                Path(args.review_resource_manifest),
                review_receipt["reviewer_session_digest"],
                review_receipt["packet_digest"],
                review_receipt["inheritance_evidence_digest"],
            )
            if args.implementation_mode == "candidate":
                (
                    review_target,
                    review_identity,
                    review_attempt_id,
                    review_candidate_digest,
                    expected_worker_receipts,
                ) = candidate_review_identity(
                    state,
                    Path(args.lifecycle_state),
                    Path(args.candidate_manifest),
                )
                attempt_reviews = [
                    event for event in state["events"]
                    if event["event_type"] == "parent_review"
                    and event["attempt_id"] == review_attempt_id
                    and event["review_target_digest"]
                ]
                if any(
                    event["candidate_lifecycle_digest"] != review_identity
                    or event["candidate_digest"] != review_candidate_digest
                    or event["review_target_digest"] != review_target
                    for event in attempt_reviews
                ):
                    raise StateError(
                        "writable attempt is already bound to another admitted candidate"
                    )
            else:
                review_target, review_identity = parent_direct_review_identity(state)
                review_attempt_id = ""
                review_candidate_digest = ""
                expected_worker_receipts = []
            if (
                review_receipt["review_target_digest"] != review_target
                or review_receipt["admitted_diff_digest"] != review_target
            ):
                raise StateError("review receipt target differs from the admitted candidate diff")
            if review_receipt["worker_receipt_digests"] != expected_worker_receipts:
                raise StateError("review receipt does not bind the verified worker receipt")
            if (
                review_receipt["applicable_specification_digests"]
                != applicable_specification_digests(state)
            ):
                raise StateError(
                    "review receipt does not bind the applicable specifications"
                )
            prior_reviews = [
                event for event in state["events"]
                if event["event_type"] == "parent_review"
                and event["independent_review_receipt_digest"]
                and event["candidate_lifecycle_digest"] == review_identity
            ]
            if (
                review_receipt["review_round"] != len(prior_reviews) + 1
                or len(prior_reviews) >= 2
            ):
                raise StateError(
                    "review budget permits one initial review and one bounded rereview"
                )
            has_predecessor = bool(state["predecessor_plan_digest"])
            if has_predecessor and not args.predecessor_checkpoint:
                raise StateError(
                    "dependent plan review requires the predecessor session checkpoint"
                )
            if args.predecessor_checkpoint:
                checkpoint = read_session_checkpoint(Path(args.predecessor_checkpoint))
                if checkpoint["plan_digest"] != state["predecessor_plan_digest"]:
                    raise StateError(
                        "review predecessor checkpoint differs from the execution ledger"
                    )
                if (
                    review_receipt["reviewer_session_digest"]
                    in checkpoint["reviewer_session_digests"]
                ):
                    raise StateError(
                        "reviewer session cannot be reused across numbered plans"
                    )
            args.independent_review_receipt_digest = file_digest(receipt_path)
            args.candidate_lifecycle_digest = review_identity
            args.review_target_digest = review_target
            args.review_attempt_id = review_attempt_id
            args.review_candidate_digest = review_candidate_digest
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
        if args.event_type == "parent_review" and (
            args.implementation_mode == "parent_direct" or receipt
        ):
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
            "attempt_id": getattr(args, "review_attempt_id", ""),
            "attempt_kind": "",
            "candidate_digest": getattr(args, "review_candidate_digest", ""),
            "review_outcome": "",
            "review_reason_code": "",
            "review_author": "",
            "review_evidence_digest": "",
            "review_target_digest": getattr(args, "review_target_digest", ""),
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
            if bool(args.predecessor_checkpoint) != bool(args.root_session_manifest):
                raise StateError(
                    "predecessor checkpoint and root session manifest must be supplied together"
                )
            predecessor_path = Path(args.predecessor_state)
            if predecessor_path.absolute() == path.absolute():
                raise StateError("predecessor execution state cannot be the current ledger")
            require_predecessor_ancestry(
                predecessor["predecessor_accepted_source_head"], state["source_head"]
            )
            claim_predecessor_for_successor(
                predecessor_path, predecessor, state, args.elapsed_seconds
            )
            if args.predecessor_checkpoint:
                successor_resources = resource_observations_from_manifest(
                    Path(args.root_session_manifest)
                )
                claim_session_checkpoint(
                    Path(args.predecessor_checkpoint),
                    predecessor_path,
                    state,
                    successor_resources["root_session_identity"],
                )
        elif (
            args.attempt_kind == "initial"
            and args.predecessor_state
            and args.predecessor_checkpoint
            and args.root_session_manifest
        ):
            successor_resources = resource_observations_from_manifest(
                Path(args.root_session_manifest)
            )
            claim_session_checkpoint(
                Path(args.predecessor_checkpoint),
                Path(args.predecessor_state),
                state,
                successor_resources["root_session_identity"],
            )
        elif (
            args.predecessor_state
            or args.predecessor_checkpoint
            or args.root_session_manifest
        ):
            raise StateError(
                "predecessor execution state, checkpoint, and root session manifest "
                "are valid only for an initial dependent start"
            )
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
            "review_target_digest": "",
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
                event["event_type"] == "attempt_closed"
                and event["candidate_digest"] == candidate_digest
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
            accepted_target = f"sha256:{manifest['patch_digest']}"
            accepted_identity = review_candidate_identity_digest(
                args.attempt_id, candidate_digest, accepted_target
            )
            matching_reviews = [
                event for event in state["events"]
                if event["event_type"] == "parent_review"
                and event["candidate_lifecycle_digest"] == accepted_identity
                and event["attempt_id"] == args.attempt_id
                and event["candidate_digest"] == candidate_digest
                and event["review_target_digest"] == accepted_target
            ]
            if not matching_reviews:
                raise StateError("accepted candidate identity lacks a bounded review")
            if set(matching_reviews[-1]["finding_severities"]) & {"High", "Medium"}:
                raise StateError("accepted candidate review has unresolved findings")
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
            "review_target_digest": (
                f"sha256:{manifest['patch_digest']}" if manifest is not None else ""
            ),
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
    init.add_argument("--predecessor-checkpoint")
    init.add_argument("--root-session-manifest")
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
    start.add_argument("--predecessor-checkpoint")
    start.add_argument("--root-session-manifest")
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
    checkpoint = sub.add_parser("checkpoint")
    checkpoint.add_argument("state")
    checkpoint.add_argument("--run-id", required=True)
    checkpoint.add_argument("--output", required=True)
    checkpoint.add_argument("--boundary", choices=sorted(SESSION_BOUNDARIES), required=True)
    checkpoint.add_argument("--resource-manifest", required=True)
    checkpoint.add_argument("--review-receipt", action="append")
    checkpoint.set_defaults(handler=create_session_checkpoint)
    verify_checkpoint = sub.add_parser("verify-checkpoint")
    verify_checkpoint.add_argument("checkpoint")
    verify_checkpoint.add_argument("--state", required=True)
    verify_checkpoint.set_defaults(handler=verify_session_checkpoint)
    review = sub.add_parser("review")
    review.add_argument("state")
    review.add_argument("--run-id", required=True)
    review.add_argument("--event-id", required=True)
    review.add_argument("--implementation-mode", choices=sorted(MODES), required=True)
    review.add_argument("--review-receipt", required=True)
    review.add_argument("--review-resource-manifest", required=True)
    review.add_argument("--candidate-manifest")
    review.add_argument("--predecessor-checkpoint")
    review.add_argument("--invariant-digest", action="append", required=True)
    review.add_argument("--finding-severity", action="append", choices=("High", "Medium", "Low"))
    review.add_argument("--lifecycle-state", required=True)
    review.add_argument("--elapsed-seconds", type=float, default=0.0)
    review.set_defaults(handler=record_bounded_review)
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
