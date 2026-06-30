#!/usr/bin/env python3
"""Validate hybrid agent log run manifests."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


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
    return run_dir / value


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
    redaction_report = resolve_declared_path(run_dir, manifest.get("redaction_report"), "redaction_report")
    if redaction_report is not None and not redaction_report.is_file():
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


def validate_manifest(path: Path, require_transcript: bool = False, require_hooks: bool = False) -> list[str]:
    manifest = load_json(path)
    if not isinstance(manifest, dict):
        raise ValidationError(f"{path}: manifest must be an object")
    missing = sorted(REQUIRED_KEYS - set(manifest))
    if missing:
        raise ValidationError(f"{path}: missing required keys: {missing}")
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
    }


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
        expect_failure(bad_transcript)


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
