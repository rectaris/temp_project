#!/usr/bin/env python3
"""Normalize an external Codex session transcript into agent log format."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECRET_KEY_RE = re.compile(r"(token|secret|password|passwd|api[_-]?key|authorization|credential|private[_-]?key)", re.I)
SECRET_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|xox[baprs]-[A-Za-z0-9-]{16,})")
MAX_STRING = 12000
TRANSCRIPT_REL = "raw/transcript.jsonl"


class ImportErrorWithContext(Exception):
    """Raised when transcript import cannot be completed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_root() -> Path:
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned.strip("-")[:120] or "codex-run"


def default_run_id(source: Path) -> str:
    existing = os.environ.get("CODEX_AGENT_LOG_RUN_ID") or os.environ.get("AGENT_LOG_RUN_ID")
    if existing:
        return safe_name(existing)
    session = os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID")
    if session:
        date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
        digest = hashlib.sha256(f"{repo_root()}:{session}".encode("utf-8", errors="replace")).hexdigest()[:10]
        return f"{date_prefix}-codex-{digest}"
    return safe_name(source.stem)


def redact(value: Any, key: str = "") -> Any:
    if SECRET_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        redacted = SECRET_VALUE_RE.sub("[REDACTED]", value)
        if len(redacted) > MAX_STRING:
            return {
                "truncated": True,
                "length": len(redacted),
                "sha256": hashlib.sha256(redacted.encode("utf-8", errors="replace")).hexdigest(),
                "head": redacted[:MAX_STRING],
            }
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {str(item_key): redact(item_value, str(item_key)) for item_key, item_value in value.items()}
    return value


def content_text(value: Any) -> str:
    redacted = redact(value)
    if isinstance(redacted, str):
        return redacted
    return json.dumps(redacted, ensure_ascii=False, sort_keys=True)


def extract_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content_text(content)
    if not isinstance(content, list):
        return content_text(content)
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict):
            item_type = item.get("type")
            if item_type in {"reasoning", "redacted_reasoning"}:
                continue
            for key in ("text", "input_text", "output_text"):
                if isinstance(item.get(key), str):
                    parts.append(content_text(item[key]))
                    break
            else:
                parts.append(content_text(item))
        else:
            parts.append(content_text(item))
    return "\n".join(part for part in parts if part)


def nested_turn_id(raw: dict[str, Any], line_number: int) -> str:
    payload = raw.get("payload")
    if isinstance(payload, dict):
        metadata = payload.get("internal_chat_message_metadata_passthrough")
        if isinstance(metadata, dict) and metadata.get("turn_id"):
            return str(metadata["turn_id"])
        if payload.get("turn_id"):
            return str(payload["turn_id"])
    if raw.get("turn_id"):
        return str(raw["turn_id"])
    return f"source-line-{line_number}"


def normalize_record(raw: dict[str, Any], run_id: str, line_number: int) -> dict[str, Any]:
    payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
    assert isinstance(payload, dict)
    top_type = str(raw.get("type") or "unknown")
    payload_type = str(payload.get("type") or top_type)
    created_at = str(raw.get("timestamp") or payload.get("created_at") or utc_now())
    metadata = {
        "source_line": line_number,
        "source_type": top_type,
        "payload_type": payload_type,
    }
    if payload.get("call_id"):
        metadata["call_id"] = str(payload["call_id"])
    if payload.get("id"):
        metadata["item_id"] = str(payload["id"])

    if top_type == "response_item" and payload_type == "message":
        role = str(payload.get("role") or "system_event")
        if role not in {"user", "assistant"}:
            role = "system_event"
        content = extract_message_content(payload.get("content"))
        record_type = "message"
    elif top_type == "response_item" and payload_type == "function_call":
        role = "tool"
        record_type = "tool_call"
        content = content_text(
            {
                "name": payload.get("name"),
                "arguments": payload.get("arguments"),
                "call_id": payload.get("call_id"),
            }
        )
    elif top_type == "response_item" and payload_type == "function_call_output":
        role = "tool"
        record_type = "tool_result"
        content = content_text(payload.get("output", ""))
    elif top_type == "event_msg" and payload_type == "user_message":
        role = "user"
        record_type = "message"
        content = content_text(payload.get("message", ""))
    else:
        role = "system_event"
        record_type = "system_event"
        content = content_text({"type": payload_type, "message": payload.get("message")})

    return {
        "schema_version": 1,
        "record_type": record_type,
        "created_at": created_at,
        "run_id": run_id,
        "turn_id": nested_turn_id(raw, line_number),
        "role": role,
        "content": content,
        "metadata": metadata,
    }


def load_source_records(source: Path, run_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except Exception as exc:
            raise ImportErrorWithContext(f"{source}: line {line_number} is not valid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ImportErrorWithContext(f"{source}: line {line_number} must be a JSON object")
        records.append(normalize_record(raw, run_id, line_number))
    if not records:
        raise ImportErrorWithContext(f"{source}: no transcript records found")
    return records


def write_json(path: Path, value: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records), encoding="utf-8")
    tmp.replace(path)


def source_coverage(path: str | None, present: bool, status: str, redaction_status: str) -> dict[str, Any]:
    return {
        "present": present,
        "path": path,
        "status": status,
        "redaction_status": redaction_status,
    }


def update_manifest(run_dir: Path, run_id: str, redaction_status: str) -> None:
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
    else:
        manifest = {}
    manifest.setdefault("run_id", run_id)
    manifest.setdefault("created_at", utc_now())
    manifest.setdefault("task", "codex transcript import")
    manifest.setdefault("plans", [])
    manifest.setdefault("artifacts", [])
    manifest.setdefault("compressed_outputs", [])
    manifest.setdefault("redaction_report", "redaction-report.md")
    manifest.setdefault("pinned", False)
    manifest["transcript_log"] = TRANSCRIPT_REL

    hook_rel = manifest.get("hook_event_log")
    hook_present = isinstance(hook_rel, str) and (run_dir / hook_rel).is_file()
    if not hook_present:
        hook_rel = None
        manifest["hook_event_log"] = None

    raw_logs = set()
    for rel in manifest.get("raw_logs", []):
        if not isinstance(rel, str):
            continue
        if rel == TRANSCRIPT_REL or (run_dir / rel).is_file():
            raw_logs.add(rel)
    raw_logs.add(TRANSCRIPT_REL)
    if isinstance(hook_rel, str):
        raw_logs.add(hook_rel)
    manifest["raw_logs"] = sorted(raw_logs)
    manifest["coverage"] = {
        "external_transcript": source_coverage(TRANSCRIPT_REL, True, "present", redaction_status),
        "codex_hooks": source_coverage(
            hook_rel if isinstance(hook_rel, str) else None,
            hook_present,
            "present" if hook_present else "missing",
            "automatic_redaction" if hook_present else "not_applicable",
        ),
    }
    missing_sources = []
    if not hook_present:
        missing_sources.append("codex_hooks")
    manifest["missing_sources"] = missing_sources
    manifest["updated_at"] = utc_now()
    write_json(manifest_path, manifest)


def update_redaction_report(run_dir: Path, redaction_status: str) -> None:
    report = run_dir / "redaction-report.md"
    section = "\n".join(
        [
            "## External Transcript Import",
            "",
            "- created_by: scripts/import-codex-transcript.py",
            "- scope: external Codex session transcript normalized into raw/transcript.jsonl.",
            f"- redaction_status: {redaction_status}",
            "- redaction: obvious secret-like keys and common token patterns are replaced with [REDACTED]; reasoning content items are excluded.",
            "",
        ]
    )
    if not report.exists():
        report.write_text("# Redaction Report\n\n" + section, encoding="utf-8")
        return
    text = report.read_text(encoding="utf-8")
    if "## External Transcript Import" not in text:
        report.write_text(text.rstrip() + "\n\n" + section, encoding="utf-8")


def import_transcript(source: Path, run_dir: Path, run_id: str, redaction_status: str, overwrite: bool) -> Path:
    if not source.is_file():
        raise ImportErrorWithContext(f"transcript source does not exist: {source}")
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = run_dir / TRANSCRIPT_REL
    if target.exists() and not overwrite:
        update_manifest(run_dir, run_id, redaction_status)
        update_redaction_report(run_dir, redaction_status)
        return target
    records = load_source_records(source, run_id)
    write_jsonl(target, records)
    update_manifest(run_dir, run_id, redaction_status)
    update_redaction_report(run_dir, redaction_status)
    return target


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "session.jsonl"
        source.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "timestamp": "2026-07-05T00:00:00Z",
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": "user",
                                "content": [{"type": "input_text", "text": "hello"}],
                                "internal_chat_message_metadata_passthrough": {"turn_id": "turn-1"},
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "timestamp": "2026-07-05T00:00:01Z",
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": "done"}],
                                "internal_chat_message_metadata_passthrough": {"turn_id": "turn-1"},
                            },
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        run_dir = root / ".agent-logs/self-test"
        target = import_transcript(source, run_dir, "self-test", "redacted", overwrite=False)
        records = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
        if [record["role"] for record in records] != ["user", "assistant"]:
            raise AssertionError("self-test roles did not match")
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        if manifest["coverage"]["external_transcript"]["status"] != "present":
            raise AssertionError("self-test manifest did not record transcript coverage")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--redaction-status", choices=("redacted", "pending_review"), default="redacted")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        try:
            self_test()
        except Exception as exc:
            print(f"codex transcript import self-test failed: {exc}", file=sys.stderr)
            return 1
        print("codex transcript import self-test passed")
        return 0

    if not args.source:
        parser.error("source is required unless --self-test is used")
    source = Path(args.source).expanduser().resolve()
    run_id = safe_name(args.run_id) if args.run_id else default_run_id(source)
    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else repo_root() / ".agent-logs" / run_id
    try:
        target = import_transcript(source, run_dir, run_id, args.redaction_status, args.overwrite)
    except ImportErrorWithContext as exc:
        print(f"codex transcript import failed: {exc}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
