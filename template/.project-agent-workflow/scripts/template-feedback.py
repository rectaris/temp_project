#!/usr/bin/env python3
"""Record template improvement evidence observed in a generated repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

MAX_BYTES = 64 * 1024
MAX_FIELD_BYTES = 4096
MAX_EVIDENCE = 16
RECORD_ROOT = PurePosixPath("docs/template-feedback")
DRAFT_ROOT = PurePosixPath(".agent-artifacts/template-feedback")
CONFIG_PATH = PurePosixPath("docs/agent/template-feedback.json")
ID_RE = re.compile(r"[a-z][a-z0-9-]{0,63}")
ALIAS_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
REVISION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}")
EVIDENCE_KINDS = {"agent_paraphrase", "synthetic_reproduction", "change_reference"}
CERTAINTIES = {"template_defect", "project_specific", "unknown"}
MODES = {"agent_select_local", "disabled"}
UNKNOWN = "unknown"
NONE = "none"

RECORD_KEYS = {
    "schema_version",
    "report_id",
    "project_alias",
    "template_source",
    "expected_behavior",
    "observed_behavior",
    "impact",
    "evidence",
    "desired_behavior",
    "workaround",
    "attribution",
    "supersedes",
}

# Selection of evidence is an explicit agent decision reviewed before any write.
# These patterns refuse obvious credential shapes; they are a floor, never a
# redaction service and never proof that reviewed text is safe to publish.
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(
        r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\b"
        r"\s*[:=]\s*\S{8,}"
    ),
)


class FeedbackError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_regular(path: Path, label: str) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as exc:
        raise FeedbackError(f"{label} is not a readable regular file: {path}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_BYTES:
            raise FeedbackError(f"{label} must be a bounded regular file: {path}")
        os.set_blocking(descriptor, True)
        data = b""
        while len(data) <= MAX_BYTES:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                break
            data += chunk
        if len(data) > MAX_BYTES:
            raise FeedbackError(f"{label} exceeds its byte bound: {path}")
        return data
    finally:
        os.close(descriptor)


def load_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    raw = read_regular(path, label)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FeedbackError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise FeedbackError(f"{label} must contain an object")
    return value, raw


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise FeedbackError(f"{label} has an invalid exact field shape")
    return value


def bounded_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise FeedbackError(f"{label} must be a string")
    if not value.strip():
        raise FeedbackError(f"{label} must not be empty; state an explicit unknown instead")
    if len(value.encode()) > MAX_FIELD_BYTES:
        raise FeedbackError(f"{label} exceeds its byte bound")
    if any(character in value for character in "\x00\r"):
        raise FeedbackError(f"{label} must not contain control characters")
    return value


def reject_suspected_secrets(value: str, label: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(value):
            raise FeedbackError(f"{label} contains a suspected credential; remove it before recording")


def safe_repository_path(root: Path, value: str, label: str) -> Path:
    if not isinstance(value, str) or "\\" in value:
        raise FeedbackError(f"{label} must be a repository-relative path")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or str(relative) != value
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise FeedbackError(f"{label} must be a normalized repository-relative path")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise FeedbackError(f"{label} must not contain a symlink")
    try:
        current.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise FeedbackError(f"{label} escapes the repository") from exc
    return current


def parse_evidence(entries: Any, root: Path) -> list[dict[str, Any]]:
    if not isinstance(entries, list) or not entries:
        raise FeedbackError("evidence must list at least one reviewed item")
    if len(entries) > MAX_EVIDENCE:
        raise FeedbackError("evidence exceeds its bounded item count")
    parsed: list[dict[str, Any]] = []
    for index, raw in enumerate(entries):
        label = f"evidence[{index}]"
        item = exact(raw, {"kind", "summary", "reference"}, label)
        if item["kind"] not in EVIDENCE_KINDS:
            raise FeedbackError(f"{label} uses an unsupported evidence kind")
        summary = bounded_text(item["summary"], f"{label}.summary")
        reject_suspected_secrets(summary, f"{label}.summary")
        reference = bounded_text(item["reference"], f"{label}.reference")
        reject_suspected_secrets(reference, f"{label}.reference")
        if reference != NONE:
            # A reference names a repository-relative location so a reader can
            # re-derive the claim; the recorder never copies raw file content.
            # Keeping it whitespace-free keeps it a location rather than a
            # second free-text field that escapes the evidence review.
            if any(character.isspace() for character in reference):
                raise FeedbackError(f"{label}.reference must be a path without whitespace")
            safe_repository_path(root, reference, f"{label}.reference")
        parsed.append(item)
    return parsed


def parse_record(path: Path, root: Path) -> tuple[dict[str, Any], bytes]:
    value, raw = load_json(path, "record")
    exact(value, RECORD_KEYS, "record")
    if value["schema_version"] != 1:
        raise FeedbackError("unsupported record schema")
    if not isinstance(value["report_id"], str) or not ID_RE.fullmatch(value["report_id"]):
        raise FeedbackError("report_id must use 1-64 lowercase letters, digits, or hyphens")
    if not isinstance(value["project_alias"], str) or not ALIAS_RE.fullmatch(value["project_alias"]):
        raise FeedbackError("project_alias must use 1-64 lowercase letters, digits, or hyphens")

    source = exact(value["template_source"], {"alias", "revision"}, "template_source")
    if not isinstance(source["alias"], str) or not ALIAS_RE.fullmatch(source["alias"]):
        raise FeedbackError("template_source.alias must use 1-64 lowercase letters, digits, or hyphens")
    revision = source["revision"]
    # An absent upstream revision stays an explicit unknown. Guessing one would
    # attach the report to a revision nobody observed.
    if revision != UNKNOWN and (not isinstance(revision, str) or not REVISION_RE.fullmatch(revision)):
        raise FeedbackError("template_source.revision must be an exact revision or the explicit unknown value")

    for field in ("expected_behavior", "observed_behavior", "impact", "desired_behavior"):
        text = bounded_text(value[field], field)
        reject_suspected_secrets(text, field)

    workaround = bounded_text(value["workaround"], "workaround")
    reject_suspected_secrets(workaround, "workaround")

    attribution = exact(value["attribution"], {"certainty", "reason"}, "attribution")
    if attribution["certainty"] not in CERTAINTIES:
        raise FeedbackError("attribution.certainty must be template_defect, project_specific, or unknown")
    reason = bounded_text(attribution["reason"], "attribution.reason")
    reject_suspected_secrets(reason, "attribution.reason")

    supersedes = value["supersedes"]
    if supersedes != NONE and (not isinstance(supersedes, str) or not ID_RE.fullmatch(supersedes)):
        raise FeedbackError("supersedes must name an existing report id or the explicit none value")
    if supersedes == value["report_id"]:
        raise FeedbackError("supersedes must not name the record itself")

    value["evidence"] = parse_evidence(value["evidence"], root)
    return value, raw


def parse_config(path: Path) -> dict[str, Any]:
    value, _ = load_json(path, "configuration")
    exact(value, {"schema_version", "project_alias", "mode"}, "configuration")
    if value["schema_version"] != 1:
        raise FeedbackError("unsupported configuration schema")
    if not isinstance(value["project_alias"], str) or not ALIAS_RE.fullmatch(value["project_alias"]):
        raise FeedbackError("configuration project_alias must use 1-64 lowercase letters, digits, or hyphens")
    if value["mode"] not in MODES:
        raise FeedbackError("configuration mode must be agent_select_local or disabled")
    return value


def record_relative_path(record: dict[str, Any]) -> PurePosixPath:
    return RECORD_ROOT / record["project_alias"] / f"{record['report_id']}.json"


def guard_command(root: Path) -> list[str] | None:
    # Resolve the working tree first, matching the shell lifecycle entry points.
    # A caller that points --root at a subdirectory must still meet the guard
    # that its repository ships.
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        top = Path(completed.stdout.strip()) if completed.returncode == 0 and completed.stdout.strip() else root
    except OSError:
        top = root
    for base in (top, root):
        for candidate in (
            Path(".project-agent-workflow/scripts/worktree_guard.py"),
            Path("scripts/project_workflow/worktree_guard.py"),
        ):
            if (base / candidate).is_file():
                return [sys.executable, str(base / candidate)]
    return None


def require_task_binding(root: Path, action: str) -> None:
    """Refuse a repository effect outside the task-bound worktree that owns it.

    A repository that ships no guard keeps its previous behavior instead of
    refusing every run, matching the shell lifecycle entry points.
    """

    command = guard_command(root)
    if command is None:
        return
    completed = subprocess.run(
        [*command, "require", "--action", action],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise FeedbackError(completed.stderr.strip() or "task worktree guard refused this write")


def atomic_write(path: Path, content: str) -> None:
    if path.is_symlink():
        raise FeedbackError(f"refusing symlink output: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_directory(root: Path, relative: PurePosixPath) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise FeedbackError(f"refusing symlink directory: {relative}")
        current.mkdir(exist_ok=True)
        if not current.is_dir():
            raise FeedbackError(f"refusing non-directory output location: {relative}")
    return current


def resolve_root(value: str | None) -> Path:
    root = Path(value or ".").resolve()
    if not root.is_dir():
        raise FeedbackError(f"repository root is not a directory: {root}")
    return root


def resolve_config(root: Path, value: str | None) -> Path:
    if value is None:
        return root / CONFIG_PATH
    return Path(value)


def existing_report_ids(root: Path, alias: str) -> set[str]:
    directory = root / RECORD_ROOT / alias
    if not directory.is_dir() or directory.is_symlink():
        return set()
    return {entry.stem for entry in directory.iterdir() if entry.is_file() and entry.suffix == ".json"}


def assessment(root: Path, record: dict[str, Any], raw: bytes, config: dict[str, Any]) -> dict[str, Any]:
    if record["project_alias"] != config["project_alias"]:
        raise FeedbackError("record project_alias does not match the configured project alias")
    relative = record_relative_path(record)
    return {
        "decision": "no_op" if config["mode"] == "disabled" else "record",
        "mode": config["mode"],
        "report_id": record["report_id"],
        "checked_digest": digest(raw),
        "record_path": str(relative),
        "template_revision": record["template_source"]["revision"],
        "attribution_certainty": record["attribution"]["certainty"],
        "supersedes": record["supersedes"],
    }


def command_example(args: argparse.Namespace) -> int:
    del args
    sys.stdout.write(
        json_text(
            {
                "schema_version": 1,
                "report_id": "plan-worktree-publish-confusion",
                "project_alias": "example-project",
                "template_source": {"alias": "project-agent-workflow", "revision": UNKNOWN},
                "expected_behavior": "Publishing a finished plan leaves no task worktree behind.",
                "observed_behavior": "The worktree stayed after publish, so the next task resumed the stale checkout.",
                "impact": "Two tasks wrote to the same checkout for one afternoon before anyone noticed.",
                "evidence": [
                    {
                        "kind": "agent_paraphrase",
                        "summary": "The publish output reported success while the worktree list still showed the task path.",
                        "reference": NONE,
                    },
                    {
                        "kind": "change_reference",
                        "summary": "The local workaround removes the worktree by hand after every publish.",
                        "reference": "docs/agent/SPEC_PLAN_WORKFLOW.md",
                    },
                ],
                "desired_behavior": "Publish should report the worktree removal it actually performed.",
                "workaround": "Run the retirement command by hand after each publish.",
                "attribution": {
                    "certainty": UNKNOWN,
                    "reason": "The local checkout carries project-specific hooks that were not ruled out.",
                },
                "supersedes": NONE,
            }
        )
    )
    return 0


def command_check(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    config = parse_config(resolve_config(root, args.config))
    record, raw = parse_record(Path(args.record), root)
    sys.stdout.write(json_text(assessment(root, record, raw, config)))
    return 0


def command_draft(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    config = parse_config(resolve_config(root, args.config))
    record, raw = parse_record(Path(args.record), root)
    result = assessment(root, record, raw, config)
    if result["decision"] == "no_op":
        sys.stdout.write(json_text(result))
        return 0
    # A draft stays in the ignored local artifact tree, so preparing one needs
    # no task binding and leaves the tracked tree untouched.
    directory = prepare_directory(root, DRAFT_ROOT)
    destination = directory / f"{record['report_id']}.json"
    atomic_write(destination, json_text(record))
    result["draft_path"] = str(DRAFT_ROOT / destination.name)
    sys.stdout.write(json_text(result))
    return 0


def command_record(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    config = parse_config(resolve_config(root, args.config))
    record, raw = parse_record(Path(args.record), root)
    result = assessment(root, record, raw, config)
    if result["decision"] == "no_op":
        raise FeedbackError("recording is disabled for this project; no report was written")
    if args.checked_digest != result["checked_digest"]:
        raise FeedbackError("checked digest does not match the supplied record bytes")

    known = existing_report_ids(root, record["project_alias"])
    if record["supersedes"] != NONE and record["supersedes"] not in known:
        raise FeedbackError("supersedes names a report that this repository does not hold")

    relative = record_relative_path(record)
    content = json_text(record)
    destination = safe_repository_path(root, str(relative), "record_path")
    if destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise FeedbackError(f"refusing unsafe existing record: {relative}")
        if destination.read_text(encoding="utf-8") == content:
            # An identical retry is the same accepted record, not a second one.
            result["outcome"] = "unchanged"
            sys.stdout.write(json_text(result))
            return 0
        raise FeedbackError(
            f"an immutable record already exists with different bytes: {relative}; "
            "record a correction under a new report id with an explicit supersedes reference"
        )

    require_task_binding(root, "recording template improvement evidence")
    prepare_directory(root, relative.parent)
    atomic_write(root / relative, content)
    result["outcome"] = "written"
    sys.stdout.write(json_text(result))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("example", help="print a complete example improvement record")

    for name, help_text in (
        ("check", "validate a record and report the decision its configuration allows"),
        ("draft", "validate a record and keep it in the ignored local artifact tree"),
        ("record", "persist a reviewed record under the project-owned report tree"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--record", required=True, help="path to the structured improvement record")
        command.add_argument("--config", help=f"path to the project configuration (default {CONFIG_PATH})")
        command.add_argument("--root", help="repository root (default the current directory)")
        if name == "record":
            command.add_argument(
                "--checked-digest",
                required=True,
                help="the checked_digest reported by the preceding check",
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "example": command_example,
        "check": command_check,
        "draft": command_draft,
        "record": command_record,
    }
    try:
        return handlers[args.command](args)
    except FeedbackError as exc:
        print(f"template feedback failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
