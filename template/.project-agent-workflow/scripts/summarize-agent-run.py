#!/usr/bin/env python3
"""Summarize observed agent-run resources from explicitly supplied local records.

The report is advisory derived information. It reads only the files named on the
command line, never discovers sessions, never executes a recorded command, never
contacts a network or model service, and never writes a file. A value that the
supplied records do not observe stays ``not_observed``; it never becomes zero, an
estimate, or a price lookup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
from typing import Any


MAX_INPUT_FILES = 32
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 256 * 1024
REPORT_SCHEMA_VERSION = 1

RESOURCE_OBSERVATION_SCHEMA_VERSION = 1
CANDIDATE_MANIFEST_SCHEMA_VERSION = 2
CANDIDATE_TELEMETRY_SCHEMA_VERSION = 1
EXECUTION_STATE_SCHEMA_VERSION = 6

TELEMETRY_MAX_DURATION_SECONDS = 31_536_000.0

RESOURCE_METRICS = (
    "provider_input_tokens",
    "provider_cached_input_tokens",
    "provider_output_tokens",
    "provider_reasoning_tokens",
    "model_response_count",
    "compaction_count",
    "helper_turn_count",
    "tool_call_count",
)
EVIDENCE_SOURCES = ("external_transcript", "codex_hooks")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")

TELEMETRY_KEYS = {
    "schema_version",
    "attempt_durations_seconds",
    "runner_duration_seconds",
    "model_starts",
    "availability_failures",
    "skipped_known_unavailable_starts",
    "candidate_generations",
    "full_validation_count",
    "authoritative_validation_count",
    "focused_validation_count",
    "parent_review_rejections",
    "correction_round",
    "implementation_risk",
    "implementation_ambiguity",
}
TELEMETRY_COUNTERS = (
    "model_starts",
    "availability_failures",
    "skipped_known_unavailable_starts",
    "candidate_generations",
    "full_validation_count",
    "authoritative_validation_count",
    "focused_validation_count",
    "parent_review_rejections",
    "correction_round",
)
EXECUTION_COUNTERS = (
    "candidate_generations",
    "correction_rounds",
    "parent_direct_remediation_rounds",
    "focused_validation_events",
    "authoritative_validation_events",
)
EXECUTION_REASON_FIELDS = (
    "repair_reason_codes",
    "replan_reason_codes",
    "descope_reason_codes",
    "descope_pending_reason_codes",
    "review_reason_codes",
)

# Values this command never derives. A reader sees each one only when a supplied
# record observes it directly, so an unobserved quantity never becomes a total.
NEVER_INFERRED = (
    "billed_cost",
    "human_intervention_count",
    "phase_durations_seconds",
    "replan_count",
    "wall_clock_total_seconds",
)


class SummaryError(Exception):
    """An input or bound violation that must reject the whole report."""


def metric_unit(metric: str) -> str:
    return "tokens" if metric.startswith("provider_") else "count"


def expected_provenance(metric: str) -> str:
    return "provider" if metric.startswith("provider_") else "deterministic_proxy"


def read_bounded_regular_file(path: str, label: str) -> bytes:
    """Read an explicitly supplied regular file without following a symlink."""

    # O_NONBLOCK classifies the file before any wait: opening a FIFO without it
    # blocks until a writer appears, so the regular-file check would never run.
    try:
        descriptor = os.open(
            path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        )
    except OSError as exc:
        raise SummaryError(f"{label} is not a readable regular file: {path}") from exc
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            raise SummaryError(f"{label} must be a regular file: {path}")
        os.set_blocking(descriptor, True)
        if status.st_size > MAX_INPUT_BYTES:
            raise SummaryError(
                f"{label} exceeds the {MAX_INPUT_BYTES}-byte input bound: {path}"
            )
        data = b""
        while len(data) <= MAX_INPUT_BYTES:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                break
            data += chunk
        if len(data) > MAX_INPUT_BYTES:
            raise SummaryError(
                f"{label} exceeds the {MAX_INPUT_BYTES}-byte input bound: {path}"
            )
        return data
    except OSError as exc:
        raise SummaryError(f"{label} could not be read: {path}") from exc
    finally:
        os.close(descriptor)


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def load_json_object(path: str) -> dict[str, Any]:
    data = read_bounded_regular_file(path, "input record")
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SummaryError(f"input record is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SummaryError(f"input record must contain a JSON object: {path}")
    return {"payload": value, "source_digest": digest_bytes(data)}


def require_digest_or_none(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not DIGEST_PATTERN.match(value):
        raise SummaryError(f"{label} is not a well-formed sha256 digest")
    return value


def require_bounded_counter(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SummaryError(f"{label} must be a nonnegative integer")
    return value


def require_duration(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SummaryError(f"{label} must be numeric seconds")
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= TELEMETRY_MAX_DURATION_SECONDS:
        raise SummaryError(f"{label} is outside the supported duration bound")
    return number


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SummaryError(f"{label} must be a nonempty string")
    return value


def classify(payload: dict[str, Any], path: str) -> str:
    if "resource_observations" in payload:
        return "run_manifest"
    if "telemetry" in payload and "patch_digest" in payload:
        return "candidate_manifest"
    if "events" in payload and "genesis_digest" in payload:
        return "execution_state"
    raise SummaryError(
        "input record does not match a supported run manifest, candidate manifest, "
        f"or execution state record: {path}"
    )


def parse_billed_cost(value: Any) -> dict[str, Any]:
    """Read an explicit billed amount; never derive one from a price table."""

    if value is None:
        return {"status": "not_observed", "amount": None, "currency": None}
    if not isinstance(value, dict) or set(value) != {"status", "amount", "currency"}:
        raise SummaryError("billed_cost has an invalid exact field shape")
    if value["status"] == "not_observed":
        if value["amount"] is not None or value["currency"] is not None:
            raise SummaryError("unavailable billed_cost must remain not_observed")
        return {"status": "not_observed", "amount": None, "currency": None}
    if value["status"] != "observed":
        raise SummaryError("billed_cost status must be observed or not_observed")
    amount = value["amount"]
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise SummaryError("observed billed_cost requires a numeric amount")
    amount = float(amount)
    if not math.isfinite(amount) or amount < 0:
        raise SummaryError("observed billed_cost amount is outside the supported bound")
    currency = value["currency"]
    if not isinstance(currency, str) or not CURRENCY_PATTERN.match(currency):
        raise SummaryError("observed billed_cost requires an explicit ISO currency code")
    return {"status": "observed", "amount": amount, "currency": currency}


def parse_run_manifest(payload: dict[str, Any], path: str, source_digest: str) -> dict[str, Any]:
    run_id = require_text(payload.get("run_id"), f"run manifest run_id in {path}")
    observations = payload.get("resource_observations")
    if not isinstance(observations, dict):
        raise SummaryError(f"run manifest resource_observations must be an object: {path}")
    if observations.get("schema_version") != RESOURCE_OBSERVATION_SCHEMA_VERSION:
        raise SummaryError(
            "run manifest has an unsupported resource observation schema version: "
            f"{observations.get('schema_version')}"
        )
    allowed = {"schema_version", "root_session_identity", "evidence_digests", "metrics", "billed_cost"}
    required = {"schema_version", "root_session_identity", "evidence_digests", "metrics"}
    keys = set(observations)
    if not required <= keys or not keys <= allowed:
        raise SummaryError(f"run manifest resource_observations has an unsupported field set: {path}")

    identity = observations["root_session_identity"]
    if not isinstance(identity, dict) or set(identity) != {"status", "digest"}:
        raise SummaryError("root_session_identity has an invalid exact field shape")
    if identity["status"] == "observed":
        session_identity = {
            "status": "observed",
            "digest": require_digest_or_none(identity["digest"], "root_session_identity digest"),
        }
        if session_identity["digest"] is None:
            raise SummaryError("observed root_session_identity requires a digest")
    elif identity == {"status": "not_observed", "digest": None}:
        session_identity = {"status": "not_observed", "digest": None}
    else:
        raise SummaryError("unavailable root_session_identity must remain not_observed")

    raw_digests = observations["evidence_digests"]
    if not isinstance(raw_digests, dict) or set(raw_digests) != set(EVIDENCE_SOURCES):
        raise SummaryError("evidence_digests has an invalid exact field shape")
    evidence = {
        source: require_digest_or_none(raw_digests[source], f"{source} evidence digest")
        for source in EVIDENCE_SOURCES
    }

    raw_metrics = observations["metrics"]
    if not isinstance(raw_metrics, dict) or set(raw_metrics) != set(RESOURCE_METRICS):
        raise SummaryError("resource observation metrics have an invalid exact field shape")
    metrics: dict[str, dict[str, Any]] = {}
    for metric in RESOURCE_METRICS:
        observation = raw_metrics[metric]
        if not isinstance(observation, dict) or set(observation) != {"status", "value", "provenance"}:
            raise SummaryError(f"resource metric {metric} has an invalid exact field shape")
        if observation["status"] == "observed":
            value = require_bounded_counter(observation["value"], f"resource metric {metric}")
            provenance = observation["provenance"]
            if provenance != expected_provenance(metric):
                # A provider provenance on a proxy counter would silently
                # republish a deterministic count as a billed provider token.
                raise SummaryError(
                    f"resource metric {metric} declares an incompatible provenance: {provenance}"
                )
            metrics[metric] = {"status": "observed", "value": value, "provenance": provenance}
            continue
        if observation != {"status": "not_observed", "value": None, "provenance": "not_observed"}:
            raise SummaryError(f"unavailable resource metric {metric} must remain not_observed")
        metrics[metric] = {"status": "not_observed", "value": None, "provenance": "not_observed"}

    return {
        "kind": "run_manifest",
        "path": path,
        "source_digest": source_digest,
        "identity": run_id,
        "root_session_identity": session_identity,
        "evidence_digests": evidence,
        "metrics": metrics,
        "billed_cost": parse_billed_cost(observations.get("billed_cost")),
    }


def parse_candidate_manifest(payload: dict[str, Any], path: str, source_digest: str) -> dict[str, Any]:
    if payload.get("schema_version") != CANDIDATE_MANIFEST_SCHEMA_VERSION:
        raise SummaryError(
            f"candidate manifest has an unsupported schema version: {payload.get('schema_version')}"
        )
    run_id = require_text(payload.get("orchestration_run_id"), "candidate orchestration_run_id")
    attempt_id = require_text(
        payload.get("plan_execution_attempt_id"), "candidate plan_execution_attempt_id"
    )
    patch_digest = require_text(payload.get("patch_digest"), "candidate patch_digest")
    telemetry = payload.get("telemetry")
    if not isinstance(telemetry, dict) or set(telemetry) != TELEMETRY_KEYS:
        raise SummaryError("candidate telemetry has an invalid exact field shape")
    if telemetry["schema_version"] != CANDIDATE_TELEMETRY_SCHEMA_VERSION:
        raise SummaryError(
            f"candidate telemetry has an unsupported schema version: {telemetry['schema_version']}"
        )
    durations = telemetry["attempt_durations_seconds"]
    if not isinstance(durations, list) or len(durations) > 2:
        raise SummaryError("candidate telemetry attempt durations exceed the bound")
    attempt_durations = [
        require_duration(value, "candidate attempt duration") for value in durations
    ]
    runner_duration = require_duration(
        telemetry["runner_duration_seconds"], "candidate runner duration"
    )
    counters = {}
    for key in TELEMETRY_COUNTERS:
        value = require_bounded_counter(telemetry[key], f"candidate telemetry {key}")
        if value > 3:
            raise SummaryError(f"candidate telemetry counter is outside the bound: {key}")
        counters[key] = value
    return {
        "kind": "candidate_manifest",
        "path": path,
        "source_digest": source_digest,
        "identity": f"{run_id}/{attempt_id}/{patch_digest}",
        "plan_path": payload.get("plan_path") if isinstance(payload.get("plan_path"), str) else None,
        "attempt_durations_seconds": attempt_durations,
        "runner_duration_seconds": runner_duration,
        "counters": counters,
        "implementation_risk": require_text(
            telemetry["implementation_risk"], "candidate implementation_risk"
        ),
        "implementation_ambiguity": require_text(
            telemetry["implementation_ambiguity"], "candidate implementation_ambiguity"
        ),
    }


def parse_execution_state(payload: dict[str, Any], path: str, source_digest: str) -> dict[str, Any]:
    if payload.get("schema_version") != EXECUTION_STATE_SCHEMA_VERSION:
        raise SummaryError(
            f"execution state has an unsupported schema version: {payload.get('schema_version')}"
        )
    run_id = require_text(payload.get("run_id"), "execution state run_id")
    state = require_text(payload.get("state"), "execution state")
    plan_path = require_text(payload.get("plan_path"), "execution state plan_path")
    events = payload.get("events")
    if not isinstance(events, list):
        raise SummaryError("execution state events must be a list")
    counters = {
        key: require_bounded_counter(payload.get(key), f"execution state {key}")
        for key in EXECUTION_COUNTERS
    }
    reasons: dict[str, list[str]] = {}
    for key in EXECUTION_REASON_FIELDS:
        value = payload.get(key)
        if not isinstance(value, list) or not all(isinstance(code, str) for code in value):
            raise SummaryError(f"execution state {key} must be a list of reason codes")
        reasons[key] = list(value)
    elapsed: list[float] = []
    for event in events:
        if not isinstance(event, dict):
            raise SummaryError("execution state event must be an object")
        if event.get("event_type") != "elapsed_checkpoint":
            continue
        elapsed.append(require_duration(event.get("elapsed_seconds"), "elapsed checkpoint"))
    return {
        "kind": "execution_state",
        "path": path,
        "source_digest": source_digest,
        "identity": run_id,
        "plan_path": plan_path,
        "state": state,
        "counters": counters,
        "reason_codes": reasons,
        "event_count": len(events),
        "elapsed_checkpoint_seconds": elapsed,
    }


PARSERS = {
    "run_manifest": parse_run_manifest,
    "candidate_manifest": parse_candidate_manifest,
    "execution_state": parse_execution_state,
}


def load_records(paths: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse each explicit input once, deduplicating by identity and source digest."""

    records: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], str] = {}
    for path in paths:
        loaded = load_json_object(path)
        payload = loaded["payload"]
        source_digest = loaded["source_digest"]
        kind = classify(payload, path)
        record = PARSERS[kind](payload, path, source_digest)
        key = (record["kind"], record["identity"])
        previous = seen.get(key)
        if previous is None:
            seen[key] = source_digest
            records.append(record)
            inventory.append(
                {
                    "path": path,
                    "kind": kind,
                    "identity": record["identity"],
                    "source_digest": source_digest,
                    "status": "included",
                }
            )
            continue
        if previous != source_digest:
            # The same run reported by two different byte sequences cannot be
            # deduplicated or added; either choice would misstate the totals.
            raise SummaryError(
                f"conflicting records for {kind} identity {record['identity']}: "
                "the same run is supplied with two different source digests"
            )
        inventory.append(
            {
                "path": path,
                "kind": kind,
                "identity": record["identity"],
                "source_digest": source_digest,
                "status": "duplicate_ignored",
            }
        )
    return records, inventory


def verify_evidence(records: list[dict[str, Any]], evidence_paths: list[str]) -> list[dict[str, Any]]:
    """Hash explicitly supplied raw evidence and bind it to declared digests."""

    declared: dict[str, list[dict[str, str]]] = {}
    for record in records:
        if record["kind"] != "run_manifest":
            continue
        for source in EVIDENCE_SOURCES:
            digest = record["evidence_digests"][source]
            if digest is None:
                continue
            declared.setdefault(digest, []).append({"run_id": record["identity"], "source": source})

    verified: set[str] = set()
    for path in evidence_paths:
        data = read_bounded_regular_file(path, "evidence file")
        digest = digest_bytes(data)
        if digest not in declared:
            raise SummaryError(
                f"supplied evidence file matches no declared evidence digest: {path}"
            )
        verified.add(digest)

    report: list[dict[str, Any]] = []
    for record in records:
        if record["kind"] != "run_manifest":
            continue
        for source in EVIDENCE_SOURCES:
            digest = record["evidence_digests"][source]
            report.append(
                {
                    "run_id": record["identity"],
                    "source": source,
                    "digest": digest,
                    "verification": (
                        "not_observed"
                        if digest is None
                        else ("verified" if digest in verified else "declared_only")
                    ),
                }
            )
    return report


def summarize_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    manifests = [record for record in records if record["kind"] == "run_manifest"]
    summary: dict[str, Any] = {}
    for metric in RESOURCE_METRICS:
        buckets: dict[str, dict[str, Any]] = {}
        observed = 0
        for record in manifests:
            observation = record["metrics"][metric]
            if observation["status"] != "observed":
                continue
            observed += 1
            bucket = buckets.setdefault(
                observation["provenance"], {"total": 0, "records": 0}
            )
            bucket["total"] += observation["value"]
            bucket["records"] += 1
        summary[metric] = {
            "unit": metric_unit(metric),
            "totals_by_provenance": buckets,
            "coverage": {
                "records_total": len(manifests),
                "records_observed": observed,
                "records_not_observed": len(manifests) - observed,
            },
        }
    return summary


def summarize_durations(records: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [record for record in records if record["kind"] == "candidate_manifest"]
    states = [record for record in records if record["kind"] == "execution_state"]

    runner_records = list(candidates)
    attempt_values = [
        value for record in candidates for value in record["attempt_durations_seconds"]
    ]
    attempt_records = [record for record in candidates if record["attempt_durations_seconds"]]
    elapsed_values = [
        value for record in states for value in record["elapsed_checkpoint_seconds"]
    ]
    elapsed_records = [record for record in states if record["elapsed_checkpoint_seconds"]]

    def group(total: float, observations: int, records_observed: int, records_total: int) -> dict[str, Any]:
        return {
            "unit": "seconds",
            "total": round(total, 6),
            "observation_count": observations,
            "coverage": {
                "records_total": records_total,
                "records_observed": records_observed,
                "records_not_observed": records_total - records_observed,
            },
        }

    # Runner wall time, per-attempt wall time, and ledger elapsed checkpoints are
    # different measurement boundaries. They stay in separate groups so no total
    # merges observations that were never comparable.
    return {
        "candidate_runner_duration": group(
            sum(record["runner_duration_seconds"] for record in runner_records),
            len(runner_records),
            len(runner_records),
            len(candidates),
        ),
        "candidate_attempt_duration": group(
            sum(attempt_values), len(attempt_values), len(attempt_records), len(candidates)
        ),
        "execution_elapsed_checkpoint": group(
            sum(elapsed_values), len(elapsed_values), len(elapsed_records), len(states)
        ),
    }


def summarize_billed_cost(records: list[dict[str, Any]]) -> dict[str, Any]:
    manifests = [record for record in records if record["kind"] == "run_manifest"]
    observed = [record for record in manifests if record["billed_cost"]["status"] == "observed"]
    if not observed:
        return {
            "status": "not_observed",
            "totals_by_currency": {},
            "coverage": {
                "records_total": len(manifests),
                "records_observed": 0,
                "records_not_observed": len(manifests),
            },
        }
    totals: dict[str, dict[str, Any]] = {}
    for record in observed:
        cost = record["billed_cost"]
        bucket = totals.setdefault(cost["currency"], {"total": 0.0, "records": 0})
        bucket["total"] = round(bucket["total"] + cost["amount"], 6)
        bucket["records"] += 1
    return {
        "status": "observed",
        "totals_by_currency": totals,
        "coverage": {
            "records_total": len(manifests),
            "records_observed": len(observed),
            "records_not_observed": len(manifests) - len(observed),
        },
    }


def build_report(
    records: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_kind": "observed_run_resources",
        "inputs": inventory,
        "record_counts": {
            kind: sum(1 for record in records if record["kind"] == kind)
            for kind in ("run_manifest", "candidate_manifest", "execution_state")
        },
        "sessions": [
            {
                "run_id": record["identity"],
                "source_digest": record["source_digest"],
                "root_session_identity": record["root_session_identity"],
            }
            for record in records
            if record["kind"] == "run_manifest"
        ],
        "evidence": evidence,
        "metrics": summarize_metrics(records),
        "durations": summarize_durations(records),
        "billed_cost": summarize_billed_cost(records),
        "candidate_runs": [
            {
                "identity": record["identity"],
                "source_digest": record["source_digest"],
                "plan_path": record["plan_path"],
                "counters": record["counters"],
                "implementation_risk": record["implementation_risk"],
                "implementation_ambiguity": record["implementation_ambiguity"],
            }
            for record in records
            if record["kind"] == "candidate_manifest"
        ],
        "execution_runs": [
            {
                "run_id": record["identity"],
                "source_digest": record["source_digest"],
                "plan_path": record["plan_path"],
                "state": record["state"],
                "event_count": record["event_count"],
                "counters": record["counters"],
                "reason_codes": record["reason_codes"],
            }
            for record in records
            if record["kind"] == "execution_state"
        ],
        "never_inferred": list(NEVER_INFERRED),
    }


def render_text(report: dict[str, Any]) -> str:
    lines = ["# Observed run resources", ""]
    counts = report["record_counts"]
    lines.append(
        "records: run_manifest={run_manifest} candidate_manifest={candidate_manifest} "
        "execution_state={execution_state}".format(**counts)
    )
    duplicates = sum(1 for entry in report["inputs"] if entry["status"] == "duplicate_ignored")
    lines.append(f"inputs: {len(report['inputs'])} supplied, {duplicates} duplicate ignored")
    lines.append("")

    lines.append("## Sources")
    for entry in report["inputs"]:
        lines.append(
            f"- {entry['kind']} {entry['identity']}: {entry['status']} "
            f"source_digest={entry['source_digest']}"
        )
    lines.append("")

    lines.append("## Evidence")
    if not report["evidence"]:
        lines.append("- no run manifest declares evidence")
    for entry in report["evidence"]:
        lines.append(
            f"- {entry['run_id']} {entry['source']}: {entry['verification']} "
            f"digest={entry['digest'] or 'not_observed'}"
        )
    for session in report["sessions"]:
        identity = session["root_session_identity"]
        lines.append(
            f"- {session['run_id']} root_session_identity: {identity['status']} "
            f"digest={identity['digest'] or 'not_observed'}"
        )
    lines.append("")

    lines.append("## Metrics")
    for metric, summary in report["metrics"].items():
        coverage = summary["coverage"]
        if not summary["totals_by_provenance"]:
            lines.append(
                f"- {metric}: not_observed "
                f"({coverage['records_observed']}/{coverage['records_total']} records)"
            )
            continue
        for provenance, bucket in sorted(summary["totals_by_provenance"].items()):
            lines.append(
                f"- {metric}: {bucket['total']} {summary['unit']} "
                f"[provenance={provenance}] "
                f"({bucket['records']}/{coverage['records_total']} records observed)"
            )
    lines.append("")

    lines.append("## Durations")
    for group, summary in report["durations"].items():
        coverage = summary["coverage"]
        if summary["observation_count"] == 0:
            lines.append(f"- {group}: not_observed (0/{coverage['records_total']} records)")
            continue
        lines.append(
            f"- {group}: {summary['total']} {summary['unit']} "
            f"over {summary['observation_count']} observations "
            f"({coverage['records_observed']}/{coverage['records_total']} records observed)"
        )
    lines.append("")

    lines.append("## Candidate runs")
    if not report["candidate_runs"]:
        lines.append("- none supplied")
    for run in report["candidate_runs"]:
        counters = run["counters"]
        lines.append(
            f"- {run['identity']}: generations={counters['candidate_generations']} "
            f"corrections={counters['correction_round']} "
            f"model_starts={counters['model_starts']} "
            f"source_digest={run['source_digest']}"
        )
    lines.append("")

    lines.append("## Execution runs")
    if not report["execution_runs"]:
        lines.append("- none supplied")
    for run in report["execution_runs"]:
        stops = sorted(
            code for codes in run["reason_codes"].values() for code in codes
        )
        lines.append(
            f"- {run['run_id']}: state={run['state']} events={run['event_count']} "
            f"stop_reason_codes={stops or 'none'} source_digest={run['source_digest']}"
        )
    lines.append("")

    billed = report["billed_cost"]
    lines.append("## Billed cost")
    if billed["status"] != "observed":
        lines.append("- not_observed (no supplied record carries an explicit billed amount)")
    else:
        coverage = billed["coverage"]
        for currency, bucket in sorted(billed["totals_by_currency"].items()):
            lines.append(
                f"- {bucket['total']} {currency} "
                f"({bucket['records']}/{coverage['records_total']} records observed)"
            )
    lines.append("")

    lines.append("## Never inferred")
    lines.append("These values are reported only when a supplied record observes them directly.")
    for name in report["never_inferred"]:
        lines.append(f"- {name}")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize observed resources from explicitly supplied local agent-run records. "
            "The report is advisory; it is never acceptance or validation evidence."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="explicit local run manifest, candidate manifest, or execution state files",
    )
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        metavar="PATH",
        help="explicit raw evidence file to hash and bind to a declared evidence digest",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    supplied = list(args.inputs) + list(args.evidence)
    try:
        if len(supplied) > MAX_INPUT_FILES:
            raise SummaryError(
                f"at most {MAX_INPUT_FILES} explicit input files are supported; "
                f"{len(supplied)} were supplied"
            )
        records, inventory = load_records(list(args.inputs))
        evidence = verify_evidence(records, list(args.evidence))
        report = build_report(records, inventory, evidence)
        if args.format == "json":
            rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        else:
            rendered = render_text(report)
        encoded = rendered.encode("utf-8")
        if len(encoded) > MAX_OUTPUT_BYTES:
            raise SummaryError(
                f"report exceeds the {MAX_OUTPUT_BYTES}-byte output bound; "
                "summarize fewer records per invocation"
            )
    except SummaryError as exc:
        print(f"summarize-agent-run failed: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
