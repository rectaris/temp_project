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
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_log_manifest  # noqa: E402


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
# The model contract is owned by agent_log_manifest, which produces every
# summary this command reports. Sourcing the constants and the source scan from
# there is what lets the report verify a summary by recomputing it, instead of
# maintaining a second table that could drift into accepting evidence the
# producer would have refused.
MODEL_OBSERVATION_SCHEMA_VERSION = agent_log_manifest.MODEL_OBSERVATION_SCHEMA_VERSION
MODEL_ATTRIBUTES = agent_log_manifest.MODEL_ATTRIBUTES
MODEL_EVIDENCE_CLASSES = agent_log_manifest.MODEL_EVIDENCE_CLASSES
MODEL_SOURCE_KINDS = agent_log_manifest.MODEL_SOURCE_KINDS
MODEL_SOURCE_CAPABILITIES = agent_log_manifest.MODEL_SOURCE_CAPABILITIES
MODEL_PROVIDER_CONTEXT_FIELDS = agent_log_manifest.MODEL_PROVIDER_CONTEXT_FIELDS
MODEL_COVERAGE_STATUSES = ("present", "missing", "unreadable")
MODEL_DIAGNOSTIC_CODES = agent_log_manifest.MODEL_DIAGNOSTIC_CODES
# Each source file stores its observation under one container key, exactly as
# the producer wrote it.
MODEL_SOURCE_CONTAINERS = {"external_transcript": "metadata", "codex_hooks": "payload"}
# The manifest field each source is declared under, as the producer reads it.
MODEL_SOURCE_MANIFEST_KEYS = {
    "external_transcript": "transcript_log",
    "codex_hooks": "hook_event_log",
}
# A session identity alone does not separate two executions: one hook log
# reports many turns under one session. Only a shape that names a turn can
# establish a scope two statements may be compared within.
MODEL_TURN_SCOPED_KINDS = tuple(
    kind
    for kind in MODEL_SOURCE_KINDS
    if "turn_id" in MODEL_SOURCE_CAPABILITIES[kind]["execution_scope"]
)
MAX_MODEL_VALUE_LENGTH = agent_log_manifest.MAX_MODEL_VALUE_LENGTH
MAX_MODEL_STATEMENTS = agent_log_manifest.MAX_MODEL_STATEMENTS
MAX_MODEL_PROVIDER_VALUES = agent_log_manifest.MAX_MODEL_PROVIDER_VALUES
MAX_MODEL_DIAGNOSTICS = len(MODEL_DIAGNOSTIC_CODES)
# A model statement says which model a scope reported. It never says how many
# tokens that model consumed, so the report names the unavailable attribution
# instead of dividing a run total by a model name.
MODEL_ATTRIBUTION_UNAVAILABLE = (
    "per_model_token_totals",
    "per_model_billed_cost",
    "per_model_completed_task_counts",
)
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
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
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
    try:
        number = float(value)
    except OverflowError as exc:
        raise SummaryError(f"{label} is outside the supported duration bound") from exc
    if not math.isfinite(number) or not 0 <= number <= TELEMETRY_MAX_DURATION_SECONDS:
        raise SummaryError(f"{label} is outside the supported duration bound")
    return number


def reject_unrenderable_text(value: str, label: str) -> str:
    """Refuse text that would corrupt or spoof the rendered report.

    The text report is line oriented, so an embedded newline would let a record
    identifier forge a report line, and a Unicode format character such as a
    bidirectional override would let a value reorder what a reader sees. Neither
    is a legitimate identifier, so both reject rather than being rewritten.
    """

    for character in value:
        if unicodedata.category(character) in ("Cc", "Cf", "Cs", "Co", "Zl", "Zp"):
            raise SummaryError(
                f"{label} contains a control or formatting character that cannot be reported"
            )
    return value


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SummaryError(f"{label} must be a nonempty string")
    return reject_unrenderable_text(value, label)


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
    try:
        amount = float(amount)
    except OverflowError as exc:
        raise SummaryError(
            "observed billed_cost amount is outside the supported bound"
        ) from exc
    if not math.isfinite(amount) or amount < 0:
        raise SummaryError("observed billed_cost amount is outside the supported bound")
    currency = value["currency"]
    if not isinstance(currency, str) or not CURRENCY_PATTERN.match(currency):
        raise SummaryError("observed billed_cost requires an explicit ISO currency code")
    return {"status": "observed", "amount": amount, "currency": currency}


def require_model_value_slot(slot: Any, label: str) -> dict[str, Any]:
    if not isinstance(slot, dict) or set(slot) != {"status", "value"}:
        raise SummaryError(f"{label} has an invalid exact field shape")
    if slot["status"] == "not_observed":
        if slot["value"] is not None:
            raise SummaryError(f"unavailable {label} must remain not_observed")
        return {"status": "not_observed", "value": None}
    if slot["status"] != "observed":
        raise SummaryError(f"{label} has an unsupported status: {slot['status']}")
    value = slot["value"]
    if not isinstance(value, str) or not value or len(value) > MAX_MODEL_VALUE_LENGTH:
        raise SummaryError(f"observed {label} requires a bounded non-empty string")
    return {"status": "observed", "value": value}


def parse_model_statement(value: Any, path: str) -> dict[str, Any]:
    expected = {
        "source",
        "record_line",
        "source_line",
        "source_kind",
        "attribute",
        "evidence_class",
        "value",
        "session_digest",
        "turn_id",
        "root_turn_id",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise SummaryError(f"model statement has an invalid exact field shape: {path}")
    if value["source"] not in EVIDENCE_SOURCES:
        raise SummaryError(f"model statement names an unsupported source: {value['source']}")
    if value["source_kind"] not in MODEL_SOURCE_KINDS:
        raise SummaryError(f"model statement names an unsupported source kind: {path}")
    if (
        MODEL_SOURCE_CAPABILITIES[value["source_kind"]]["container"]
        != MODEL_SOURCE_CONTAINERS[value["source"]]
    ):
        # The producer can only read this shape out of the other file, so the
        # pairing names a record that could never have existed.
        raise SummaryError(
            "model statement pairs a source kind with a source that cannot hold it: "
            f"{value['source_kind']}/{value['source']}"
        )
    if value["attribute"] not in MODEL_ATTRIBUTES:
        raise SummaryError(f"model statement names an unsupported attribute: {path}")
    if value["evidence_class"] not in MODEL_EVIDENCE_CLASSES:
        raise SummaryError(f"model statement names an unsupported evidence class: {path}")
    capability = MODEL_SOURCE_CAPABILITIES[value["source_kind"]]
    if value["evidence_class"] not in capability["evidence_classes"]:
        # Reporting a class its source never observes would let a runtime
        # context statement arrive as though a provider had confirmed it.
        raise SummaryError(
            "model statement claims an evidence class its source kind cannot observe: "
            f"{value['source_kind']}/{value['evidence_class']}"
        )
    record_line = value["record_line"]
    if isinstance(record_line, bool) or not isinstance(record_line, int) or record_line < 1:
        raise SummaryError(f"model statement requires a positive record line: {path}")
    source_line = value["source_line"]
    if source_line is not None and (
        isinstance(source_line, bool) or not isinstance(source_line, int) or source_line < 1
    ):
        raise SummaryError(f"model statement source line must be positive or absent: {path}")
    text = value["value"]
    if isinstance(text, str):
        reject_unrenderable_text(text, "model statement value")
    if not agent_log_manifest.canonical_model_value(text):
        # The producer refuses a secret, a redaction marker, a control
        # character, a padded identifier, and an overlong value. Repeating
        # those refusals on read stops a hand-edited manifest from presenting
        # any of them as an observed model identifier.
        raise SummaryError(f"model statement requires a bounded non-empty value: {path}")
    allowed_scope = capability["execution_scope"]
    for field in ("turn_id", "root_turn_id"):
        scope = value[field]
        if scope is None:
            continue
        if field not in allowed_scope:
            raise SummaryError(
                f"model statement claims a {field} its source kind cannot establish: {path}"
            )
        if isinstance(scope, str):
            reject_unrenderable_text(scope, f"model statement {field}")
        if not agent_log_manifest.canonical_model_value(scope):
            raise SummaryError(f"model statement {field} must be a bounded string or absent: {path}")
    return {
        "source": value["source"],
        "record_line": record_line,
        "source_line": source_line,
        "source_kind": value["source_kind"],
        "attribute": value["attribute"],
        "evidence_class": value["evidence_class"],
        "value": text,
        "session_digest": require_digest_or_none(value["session_digest"], "model session digest"),
        "turn_id": value["turn_id"],
        "root_turn_id": value["root_turn_id"],
    }


def parse_model_observations(payload: Any, path: str) -> dict[str, Any] | None:
    """Read the optional model observation summary a run manifest may carry.

    A manifest written before the contract existed carries nothing here, and
    that absence is valid legacy input rather than an error.
    """

    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise SummaryError(f"run manifest model_observations must be an object: {path}")
    if payload.get("schema_version") != MODEL_OBSERVATION_SCHEMA_VERSION:
        raise SummaryError(
            "run manifest has an unsupported model observation schema version: "
            f"{payload.get('schema_version')}"
        )
    expected = {
        "schema_version",
        "evidence_digests",
        "coverage",
        "statements",
        "provider_context",
        "identity_counts",
        "diagnostics",
        "truncated",
    }
    if set(payload) != expected:
        raise SummaryError(f"run manifest model_observations has an unsupported field set: {path}")

    raw_digests = payload["evidence_digests"]
    if not isinstance(raw_digests, dict) or set(raw_digests) != set(EVIDENCE_SOURCES):
        raise SummaryError("model evidence_digests has an invalid exact field shape")
    digests = {
        source: require_digest_or_none(raw_digests[source], f"model {source} evidence digest")
        for source in EVIDENCE_SOURCES
    }

    raw_coverage = payload["coverage"]
    if not isinstance(raw_coverage, dict) or set(raw_coverage) != set(EVIDENCE_SOURCES):
        raise SummaryError("model coverage has an invalid exact field shape")
    coverage: dict[str, Any] = {}
    for source in EVIDENCE_SOURCES:
        entry = raw_coverage[source]
        if not isinstance(entry, dict) or set(entry) != {
            "status",
            "records_scanned",
            "records_with_model_observation",
        }:
            raise SummaryError(f"model coverage for {source} has an invalid exact field shape")
        if entry["status"] not in MODEL_COVERAGE_STATUSES:
            raise SummaryError(f"model coverage for {source} has an unsupported status")
        coverage[source] = {
            "status": entry["status"],
            "records_scanned": require_bounded_counter(
                entry["records_scanned"], f"model coverage records_scanned for {source}"
            ),
            "records_with_model_observation": require_bounded_counter(
                entry["records_with_model_observation"],
                f"model coverage records_with_model_observation for {source}",
            ),
        }

    raw_statements = payload["statements"]
    if not isinstance(raw_statements, list) or len(raw_statements) > MAX_MODEL_STATEMENTS:
        raise SummaryError(f"model statements must be a bounded list: {path}")
    statements = [parse_model_statement(item, path) for item in raw_statements]
    for statement in statements:
        if digests[statement["source"]] is None:
            # A statement without its source digest cannot be bound to any
            # bytes, so it could never be verified or refuted.
            raise SummaryError(
                f"model statement names a source with no evidence digest: {statement['source']}"
            )

    raw_provider = payload["provider_context"]
    if not isinstance(raw_provider, dict) or set(raw_provider) != set(
        MODEL_PROVIDER_CONTEXT_FIELDS
    ):
        raise SummaryError("model provider_context has an invalid exact field shape")
    provider_context: dict[str, Any] = {}
    for field in MODEL_PROVIDER_CONTEXT_FIELDS:
        entry = raw_provider[field]
        if not isinstance(entry, dict) or set(entry) != {"status", "values"}:
            raise SummaryError(f"model provider_context {field} has an invalid exact field shape")
        values = entry["values"]
        if not isinstance(values, list) or len(values) > MAX_MODEL_PROVIDER_VALUES:
            raise SummaryError(f"model provider_context {field} must be a bounded list")
        for item in values:
            if isinstance(item, str):
                reject_unrenderable_text(item, f"model provider_context {field}")
            if not agent_log_manifest.canonical_model_value(item):
                raise SummaryError(
                    f"model provider_context {field} requires bounded non-empty strings"
                )
        if entry["status"] == "observed":
            if not values:
                raise SummaryError(f"observed model provider_context {field} requires a value")
        elif entry["status"] != "not_observed" or values:
            raise SummaryError(f"unavailable model provider_context {field} must stay not_observed")
        provider_context[field] = {"status": entry["status"], "values": list(values)}

    raw_counts = payload["identity_counts"]
    if not isinstance(raw_counts, dict) or set(raw_counts) != {"session_digests", "turn_ids"}:
        raise SummaryError("model identity_counts has an invalid exact field shape")
    identity_counts = {
        name: require_bounded_counter(raw_counts[name], f"model identity count {name}")
        for name in ("session_digests", "turn_ids")
    }

    diagnostics = payload["diagnostics"]
    if not isinstance(diagnostics, list) or len(diagnostics) > MAX_MODEL_DIAGNOSTICS:
        raise SummaryError(f"model diagnostics must be a bounded list: {path}")
    if any(code not in MODEL_DIAGNOSTIC_CODES for code in diagnostics):
        raise SummaryError(f"model diagnostics name an unsupported code: {path}")
    if not isinstance(payload["truncated"], bool):
        raise SummaryError(f"model truncated must be a boolean: {path}")

    return {
        "evidence_digests": digests,
        "coverage": coverage,
        "statements": statements,
        "provider_context": provider_context,
        "identity_counts": identity_counts,
        "diagnostics": list(diagnostics),
        "truncated": payload["truncated"],
    }


def declared_model_sources(payload: dict[str, Any]) -> dict[str, str]:
    """Name the evidence sources the manifest itself says the run has.

    The producer derives a summary from every source the manifest declares, so
    the declaration, not the summary, is what says how many sources a rebuild
    needs. Reading the source set back out of the summary would let a summary
    that silently dropped a declared source look complete.
    """

    declared: dict[str, str] = {}
    for source, key in MODEL_SOURCE_MANIFEST_KEYS.items():
        value = payload.get(key)
        if isinstance(value, str) and value:
            declared[source] = value
    return declared


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
        "model_observations": parse_model_observations(payload.get("model_observations"), path),
        "model_observations_declared": payload.get("model_observations"),
        "declared_model_sources": declared_model_sources(payload),
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


def verify_evidence(
    records: list[dict[str, Any]], evidence_paths: list[str]
) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    """Hash explicitly supplied raw evidence and bind it to declared digests."""

    declared: dict[str, list[dict[str, str]]] = {}
    for record in records:
        if record["kind"] != "run_manifest":
            continue
        for source in EVIDENCE_SOURCES:
            digest = record["evidence_digests"][source]
            if digest is not None:
                declared.setdefault(digest, []).append(
                    {"run_id": record["identity"], "source": source}
                )
            observations = record["model_observations"]
            if observations is None:
                continue
            model_digest = observations["evidence_digests"][source]
            if model_digest is not None:
                # Model statements bind to their own scanned bytes, which may
                # differ from the resource evidence for the same source.
                declared.setdefault(model_digest, []).append(
                    {"run_id": record["identity"], "source": source}
                )

    verified: dict[str, bytes] = {}
    for path in evidence_paths:
        data = read_bounded_regular_file(path, "evidence file")
        digest = digest_bytes(data)
        if digest not in declared:
            raise SummaryError(
                f"supplied evidence file matches no declared evidence digest: {path}"
            )
        verified[digest] = data

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
    return report, verified


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


def exact_json_equal(left: Any, right: Any) -> bool:
    """Compare two decoded JSON values by type as well as by value.

    Python equates ``True`` with ``1`` and ``1.0`` with ``1``, so plain equality
    would accept a stored value the producer could never have written. An exact
    match has to mean exactly that.
    """

    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            exact_json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            exact_json_equal(item, other) for item, other in zip(left, right)
        )
    return left == right


def verify_model_observations(
    records: list[dict[str, Any]], supplied: dict[str, bytes]
) -> set[str]:
    """Recompute each whole summary from its verified bytes and require a match.

    A matching file digest proves only that the bytes are unchanged. It cannot
    detect a forged statement, a fabricated provider value, an inflated count,
    a forged diagnostic, or a summary that omits evidence the sources hold.
    Rebuilding the entire object with the producer that wrote it is what makes
    the report say exactly what the sources say, and it keeps the producer's
    own ordering, deduplication, truncation, and identity counting authoritative
    instead of reimplementing them here.

    The rebuild runs against a private snapshot of the bytes whose digest was
    already verified, never against the supplied path. Rereading the path would
    let a file that changed between the digest check and the rescan bind one
    version's statements to another version's digest.

    Verification is all or nothing per manifest. A summary is derived from every
    declared source together, so one missing source leaves nothing to check the
    remainder against, and the manifest stays an unverified claim.
    """

    recomputed: set[str] = set()
    for record in records:
        if record["kind"] != "run_manifest" or record["model_observations"] is None:
            continue
        declared = record["model_observations_declared"]
        digests = declared["evidence_digests"]
        sources = {
            source: digests[source] for source in EVIDENCE_SOURCES if digests[source] is not None
        }
        # A source the manifest declares but the summary carries no digest for
        # was never rebuilt into that summary, and this reader holds no bytes
        # the producer did not already read. Either way the manifest stays an
        # unverified claim rather than a rejected one.
        paths = record["declared_model_sources"]
        if set(paths) != set(sources):
            continue
        if not sources or not all(digest in supplied for digest in sources.values()):
            continue
        # Two source kinds naming one path are one file, so the producer read
        # one set of bytes for both. Declaring different digests for that one
        # path describes a run that could not have happened, so it is not
        # verifiable. Distinct paths holding identical bytes stay verifiable.
        if len(set(paths.values())) != len(paths) and len(set(sources.values())) != 1:
            continue
        with tempfile.TemporaryDirectory() as snapshot:
            root = Path(snapshot)
            manifest: dict[str, Any] = {}
            names: dict[str, str] = {}
            for source, digest in sources.items():
                name = names.setdefault(paths[source], f"{source}.jsonl")
                target = root / name
                # The snapshot is written from the bytes this process already
                # read and hashed, so the rescan cannot observe different bytes
                # and cannot exceed the bound those bytes already satisfied.
                target.write_bytes(supplied[digest])
                target.chmod(0o600)
                manifest[MODEL_SOURCE_MANIFEST_KEYS[source]] = name
            try:
                rebuilt = agent_log_manifest.compute_model_observations(root, manifest)
            except (OSError, ValueError, RecursionError, MemoryError) as exc:
                raise SummaryError(
                    f"supplied model evidence could not be rescanned: {exc}"
                ) from exc
        if not exact_json_equal(rebuilt, declared):
            raise SummaryError(
                "recomputing model observations from the supplied evidence does not "
                f"reproduce the summary in {record['path']}"
            )
        recomputed.add(record["identity"])
    return recomputed


def statement_scope(statement: dict[str, Any]) -> tuple[bool, tuple[str | None, str | None]]:
    """Return whether a statement names a comparable scope, and that scope.

    Two statements may only be called incompatible when both name the same
    confirmed execution scope. An unconfirmed scope is reported as such rather
    than silently compared against an unrelated turn or session.
    """

    turn_scoped = statement["source_kind"] in MODEL_TURN_SCOPED_KINDS
    turn_id = statement["turn_id"] if turn_scoped else None
    confirmed = turn_scoped and statement["session_digest"] is not None and turn_id is not None
    return confirmed, (statement["session_digest"], turn_id)


def summarize_model_evidence(
    records: list[dict[str, Any]], recomputed: set[str]
) -> dict[str, Any]:
    """Report model statements as observations, never as usage attribution."""

    manifests = [record for record in records if record["kind"] == "run_manifest"]
    with_observations = [record for record in manifests if record["model_observations"] is not None]

    coverage: list[dict[str, Any]] = []
    provider_context: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    identity_counts: list[dict[str, Any]] = []
    deduplicated: dict[tuple[Any, ...], dict[str, Any]] = {}

    for record in with_observations:
        observations = record["model_observations"]
        run_id = record["identity"]
        manifest_verification = "recomputed" if run_id in recomputed else "declared_only"
        for source in EVIDENCE_SOURCES:
            digest = observations["evidence_digests"][source]
            entry = observations["coverage"][source]
            coverage.append(
                {
                    "run_id": run_id,
                    "source": source,
                    "status": entry["status"],
                    "records_scanned": entry["records_scanned"],
                    "records_with_model_observation": entry["records_with_model_observation"],
                    "digest": digest,
                    "verification": manifest_verification,
                }
            )
        for field in MODEL_PROVIDER_CONTEXT_FIELDS:
            entry = observations["provider_context"][field]
            provider_context.append(
                {
                    "run_id": run_id,
                    "field": field,
                    "status": entry["status"],
                    "values": list(entry["values"]),
                    "verification": manifest_verification,
                }
            )
        diagnostics.append(
            {
                "run_id": run_id,
                "codes": list(observations["diagnostics"]),
                "truncated": observations["truncated"],
                "verification": manifest_verification,
            }
        )
        identity_counts.append(
            {
                "run_id": run_id,
                "session_digests": observations["identity_counts"]["session_digests"],
                "turn_ids": observations["identity_counts"]["turn_ids"],
                "verification": manifest_verification,
            }
        )

        for statement in observations["statements"]:
            source_digest = observations["evidence_digests"][statement["source"]]
            key = (
                source_digest,
                statement["source"],
                statement["record_line"],
                statement["source_line"],
                statement["source_kind"],
                statement["attribute"],
                statement["evidence_class"],
                statement["value"],
                statement["session_digest"],
                statement["turn_id"],
                statement["root_turn_id"],
            )
            existing = deduplicated.get(key)
            if existing is None:
                confirmed, scope = statement_scope(statement)
                deduplicated[key] = {
                    "attribute": statement["attribute"],
                    "evidence_class": statement["evidence_class"],
                    "value": statement["value"],
                    "source": statement["source"],
                    "source_kind": statement["source_kind"],
                    "source_digest": source_digest,
                    "record_line": statement["record_line"],
                    "source_line": statement["source_line"],
                    "session_digest": statement["session_digest"],
                    "turn_id": statement["turn_id"],
                    "root_turn_id": statement["root_turn_id"],
                    "scope_confirmed": confirmed,
                    "scope": scope,
                    "runs": {run_id},
                }
                continue
            existing["runs"].add(run_id)

    for entry in deduplicated.values():
        runs = sorted(entry.pop("runs"))
        entry["runs"] = [
            {
                "run_id": run_id,
                "verification": "recomputed" if run_id in recomputed else "declared_only",
            }
            for run_id in runs
        ]
        entry["run_ids"] = runs
        # The claim itself is verified once any manifest reproduced it from the
        # bytes it names. Each manifest still carries its own state, so a
        # partially supplied one is never presented as recomputed.
        entry["verification"] = (
            "recomputed"
            if any(item["verification"] == "recomputed" for item in entry["runs"])
            else "declared_only"
        )

    statements = sorted(
        deduplicated.values(),
        key=lambda item: (
            item["evidence_class"],
            item["attribute"],
            item["source"],
            item["source_digest"] or "",
            item["record_line"],
            item["source_line"] or 0,
            item["value"],
        ),
    )

    conflicts: list[dict[str, Any]] = []
    positions: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    scopes: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for statement in statements:
        positions.setdefault(
            (
                statement["source_digest"],
                statement["source"],
                statement["record_line"],
                statement["attribute"],
                statement["evidence_class"],
            ),
            [],
        ).append(statement)
        if statement["scope_confirmed"]:
            scopes.setdefault(
                (
                    statement["attribute"],
                    statement["evidence_class"],
                    statement["scope"][0],
                    statement["scope"][1],
                ),
                [],
            ).append(statement)

    def conflict_entry(kind: str, group: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "kind": kind,
            "attribute": group[0]["attribute"],
            "evidence_class": group[0]["evidence_class"],
            "session_digest": group[0]["session_digest"],
            "turn_id": group[0]["turn_id"],
            "values": sorted({item["value"] for item in group}),
            "records": sorted(
                {
                    (item["source"], item["source_digest"] or "", item["record_line"])
                    for item in group
                }
            ),
        }

    for group in positions.values():
        claims = {
            (
                item["value"],
                item["source_kind"],
                item["source_line"],
                item["session_digest"],
                item["turn_id"],
                item["root_turn_id"],
            )
            for item in group
        }
        if len(claims) > 1:
            # One record position in one set of bytes reported one claim. Two
            # differing claims mean at least one of them was not read from
            # those bytes, whichever scope each one names.
            conflicts.append(conflict_entry("record_position", group))
    for group in scopes.values():
        if len({item["value"] for item in group}) > 1:
            conflicts.append(conflict_entry("execution_scope", group))
    conflicts.sort(
        key=lambda item: (item["kind"], item["attribute"], item["evidence_class"], item["values"])
    )

    by_class: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for evidence_class in MODEL_EVIDENCE_CLASSES:
        attributes: dict[str, list[dict[str, Any]]] = {}
        for attribute in MODEL_ATTRIBUTES:
            selected = [
                item
                for item in statements
                if item["evidence_class"] == evidence_class and item["attribute"] == attribute
            ]
            values: dict[str, dict[str, Any]] = {}
            for item in selected:
                bucket = values.setdefault(
                    item["value"],
                    {
                        "value": item["value"],
                        "statement_count": 0,
                        "recomputed_statement_count": 0,
                        "source_kinds": [],
                        "scope_confirmed_count": 0,
                    },
                )
                bucket["statement_count"] += 1
                if item["verification"] == "recomputed":
                    bucket["recomputed_statement_count"] += 1
                if item["scope_confirmed"]:
                    bucket["scope_confirmed_count"] += 1
                if item["source_kind"] not in bucket["source_kinds"]:
                    bucket["source_kinds"].append(item["source_kind"])
            for bucket in values.values():
                bucket["source_kinds"].sort()
            if values:
                attributes[attribute] = sorted(values.values(), key=lambda item: item["value"])
        if attributes:
            by_class[evidence_class] = attributes

    return {
        "manifests_with_observations": len(with_observations),
        "manifests_without_observations": len(manifests) - len(with_observations),
        "coverage": coverage,
        "identity_counts": identity_counts,
        "provider_context": provider_context,
        "diagnostics": diagnostics,
        "statements": [
            {
                key: value
                for key, value in statement.items()
                if key not in ("scope", "scope_confirmed")
            }
            | {"scope_confirmed": statement["scope_confirmed"]}
            for statement in statements
        ],
        "values_by_evidence_class": by_class,
        "conflicts": conflicts,
        "unconfirmed_scope_statements": sum(
            1 for statement in statements if not statement["scope_confirmed"]
        ),
        "attribution_unavailable": list(MODEL_ATTRIBUTION_UNAVAILABLE),
    }


def build_report(
    records: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    recomputed: set[str],
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
        "model_evidence": summarize_model_evidence(records, recomputed),
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

    lines.append("## Model evidence")
    model = report["model_evidence"]
    lines.append(
        f"manifests: {model['manifests_with_observations']} with model observations, "
        f"{model['manifests_without_observations']} without"
    )
    if not model["coverage"]:
        lines.append("- no supplied run manifest carries model observations")
    for entry in model["coverage"]:
        lines.append(
            f"- {entry['run_id']} {entry['source']} coverage: {entry['status']} "
            f"{entry['records_with_model_observation']}/{entry['records_scanned']} records "
            f"({entry['verification']})"
        )
    for evidence_class in MODEL_EVIDENCE_CLASSES:
        attributes = model["values_by_evidence_class"].get(evidence_class)
        if not attributes:
            continue
        lines.append(f"- {evidence_class}:")
        for attribute in MODEL_ATTRIBUTES:
            for bucket in attributes.get(attribute, []):
                lines.append(
                    f"  - {attribute}={bucket['value']}: "
                    f"{bucket['statement_count']} statements, "
                    f"{bucket['recomputed_statement_count']} recomputed, "
                    f"{bucket['scope_confirmed_count']} scope confirmed "
                    f"[{' '.join(bucket['source_kinds'])}]"
                )
    # The aggregate above says what was observed; a reader also has to be able
    # to go back to the record that said it, in the default format and not only
    # in JSON.
    for statement in model["statements"]:
        runs = " ".join(
            f"{run['run_id']}:{run['verification']}" for run in statement["runs"]
        )
        scope = (
            f"{statement['session_digest']}/{statement['turn_id']}"
            if statement["scope_confirmed"]
            else "unconfirmed"
        )
        source_line = statement["source_line"]
        lines.append(
            f"- {statement['evidence_class']} {statement['attribute']}="
            f"{statement['value']} from {statement['source_kind']} in "
            f"{statement['source']} {statement['source_digest']} "
            f"record {statement['record_line']} "
            f"source_line={source_line if source_line is not None else 'not_observed'} "
            f"scope={scope} runs={runs}"
        )
    for entry in model["provider_context"]:
        if entry["status"] != "observed":
            continue
        lines.append(
            f"- {entry['run_id']} {entry['field']}: {' '.join(entry['values'])} "
            f"({entry['verification']})"
        )
    for entry in model["identity_counts"]:
        lines.append(
            f"- {entry['run_id']} identities: {entry['session_digests']} sessions, "
            f"{entry['turn_ids']} turns ({entry['verification']})"
        )
    if model["unconfirmed_scope_statements"]:
        lines.append(
            f"- {model['unconfirmed_scope_statements']} statements name no confirmed "
            "execution scope and are not compared"
        )
    for conflict in model["conflicts"]:
        lines.append(
            f"- conflict ({conflict['kind']}) {conflict['evidence_class']} "
            f"{conflict['attribute']}: {' vs '.join(conflict['values'])}"
        )
    for entry in model["diagnostics"]:
        if not entry["codes"] and not entry["truncated"]:
            continue
        codes = " ".join(entry["codes"]) or "none"
        lines.append(
            f"- {entry['run_id']} diagnostics: {codes} truncated={entry['truncated']} "
            f"({entry['verification']})"
        )
    lines.append("")
    lines.append("A model statement names an observed model, never its resource usage.")
    for name in model["attribution_unavailable"]:
        lines.append(f"- {name}: not attributable from these records")
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
        evidence, supplied = verify_evidence(records, list(args.evidence))
        recomputed = verify_model_observations(records, supplied)
        report = build_report(records, inventory, evidence, recomputed)
        try:
            if args.format == "json":
                rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            else:
                rendered = render_text(report)
        except (ValueError, OverflowError, RecursionError, MemoryError) as exc:
            raise SummaryError(f"report could not be rendered: {exc}") from exc
        try:
            encoded = rendered.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise SummaryError(f"report contains text that cannot be encoded: {exc}") from exc
        if len(encoded) > MAX_OUTPUT_BYTES:
            raise SummaryError(
                f"report exceeds the {MAX_OUTPUT_BYTES}-byte output bound; "
                "summarize fewer records per invocation"
            )
    except SummaryError as exc:
        print(f"summarize-agent-run failed: {exc}", file=sys.stderr)
        return 1
    # The encoded bytes were already checked, so writing them avoids failing
    # on whatever encoding the surrounding environment configured for stdout.
    stream = getattr(sys.stdout, "buffer", None)
    if stream is None:
        sys.stdout.write(rendered)
    else:
        sys.stdout.flush()
        stream.write(encoded)
        stream.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
