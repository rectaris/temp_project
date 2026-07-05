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


SECRET_KEY_RE = re.compile(r"(token|secret|password|passwd|api[_-]?key|authorization|credential|private[_-]?key)", re.I)
SECRET_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|xox[baprs]-[A-Za-z0-9-]{16,})")
MAX_STRING = 12000
MAX_LIST = 200
MAX_DICT = 200


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
    date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    seed = f"{repo_root()}:{session or date_prefix}"
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
        return value if isinstance(value, dict) else {"payload": value}
    except Exception as exc:
        return {"_parse_error": str(exc)}


def write_json(path: Path, value: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


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
        "redaction_status": "automatic_redaction",
    }
    manifest["coverage"] = coverage
    missing_sources = []
    if not coverage["external_transcript"]["present"]:
        missing_sources.append("external_transcript")
    if not coverage["codex_hooks"]["present"]:
        missing_sources.append("codex_hooks")
    manifest["missing_sources"] = missing_sources
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
    update_manifest(run_dir, run, event_path)
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
