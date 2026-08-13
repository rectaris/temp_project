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
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
MAX_BYTES = 65_536
MAX_EVENTS = 64
MAX_CORRECTIONS = 2
MAX_PARENT_REMEDIATIONS = 2
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
MODES = {"candidate", "parent_direct"}
EVENT_TYPES = {
    "candidate_generation",
    "correction_rejected",
    "parent_review",
    "focused_validation",
    "authoritative_validation",
    "scope_drift",
    "spec_drift",
    "security_boundary_drift",
    "post_authoritative_design_change",
    "elapsed_checkpoint",
}
EXACT_KEYS = {
    "schema_version", "run_id", "plan_path", "plan_digest", "source_head",
    "primary_invariant_digest", "candidate_lifecycle_identity_digest", "state",
    "implementation_mode", "candidate_generations", "correction_rounds",
    "parent_direct_remediation_rounds", "focused_validation_events",
    "authoritative_validation_events", "replan_reason_codes", "last_monotonic_ns", "event_chain_digest", "events",
}
EVENT_KEYS = {
    "sequence", "event_id", "event_type", "implementation_mode", "invariant_digests",
    "finding_severities", "independent_review_receipt_digest", "candidate_lifecycle_digest",
    "elapsed_seconds", "monotonic_ns", "previous_event_digest", "event_digest",
}
EMPTY_CHAIN_DIGEST = digest(b"") if "digest" in globals() else "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class StateError(ValueError):
    pass


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
    )
    if completed.returncode != 0:
        raise StateError("current directory is not a Git repository")
    return Path(completed.stdout.strip()).resolve()


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
    if value["state"] not in {"active", "replan_required"}:
        raise StateError("invalid state")
    if value["implementation_mode"] not in MODES:
        raise StateError("invalid implementation_mode")
    counter_keys = (
        "candidate_generations", "correction_rounds", "parent_direct_remediation_rounds",
        "focused_validation_events", "authoritative_validation_events", "last_monotonic_ns",
    )
    for key in counter_keys:
        item = value[key]
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise StateError(f"{key} must be a nonnegative integer")
    reasons = value["replan_reason_codes"]
    if not isinstance(reasons, list) or len(reasons) != len(set(reasons)) or any(
        not isinstance(reason, str) or reason not in REASON_CODES for reason in reasons
    ):
        raise StateError("invalid replan_reason_codes")
    if value["state"] == "replan_required" and not reasons:
        raise StateError("replan_required state needs a reason")
    events = value["events"]
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise StateError("invalid event list")
    seen_ids: set[str] = set()
    previous_ns = 0
    previous_digest = EMPTY_CHAIN_DIGEST
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict) or set(event) != EVENT_KEYS:
            raise StateError("event has an invalid exact schema")
        if event["sequence"] != index or isinstance(event["sequence"], bool):
            raise StateError("event sequence mismatch")
        if not isinstance(event["event_id"], str) or not ID_RE.fullmatch(event["event_id"]):
            raise StateError("invalid event_id")
        if event["event_id"] in seen_ids:
            raise StateError("duplicate event_id")
        seen_ids.add(event["event_id"])
        if event["event_type"] not in EVENT_TYPES or event["implementation_mode"] not in MODES:
            raise StateError("invalid event classification")
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
        require_digest(event["candidate_lifecycle_digest"], "candidate_lifecycle_digest", allow_empty=True)
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
        unsigned = {key: event[key] for key in EVENT_KEYS if key != "event_digest"}
        expected_event_digest = digest(json.dumps(unsigned, sort_keys=True, separators=(",", ":")))
        if event["event_digest"] != expected_event_digest:
            raise StateError("event hash-chain digest mismatch")
        previous_digest = event["event_digest"]
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
    reasons: list[str] = []

    def add_reason(reason: str) -> None:
        if reason not in reasons:
            reasons.append(reason)

    for event in events:
        event_type = event["event_type"]
        if event_type == "candidate_generation":
            candidate_generations += 1
        elif event_type == "correction_rejected":
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
        elif event_type in {
            "scope_drift", "spec_drift", "security_boundary_drift", "post_authoritative_design_change"
        }:
            add_reason(event_type)
    return {
        "state": "replan_required" if reasons else "active",
        "candidate_generations": candidate_generations,
        "correction_rounds": correction_rounds,
        "parent_direct_remediation_rounds": parent_rounds,
        "focused_validation_events": focused_events,
        "authoritative_validation_events": authoritative_events,
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


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    reject_symlink_ancestors(path, include_target=False)
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    if len(data) > MAX_BYTES:
        raise StateError("execution state exceeds size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def with_lock(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    reject_symlink_ancestors(lock_path, include_target=True)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
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
    actual_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if actual_head != args.source_head:
        raise StateError("source HEAD mismatch")
    state = {
        "schema_version": 1,
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
        "replan_reason_codes": [],
        "last_monotonic_ns": 0,
        "event_chain_digest": EMPTY_CHAIN_DIGEST,
        "events": [],
    }
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


def record_event(args: argparse.Namespace) -> None:
    path = Path(args.state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        if state["run_id"] != args.run_id:
            raise StateError("run_id mismatch")
        if state["state"] != "active":
            raise StateError("plan execution is stopped for restructuring")
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
        lifecycle = args.candidate_lifecycle_digest or ""
        if args.implementation_mode == "parent_direct" and args.event_type == "parent_review":
            require_digest(receipt, "independent_review_receipt_digest")
            if any(event["independent_review_receipt_digest"] == receipt for event in state["events"]):
                raise StateError("independent review receipt replay is not allowed")
        if args.event_type in {
            "parent_review", "scope_drift", "spec_drift", "security_boundary_drift",
            "post_authoritative_design_change",
        } and not invariants:
            raise StateError("this event requires at least one affected invariant digest")
        if args.event_type in {"candidate_generation", "correction_rejected", "focused_validation", "authoritative_validation"}:
            require_digest(lifecycle, "candidate_lifecycle_digest")
            if lifecycle != file_digest(Path(args.lifecycle_state)):
                raise StateError("candidate lifecycle content digest mismatch")
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
            "candidate_lifecycle_digest": lifecycle,
            "elapsed_seconds": args.elapsed_seconds,
            "monotonic_ns": monotonic_ns,
            "previous_event_digest": state["event_chain_digest"],
        }
        event["event_digest"] = digest(
            json.dumps(event, sort_keys=True, separators=(",", ":"))
        )
        state["implementation_mode"] = args.implementation_mode
        state["events"].append(event)
        state["last_monotonic_ns"] = monotonic_ns
        state["event_chain_digest"] = event["event_digest"]
        if args.event_type == "candidate_generation":
            if state["candidate_generations"] != 0:
                raise StateError("initial candidate generation already recorded")
            state["candidate_generations"] += 1
        elif args.event_type == "correction_rejected":
            if state["candidate_generations"] != state["correction_rounds"] + 1:
                raise StateError("correction event is out of order")
            state["correction_rounds"] += 1
            state["candidate_generations"] += 1
            if state["correction_rounds"] >= MAX_CORRECTIONS:
                trigger(state, "candidate_correction_budget_exhausted")
        elif args.event_type == "parent_review":
            if len(invariants) > 1:
                trigger(state, "multiple_independent_invariants")
            if args.implementation_mode == "parent_direct" and set(severities) & {"High", "Medium"}:
                state["parent_direct_remediation_rounds"] += 1
                if state["parent_direct_remediation_rounds"] >= MAX_PARENT_REMEDIATIONS:
                    trigger(state, "parent_remediation_budget_exhausted")
        elif args.event_type == "focused_validation":
            state["focused_validation_events"] += 1
        elif args.event_type == "authoritative_validation":
            state["authoritative_validation_events"] += 1
        elif args.event_type in {
            "scope_drift", "spec_drift", "security_boundary_drift", "post_authoritative_design_change"
        }:
            if args.event_type == "post_authoritative_design_change" and not state["authoritative_validation_events"]:
                raise StateError("post-authoritative design change requires an authoritative event")
            trigger(state, args.event_type)
        validate_state(state)
        atomic_write(path, state)


def check_gate(args: argparse.Namespace) -> None:
    state = read_state(Path(args.state))
    if state["run_id"] != args.run_id:
        raise StateError("run_id mismatch")
    if state["state"] != "active":
        raise StateError("plan execution is stopped for restructuring")
    if args.plan and state["plan_path"] != args.plan:
        raise StateError("plan path mismatch")
    if args.lifecycle_state and state["candidate_lifecycle_identity_digest"] != lifecycle_identity_digest(
        args.run_id, Path(args.lifecycle_state)
    ):
        raise StateError("candidate lifecycle identity mismatch")
    recorded_lifecycle_digests = [
        event["candidate_lifecycle_digest"] for event in state["events"]
        if event["candidate_lifecycle_digest"]
    ]
    if recorded_lifecycle_digests and file_digest(Path(args.lifecycle_state)) != recorded_lifecycle_digests[-1]:
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
    init.add_argument("--implementation-mode", choices=sorted(MODES), required=True)
    init.set_defaults(handler=init_state)
    record = sub.add_parser("record")
    record.add_argument("state")
    record.add_argument("--run-id", required=True)
    record.add_argument("--event-id", required=True)
    record.add_argument("--event-type", choices=sorted(EVENT_TYPES), required=True)
    record.add_argument("--implementation-mode", choices=sorted(MODES), required=True)
    record.add_argument("--invariant-digest", action="append")
    record.add_argument("--finding-severity", action="append", choices=("High", "Medium", "Low"))
    record.add_argument("--independent-review-receipt-digest")
    record.add_argument("--candidate-lifecycle-digest")
    record.add_argument("--lifecycle-state", required=True)
    record.add_argument("--elapsed-seconds", type=float, default=0.0)
    record.set_defaults(handler=record_event)
    check = sub.add_parser("check")
    check.add_argument("state")
    check.add_argument("--run-id", required=True)
    check.add_argument("--plan")
    check.add_argument("--lifecycle-state")
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
