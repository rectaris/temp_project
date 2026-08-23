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
    "hook_event_name",
    "inherited_turns",
    "review_packet_digest",
    "session_id",
    "stop_hook_active",
    "tool",
    "tool_name",
}
OPERATIONAL_PAYLOAD_KEYS = {*ALLOWED_METADATA_KEYS, "transcript_path"}
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
    return metadata


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
            with event_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
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
