#!/usr/bin/env python3
"""Create and update generated-project agent log manifests."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRANSCRIPT_REL = "raw/transcript.jsonl"
HOOK_REL = "raw/events.jsonl"


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
    manifest["updated_at"] = utc_now()
    write_json(run_dir / "manifest.json", manifest)


def record_hook(run_dir: Path, run_id: str, event_path: Path) -> None:
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
        finalize_manifest(run_dir, manifest)


def record_transcript(run_dir: Path, run_id: str, redaction_status: str) -> None:
    with manifest_lock(run_dir):
        manifest = load_manifest(run_dir, run_id, "codex transcript import")
        manifest["transcript_log"] = TRANSCRIPT_REL
        raw_logs = {value for value in manifest.get("raw_logs", []) if isinstance(value, str)}
        raw_logs.add(TRANSCRIPT_REL)
        manifest["raw_logs"] = sorted(raw_logs)
        coverage = manifest.get("coverage") if isinstance(manifest.get("coverage"), dict) else {}
        coverage["external_transcript"] = source_coverage(TRANSCRIPT_REL, True, redaction_status)
        manifest["coverage"] = coverage
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
