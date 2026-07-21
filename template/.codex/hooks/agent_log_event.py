#!/usr/bin/env python3
"""Best-effort Codex lifecycle event logger."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import agent_log_manifest


SECRET_KEY_RE = re.compile(r"(token|secret|password|passwd|api[_-]?key|authorization|credential|private[_-]?key)", re.I)
SECRET_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|xox[baprs]-[A-Za-z0-9-]{16,})")
MAX_STRING = 12000
MAX_LIST = 200
MAX_DICT = 200
ALLOWED_PAYLOAD_KEYS = {
    "arguments",
    "cwd",
    "hook_event_name",
    "prompt",
    "result",
    "session_id",
    "stop_hook_active",
    "tool",
    "tool_input",
    "tool_name",
    "tool_response",
    "transcript_path",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_root() -> Path:
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def run_id() -> str:
    existing = os.environ.get("CODEX_AGENT_LOG_RUN_ID") or os.environ.get("AGENT_LOG_RUN_ID")
    if existing:
        return safe_name(existing)
    session = os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID")
    date_prefix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    seed = f"{repo_root()}:{session or f'{date_prefix}:{os.getpid()}'}"
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
        return {key: item for key, item in value.items() if key in ALLOWED_PAYLOAD_KEYS}
    except Exception as exc:
        return {"_parse_error": str(exc)}


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
    run = run_id()
    run_dir = root / ".agent-logs" / run
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    event_path = raw_dir / "events.jsonl"
    record = {
        "schema_version": 1,
        "event": event,
        "created_at": utc_now(),
        "cwd": str(Path.cwd()),
        "payload": redact(payload),
    }
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    agent_log_manifest.record_hook(run_dir, run, event_path)
    ensure_redaction_report(run_dir)
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
        append_event(args.event, load_payload())
    except Exception:
        pass
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
