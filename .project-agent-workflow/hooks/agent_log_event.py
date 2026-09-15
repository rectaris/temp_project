#!/usr/bin/env python3
"""Best-effort Codex lifecycle event logger."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECRET_KEY_RE = re.compile(r"(token|secret|password|passwd|api[_-]?key|authorization|credential|private[_-]?key)", re.I)
SECRET_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|xox[baprs]-[A-Za-z0-9-]{16,})")
MAX_STRING = 12000
MAX_LIST = 200
MAX_DICT = 200
ALLOWED_METADATA_KEYS = {
    "cwd",
    "effort",
    "hook_event_name",
    "inherited_turns",
    "model",
    "review_packet_digest",
    "session_id",
    "stop_hook_active",
    "tool",
    "tool_name",
}
OPERATIONAL_PAYLOAD_KEYS = {*ALLOWED_METADATA_KEYS, "prompt", "transcript_path"}
REVIEW_PACKET_MARKER = re.compile(r"^ReviewPacket: (sha256:[0-9a-f]{64})$", re.MULTILINE)
MAX_REVIEW_PROMPT_BYTES = 256 * 1024
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_root() -> Path:
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def run_id(payload: dict[str, Any]) -> str:
    existing = os.environ.get("CODEX_AGENT_LOG_RUN_ID") or os.environ.get("AGENT_LOG_RUN_ID")
    if existing:
        return safe_name(existing)
    session = (
        os.environ.get("CODEX_SESSION_ID")
        or os.environ.get("CODEX_THREAD_ID")
        or payload.get("session_id")
    )
    if isinstance(session, str) and session:
        seed = f"{repo_root()}:{session}"
        digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:16]
        return f"codex-session-{digest}"
    date_prefix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    seed = f"{repo_root()}:{date_prefix}:{os.getpid()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:10]
    return f"{date_prefix}-codex-{digest}"


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned.strip("-")[:120] or "codex-run"


def redact(value: Any, key: str = "") -> Any:
    if SECRET_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        redacted = SECRET_VALUE_RE.sub("[REDACTED]", value)
        if len(redacted) > MAX_STRING:
            return {
                "truncated": True,
                "length": len(redacted),
                "head": redacted[:MAX_STRING],
            }
        return redacted
    if isinstance(value, list):
        items = [redact(item) for item in value[:MAX_LIST]]
        if len(value) > MAX_LIST:
            items.append({"truncated": True, "omitted_items": len(value) - MAX_LIST})
        return items
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (item_key, item_value) in enumerate(value.items()):
            if index >= MAX_DICT:
                out["_truncated"] = {"omitted_keys": len(value) - MAX_DICT}
                break
            text_key = str(item_key)
            out[text_key] = redact(item_value, text_key)
        return out
    return value


def load_payload() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        value = json.loads(raw)
        if not isinstance(value, dict):
            return {}
        return {key: item for key, item in value.items() if key in OPERATIONAL_PAYLOAD_KEYS}
    except Exception as exc:
        return {"_parse_error": str(exc)}


def event_metadata(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in sorted(ALLOWED_METADATA_KEYS):
        value = payload.get(key)
        if isinstance(value, bool):
            metadata[key] = value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            metadata[key] = value
        elif isinstance(value, str):
            metadata[key] = value[:512]
    if payload.get("transcript_path"):
        metadata["transcript_available"] = True
    if (
        event != "ReviewPacketStart"
        or not isinstance(metadata.get("review_packet_digest"), str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", metadata["review_packet_digest"])
        or isinstance(metadata.get("inherited_turns"), bool)
        or not isinstance(metadata.get("inherited_turns"), int)
        or metadata["inherited_turns"] < 0
    ):
        metadata.pop("review_packet_digest", None)
        metadata.pop("inherited_turns", None)
    model_observation = build_model_observation(
        "hook_event_metadata",
        runtime_model=metadata.get("model"),
        runtime_effort=metadata.get("effort"),
        session_id=metadata.get("session_id"),
    )
    retain_bounded_model_fields(metadata, model_observation)
    if model_observation is not None:
        metadata["model_observation"] = model_observation
    return metadata


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


def bounded_model_value(value: Any, diagnostics: list[str]) -> str | None:
    """Return one allowlisted model string, or None with a bounded diagnostic."""

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


def build_model_observation(
    source_kind: str,
    runtime_model: Any = None,
    runtime_effort: Any = None,
    session_id: Any = None,
    turn_id: Any = None,
    root_turn_id: Any = None,
) -> dict[str, Any] | None:
    """Normalize allowlisted hook model statements into the shared contract.

    A hook reports what the runtime told it. That is not a caller request and
    not provider-resolved execution, so only the runtime-reported slot is ever
    filled here.
    """

    if source_kind not in MODEL_SOURCE_KINDS:
        return None
    capability = MODEL_SOURCE_CAPABILITIES[source_kind]
    diagnostics: list[str] = []
    attributes = {
        attribute: {
            evidence_class: not_observed_model_value()
            for evidence_class in MODEL_EVIDENCE_CLASSES
        }
        for attribute in MODEL_ATTRIBUTES
    }
    if "runtime_reported" in capability["evidence_classes"]:
        attributes["model"]["runtime_reported"] = observed_model_value(
            bounded_model_value(runtime_model, diagnostics)
        )
        attributes["reasoning_effort"]["runtime_reported"] = observed_model_value(
            bounded_model_value(runtime_effort, diagnostics)
        )
    scope = {field: not_observed_model_value() for field in MODEL_SCOPE_FIELDS}
    for field, raw_value in (
        ("session_id", session_id),
        ("turn_id", turn_id),
        ("root_turn_id", root_turn_id),
    ):
        if field not in capability["execution_scope"]:
            continue
        scope[field] = observed_model_value(bounded_model_value(raw_value, diagnostics))
    observed = any(
        attributes[attribute][evidence_class]["status"] == "observed"
        for attribute in MODEL_ATTRIBUTES
        for evidence_class in MODEL_EVIDENCE_CLASSES
    )
    if not observed and not diagnostics:
        return None
    return {
        "schema_version": MODEL_OBSERVATION_SCHEMA_VERSION,
        "source_kind": source_kind,
        "attributes": attributes,
        "execution_scope": scope,
        "provider_context": {
            field: not_observed_model_value() for field in MODEL_PROVIDER_CONTEXT_FIELDS
        },
        "diagnostics": diagnostics,
    }


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
        if any(not valid_model_value_slot(slot) for slot in classes.values()):
            return None
    for key, fields in (
        ("execution_scope", MODEL_SCOPE_FIELDS),
        ("provider_context", MODEL_PROVIDER_CONTEXT_FIELDS),
    ):
        if any(not valid_model_value_slot(value[key][field]) for field in fields):
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


def file_digest(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return "sha256:" + hashlib.sha256(data).hexdigest()


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


def model_session_digest(value: str | None) -> str | None:
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
                        "session_digest": model_session_digest(scope["session_id"]["value"]),
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


def write_json(path: Path, value: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def hook_resource_observations(event_path: Path) -> dict[str, Any]:
    session_id: str | None = None
    compaction_count = 0
    tool_call_count = 0
    for line in event_path.read_text(encoding="utf-8").splitlines():
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
    not_observed = {
        "status": "not_observed",
        "value": None,
        "provenance": "not_observed",
    }
    metrics = {name: dict(not_observed) for name in RESOURCE_METRICS}
    metrics["compaction_count"] = {
        "status": "observed",
        "value": compaction_count,
        "provenance": "deterministic_proxy",
    }
    metrics["tool_call_count"] = {
        "status": "observed",
        "value": tool_call_count,
        "provenance": "deterministic_proxy",
    }
    return {
        "schema_version": 1,
        "root_session_identity": (
            {
                "status": "observed",
                "digest": "sha256:" + hashlib.sha256(session_id.encode()).hexdigest(),
            }
            if session_id
            else {"status": "not_observed", "digest": None}
        ),
        "evidence_digests": {
            "external_transcript": None,
            "codex_hooks": "sha256:" + hashlib.sha256(event_path.read_bytes()).hexdigest(),
        },
        "metrics": metrics,
    }


def update_manifest(run_dir: Path, run: str, event_path: Path) -> None:
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
    else:
        manifest = {}
    manifest.setdefault("run_id", run)
    manifest.setdefault("created_at", utc_now())
    manifest.setdefault("task", "codex hook event log")
    manifest.setdefault("plans", [])
    hook_rel = str(event_path.relative_to(run_dir))
    transcript_rel = manifest.get("transcript_log")
    raw_logs = set(manifest.get("raw_logs", []))
    raw_logs.add(hook_rel)
    if isinstance(transcript_rel, str) and transcript_rel:
        raw_logs.add(transcript_rel)
    manifest["raw_logs"] = sorted(raw_logs)
    manifest.setdefault("artifacts", [])
    manifest.setdefault("compressed_outputs", [])
    manifest.setdefault("redaction_report", "redaction-report.md")
    manifest.setdefault("pinned", False)
    manifest.setdefault("transcript_log", None)
    manifest["hook_event_log"] = hook_rel
    coverage = manifest.get("coverage") if isinstance(manifest.get("coverage"), dict) else {}
    transcript_path = manifest.get("transcript_log")
    transcript_present = isinstance(transcript_path, str) and (run_dir / transcript_path).is_file()
    existing_transcript = coverage.get("external_transcript") if isinstance(coverage.get("external_transcript"), dict) else {}
    coverage["external_transcript"] = {
        "present": transcript_present,
        "path": transcript_path if isinstance(transcript_path, str) else None,
        "status": "present" if transcript_present else ("path_missing" if transcript_path else "missing"),
        "redaction_status": existing_transcript.get(
            "redaction_status",
            "pending_review" if transcript_present else "not_applicable",
        ),
    }
    coverage["codex_hooks"] = {
        "present": True,
        "path": hook_rel,
        "status": "present",
        "redaction_status": "pending_review",
    }
    manifest["coverage"] = coverage
    missing_sources = []
    if not coverage["external_transcript"]["present"]:
        missing_sources.append("external_transcript")
    if not coverage["codex_hooks"]["present"]:
        missing_sources.append("codex_hooks")
    manifest["missing_sources"] = missing_sources
    current_resources = manifest.get("resource_observations")
    resources = hook_resource_observations(event_path)
    if isinstance(current_resources, dict):
        current_digests = current_resources.get("evidence_digests")
        if isinstance(current_digests, dict):
            resources["evidence_digests"]["external_transcript"] = current_digests.get(
                "external_transcript"
            )
        current_metrics = current_resources.get("metrics")
        if isinstance(current_metrics, dict):
            for name in RESOURCE_METRICS:
                if name in {"compaction_count", "tool_call_count"}:
                    continue
                if isinstance(current_metrics.get(name), dict):
                    resources["metrics"][name] = current_metrics[name]
    manifest["resource_observations"] = resources
    model_observations = compute_model_observations(run_dir, manifest)
    if model_observations is None:
        manifest.pop("model_observations", None)
    else:
        manifest["model_observations"] = model_observations
    manifest["updated_at"] = utc_now()
    write_json(manifest_path, manifest)


def ensure_redaction_report(run_dir: Path) -> None:
    report = run_dir / "redaction-report.md"
    if report.exists():
        return
    report.write_text(
        "\n".join(
            [
                "# Redaction Report",
                "",
                "- created_by: .codex/hooks/agent_log_event.py",
                "- scope: Codex hook event payloads.",
                "- redaction: obvious secret-like keys and common token patterns are replaced with [REDACTED].",
                "- limitation: hook logs capture observable hook payloads only; unavailable internal reasoning and assistant text absent from hook payloads are not reconstructed.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def submitted_review_packet_digest(prompt: Any) -> str | None:
    if not isinstance(prompt, str):
        return None
    try:
        if len(prompt.encode("utf-8")) > MAX_REVIEW_PROMPT_BYTES:
            return None
        markers = list(REVIEW_PACKET_MARKER.finditer(prompt))
        if len(markers) != 1:
            return None
        marker = markers[0]
        packet = json.loads(prompt[marker.end():])
        if not isinstance(packet, dict):
            return None
        canonical = json.dumps(packet, sort_keys=True, separators=(",", ":"), allow_nan=False)
        recomputed = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except (ValueError, RecursionError, UnicodeError):
        return None
    return recomputed if recomputed == marker.group(1) else None


def prior_prompt_count(event_path: Path, session_id: str) -> int | None:
    if not event_path.exists():
        return 0
    count = 0
    try:
        with event_path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("invalid event record")
                if record.get("event") != "UserPromptSubmit":
                    continue
                metadata = record.get("payload")
                if not isinstance(metadata, dict) or not metadata.get("session_id"):
                    raise ValueError("prompt record has no session identity")
                if metadata["session_id"] == session_id:
                    count += 1
    except (OSError, ValueError, UnicodeError):
        print("review packet observation unavailable: unreadable prompt history", file=sys.stderr)
        return None
    return count


def append_event(event: str, payload: dict[str, Any]) -> None:
    root = repo_root()
    run = run_id(payload)
    run_dir = root / ".agent-logs" / run
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    event_path = raw_dir / "events.jsonl"
    record = {
        "schema_version": 1,
        "event": event,
        "created_at": utc_now(),
        "cwd": str(Path.cwd()),
        "payload": redact(event_metadata(event, payload)),
    }
    with (run_dir / ".events.lock").open("a", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            packet_record = None
            session_id = payload.get("session_id")
            if (
                event == "UserPromptSubmit"
                and isinstance(session_id, str)
                and session_id
                and record["payload"].get("session_id") == session_id
            ):
                packet_digest = submitted_review_packet_digest(payload.get("prompt"))
                if packet_digest is not None and prior_prompt_count(event_path, session_id) == 0:
                    packet_record = {
                        **record,
                        "event": "ReviewPacketStart",
                        "payload": {
                            "hook_event_name": "ReviewPacketStart",
                            "session_id": session_id,
                            "review_packet_digest": packet_digest,
                            "inherited_turns": 0,
                        },
                    }
            with event_path.open("a", encoding="utf-8") as handle:
                # Record the prompt first under the same lock, so a partial append
                # cannot let a retry claim another first prompt.
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                if packet_record is not None:
                    handle.write(json.dumps(packet_record, ensure_ascii=False, sort_keys=True) + "\n")
            update_manifest(run_dir, run, event_path)
            ensure_redaction_report(run_dir)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    if event == "Stop":
        import_external_transcript(root, run, payload)


def import_external_transcript(root: Path, run: str, payload: dict[str, Any]) -> None:
    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return
    source = Path(transcript_path).expanduser()
    if not source.is_file():
        return
    importer = root / "scripts/import-codex-transcript.py"
    if not importer.is_file():
        return
    try:
        subprocess.run(
            [sys.executable, str(importer), str(source), "--run-id", run, "--overwrite"],
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", default="unknown")
    args = parser.parse_args()
    try:
        payload = load_payload()
        append_event(args.event, payload)
    except Exception:
        pass
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
