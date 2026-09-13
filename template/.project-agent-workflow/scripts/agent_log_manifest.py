#!/usr/bin/env python3
"""Create and update generated-project agent log manifests."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRANSCRIPT_REL = "raw/transcript.jsonl"
HOOK_REL = "raw/events.jsonl"
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
MODEL_OBSERVATION_SCHEMA_VERSION = 1
MODEL_ATTRIBUTES = ("model", "reasoning_effort")
MODEL_EVIDENCE_CLASSES = ("requested", "runtime_reported", "provider_reported")
MODEL_SOURCE_KINDS = (
    "transcript_turn_context",
    "transcript_session_meta",
    "hook_event_metadata",
)
MODEL_SCOPE_FIELDS = ("session_id", "turn_id", "root_turn_id")
MODEL_PROVIDER_CONTEXT_FIELDS = ("model_provider", "cli_version")
MODEL_OBSERVATION_KEYS = (
    "schema_version",
    "source_kind",
    "attributes",
    "execution_scope",
    "provider_context",
    "diagnostics",
)
# Each source kind may report only what its own shape can actually observe.
# A transcript `session_meta` record describes the session, not a turn, so it
# carries no runtime statement; a hook event sees no provider name. Declaring
# the capability once lets the producer refuse to invent a slot and lets the
# reader reject a stored record that claims evidence its source cannot hold.
MODEL_SOURCE_CAPABILITIES: dict[str, dict[str, tuple[str, ...] | str]] = {
    "transcript_turn_context": {
        "container": "metadata",
        "record_type": "turn_context",
        "evidence_classes": ("runtime_reported",),
        "provider_context": (),
        "execution_scope": MODEL_SCOPE_FIELDS,
    },
    "transcript_session_meta": {
        "container": "metadata",
        "record_type": "session_meta",
        "evidence_classes": (),
        "provider_context": MODEL_PROVIDER_CONTEXT_FIELDS,
        "execution_scope": ("session_id",),
    },
    "hook_event_metadata": {
        "container": "payload",
        "record_type": "",
        "evidence_classes": ("runtime_reported",),
        "provider_context": (),
        "execution_scope": ("session_id",),
    },
}
MODEL_DIAGNOSTIC_CODES = (
    "malformed_value",
    "unsupported_type",
    "value_too_long",
    "unknown_source_shape",
    "statements_truncated",
    "source_unreadable",
    "source_too_large",
    "record_unparsable",
    "redacted_value",
    "provider_context_truncated",
)
MODEL_SOURCE_KEYS = ("external_transcript", "codex_hooks")
MAX_MODEL_VALUE_LENGTH = 128
MAX_MODEL_STATEMENTS = 64
MAX_MODEL_PROVIDER_VALUES = 8
MAX_MODEL_DIAGNOSTICS = len(MODEL_DIAGNOSTIC_CODES)
MAX_MODEL_SOURCE_BYTES = 8 * 1024 * 1024
REDACTION_MARKER = "[REDACTED]"
MODEL_VALUE_RE = re.compile(r"\A[^\x00-\x1f\x7f]+\Z")
SECRET_VALUE_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|xox[baprs]-[A-Za-z0-9-]{16,})"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


@contextmanager
def manifest_lock(run_dir: Path):
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / ".manifest.lock").open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def relative_to_run(run_dir: Path, path: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(run_dir.resolve()))
    except ValueError:
        return None


def source_coverage(path: str | None, present: bool, redaction_status: str) -> dict[str, Any]:
    return {
        "present": present,
        "path": path,
        "status": "present" if present else ("path_missing" if path else "missing"),
        "redaction_status": redaction_status if present else "not_applicable",
    }


def not_observed_resource_observations() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "root_session_identity": {
            "status": "not_observed",
            "digest": None,
        },
        "evidence_digests": {
            "external_transcript": None,
            "codex_hooks": None,
        },
        "metrics": {
            metric: {
                "status": "not_observed",
                "value": None,
                "provenance": "not_observed",
            }
            for metric in RESOURCE_METRICS
        },
    }


def observed_session_identity(value: str | None) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {"status": "not_observed", "digest": None}
    return {
        "status": "observed",
        "digest": "sha256:" + hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest(),
    }


def observed_metric(value: int | None, provenance: str) -> dict[str, Any]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return {
            "status": "not_observed",
            "value": None,
            "provenance": "not_observed",
        }
    return {
        "status": "observed",
        "value": value,
        "provenance": provenance,
    }


def file_digest(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return "sha256:" + hashlib.sha256(data).hexdigest()


def bounded_model_value(value: Any, diagnostics: list[str]) -> str | None:
    """Return one allowlisted model string, or None with a bounded diagnostic.

    A value is evidence only when the source reported it as a plain non-empty
    string within the declared bound. Every other shape stays unobserved and
    names why, so an absent value is never confused with a rejected one.

    A value that carries a secret, or that already carries a redaction marker,
    is rejected rather than rewritten. Substituting the marker and keeping the
    slot observed would publish a model identifier that no source ever
    reported, which is the invention this contract exists to prevent.
    """

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, str):
        record_model_diagnostic(diagnostics, "unsupported_type")
        return None
    # The exact source string is the evidence. Trimming surrounding
    # whitespace would report an identifier the source never wrote, so a value
    # that needs trimming is refused instead of normalized.
    if not value or value != value.strip() or not MODEL_VALUE_RE.fullmatch(value):
        record_model_diagnostic(diagnostics, "malformed_value")
        return None
    text = value
    if REDACTION_MARKER in text or SECRET_VALUE_RE.search(text):
        record_model_diagnostic(diagnostics, "redacted_value")
        return None
    if len(text) > MAX_MODEL_VALUE_LENGTH:
        record_model_diagnostic(diagnostics, "value_too_long")
        return None
    return text


def record_model_diagnostic(diagnostics: list[str], code: str) -> None:
    if code not in MODEL_DIAGNOSTIC_CODES:
        return
    if code in diagnostics or len(diagnostics) >= MAX_MODEL_DIAGNOSTICS:
        return
    diagnostics.append(code)


def not_observed_model_value() -> dict[str, Any]:
    return {"status": "not_observed", "value": None}


def observed_model_value(value: str | None) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return not_observed_model_value()
    return {"status": "observed", "value": value}


def empty_model_observation(source_kind: str) -> dict[str, Any]:
    return {
        "schema_version": MODEL_OBSERVATION_SCHEMA_VERSION,
        "source_kind": source_kind,
        "attributes": {
            attribute: {
                evidence_class: not_observed_model_value()
                for evidence_class in MODEL_EVIDENCE_CLASSES
            }
            for attribute in MODEL_ATTRIBUTES
        },
        "execution_scope": {field: not_observed_model_value() for field in MODEL_SCOPE_FIELDS},
        "provider_context": {
            field: not_observed_model_value() for field in MODEL_PROVIDER_CONTEXT_FIELDS
        },
        "diagnostics": [],
    }


def model_observation_has_evidence(observation: dict[str, Any]) -> bool:
    """Whether the observation carries anything beyond its own shape."""

    for attribute in MODEL_ATTRIBUTES:
        for evidence_class in MODEL_EVIDENCE_CLASSES:
            if observation["attributes"][attribute][evidence_class]["status"] == "observed":
                return True
    for field in MODEL_PROVIDER_CONTEXT_FIELDS:
        if observation["provider_context"][field]["status"] == "observed":
            return True
    return bool(observation["diagnostics"])


def build_model_observation(
    source_kind: str,
    runtime_model: Any = None,
    runtime_effort: Any = None,
    requested_model: Any = None,
    requested_effort: Any = None,
    model_provider: Any = None,
    cli_version: Any = None,
    session_id: Any = None,
    turn_id: Any = None,
    root_turn_id: Any = None,
) -> dict[str, Any] | None:
    """Normalize allowlisted model statements into the shared contract.

    Requested and runtime-reported settings occupy separate slots because a
    caller's request is not evidence that the runtime used it. Provider name
    and CLI version stay in `provider_context`: they describe the environment
    that reported the value and never establish that a provider resolved and
    executed a model.
    """

    if source_kind not in MODEL_SOURCE_KINDS:
        return None
    capability = MODEL_SOURCE_CAPABILITIES[source_kind]
    observation = empty_model_observation(source_kind)
    diagnostics = observation["diagnostics"]
    pairs = (
        ("model", "runtime_reported", runtime_model),
        ("reasoning_effort", "runtime_reported", runtime_effort),
        ("model", "requested", requested_model),
        ("reasoning_effort", "requested", requested_effort),
    )
    for attribute, evidence_class, raw_value in pairs:
        if evidence_class not in capability["evidence_classes"]:
            continue
        observation["attributes"][attribute][evidence_class] = observed_model_value(
            bounded_model_value(raw_value, diagnostics)
        )
    for key, values in (
        ("provider_context", (("model_provider", model_provider), ("cli_version", cli_version))),
        (
            "execution_scope",
            (("session_id", session_id), ("turn_id", turn_id), ("root_turn_id", root_turn_id)),
        ),
    ):
        for field, raw_value in values:
            if field not in capability[key]:
                continue
            observation[key][field] = observed_model_value(
                bounded_model_value(raw_value, diagnostics)
            )
    if not model_observation_has_evidence(observation):
        return None
    return observation


def retain_bounded_model_fields(
    metadata: dict[str, Any], observation: dict[str, Any] | None
) -> None:
    """Keep a raw model or effort field only when it is accepted evidence.

    A value the observation contract rejected as oversized, malformed or
    credential-shaped is not evidence, so it is dropped rather than kept
    verbatim. Otherwise the newly allowlisted keys would become a way to store
    unbounded or sensitive text that the observation itself refuses to report.
    """

    for attribute, key in (("model", "model"), ("reasoning_effort", "effort")):
        slot: Any = None
        if isinstance(observation, dict):
            slot = observation["attributes"][attribute]["runtime_reported"]
        if isinstance(slot, dict) and slot["status"] == "observed":
            metadata[key] = slot["value"]
        else:
            metadata.pop(key, None)


def read_model_observation(value: Any) -> dict[str, Any] | None:
    """Accept one stored observation only when it matches the exact contract."""

    if not isinstance(value, dict) or set(value) != set(MODEL_OBSERVATION_KEYS):
        return None
    if value.get("schema_version") != MODEL_OBSERVATION_SCHEMA_VERSION:
        return None
    if value.get("source_kind") not in MODEL_SOURCE_KINDS:
        return None
    capability = MODEL_SOURCE_CAPABILITIES[value["source_kind"]]
    for key, fields in (
        ("attributes", MODEL_ATTRIBUTES),
        ("execution_scope", MODEL_SCOPE_FIELDS),
        ("provider_context", MODEL_PROVIDER_CONTEXT_FIELDS),
    ):
        section = value.get(key)
        if not isinstance(section, dict) or set(section) != set(fields):
            return None
    for attribute in MODEL_ATTRIBUTES:
        classes = value["attributes"][attribute]
        if not isinstance(classes, dict) or set(classes) != set(MODEL_EVIDENCE_CLASSES):
            return None
        for slot in classes.values():
            if not valid_model_value_slot(slot):
                return None
    for key, fields in (
        ("execution_scope", MODEL_SCOPE_FIELDS),
        ("provider_context", MODEL_PROVIDER_CONTEXT_FIELDS),
    ):
        for field in fields:
            if not valid_model_value_slot(value[key][field]):
                return None
    diagnostics = value.get("diagnostics")
    if not isinstance(diagnostics, list) or len(diagnostics) > MAX_MODEL_DIAGNOSTICS:
        return None
    if any(code not in MODEL_DIAGNOSTIC_CODES for code in diagnostics):
        return None
    for attribute in MODEL_ATTRIBUTES:
        for evidence_class, slot in value["attributes"][attribute].items():
            if slot["status"] == "observed" and evidence_class not in capability["evidence_classes"]:
                return None
    for key in ("execution_scope", "provider_context"):
        for field, slot in value[key].items():
            if slot["status"] == "observed" and field not in capability[key]:
                return None
    return value


def record_reports_shape(holder: dict[str, Any], container: str, observation: dict[str, Any]) -> bool:
    """Whether the record itself identifies the shape its observation claims.

    A record reports one source shape. The record type is written by the
    source and read by unrelated parts of the importer, so binding the
    observation to it is what stops a record from granting itself a shape it
    never reported, and stops one shape's evidence from arriving under
    another shape's authority.
    """

    capability = MODEL_SOURCE_CAPABILITIES[observation["source_kind"]]
    if capability["container"] != container:
        return False
    required = capability["record_type"]
    if not required:
        return True
    return required in {
        holder.get(key) for key in ("source_type", "payload_type") if isinstance(holder.get(key), str)
    }


def canonical_model_value(value: Any) -> bool:
    """Whether a stored value still satisfies every producer rule.

    The reader repeats the producer's refusals instead of trusting the stored
    string, so a hand-edited record cannot present a secret, a control
    character, a padded identifier, or an overlong value as observed evidence.
    """

    return (
        isinstance(value, str)
        and not isinstance(value, bool)
        and bool(value)
        and value == value.strip()
        and bool(MODEL_VALUE_RE.fullmatch(value))
        and REDACTION_MARKER not in value
        and SECRET_VALUE_RE.search(value) is None
        and len(value) <= MAX_MODEL_VALUE_LENGTH
    )


def valid_model_value_slot(slot: Any) -> bool:
    if not isinstance(slot, dict) or set(slot) != {"status", "value"}:
        return False
    if slot["status"] == "not_observed":
        return slot["value"] is None
    if slot["status"] != "observed":
        return False
    return canonical_model_value(slot["value"])


def empty_model_observations() -> dict[str, Any]:
    return {
        "schema_version": MODEL_OBSERVATION_SCHEMA_VERSION,
        "evidence_digests": {key: None for key in MODEL_SOURCE_KEYS},
        "coverage": {
            key: {
                "status": "missing",
                "records_scanned": 0,
                "records_with_model_observation": 0,
            }
            for key in MODEL_SOURCE_KEYS
        },
        "statements": [],
        "provider_context": {
            field: {"status": "not_observed", "values": []}
            for field in MODEL_PROVIDER_CONTEXT_FIELDS
        },
        "identity_counts": {"session_digests": 0, "turn_ids": 0},
        "diagnostics": [],
        "truncated": False,
    }


def session_digest(value: str | None) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return "sha256:" + hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def scan_model_source(path: Path, source_key: str, container: str) -> dict[str, Any]:
    """Read one evidence file and return its statements and coverage.

    `container` names the record key that holds the observation, because the
    transcript stores it under `metadata` and the hook log under `payload`.
    Nothing else in either record is searched: a model-looking string that no
    supported field reported is not evidence.
    """

    result: dict[str, Any] = {
        "status": "present",
        "records_scanned": 0,
        "records_with_model_observation": 0,
        "statements": [],
        "provider_context": {field: [] for field in MODEL_PROVIDER_CONTEXT_FIELDS},
        "diagnostics": [],
    }
    try:
        # The size is checked before any read so an oversized source never
        # costs a full file read on a live hook append.
        if path.stat().st_size > MAX_MODEL_SOURCE_BYTES:
            result["status"] = "unreadable"
            record_model_diagnostic(result["diagnostics"], "source_too_large")
            return result
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError, UnicodeDecodeError):
        result["status"] = "unreadable"
        record_model_diagnostic(result["diagnostics"], "source_unreadable")
        return result
    for record_line, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        result["records_scanned"] += 1
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            record_model_diagnostic(result["diagnostics"], "record_unparsable")
            continue
        if not isinstance(record, dict):
            record_model_diagnostic(result["diagnostics"], "record_unparsable")
            continue
        holder = record.get(container)
        if not isinstance(holder, dict):
            continue
        stored = holder.get("model_observation")
        observation = read_model_observation(stored)
        if observation is None or not record_reports_shape(holder, container, observation):
            # A record that carries something under the observation key but
            # does not match the contract is malformed evidence, not absent
            # evidence, so it is named rather than silently skipped.
            if stored is not None:
                record_model_diagnostic(result["diagnostics"], "unknown_source_shape")
            continue
        result["records_with_model_observation"] += 1
        source_line = holder.get("source_line")
        if isinstance(source_line, bool) or not isinstance(source_line, int) or source_line < 1:
            source_line = None
        for code in observation["diagnostics"]:
            record_model_diagnostic(result["diagnostics"], code)
        scope = observation["execution_scope"]
        for field in MODEL_PROVIDER_CONTEXT_FIELDS:
            slot = observation["provider_context"][field]
            if slot["status"] != "observed":
                continue
            collected = result["provider_context"][field]
            if slot["value"] in collected:
                continue
            if len(collected) >= MAX_MODEL_PROVIDER_VALUES:
                record_model_diagnostic(result["diagnostics"], "provider_context_truncated")
                continue
            collected.append(slot["value"])
        for attribute in MODEL_ATTRIBUTES:
            for evidence_class in MODEL_EVIDENCE_CLASSES:
                slot = observation["attributes"][attribute][evidence_class]
                if slot["status"] != "observed":
                    continue
                result["statements"].append(
                    {
                        "source": source_key,
                        "record_line": record_line,
                        "source_line": source_line,
                        "source_kind": observation["source_kind"],
                        "attribute": attribute,
                        "evidence_class": evidence_class,
                        "value": slot["value"],
                        "session_digest": session_digest(scope["session_id"]["value"]),
                        "turn_id": scope["turn_id"]["value"],
                        "root_turn_id": scope["root_turn_id"]["value"],
                    }
                )

    return result


def compute_model_observations(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any] | None:
    """Rebuild the whole summary from the declared source files.

    The summary is derived, never accumulated. Recomputing it on every accepted
    update is what keeps a repeated import or an appended hook log from leaving
    a stale digest or a duplicated statement behind.
    """

    sources = (
        ("external_transcript", manifest.get("transcript_log"), "metadata"),
        ("codex_hooks", manifest.get("hook_event_log"), "payload"),
    )
    summary = empty_model_observations()
    present = False
    for source_key, declared, container in sources:
        if not isinstance(declared, str) or not declared:
            continue
        path = run_dir / declared
        if not path.is_file():
            continue
        present = True
        scanned = scan_model_source(path, source_key, container)
        for code in scanned["diagnostics"]:
            record_model_diagnostic(summary["diagnostics"], code)
        digest = file_digest(path) if scanned["status"] == "present" else None
        if digest is None:
            # Without readable bytes there is no digest to bind evidence to, so
            # the source contributes nothing rather than leaving statements
            # that cannot be verified.
            summary["coverage"][source_key] = {
                "status": "unreadable",
                "records_scanned": 0,
                "records_with_model_observation": 0,
            }
            record_model_diagnostic(summary["diagnostics"], "source_unreadable")
            continue
        summary["evidence_digests"][source_key] = digest
        summary["coverage"][source_key] = {
            "status": "present",
            "records_scanned": scanned["records_scanned"],
            "records_with_model_observation": scanned["records_with_model_observation"],
        }
        summary["statements"].extend(scanned["statements"])
        for field in MODEL_PROVIDER_CONTEXT_FIELDS:
            existing = summary["provider_context"][field]["values"]
            for value in scanned["provider_context"][field]:
                if value in existing:
                    continue
                if len(existing) >= MAX_MODEL_PROVIDER_VALUES:
                    # A dropped provider value is reported, so a consumer can
                    # tell bounded evidence from complete evidence.
                    record_model_diagnostic(summary["diagnostics"], "provider_context_truncated")
                    continue
                existing.append(value)
    if not present:
        return None
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for statement in sorted(
        summary["statements"],
        key=lambda item: (
            MODEL_SOURCE_KEYS.index(item["source"]),
            item["record_line"],
            item["attribute"],
            item["evidence_class"],
        ),
    ):
        key = (
            statement["source"],
            statement["record_line"],
            statement["attribute"],
            statement["evidence_class"],
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(statement)
    if len(unique) > MAX_MODEL_STATEMENTS:
        unique = unique[:MAX_MODEL_STATEMENTS]
        summary["truncated"] = True
        record_model_diagnostic(summary["diagnostics"], "statements_truncated")
    summary["statements"] = unique
    summary["identity_counts"] = {
        "session_digests": len(
            {item["session_digest"] for item in unique if item["session_digest"]}
        ),
        "turn_ids": len({item["turn_id"] for item in unique if item["turn_id"]}),
    }
    for field in MODEL_PROVIDER_CONTEXT_FIELDS:
        values = summary["provider_context"][field]["values"]
        summary["provider_context"][field]["status"] = "observed" if values else "not_observed"
    return summary


def hook_resource_observations(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    observations = not_observed_resource_observations()
    hook_rel = manifest.get("hook_event_log")
    if not isinstance(hook_rel, str):
        return observations
    hook_path = run_dir / hook_rel
    try:
        lines = hook_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return observations
    session_id: str | None = None
    compaction_count = 0
    tool_call_count = 0
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        event = record.get("event")
        payload = record.get("payload")
        if event == "PreCompact":
            compaction_count += 1
        if event == "PreToolUse":
            tool_call_count += 1
        if isinstance(payload, dict) and isinstance(payload.get("session_id"), str):
            session_id = payload["session_id"]
    observations["root_session_identity"] = observed_session_identity(session_id)
    observations["evidence_digests"]["codex_hooks"] = file_digest(hook_path)
    observations["metrics"]["compaction_count"] = observed_metric(
        compaction_count, "deterministic_proxy"
    )
    observations["metrics"]["tool_call_count"] = observed_metric(
        tool_call_count, "deterministic_proxy"
    )
    return observations


def merge_resource_observations(current: Any, incoming: Any) -> dict[str, Any]:
    merged = current if isinstance(current, dict) else not_observed_resource_observations()
    if not isinstance(merged.get("metrics"), dict):
        merged = not_observed_resource_observations()
    if not isinstance(incoming, dict):
        return merged
    identity = incoming.get("root_session_identity")
    if isinstance(identity, dict) and identity.get("status") == "observed":
        merged["root_session_identity"] = identity
    incoming_digests = incoming.get("evidence_digests")
    if isinstance(incoming_digests, dict):
        merged_digests = merged.setdefault("evidence_digests", {"external_transcript": None, "codex_hooks": None})
        for source_key in ("external_transcript", "codex_hooks"):
            candidate = incoming_digests.get(source_key)
            if isinstance(candidate, str) and candidate.startswith("sha256:"):
                merged_digests[source_key] = candidate
    incoming_metrics = incoming.get("metrics")
    if not isinstance(incoming_metrics, dict):
        return merged
    for metric in RESOURCE_METRICS:
        candidate = incoming_metrics.get(metric)
        if not isinstance(candidate, dict) or candidate.get("status") != "observed":
            continue
        existing = merged["metrics"].get(metric)
        if (
            not isinstance(existing, dict)
            or existing.get("status") != "observed"
            or candidate.get("value", -1) >= existing.get("value", -1)
        ):
            merged["metrics"][metric] = candidate
    return merged


def ensure_compression_redaction_report(run_dir: Path, source: Path) -> None:
    report = run_dir / "redaction-report.md"
    if report.exists():
        return
    report.write_text(
        "\n".join(
            [
                "# Redaction Report",
                "",
                "- created_by: .project-agent-workflow/scripts/context-compress.sh",
                f"- source: {source}",
                "- note: This wrapper does not redact source content. Review raw logs before sharing or committing summaries.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def load_manifest(run_dir: Path, run_id: str, task: str) -> dict[str, Any]:
    path = run_dir / "manifest.json"
    if path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            manifest = value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            manifest = {}
    else:
        manifest = {}
    manifest["run_id"] = run_id
    manifest.setdefault("created_at", utc_now())
    manifest.setdefault("task", task)
    manifest.setdefault("plans", [])
    manifest.setdefault("raw_logs", [])
    manifest.setdefault("transcript_log", None)
    manifest.setdefault("hook_event_log", None)
    manifest.setdefault("artifacts", [])
    manifest.setdefault("compressed_outputs", [])
    manifest.setdefault("redaction_report", "redaction-report.md")
    manifest.setdefault("pinned", False)
    manifest.setdefault("coverage", {})
    manifest.setdefault("missing_sources", [])
    manifest.setdefault("resource_observations", not_observed_resource_observations())
    for field in ("plans", "raw_logs", "artifacts", "compressed_outputs", "missing_sources"):
        if not isinstance(manifest[field], list):
            manifest[field] = []
    for field in ("transcript_log", "hook_event_log"):
        if not isinstance(manifest[field], str):
            manifest[field] = None
    if not isinstance(manifest["coverage"], dict):
        manifest["coverage"] = {}
    if not isinstance(manifest["redaction_report"], str) or not manifest["redaction_report"]:
        manifest["redaction_report"] = "redaction-report.md"
    if not isinstance(manifest["pinned"], bool):
        manifest["pinned"] = False
    manifest["resource_observations"] = merge_resource_observations(
        not_observed_resource_observations(),
        manifest["resource_observations"],
    )
    return manifest


def finalize_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
    coverage = manifest.get("coverage") if isinstance(manifest.get("coverage"), dict) else {}
    transcript_rel = manifest.get("transcript_log") if isinstance(manifest.get("transcript_log"), str) else None
    hook_rel = manifest.get("hook_event_log") if isinstance(manifest.get("hook_event_log"), str) else None
    transcript_present = bool(transcript_rel and (run_dir / transcript_rel).is_file())
    hook_present = bool(hook_rel and (run_dir / hook_rel).is_file())
    transcript_existing = coverage.get("external_transcript") if isinstance(coverage.get("external_transcript"), dict) else {}
    hook_existing = coverage.get("codex_hooks") if isinstance(coverage.get("codex_hooks"), dict) else {}
    coverage["external_transcript"] = source_coverage(
        transcript_rel,
        transcript_present,
        str(transcript_existing.get("redaction_status") or "pending_review"),
    )
    coverage["codex_hooks"] = source_coverage(
        hook_rel,
        hook_present,
        str(hook_existing.get("redaction_status") or "pending_review"),
    )
    manifest["coverage"] = coverage
    manifest["missing_sources"] = [
        source
        for source, present in (("external_transcript", transcript_present), ("codex_hooks", hook_present))
        if not present
    ]
    model_observations = compute_model_observations(run_dir, manifest)
    if model_observations is None:
        manifest.pop("model_observations", None)
    else:
        manifest["model_observations"] = model_observations
    manifest["updated_at"] = utc_now()
    write_json(run_dir / "manifest.json", manifest)


def record_hook(
    run_dir: Path,
    run_id: str,
    event_path: Path,
    resource_observations: dict[str, Any] | None = None,
) -> None:
    with manifest_lock(run_dir):
        manifest = load_manifest(run_dir, run_id, "codex hook event log")
        hook_rel = relative_to_run(run_dir, event_path)
        if hook_rel is None:
            raise ValueError("hook event log must be inside the run directory")
        manifest["hook_event_log"] = hook_rel
        raw_logs = {value for value in manifest.get("raw_logs", []) if isinstance(value, str)}
        raw_logs.add(hook_rel)
        manifest["raw_logs"] = sorted(raw_logs)
        coverage = manifest.get("coverage") if isinstance(manifest.get("coverage"), dict) else {}
        coverage["codex_hooks"] = source_coverage(hook_rel, True, "pending_review")
        manifest["coverage"] = coverage
        manifest["resource_observations"] = merge_resource_observations(
            manifest.get("resource_observations"),
            resource_observations,
        )
        finalize_manifest(run_dir, manifest)


def record_transcript(
    run_dir: Path,
    run_id: str,
    redaction_status: str,
    resource_observations: dict[str, Any] | None = None,
) -> None:
    with manifest_lock(run_dir):
        manifest = load_manifest(run_dir, run_id, "codex transcript import")
        manifest["transcript_log"] = TRANSCRIPT_REL
        raw_logs = {value for value in manifest.get("raw_logs", []) if isinstance(value, str)}
        raw_logs.add(TRANSCRIPT_REL)
        manifest["raw_logs"] = sorted(raw_logs)
        coverage = manifest.get("coverage") if isinstance(manifest.get("coverage"), dict) else {}
        coverage["external_transcript"] = source_coverage(TRANSCRIPT_REL, True, redaction_status)
        manifest["coverage"] = coverage
        manifest["resource_observations"] = merge_resource_observations(
            merge_resource_observations(
                not_observed_resource_observations(),
                resource_observations,
            ),
            hook_resource_observations(run_dir, manifest),
        )
        finalize_manifest(run_dir, manifest)


def record_compression(run_dir: Path, run_id: str, source: Path, output: Path) -> None:
    with manifest_lock(run_dir):
        manifest = load_manifest(run_dir, run_id, "context compression")
        ensure_compression_redaction_report(run_dir, source)
        output_rel = relative_to_run(run_dir, output)
        if output_rel is None:
            raise ValueError("compressed output must be inside the run directory")
        compressed = {value for value in manifest.get("compressed_outputs", []) if isinstance(value, str)}
        compressed.add(output_rel)
        manifest["compressed_outputs"] = sorted(compressed)
        source_rel = relative_to_run(run_dir, source)
        if source_rel is not None:
            raw_logs = {value for value in manifest.get("raw_logs", []) if isinstance(value, str)}
            raw_logs.add(source_rel)
            manifest["raw_logs"] = sorted(raw_logs)
        else:
            artifacts = {value for value in manifest.get("artifacts", []) if isinstance(value, str)}
            artifacts.add(str(source))
            manifest["artifacts"] = sorted(artifacts)
        finalize_manifest(run_dir, manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    compression = subparsers.add_parser("record-compression")
    compression.add_argument("--run-dir", required=True)
    compression.add_argument("--run-id", required=True)
    compression.add_argument("--source", required=True)
    compression.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "record-compression":
        run_dir = Path(args.run_dir)
        record_compression(run_dir, args.run_id, Path(args.source), Path(args.output))
        return 0
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
