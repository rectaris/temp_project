#!/usr/bin/env python3
"""Validate hybrid agent log run manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_log_manifest  # noqa: E402


REQUIRED_KEYS = {
    "run_id",
    "created_at",
    "task",
    "plans",
    "raw_logs",
    "artifacts",
    "compressed_outputs",
    "redaction_report",
    "pinned",
    "transcript_log",
    "hook_event_log",
    "coverage",
    "missing_sources",
}

SOURCES = ("external_transcript", "codex_hooks")
SOURCE_FIELDS = {
    "external_transcript": "transcript_log",
    "codex_hooks": "hook_event_log",
}
TRANSCRIPT_REQUIRED_FIELDS = {
    "schema_version",
    "record_type",
    "created_at",
    "run_id",
    "turn_id",
    "role",
    "content",
    "metadata",
}
ALLOWED_ROLES = {"user", "assistant", "tool", "system_event"}
ALLOWED_REDACTION_STATUS = {
    "redacted",
    "automatic_redaction",
    "pending_review",
    "not_applicable",
}
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
# The model contract is owned by agent_log_manifest, which produces every
# summary this checker validates. Sourcing the constants from there keeps a
# newly supported diagnostic or bound from silently diverging into a false
# rejection of legitimate producer output.
MODEL_OBSERVATION_SCHEMA_VERSION = agent_log_manifest.MODEL_OBSERVATION_SCHEMA_VERSION
MODEL_ATTRIBUTES = agent_log_manifest.MODEL_ATTRIBUTES
MODEL_EVIDENCE_CLASSES = agent_log_manifest.MODEL_EVIDENCE_CLASSES
MODEL_SOURCE_KINDS = agent_log_manifest.MODEL_SOURCE_KINDS
MODEL_PROVIDER_CONTEXT_FIELDS = agent_log_manifest.MODEL_PROVIDER_CONTEXT_FIELDS
MODEL_DIAGNOSTIC_CODES = agent_log_manifest.MODEL_DIAGNOSTIC_CODES
MODEL_STATEMENT_FIELDS = {
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
MAX_MODEL_VALUE_LENGTH = agent_log_manifest.MAX_MODEL_VALUE_LENGTH
MAX_MODEL_STATEMENTS = agent_log_manifest.MAX_MODEL_STATEMENTS
MAX_MODEL_PROVIDER_VALUES = agent_log_manifest.MAX_MODEL_PROVIDER_VALUES
MAX_MODEL_DIAGNOSTICS = agent_log_manifest.MAX_MODEL_DIAGNOSTICS


class ValidationError(Exception):
    """Raised when a manifest is invalid."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc


def fail(message: str) -> None:
    print(f"agent log manifest check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def is_safe_relative_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def resolve_declared_path(run_dir: Path, value: Any, field: str) -> Path | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a relative path string or null")
    if not is_safe_relative_path(value):
        raise ValidationError(f"{field} must be a safe relative path: {value}")
    path = run_dir / value
    try:
        path.resolve().relative_to(run_dir.resolve())
    except ValueError as exc:
        raise ValidationError(f"{field} resolves outside the run directory: {value}") from exc
    return path


def repository_root(run_dir: Path) -> Path:
    for candidate in (run_dir, *run_dir.parents):
        if (candidate / ".git").exists():
            return candidate
    raise ValidationError(f"could not locate repository root for {run_dir}")


def resolve_repository_path(run_dir: Path, value: Any, field: str) -> Path:
    if not isinstance(value, str) or not is_safe_relative_path(value):
        raise ValidationError(f"{field} must be a safe repository-relative path string")
    root = repository_root(run_dir)
    path = root / value
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError(f"{field} resolves outside the repository: {value}") from exc
    return path


def expected_source_status(run_dir: Path, manifest: dict[str, Any], source: str) -> dict[str, Any]:
    field = SOURCE_FIELDS[source]
    declared = manifest.get(field)
    path = resolve_declared_path(run_dir, declared, field)
    if path is None:
        return {
            "present": False,
            "path": None,
            "status": "missing",
            "redaction_status": "not_applicable",
        }
    if path.is_file():
        return {
            "present": True,
            "path": declared,
            "status": "present",
            "redaction_status": None,
        }
    return {
        "present": False,
        "path": declared,
        "status": "path_missing",
        "redaction_status": "not_applicable",
    }


def validate_coverage_source(
    source: str,
    actual: Any,
    expected: dict[str, Any],
    require_redaction: bool,
) -> None:
    if not isinstance(actual, dict):
        raise ValidationError(f"coverage.{source} must be an object")
    for key in ("present", "path", "status", "redaction_status"):
        if key not in actual:
            raise ValidationError(f"coverage.{source} missing {key}")
    if actual["present"] is not expected["present"]:
        raise ValidationError(f"coverage.{source}.present inconsistent with declared path")
    if actual["path"] != expected["path"]:
        raise ValidationError(f"coverage.{source}.path inconsistent with manifest")
    if actual["status"] != expected["status"]:
        raise ValidationError(f"coverage.{source}.status must be {expected['status']}")
    redaction_status = actual["redaction_status"]
    if redaction_status not in ALLOWED_REDACTION_STATUS:
        raise ValidationError(f"coverage.{source}.redaction_status has unsupported value: {redaction_status}")
    if require_redaction and expected["present"] and redaction_status == "not_applicable":
        raise ValidationError(f"coverage.{source}.redaction_status must describe reviewed or pending redaction")


def validate_declared_paths(run_dir: Path, manifest: dict[str, Any]) -> None:
    raw_logs = manifest.get("raw_logs")
    if not isinstance(raw_logs, list):
        raise ValidationError("raw_logs must be a list")
    for index, rel in enumerate(raw_logs):
        path = resolve_declared_path(run_dir, rel, f"raw_logs[{index}]")
        if path is not None and not path.is_file():
            raise ValidationError(f"raw log path is declared but missing: {rel}")
    for field in ("transcript_log", "hook_event_log"):
        path = resolve_declared_path(run_dir, manifest.get(field), field)
        if path is not None and not path.is_file():
            raise ValidationError(f"{field} is declared but missing: {manifest[field]}")
    compressed_outputs = manifest.get("compressed_outputs")
    if not isinstance(compressed_outputs, list):
        raise ValidationError("compressed_outputs must be a list")
    for index, rel in enumerate(compressed_outputs):
        path = resolve_declared_path(run_dir, rel, f"compressed_outputs[{index}]")
        if path is None or not path.is_file():
            raise ValidationError(f"compressed output path is declared but missing: {rel}")
    for field in ("plans", "artifacts"):
        values = manifest.get(field)
        if not isinstance(values, list):
            raise ValidationError(f"{field} must be a list")
        for index, rel in enumerate(values):
            path = resolve_repository_path(run_dir, rel, f"{field}[{index}]")
            if not path.exists():
                raise ValidationError(f"{field}[{index}] is declared but missing: {rel}")
    redaction_report = resolve_declared_path(run_dir, manifest.get("redaction_report"), "redaction_report")
    if redaction_report is None or not redaction_report.is_file():
        raise ValidationError(f"redaction_report is declared but missing: {manifest['redaction_report']}")


def validate_transcript(run_dir: Path, manifest: dict[str, Any]) -> None:
    path = resolve_declared_path(run_dir, manifest.get("transcript_log"), "transcript_log")
    if path is None or not path.is_file():
        return
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except Exception as exc:
            raise ValidationError(f"transcript_log line {lineno} is invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise ValidationError(f"transcript_log line {lineno} must be an object")
        missing = sorted(TRANSCRIPT_REQUIRED_FIELDS - set(record))
        if missing:
            raise ValidationError(f"transcript_log line {lineno} missing fields: {missing}")
        if record["role"] not in ALLOWED_ROLES:
            raise ValidationError(f"transcript_log line {lineno} has unsupported role: {record['role']}")
        if record["run_id"] != manifest.get("run_id"):
            raise ValidationError(f"transcript_log line {lineno} run_id does not match manifest")
        if record["record_type"] == "review_packet_start":
            metadata = record["metadata"]
            if not isinstance(metadata, dict) or set(metadata) < {
                "review_packet_digest", "inherited_turns", "session_id"
            }:
                raise ValidationError(
                    f"transcript_log line {lineno} has incomplete review packet observation"
                )
            packet_digest = metadata["review_packet_digest"]
            if (
                not isinstance(packet_digest, str)
                or len(packet_digest) != 71
                or not packet_digest.startswith("sha256:")
            ):
                raise ValidationError(
                    f"transcript_log line {lineno} has invalid review packet digest"
                )
            if (
                isinstance(metadata["inherited_turns"], bool)
                or not isinstance(metadata["inherited_turns"], int)
                or metadata["inherited_turns"] < 0
                or not isinstance(metadata["session_id"], str)
                or not metadata["session_id"]
            ):
                raise ValidationError(
                    f"transcript_log line {lineno} has invalid review turn observation"
                )


def validate_hook_events(run_dir: Path, manifest: dict[str, Any]) -> None:
    path = resolve_declared_path(run_dir, manifest.get("hook_event_log"), "hook_event_log")
    if path is None or not path.is_file():
        return
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except Exception as exc:
            raise ValidationError(f"hook_event_log line {lineno} is invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise ValidationError(f"hook_event_log line {lineno} must be an object")
        if record.get("event") != "ReviewPacketStart":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            raise ValidationError(
                f"hook_event_log line {lineno} review packet payload must be an object"
            )
        packet_digest = payload.get("review_packet_digest")
        inherited_turns = payload.get("inherited_turns")
        session_id = payload.get("session_id")
        if (
            not isinstance(packet_digest, str)
            or len(packet_digest) != 71
            or not packet_digest.startswith("sha256:")
            or isinstance(inherited_turns, bool)
            or not isinstance(inherited_turns, int)
            or inherited_turns < 0
            or not isinstance(session_id, str)
            or not session_id
        ):
            raise ValidationError(
                f"hook_event_log line {lineno} has invalid review turn observation"
            )


def validate_resource_observations(value: Any, run_dir: Path, manifest: dict[str, Any]) -> None:
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "root_session_identity", "evidence_digests", "metrics"
    }:
        raise ValidationError("resource_observations has an invalid exact field shape")
    if value["schema_version"] != 1:
        raise ValidationError("resource_observations has an unsupported schema version")
    evidence_digests = value["evidence_digests"]
    if not isinstance(evidence_digests, dict) or set(evidence_digests) != {
        "external_transcript", "codex_hooks"
    }:
        raise ValidationError("evidence_digests has an invalid exact field shape")
    source_paths = {
        "external_transcript": manifest.get("transcript_log"),
        "codex_hooks": manifest.get("hook_event_log"),
    }
    for source_key, declared_digest in evidence_digests.items():
        if declared_digest is None:
            continue
        if not isinstance(declared_digest, str) or not declared_digest.startswith("sha256:") or len(declared_digest) != 71:
            raise ValidationError(f"evidence_digests.{source_key} must be a SHA-256 digest or null")
        source_rel = source_paths.get(source_key)
        if not isinstance(source_rel, str):
            raise ValidationError(f"evidence_digests.{source_key} is set but {source_key} source path is not declared")
        source_file = run_dir / source_rel
        if not source_file.is_file():
            raise ValidationError(f"evidence_digests.{source_key} is set but source file is missing")
        actual = "sha256:" + hashlib.sha256(source_file.read_bytes()).hexdigest()
        if actual != declared_digest:
            raise ValidationError(f"evidence_digests.{source_key} does not match recomputed source file digest")
    identity = value["root_session_identity"]
    if not isinstance(identity, dict) or set(identity) != {"status", "digest"}:
        raise ValidationError("root_session_identity has an invalid exact field shape")
    if identity["status"] == "observed":
        digest = identity["digest"]
        if not isinstance(digest, str) or len(digest) != 71 or not digest.startswith("sha256:"):
            raise ValidationError("observed root_session_identity requires a SHA-256 digest")
        has_bound_evidence = any(
            isinstance(evidence_digests.get(k), str) for k in ("external_transcript", "codex_hooks")
        )
        if not has_bound_evidence:
            raise ValidationError("observed root_session_identity requires at least one bound evidence digest")
    elif identity != {"status": "not_observed", "digest": None}:
        raise ValidationError("unavailable root_session_identity must remain not_observed")
    metrics = value["metrics"]
    if not isinstance(metrics, dict) or set(metrics) != RESOURCE_METRICS:
        raise ValidationError("resource observation metrics have an invalid exact field shape")
    for name, observation in metrics.items():
        if not isinstance(observation, dict) or set(observation) != {
            "status", "value", "provenance"
        }:
            raise ValidationError(f"resource metric {name} has an invalid exact field shape")
        if observation["status"] == "observed":
            metric_value = observation["value"]
            if isinstance(metric_value, bool) or not isinstance(metric_value, int) or metric_value < 0:
                raise ValidationError(f"resource metric {name} must be a nonnegative integer")
            expected = "provider" if name.startswith("provider_") else "deterministic_proxy"
            if observation["provenance"] != expected:
                raise ValidationError(f"resource metric {name} has invalid provenance")
            has_bound = any(
                isinstance(evidence_digests.get(k), str) for k in ("external_transcript", "codex_hooks")
            )
            if not has_bound:
                raise ValidationError(f"observed resource metric {name} requires at least one bound evidence digest")
        elif observation != {
            "status": "not_observed",
            "value": None,
            "provenance": "not_observed",
        }:
            raise ValidationError(f"unavailable resource metric {name} must remain not_observed")


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 71 and value.startswith("sha256:")


def bounded_identifier(value: Any) -> bool:
    return value is None or (
        isinstance(value, str) and bool(value) and len(value) <= MAX_MODEL_VALUE_LENGTH
    )


def require_recomputed_model_observations(
    value: dict[str, Any], run_dir: Path, manifest: dict[str, Any]
) -> None:
    """Require the summary to be exactly what the declared sources produce.

    A matching file digest proves only that the bytes are unchanged. It says
    nothing about whether the summary reports what those bytes contain, so the
    summary is rebuilt from the sources and compared as a whole. That rejects a
    forged statement, a fabricated provider value and an inflated count, and it
    equally rejects a summary that silently omits evidence the sources hold.
    """

    try:
        expected = agent_log_manifest.compute_model_observations(run_dir, manifest)
    except Exception as error:  # pragma: no cover - defensive
        raise ValidationError(
            f"model_observations could not be recomputed from its sources: {error}"
        ) from error
    if expected is None:
        raise ValidationError("model_observations is present without any declared source file")
    if value != expected:
        raise ValidationError(
            "model_observations does not match the summary recomputed from its source files"
        )


def validate_model_observations(value: Any, run_dir: Path, manifest: dict[str, Any]) -> None:
    """Validate the optional model observation summary against its own version.

    This object is versioned separately from `resource_observations` and adds
    nothing to it. A model statement is never a token count, so nothing here
    may be read as usage attribution.
    """

    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "evidence_digests",
        "coverage",
        "statements",
        "provider_context",
        "identity_counts",
        "diagnostics",
        "truncated",
    }:
        raise ValidationError("model_observations has an invalid exact field shape")
    if value["schema_version"] != MODEL_OBSERVATION_SCHEMA_VERSION:
        raise ValidationError("model_observations has an unsupported schema version")
    if not isinstance(value["truncated"], bool):
        raise ValidationError("model_observations.truncated must be a boolean")
    evidence_digests = value["evidence_digests"]
    if not isinstance(evidence_digests, dict) or set(evidence_digests) != set(SOURCES):
        raise ValidationError("model_observations.evidence_digests has an invalid exact field shape")
    source_paths = {
        "external_transcript": manifest.get("transcript_log"),
        "codex_hooks": manifest.get("hook_event_log"),
    }
    for source_key, declared_digest in evidence_digests.items():
        if declared_digest is None:
            continue
        if not is_sha256(declared_digest):
            raise ValidationError(
                f"model_observations.evidence_digests.{source_key} must be a SHA-256 digest or null"
            )
        source_rel = source_paths.get(source_key)
        if not isinstance(source_rel, str):
            raise ValidationError(
                f"model_observations.evidence_digests.{source_key} is set but the source path is not declared"
            )
        source_file = run_dir / source_rel
        if not source_file.is_file():
            raise ValidationError(
                f"model_observations.evidence_digests.{source_key} is set but the source file is missing"
            )
        actual = "sha256:" + hashlib.sha256(source_file.read_bytes()).hexdigest()
        if actual != declared_digest:
            raise ValidationError(
                f"model_observations.evidence_digests.{source_key} does not match recomputed source file digest"
            )
    coverage = value["coverage"]
    if not isinstance(coverage, dict) or set(coverage) != set(SOURCES):
        raise ValidationError("model_observations.coverage has an invalid exact field shape")
    for source_key, entry in coverage.items():
        if not isinstance(entry, dict) or set(entry) != {
            "status",
            "records_scanned",
            "records_with_model_observation",
        }:
            raise ValidationError(
                f"model_observations.coverage.{source_key} has an invalid exact field shape"
            )
        if entry["status"] not in {"present", "missing", "unreadable"}:
            raise ValidationError(
                f"model_observations.coverage.{source_key}.status has an unsupported value"
            )
        for count_key in ("records_scanned", "records_with_model_observation"):
            count = entry[count_key]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValidationError(
                    f"model_observations.coverage.{source_key}.{count_key} must be a nonnegative integer"
                )
        if entry["records_with_model_observation"] > entry["records_scanned"]:
            raise ValidationError(
                f"model_observations.coverage.{source_key} reports more observations than records"
            )
        if entry["status"] == "present" and not is_sha256(evidence_digests.get(source_key)):
            raise ValidationError(
                f"model_observations.coverage.{source_key} is present without a bound evidence digest"
            )
        if entry["status"] != "present" and (
            entry["records_scanned"] or entry["records_with_model_observation"]
        ):
            raise ValidationError(
                f"model_observations.coverage.{source_key} counts records without a present source"
            )
    statements = value["statements"]
    if not isinstance(statements, list):
        raise ValidationError("model_observations.statements must be a list")
    if len(statements) > MAX_MODEL_STATEMENTS:
        raise ValidationError("model_observations.statements exceeds the declared bound")
    if value["truncated"] and len(statements) != MAX_MODEL_STATEMENTS:
        raise ValidationError("a truncated statement list must hold exactly the declared bound")
    seen: set[tuple[Any, ...]] = set()
    for index, statement in enumerate(statements):
        validate_model_statement(index, statement, evidence_digests, coverage)
        key = (
            statement["source"],
            statement["record_line"],
            statement["attribute"],
            statement["evidence_class"],
        )
        if key in seen:
            raise ValidationError(
                f"model_observations.statements[{index}] duplicates an earlier source record reference"
            )
        seen.add(key)
    provider_context = value["provider_context"]
    if not isinstance(provider_context, dict) or set(provider_context) != set(
        MODEL_PROVIDER_CONTEXT_FIELDS
    ):
        raise ValidationError("model_observations.provider_context has an invalid exact field shape")
    for field, entry in provider_context.items():
        if not isinstance(entry, dict) or set(entry) != {"status", "values"}:
            raise ValidationError(
                f"model_observations.provider_context.{field} has an invalid exact field shape"
            )
        values = entry["values"]
        if not isinstance(values, list) or len(values) > MAX_MODEL_PROVIDER_VALUES:
            raise ValidationError(
                f"model_observations.provider_context.{field}.values is not a bounded list"
            )
        if any(not bounded_identifier(item) or item is None for item in values):
            raise ValidationError(
                f"model_observations.provider_context.{field}.values holds an unsupported value"
            )
        if len(set(values)) != len(values):
            raise ValidationError(
                f"model_observations.provider_context.{field}.values repeats a value"
            )
        expected_status = "observed" if values else "not_observed"
        if entry["status"] != expected_status:
            raise ValidationError(
                f"model_observations.provider_context.{field}.status must be {expected_status}"
            )
        if values and not any(is_sha256(digest) for digest in evidence_digests.values()):
            raise ValidationError(
                f"model_observations.provider_context.{field} requires at least one bound evidence digest"
            )
    identity_counts = value["identity_counts"]
    if not isinstance(identity_counts, dict) or set(identity_counts) != {
        "session_digests",
        "turn_ids",
    }:
        raise ValidationError("model_observations.identity_counts has an invalid exact field shape")
    expected_counts = {
        "session_digests": len(
            {item["session_digest"] for item in statements if item["session_digest"]}
        ),
        "turn_ids": len({item["turn_id"] for item in statements if item["turn_id"]}),
    }
    for count_key, expected in expected_counts.items():
        count = identity_counts[count_key]
        if isinstance(count, bool) or not isinstance(count, int) or count != expected:
            raise ValidationError(
                f"model_observations.identity_counts.{count_key} must be {expected}"
            )
    diagnostics = value["diagnostics"]
    if not isinstance(diagnostics, list) or len(diagnostics) > MAX_MODEL_DIAGNOSTICS:
        raise ValidationError("model_observations.diagnostics is not a bounded list")
    if any(code not in MODEL_DIAGNOSTIC_CODES for code in diagnostics):
        raise ValidationError("model_observations.diagnostics holds an unsupported code")
    if len(set(diagnostics)) != len(diagnostics):
        raise ValidationError("model_observations.diagnostics repeats a code")
    require_recomputed_model_observations(value, run_dir, manifest)


def validate_model_statement(
    index: int,
    statement: Any,
    evidence_digests: dict[str, Any],
    coverage: dict[str, Any],
) -> None:
    label = f"model_observations.statements[{index}]"
    if not isinstance(statement, dict) or set(statement) != MODEL_STATEMENT_FIELDS:
        raise ValidationError(f"{label} has an invalid exact field shape")
    if statement["source"] not in SOURCES:
        raise ValidationError(f"{label}.source names an unsupported evidence source")
    if not is_sha256(evidence_digests.get(statement["source"])):
        raise ValidationError(f"{label} requires a bound evidence digest for its source")
    if coverage[statement["source"]]["status"] != "present":
        raise ValidationError(f"{label} references a source that is not present")
    record_line = statement["record_line"]
    if isinstance(record_line, bool) or not isinstance(record_line, int) or record_line < 1:
        raise ValidationError(f"{label}.record_line must be a positive integer")
    source_line = statement["source_line"]
    if source_line is not None and (
        isinstance(source_line, bool) or not isinstance(source_line, int) or source_line < 1
    ):
        raise ValidationError(f"{label}.source_line must be a positive integer or null")
    if statement["source_kind"] not in MODEL_SOURCE_KINDS:
        raise ValidationError(f"{label}.source_kind names an unsupported source shape")
    if statement["attribute"] not in MODEL_ATTRIBUTES:
        raise ValidationError(f"{label}.attribute names an unsupported model attribute")
    if statement["evidence_class"] not in MODEL_EVIDENCE_CLASSES:
        raise ValidationError(f"{label}.evidence_class names an unsupported evidence class")
    model_value = statement["value"]
    if (
        not isinstance(model_value, str)
        or not model_value
        or len(model_value) > MAX_MODEL_VALUE_LENGTH
    ):
        raise ValidationError(f"{label}.value must be a bounded non-empty string")
    if statement["session_digest"] is not None and not is_sha256(statement["session_digest"]):
        raise ValidationError(f"{label}.session_digest must be a SHA-256 digest or null")
    for field in ("turn_id", "root_turn_id"):
        if not bounded_identifier(statement[field]):
            raise ValidationError(f"{label}.{field} must be a bounded string or null")


def validate_manifest(path: Path, require_transcript: bool = False, require_hooks: bool = False) -> list[str]:
    manifest = load_json(path)
    if not isinstance(manifest, dict):
        raise ValidationError(f"{path}: manifest must be an object")
    missing = sorted(REQUIRED_KEYS - set(manifest))
    if missing:
        raise ValidationError(f"{path}: missing required keys: {missing}")
    if not isinstance(manifest.get("run_id"), str) or not manifest["run_id"]:
        raise ValidationError("run_id must be a non-empty string")
    if path.parent.name != manifest["run_id"]:
        raise ValidationError("run_id must match the run directory name")
    if not isinstance(manifest.get("pinned"), bool):
        raise ValidationError("pinned must be a boolean")
    run_dir = path.parent
    validate_declared_paths(run_dir, manifest)
    coverage = manifest.get("coverage")
    if not isinstance(coverage, dict):
        raise ValidationError("coverage must be an object")
    computed_missing_sources: list[str] = []
    for source in SOURCES:
        expected = expected_source_status(run_dir, manifest, source)
        if not expected["present"]:
            computed_missing_sources.append(source)
        validate_coverage_source(
            source,
            coverage.get(source),
            expected,
            require_redaction=source == "external_transcript",
        )
    actual_missing_sources = manifest.get("missing_sources")
    if not isinstance(actual_missing_sources, list):
        raise ValidationError("missing_sources must be a list")
    expected_missing_sources = sorted(computed_missing_sources)
    if sorted(actual_missing_sources) != expected_missing_sources:
        raise ValidationError(f"missing_sources must be {expected_missing_sources}")
    validate_transcript(run_dir, manifest)
    validate_hook_events(run_dir, manifest)
    if "resource_observations" in manifest:
        validate_resource_observations(manifest["resource_observations"], run_dir, manifest)
    if "model_observations" in manifest:
        validate_model_observations(manifest["model_observations"], run_dir, manifest)
    if require_transcript and "external_transcript" in computed_missing_sources:
        raise ValidationError("external transcript coverage is required but missing")
    if require_hooks and "codex_hooks" in computed_missing_sources:
        raise ValidationError("Codex hook coverage is required but missing")
    return computed_missing_sources


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records), encoding="utf-8")


def source_coverage(path: str | None, present: bool, status: str, redaction_status: str) -> dict[str, Any]:
    return {
        "present": present,
        "path": path,
        "status": status,
        "redaction_status": redaction_status,
    }


def sample_manifest(run_dir: Path, transcript: bool, hooks: bool) -> dict[str, Any]:
    raw_logs: list[str] = []
    transcript_path = "raw/transcript.jsonl" if transcript else None
    hook_path = "raw/events.jsonl" if hooks else None
    if transcript_path:
        raw_logs.append(transcript_path)
    if hook_path:
        raw_logs.append(hook_path)
    missing_sources = []
    if not transcript:
        missing_sources.append("external_transcript")
    if not hooks:
        missing_sources.append("codex_hooks")
    evidence_digests: dict[str, str | None] = {
        "external_transcript": None,
        "codex_hooks": None,
    }
    if transcript and (run_dir / "raw/transcript.jsonl").is_file():
        evidence_digests["external_transcript"] = _file_digest(run_dir / "raw/transcript.jsonl")
    if hooks and (run_dir / "raw/events.jsonl").is_file():
        evidence_digests["codex_hooks"] = _file_digest(run_dir / "raw/events.jsonl")
    return {
        "run_id": run_dir.name,
        "created_at": "2026-06-30T00:00:00Z",
        "task": "self test",
        "plans": [],
        "raw_logs": raw_logs,
        "artifacts": [],
        "compressed_outputs": [],
        "redaction_report": "redaction-report.md",
        "pinned": False,
        "transcript_log": transcript_path,
        "hook_event_log": hook_path,
        "coverage": {
            "external_transcript": source_coverage(
                transcript_path,
                transcript,
                "present" if transcript else "missing",
                "redacted" if transcript else "not_applicable",
            ),
            "codex_hooks": source_coverage(
                hook_path,
                hooks,
                "present" if hooks else "missing",
                "automatic_redaction" if hooks else "not_applicable",
            ),
        },
        "missing_sources": missing_sources,
        "resource_observations": {
            "schema_version": 1,
            "root_session_identity": {"status": "not_observed", "digest": None},
            "evidence_digests": evidence_digests,
            "metrics": {
                metric: {
                    "status": "not_observed",
                    "value": None,
                    "provenance": "not_observed",
                }
                for metric in RESOURCE_METRICS
            },
        },
    }


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def create_run(root: Path, name: str, transcript: bool, hooks: bool) -> Path:
    run_dir = root / name
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    if transcript:
        write_jsonl(
            raw_dir / "transcript.jsonl",
            [
                {
                    "schema_version": 1,
                    "record_type": "message",
                    "created_at": "2026-06-30T00:00:00Z",
                    "run_id": name,
                    "turn_id": "turn-1",
                    "role": "user",
                    "content": "hello",
                    "metadata": {},
                }
            ],
        )
    if hooks:
        write_jsonl(raw_dir / "events.jsonl", [{"schema_version": 1, "event": "Stop"}])
    (run_dir / "redaction-report.md").write_text("# Redaction Report\n", encoding="utf-8")
    write_json(run_dir / "manifest.json", sample_manifest(run_dir, transcript, hooks))
    return run_dir / "manifest.json"


def expect_failure(path: Path, **kwargs: Any) -> None:
    try:
        validate_manifest(path, **kwargs)
    except ValidationError:
        return
    raise AssertionError(f"expected validation failure for {path}")


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        both = create_run(root, "both", transcript=True, hooks=True)
        neither = create_run(root, "neither", transcript=False, hooks=False)
        transcript_only = create_run(root, "transcript-only", transcript=True, hooks=False)
        hooks_only = create_run(root, "hooks-only", transcript=False, hooks=True)
        validate_manifest(both)
        validate_manifest(neither)
        validate_manifest(transcript_only)
        validate_manifest(hooks_only)
        expect_failure(transcript_only, require_hooks=True)
        expect_failure(hooks_only, require_transcript=True)

        missing_path = create_run(root, "missing-path", transcript=True, hooks=True)
        (missing_path.parent / "raw/events.jsonl").unlink()
        expect_failure(missing_path)

        inconsistent = create_run(root, "inconsistent", transcript=True, hooks=False)
        manifest = load_json(inconsistent)
        manifest["missing_sources"] = []
        write_json(inconsistent, manifest)
        expect_failure(inconsistent)

        bad_transcript = create_run(root, "bad-transcript", transcript=True, hooks=True)
        write_jsonl(bad_transcript.parent / "raw/transcript.jsonl", [{"role": "unexpected"}])
        manifest = load_json(bad_transcript)
        manifest["resource_observations"]["evidence_digests"]["external_transcript"] = _file_digest(
            bad_transcript.parent / "raw/transcript.jsonl"
        )
        write_json(bad_transcript, manifest)
        expect_failure(bad_transcript)

        fabricated_identity = create_run(root, "fabricated-identity", transcript=False, hooks=False)
        manifest = load_json(fabricated_identity)
        manifest["resource_observations"]["root_session_identity"] = {
            "status": "observed",
            "digest": "sha256:" + "a" * 64,
        }
        write_json(fabricated_identity, manifest)
        expect_failure(fabricated_identity)

        mismatched_digest = create_run(root, "mismatched-digest", transcript=True, hooks=False)
        manifest = load_json(mismatched_digest)
        manifest["resource_observations"]["evidence_digests"]["external_transcript"] = "sha256:" + "b" * 64
        write_json(mismatched_digest, manifest)
        expect_failure(mismatched_digest)

        legacy = create_run(root, "legacy-model", transcript=True, hooks=False)
        validate_manifest(legacy)

        model_run = create_run(root, "model-evidence", transcript=True, hooks=False)
        write_json(model_run, with_model_observations(load_json(model_run), model_run.parent))
        validate_manifest(model_run)

        for label, mutate in (
            ("model-unbound", _drop_model_evidence_digest),
            ("model-stale", _stale_model_evidence_digest),
            ("model-duplicate", _duplicate_model_statement),
            ("model-unknown-version", _unknown_model_version),
            ("model-bad-count", _wrong_model_identity_count),
            ("model-outside-source", _model_statement_outside_source),
            ("model-bad-class", _model_statement_bad_class),
            ("model-forged-value", _forged_model_statement_value),
            ("model-forged-scope", _forged_model_statement_scope),
            ("model-forged-source-line", _forged_model_statement_source_line),
            ("model-fabricated-provider", _fabricated_model_provider_value),
            ("model-inflated-coverage", _inflated_model_coverage),
            ("model-false-truncation", _false_model_truncation),
        ):
            case = create_run(root, label, transcript=True, hooks=False)
            manifest = with_model_observations(load_json(case), case.parent)
            mutate(manifest)
            write_json(case, manifest)
            expect_failure(case)


def with_model_observations(manifest: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Write one source record and attach the summary that record produces.

    The summary comes from the producer rather than from a hand-written
    literal, so every mutator below is tested against real producer output and
    the positive case cannot pass because the fixture happened to agree with a
    weaker rule.
    """

    observation = agent_log_manifest.build_model_observation(
        "transcript_turn_context",
        runtime_model="example-model",
        model_provider="example-provider",
        session_id="session-1",
        turn_id="turn-1",
    )
    transcript = run_dir / "raw/transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record_type": "system_event",
                "created_at": "2026-09-01T00:00:00Z",
                "run_id": manifest["run_id"],
                "turn_id": "turn-1",
                "role": "system_event",
                "content": "",
                "metadata": {
                    "source_line": 4,
                    "source_type": "turn_context",
                    "payload_type": "turn_context",
                    "model_observation": observation,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    resource = manifest.get("resource_observations")
    if isinstance(resource, dict) and isinstance(resource.get("evidence_digests"), dict):
        resource["evidence_digests"]["external_transcript"] = _file_digest(transcript)
    manifest["model_observations"] = agent_log_manifest.compute_model_observations(
        run_dir, manifest
    )
    return manifest


def _forged_model_statement_value(manifest: dict[str, Any]) -> None:
    manifest["model_observations"]["statements"][0]["value"] = "forged-model"


def _forged_model_statement_scope(manifest: dict[str, Any]) -> None:
    manifest["model_observations"]["statements"][0]["turn_id"] = "turn-forged"
    manifest["model_observations"]["identity_counts"]["turn_ids"] = 1


def _forged_model_statement_source_line(manifest: dict[str, Any]) -> None:
    manifest["model_observations"]["statements"][0]["source_line"] = 999


def _fabricated_model_provider_value(manifest: dict[str, Any]) -> None:
    manifest["model_observations"]["provider_context"]["cli_version"] = {
        "status": "observed",
        "values": ["9.9.9"],
    }


def _inflated_model_coverage(manifest: dict[str, Any]) -> None:
    manifest["model_observations"]["coverage"]["external_transcript"]["records_scanned"] = 9


def _false_model_truncation(manifest: dict[str, Any]) -> None:
    manifest["model_observations"]["truncated"] = True


def _drop_model_evidence_digest(manifest: dict[str, Any]) -> None:
    manifest["model_observations"]["evidence_digests"]["external_transcript"] = None


def _stale_model_evidence_digest(manifest: dict[str, Any]) -> None:
    manifest["model_observations"]["evidence_digests"]["external_transcript"] = "sha256:" + "d" * 64


def _duplicate_model_statement(manifest: dict[str, Any]) -> None:
    statements = manifest["model_observations"]["statements"]
    statements.append(json.loads(json.dumps(statements[0])))


def _unknown_model_version(manifest: dict[str, Any]) -> None:
    manifest["model_observations"]["schema_version"] = 2


def _wrong_model_identity_count(manifest: dict[str, Any]) -> None:
    manifest["model_observations"]["identity_counts"]["turn_ids"] = 5


def _model_statement_outside_source(manifest: dict[str, Any]) -> None:
    manifest["model_observations"]["statements"][0]["record_line"] = 99


def _model_statement_bad_class(manifest: dict[str, Any]) -> None:
    manifest["model_observations"]["statements"][0]["evidence_class"] = "provider_confirmed"


def discover_manifests(paths: list[str]) -> list[Path]:
    if paths:
        return [Path(path) for path in paths]
    root = Path.cwd() / ".agent-logs"
    if not root.exists():
        return []
    return sorted(root.glob("*/manifest.json"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifests", nargs="*")
    parser.add_argument("--require-transcript", action="store_true")
    parser.add_argument("--require-hooks", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        try:
            self_test()
        except Exception as exc:
            fail(f"self-test failed: {exc}")
        print("agent log manifest self-test passed")
        return 0

    manifests = discover_manifests(args.manifests)
    if not manifests:
        print("no agent log manifests found")
        return 0
    try:
        for manifest in manifests:
            missing_sources = validate_manifest(
                manifest,
                require_transcript=args.require_transcript,
                require_hooks=args.require_hooks,
            )
            if missing_sources:
                print(f"{manifest}: warning: missing sources: {', '.join(missing_sources)}")
            else:
                print(f"{manifest}: ok")
    except ValidationError as exc:
        fail(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
