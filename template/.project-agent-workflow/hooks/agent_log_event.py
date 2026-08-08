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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import agent_log_manifest


SECRET_KEY_RE = re.compile(r"(token|secret|password|passwd|api[_-]?key|authorization|credential|private[_-]?key)", re.I)
SECRET_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|xox[baprs]-[A-Za-z0-9-]{16,})")
MAX_STRING = 12000
MAX_LIST = 200
MAX_DICT = 200
ALLOWED_METADATA_KEYS = {
    "cwd",
    "hook_event_name",
    "session_id",
    "stop_hook_active",
    "tool",
    "tool_name",
}
OPERATIONAL_PAYLOAD_KEYS = {*ALLOWED_METADATA_KEYS, "transcript_path"}


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
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip())
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


def event_metadata(payload: dict[str, Any]) -> dict[str, Any]:
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
    return metadata


def ensure_redaction_report(run_dir: Path) -> None:
    report = run_dir / "redaction-report.md"
    if report.exists():
        return
    report.write_text(
        "\n".join(
            [
                "# Redaction Report",
                "",
                "- created_by: .project-agent-workflow/hooks/agent_log_event.py",
                "- scope: allowlisted Codex hook event metadata only.",
                "- redaction: prompt, command, result, response, and transcript content are excluded; retained metadata still receives automatic secret-pattern redaction.",
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
        "payload": redact(event_metadata(payload)),
    }
    with (run_dir / ".events.lock").open("a", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            with event_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            agent_log_manifest.record_hook(run_dir, run, event_path)
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
    importer = root / ".project-agent-workflow/scripts/import-codex-transcript.py"
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
        append_event(args.event, load_payload())
    except Exception:
        pass
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
