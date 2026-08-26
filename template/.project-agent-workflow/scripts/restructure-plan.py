#!/usr/bin/env python3
"""Atomically replace one stopped active plan without changing its requirements."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True


ROOT = Path.cwd()
ACTIVE_INDEX = ROOT / "docs/plan/plan.md"
REPLANNED_INDEX = ROOT / "docs/plan/replanned.md"
LOCK = ROOT / ".agent-artifacts/plan-lifecycle.lock"
MAX_SPEC_BYTES = 1_048_576
MAX_PLANS = 8
ACTIVE_PLAN_STATUSES = {"in_progress", "ready_to_archive", "deferred", "replan_required"}
REQUIRED_PLAN_FIELDS = {
    "status", "task_types", "review_class", "human_design_required", "human_approval_status",
    "write_scope", "context_files", "required_specs", "validation", "acceptance",
    "checked_summary_ja",
}
REASON_CODES = {
    "scope_drift",
    "spec_drift",
    "security_boundary_drift",
    "multiple_independent_invariants",
    "post_authoritative_design_change",
    "candidate_correction_budget_exhausted",
    "parent_remediation_budget_exhausted",
}
SOURCE_KINDS = {"contract_successor", "direct_active"}
DIRECT_ACTIVE_LINEAGE_FIELDS = (
    "replan_source",
    "replan_sources",
    "replan_contract",
    "inherited_acceptance_digests",
    "successor_plans",
    "integration_source_ids",
)
SCHEMA_THREE_SOURCE_FIELDS = {
    "id",
    "path",
    "head",
    "original_plan_digest",
    "original_content",
    "stopped_plan_digest",
    "stopped_content",
    "acceptance",
    "acceptance_digests",
    "acceptance_text_by_digest",
    "reason_codes",
    "archive_path",
}
SCHEMA_THREE_CONTRACT_SOURCE_FIELDS = {
    "source_contract_path",
    "source_contract_digest",
}
PLAN_PATH_RE = re.compile(r"docs/plan/active/([0-9]{3})-([a-z0-9][a-z0-9-]*)\.md")
ARCHIVE_PATH_RE = re.compile(
    r"docs/plan/replanned/[0-9]{4}/[0-9]{2}/(?:01-15|16-31)/([0-9]{3}-[a-z0-9][a-z0-9-]*\.md)"
)
CONTRACT_PATH_RE = re.compile(r"docs/plan/replanned/contracts/[0-9]{3}-[a-z0-9][a-z0-9-]*\.json")
COMPANION_PATH = "docs/plan/replanned/baselines/live-validation-successors-v1.json"
REBIND_BASELINE_PATH = "docs/plan/replanned/baselines/live-successor-rebinds-v1.json"
COMPANION_PLAN_PATH = "docs/plan/active/190-migrate-live-plan-contracts.md"
SHA_RE = re.compile(r"sha256:[0-9a-f]{64}")
CHECKED_PATH_RE = re.compile(
    r"docs/plan/checked/[0-9]{4}/[0-9]{2}/(?:01-15|16-31)/"
    r"([0-9]{3})-([a-z0-9][a-z0-9-]*)\.md"
)
JOURNAL_SCHEMA_VERSION = 2
IDENTITY_KEYS = {"device", "inode", "mode", "link_count", "digest"}
REPLACEMENT_IDENTITY_KEYS = {"temporary", "restored"}
JOURNAL_PHASES = {
    "prepared",
    "temps_prepared",
    "applying",
    "rolling_back",
    "commit_point",
    "replaying",
    "verifying",
    "complete",
    "rolled_back",
}
JOURNAL_TRANSITIONS = {
    "prepared": {"temps_prepared", "rolling_back"},
    "temps_prepared": {"applying", "rolling_back"},
    "applying": {"applying", "commit_point", "rolling_back"},
    "rolling_back": {"rolling_back", "rolled_back"},
    "commit_point": {"replaying", "verifying"},
    "replaying": {"replaying", "verifying"},
    "verifying": {"verifying", "complete"},
    "complete": set(),
    "rolled_back": set(),
}
REBIND_KINDS = {"rebind", "activation"}
REBIND_FIELDS = {
    "completion_deferred_reason",
    "context_files",
    "focused_validation",
    "validation",
    "validation_witness_map",
    "predecessor_plans",
    "integration_gates",
}
ACTIVATION_FIELDS = {
    "status",
    "completion_deferred_reason",
    "context_files",
    "predecessor_plans",
    "integration_gates",
    "preservation_scope",
}
VALIDATION_REPLACEMENT_FIELDS = {
    "focused_validation",
    "validation",
    "validation_witness_map",
}
SEMANTIC_VALIDATION_PATH_REBINDINGS = frozenset(
    {
        (
            "scripts/project_workflow/copier_fixture.py",
            "scripts/project_workflow/copier_fixture_validator.py",
        ),
        (
            "tests/test-copier-fixture.py",
            "tests/test-copier-fixture-validator.py",
        ),
    }
)
REBIND_PROTECTED_FIELDS = {
    "status",
    "primary_invariant",
    "acceptance",
    "write_scope",
    "preservation_scope",
    "task_types",
    "required_specs",
    "implementation_risk",
    "implementation_ambiguity",
    "review_class",
    "human_design_required",
    "human_approval_status",
    "replan_source",
    "replan_sources",
    "replan_contract",
    "successor_plans",
    "inherited_acceptance_digests",
    "integration_source_ids",
    "checked_summary_ja",
}
PATH_TOKEN_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/-"
)
ACTIVE_REFERENCE_RE = re.compile(
    r"docs/plan/active/[0-9]{3}-[a-z0-9][a-z0-9-]*\.md"
)


class RestructureError(ValueError):
    pass


class SimulatedCrash(BaseException):
    pass


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_digest(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def exact_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise RestructureError(f"{label} must contain exactly: {', '.join(sorted(keys))}")
    return value


def normalized_path(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise RestructureError(f"invalid {label}: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RestructureError(f"non-normalized {label}: {value!r}")
    return value


def reject_symlink_ancestors(relative: str, *, include_target: bool) -> None:
    current = ROOT
    parts = PurePosixPath(relative).parts
    limit = len(parts) if include_target else len(parts) - 1
    for part in parts[:limit]:
        current /= part
        if current.is_symlink():
            raise RestructureError(f"symlink path component is not allowed: {current.relative_to(ROOT)}")


def run_git(*args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if completed.returncode != 0:
        raise RestructureError(completed.stderr.decode("utf-8", "replace").strip() or "git failed")
    return completed.stdout


def current_head() -> str:
    repository_root = run_git("rev-parse", "--show-toplevel").decode().strip()
    if Path(repository_root).resolve() != ROOT.resolve():
        raise RestructureError("run plan restructuring from the repository root")
    value = run_git("rev-parse", "HEAD").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise RestructureError("git HEAD is not a full object id")
    return value


def git_local_path(relative: str) -> Path:
    raw = run_git("rev-parse", "--git-path", relative).decode("utf-8").strip()
    if not raw:
        raise RestructureError("Git returned an empty local path")
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def reject_filesystem_symlinks(path: Path, *, include_target: bool) -> None:
    absolute = path.absolute()
    parts = absolute.parts
    current = Path(parts[0])
    limit = len(parts) if include_target else len(parts) - 1
    for part in parts[1:limit]:
        current /= part
        if current.is_symlink():
            raise RestructureError(f"symlink path component is not allowed: {current}")


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def ensure_directories(path: Path) -> list[Path]:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    if not current.is_dir() or current.is_symlink():
        raise RestructureError(f"parent path is not a safe directory: {current}")
    for directory in reversed(missing):
        directory.mkdir(mode=0o755)
        fsync_directory(directory.parent)
    return missing


def read_regular_file(path: Path, label: str, *, mode_0600: bool = False) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise RestructureError(f"{label} must be one unlinked regular file")
        mode = stat.S_IMODE(metadata.st_mode)
        if mode_0600 and mode != 0o600:
            raise RestructureError(f"{label} must have mode 0600")
        if not mode_0600 and mode & 0o002:
            raise RestructureError(f"{label} has an unsafe writable mode")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 65_536)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def file_snapshot(relative: str) -> tuple[str | None, int | None]:
    reject_symlink_ancestors(relative, include_target=True)
    path = ROOT / relative
    if not path.exists():
        if path.is_symlink():
            raise RestructureError(f"symlink target is not allowed: {relative}")
        reject_symlink_ancestors(relative, include_target=False)
        return None, None
    data = read_regular_file(path, relative)
    return data.decode("utf-8"), stat.S_IMODE(path.stat().st_mode)


def atomic_replace_text(path: Path, text: str, mode: int) -> None:
    ensure_directories(path.parent)
    reject_filesystem_symlinks(path, include_target=False)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def committed_file_bytes(relative: str) -> bytes | None:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{relative}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return None
    return run_git("show", f"HEAD:{relative}")


def historical_contract_snapshot(
    rows: list[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    index_relative = "docs/plan/replanned.md"
    index_path = ROOT / index_relative
    index_data = read_regular_file(index_path, index_relative)
    try:
        index_text = index_data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RestructureError("replanned plan index is not UTF-8") from exc
    if replanned_rows(index_text) != rows:
        raise RestructureError("replanned plan index rows changed during verification")
    if index_text != render_replanned(rows):
        raise RestructureError("replanned plan index bytes are not canonical")
    committed_index = committed_file_bytes("docs/plan/replanned.md")
    if committed_index is not None:
        try:
            committed_rows = replanned_rows(committed_index.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise RestructureError(
                "committed replanned plan index is not UTF-8"
            ) from exc
        if (
            committed_index.decode("utf-8") != render_replanned(committed_rows)
            or rows[:len(committed_rows)] != committed_rows
            or not index_data.startswith(committed_index)
        ):
            raise RestructureError(
                "replanned plan index rewrites committed history"
            )
    paths = sorted(
        {
            index_relative,
            *{
                path
                for _, archive_path, contract_path in rows
                for path in (archive_path, contract_path)
            },
        }
    )
    snapshot: list[dict[str, Any]] = []
    for relative in paths:
        path = ROOT / relative
        data = read_regular_file(path, relative)
        metadata = os.lstat(path)
        committed = committed_file_bytes(relative)
        if (
            relative != index_relative
            and committed is not None
            and committed != data
        ):
            raise RestructureError(
                f"historical contract or archive differs from committed bytes: {relative}"
            )
        snapshot.append(
            {
                "path": relative,
                "content_digest": sha256(data),
                "committed_digest": (
                    sha256(committed) if committed is not None else None
                ),
                "mode": stat.S_IMODE(metadata.st_mode),
                "device": metadata.st_dev,
                "inode": metadata.st_ino,
                "link_count": metadata.st_nlink,
            }
        )
    return snapshot


def require_historical_contract_snapshot(
    expected: list[dict[str, Any]],
    *,
    mutable_paths: set[str] | None = None,
) -> None:
    current_rows = (
        replanned_rows(REPLANNED_INDEX.read_text(encoding="utf-8"))
        if REPLANNED_INDEX.is_file()
        else []
    )
    current = {
        entry["path"]: entry
        for entry in historical_contract_snapshot(current_rows)
    }
    mutable = mutable_paths or set()
    for entry in expected:
        actual = current.get(entry["path"])
        if actual is None:
            raise RestructureError(
                "historical contract, archive, or index disappeared during execution"
            )
        if entry["path"] in mutable:
            stable_fields = {
                "path",
                "committed_digest",
                "mode",
                "device",
                "link_count",
            }
            if any(actual[field] != entry[field] for field in stable_fields):
                raise RestructureError(
                    "historical mutable index identity changed during execution"
                )
        elif actual != entry:
            raise RestructureError(
                "historical contract, archive, or index changed during execution"
            )


def parse_manifest(text: str) -> dict[str, str | list[str]]:
    values: dict[str, str | list[str]] = {}
    current: str | None = None
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            break
        if not line.strip():
            continue
        if ":" in line and not line.startswith(" "):
            key, rest = line.split(":", 1)
            key = key.strip()
            if key in seen:
                raise RestructureError(f"duplicate manifest field: {key}")
            seen.add(key)
            rest = rest.strip()
            values[key] = rest if rest else []
            current = None if rest else key
            continue
        if current and line.lstrip().startswith("- "):
            item = line.lstrip()[2:].strip()
            assert isinstance(values[current], list)
            values[current].append(item)
    return values


def scalar(values: dict[str, str | list[str]], key: str) -> str:
    value = values.get(key, "")
    return value if isinstance(value, str) else ""


def items(values: dict[str, str | list[str]], key: str) -> list[str]:
    value = values.get(key, [])
    return value if isinstance(value, list) else []


def acceptance_records(text: str) -> list[dict[str, str]]:
    accepted = items(parse_manifest(text), "acceptance")
    if not accepted or len(accepted) != len(set(accepted)):
        raise RestructureError("source acceptance must be non-empty and unique")
    return [{"text": item, "digest": sha256(item.encode("utf-8"))} for item in accepted]


def dirty_product_paths() -> list[str]:
    raw = run_git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    records = raw.split(b"\0")
    found: set[str] = set()
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4 or record[2:3] != b" ":
            raise RestructureError("could not parse git status")
        status = record[:2]
        paths = [record[3:]]
        if b"R" in status or b"C" in status:
            if index >= len(records) or not records[index]:
                raise RestructureError("could not parse renamed git status entry")
            paths.append(records[index])
            index += 1
        for raw_path in paths:
            path = raw_path.decode("utf-8", "strict")
            if path.startswith("docs/plan/") or path.startswith(".agent-artifacts/"):
                continue
            found.add(path)
    return sorted(found)


def dirty_product_snapshot(paths: list[str]) -> list[dict[str, Any]]:
    if paths != sorted(set(paths)):
        raise RestructureError("dirty product snapshot paths must be unique and ordered")
    snapshot: list[dict[str, Any]] = []
    for relative in paths:
        status_bytes = run_git(
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--",
            relative,
        )
        index_bytes = run_git("ls-files", "--stage", "-z", "--", relative)
        path = ROOT / relative
        try:
            metadata = os.lstat(path)
        except FileNotFoundError:
            file_state: dict[str, Any] = {"kind": "missing"}
        else:
            common = {
                "mode": stat.S_IMODE(metadata.st_mode),
                "device": metadata.st_dev,
                "inode": metadata.st_ino,
                "link_count": metadata.st_nlink,
                "size": metadata.st_size,
                "mtime_ns": metadata.st_mtime_ns,
                "ctime_ns": metadata.st_ctime_ns,
            }
            if stat.S_ISLNK(metadata.st_mode):
                file_state = {
                    **common,
                    "kind": "symlink",
                    "target_digest": sha256(
                        os.readlink(path).encode("utf-8", "surrogateescape")
                    ),
                }
            elif stat.S_ISREG(metadata.st_mode):
                descriptor = os.open(
                    path,
                    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                )
                try:
                    opened = os.fstat(descriptor)
                    chunks: list[bytes] = []
                    while True:
                        chunk = os.read(descriptor, 65_536)
                        if not chunk:
                            break
                        chunks.append(chunk)
                    finished = os.fstat(descriptor)
                finally:
                    os.close(descriptor)
                identity = (
                    opened.st_dev,
                    opened.st_ino,
                    opened.st_mode,
                    opened.st_nlink,
                    opened.st_size,
                    opened.st_mtime_ns,
                    opened.st_ctime_ns,
                )
                if identity != (
                    finished.st_dev,
                    finished.st_ino,
                    finished.st_mode,
                    finished.st_nlink,
                    finished.st_size,
                    finished.st_mtime_ns,
                    finished.st_ctime_ns,
                ):
                    raise RestructureError(
                        f"dirty product path changed while reading: {relative}"
                    )
                file_state = {
                    **common,
                    "kind": "regular",
                    "content_digest": sha256(b"".join(chunks)),
                }
            else:
                raise RestructureError(
                    f"dirty product path has unsupported type: {relative}"
                )
        snapshot.append(
            {
                "path": relative,
                "status_digest": sha256(status_bytes),
                "index_digest": sha256(index_bytes),
                "file": file_state,
            }
        )
    return snapshot


def scope_covers(scope: list[str], path: str) -> bool:
    for entry in scope:
        if entry.endswith("/") and path.startswith(entry):
            return True
        if path == entry:
            return True
    return False


def preservation_scope(manifest: dict[str, str | list[str]], label: str, *, required: bool) -> list[str]:
    if "preservation_scope" not in manifest:
        if required:
            raise RestructureError(f"{label} requires preservation_scope")
        return []
    scope = items(manifest, "preservation_scope")
    if scope == ["none"]:
        return []
    if not scope or "none" in scope or len(scope) != len(set(scope)):
        raise RestructureError(
            f"{label} preservation_scope must be none or unique normalized exact paths"
        )
    for entry in scope:
        path = PurePosixPath(entry)
        if (
            not entry
            or entry.startswith("/")
            or entry.endswith("/")
            or "\\" in entry
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise RestructureError(
                f"{label} preservation_scope must be none or unique normalized exact paths"
            )
    return scope


def reject_preservation_write_overlap(
    preservation_paths: list[str],
    write_scopes: list[list[str]],
    label: str,
) -> None:
    overlaps = sorted(
        path
        for path in preservation_paths
        if any(scope_covers(scope, path) for scope in write_scopes)
    )
    if overlaps:
        raise RestructureError(
            f"{label} preservation_scope overlaps write_scope: {', '.join(overlaps)}"
        )


def routing_contract(spec_index: Path) -> tuple[set[str], dict[str, set[str]]]:
    default_reads: set[str] = set()
    routes: dict[str, set[str]] = {}
    section = ""
    current = ""
    in_required = False
    for line in spec_index.read_text(encoding="utf-8").splitlines():
        if line == "default_reads:":
            section = "default"
            current = ""
            in_required = False
            continue
        if line == "task_types:":
            section = "routes"
            current = ""
            in_required = False
            continue
        if section == "default":
            match = re.fullmatch(r"  - (.+)", line)
            if match:
                default_reads.add(match.group(1))
            continue
        match = re.fullmatch(r"  ([a-z][a-z0-9_]*):", line)
        if match:
            current = match.group(1)
            routes[current] = set()
            in_required = False
            continue
        if current and line == "    required:":
            in_required = True
            continue
        if current and line.startswith("    ") and not line.startswith("      - "):
            in_required = False
        if current and in_required:
            required = re.fullmatch(r"      - (.+)", line)
            if required:
                routes[current].add(required.group(1))
    return default_reads, routes


def validation_command_module() -> Any:
    command_module_path = Path(__file__).with_name("plan_validation_commands.py")
    if not command_module_path.is_file():
        raise RestructureError("missing plan validation command policy")
    module_spec = importlib.util.spec_from_file_location(
        "restructure_plan_validation",
        command_module_path,
    )
    if module_spec is None or module_spec.loader is None:
        raise RestructureError("could not load plan validation command policy")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    return module


def validate_current_plan_rules(manifest: dict[str, str | list[str]], label: str) -> None:
    task_types = items(manifest, "task_types")
    required_specs = items(manifest, "required_specs")
    context_files = items(manifest, "context_files")
    write_scope = items(manifest, "write_scope")
    preserved = preservation_scope(manifest, label, required=False)
    if len(task_types) != len(set(task_types)) or not task_types:
        raise RestructureError(f"{label} task_types must be non-empty and unique")
    spec_candidates = (
        ROOT / ".project-agent-workflow/docs/agent/spec-index.yaml",
        ROOT / "docs/agent/spec-index.yaml",
    )
    spec_index = next((path for path in spec_candidates if path.is_file()), None)
    if spec_index is None:
        raise RestructureError("missing plan routing spec index")
    default_reads, routes = routing_contract(spec_index)
    unknown = sorted(set(task_types) - set(routes))
    if unknown:
        raise RestructureError(f"{label} has unknown task_types: {', '.join(unknown)}")
    expected_specs = set(default_reads)
    for task_type in task_types:
        expected_specs.update(routes[task_type])
    missing_specs = sorted(expected_specs - set(required_specs))
    if missing_specs:
        raise RestructureError(f"{label} required_specs is missing: {', '.join(missing_specs)}")
    overlap = sorted((set(write_scope) - {"none"}) & (set(context_files) - {"none"}))
    if overlap:
        raise RestructureError(f"{label} write_scope overlaps context_files: {', '.join(overlap)}")
    reject_preservation_write_overlap(preserved, [write_scope], label)
    module = validation_command_module()
    for command in [
        *items(manifest, "focused_validation"),
        *items(manifest, "validation"),
    ]:
        try:
            module.parse_validation_command(command)
        except Exception as exc:
            raise RestructureError(f"{label} validation command is invalid: {exc}") from exc


def validation_projection(
    manifest: dict[str, str | list[str]],
    label: str,
    *,
    require_witness: bool,
    enforce_witness_semantics: bool = True,
) -> dict[str, Any]:
    commands = items(manifest, "validation")
    if not commands or len(commands) != len(set(commands)):
        raise RestructureError(f"{label} validation commands must be non-empty and unique")
    schema = scalar(manifest, "validation_witness_schema")
    raw_map = items(manifest, "validation_witness_map")
    if require_witness and schema != "1":
        raise RestructureError(f"{label} requires validation_witness_schema: 1")
    if require_witness and not raw_map:
        raise RestructureError(f"{label} requires validation_witness_map")
    if schema not in {"", "1"}:
        raise RestructureError(f"{label} has unsupported validation_witness_schema")
    records: list[dict[str, str]] = []
    for index, raw in enumerate(raw_map, start=1):
        try:
            record = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RestructureError(
                f"{label} validation_witness_map entry {index} is invalid"
            ) from exc
        if not isinstance(record, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in record.items()
        ):
            raise RestructureError(
                f"{label} validation_witness_map entry {index} is invalid"
            )
        stage = record.get("stage")
        expected_keys = {"acceptance_sha256", "stage", "witness"}
        if stage == "authoritative":
            expected_keys.add("authoritative_only_reason")
        if set(record) != expected_keys or stage not in {
            "static",
            "focused",
            "authoritative",
        }:
            raise RestructureError(
                f"{label} validation_witness_map entry {index} is invalid"
            )
        witness = record["witness"]
        if enforce_witness_semantics and stage == "static":
            if witness != "resolved-context-files":
                raise RestructureError(
                    f"{label} validation_witness_map entry {index} has unknown static witness"
                )
        elif enforce_witness_semantics and stage == "focused":
            if witness not in items(manifest, "focused_validation"):
                raise RestructureError(
                    f"{label} validation_witness_map entry {index} focused witness is not declared"
                )
        elif enforce_witness_semantics and stage == "authoritative":
            if witness not in commands or witness in items(manifest, "focused_validation"):
                raise RestructureError(
                    f"{label} validation_witness_map entry {index} authoritative witness is invalid"
                )
            reason = record["authoritative_only_reason"]
            if (
                not reason
                or reason != reason.strip()
                or len(reason.encode("utf-8")) > 512
                or any(ord(char) < 0x20 for char in reason)
            ):
                raise RestructureError(
                    f"{label} validation_witness_map entry {index} authoritative-only reason is invalid"
                )
        records.append(record)
    acceptance_digests = [
        sha256(value.encode("utf-8")) for value in items(manifest, "acceptance")
    ]
    if raw_map and [record["acceptance_sha256"] for record in records] != acceptance_digests:
        raise RestructureError(
            f"{label} validation_witness_map must cover acceptance in source order"
        )
    return {
        "authoritative_validation": commands,
        "authoritative_validation_digest": canonical_digest(commands),
        "validation_witness_schema": int(schema) if schema else None,
        "validation_witness_map_digest": canonical_digest(records),
    }


def validate_projection(
    projection: dict[str, Any],
    manifest: dict[str, str | list[str]],
    label: str,
) -> None:
    expected = validation_projection(
        manifest,
        label,
        require_witness=projection["validation_witness_schema"] == 1,
    )
    if projection != expected:
        raise RestructureError(f"{label} validation projection mismatch")


def active_rows(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        if re.match(r"^[0-9]{3}\t", line):
            parts = line.split("\t")
            if len(parts) != 3:
                raise RestructureError(f"malformed active index row: {line}")
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def render_active(rows: list[tuple[str, str, str]]) -> str:
    if not rows:
        return "# Active Plan\n\nNo active development items.\n"
    body = "\n".join("\t".join(row) for row in rows)
    return f"# Active Plan\n\nid\tpath\tstatus\n{body}\n"


def replanned_rows(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        if re.match(r"^[0-9]{3}\t", line):
            parts = line.split("\t")
            if len(parts) != 3:
                raise RestructureError(f"malformed replanned index row: {line}")
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def checked_rows() -> list[tuple[str, str]]:
    index = ROOT / "docs/plan/checked.md"
    if not index.is_file():
        return []
    rows: list[tuple[str, str]] = []
    for line in index.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^[0-9]{3}\t", line):
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise RestructureError(f"malformed checked index row: {line}")
        rows.append((parts[0], parts[1]))
    return rows


def predecessor_paths(manifest: dict[str, str | list[str]], label: str) -> list[str]:
    predecessors = items(manifest, "predecessor_plans")
    if predecessors == ["[]"]:
        return []
    if len(predecessors) != len(set(predecessors)):
        raise RestructureError(f"{label} predecessor_plans must not contain duplicates")
    for predecessor in predecessors:
        path = PurePosixPath(predecessor)
        if (
            not predecessor
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or not (
                PLAN_PATH_RE.fullmatch(predecessor)
                or CHECKED_PATH_RE.fullmatch(predecessor)
            )
        ):
            raise RestructureError(f"{label} has invalid predecessor path: {predecessor!r}")
    return predecessors


def matching_checked_paths(
    plan_id: str,
    basename: str,
    rows: list[tuple[str, str]],
) -> list[str]:
    related = [
        path for indexed_id, path in rows
        if indexed_id == plan_id or Path(path).name == basename
    ]
    exact = [
        path for indexed_id, path in rows
        if indexed_id == plan_id and Path(path).name == basename
    ]
    if related and len(exact) != len(related):
        raise RestructureError(f"predecessor identity mismatch for plan {plan_id}")
    return exact


def validate_active_predecessors(
    records: dict[str, tuple[str, dict[str, str | list[str]]]],
) -> None:
    checked = checked_rows()
    graph: dict[str, list[str]] = {path: [] for path in records}
    for path, (status, manifest) in records.items():
        unresolved: list[str] = []
        for predecessor in predecessor_paths(manifest, path):
            active_match = PLAN_PATH_RE.fullmatch(predecessor)
            if active_match is not None:
                if predecessor in records:
                    graph[path].append(predecessor)
                    unresolved.append(predecessor)
                    continue
                exact_checked = matching_checked_paths(
                    active_match.group(1), Path(predecessor).name, checked
                )
                if not exact_checked:
                    raise RestructureError(f"{path} predecessor is missing: {predecessor}")
                unresolved.append(predecessor)
                continue
            checked_match = CHECKED_PATH_RE.fullmatch(predecessor)
            assert checked_match is not None
            exact_checked = matching_checked_paths(
                checked_match.group(1), Path(predecessor).name, checked
            )
            if exact_checked != [predecessor]:
                raise RestructureError(
                    f"{path} checked predecessor is missing or stale: {predecessor}"
                )
            checked_file = ROOT / predecessor
            if not checked_file.is_file():
                raise RestructureError(f"{path} checked predecessor is missing: {predecessor}")
            if scalar(parse_manifest(checked_file.read_text(encoding="utf-8")), "status") != "checked":
                raise RestructureError(f"{path} predecessor is not checked: {predecessor}")
        if unresolved and status != "deferred":
            raise RestructureError(
                f"{path} must remain deferred until active predecessors are replaced "
                "with exact checked archive paths"
            )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(path: str) -> None:
        if path in visiting:
            raise RestructureError(f"active predecessor cycle detected at: {path}")
        if path in visited:
            return
        visiting.add(path)
        for predecessor in graph[path]:
            visit(predecessor)
        visiting.remove(path)
        visited.add(path)

    for path in graph:
        visit(path)


def render_replanned(rows: list[tuple[str, str, str]]) -> str:
    header = "# Replanned Plan Index\n\nid\tpath\tcontract\n"
    if not rows:
        return header
    body = "\n".join("\t".join(row) for row in rows)
    return f"{header}{body}\n"


def checked_paths_for_successor(plan_id: str, expected_path: str) -> list[str]:
    index = ROOT / "docs/plan/checked.md"
    if not index.is_file():
        return []
    paths: list[str] = []
    for line in index.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^[0-9]{3}\t", line):
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise RestructureError(f"malformed checked index row for {plan_id}")
        indexed_id, path = parts
        filename_matches = Path(path).name == Path(expected_path).name
        if indexed_id != plan_id and not filename_matches:
            continue
        if indexed_id != plan_id or not filename_matches:
            raise RestructureError(f"checked successor index identity mismatch for {plan_id}")
        if not re.fullmatch(r"docs/plan/checked/(?:[0-9]{4}/[0-9]{2}/(?:01-15|16-31)/)?" + re.escape(plan_id) + r"-[a-z0-9][a-z0-9-]*\.md", path):
            raise RestructureError(f"invalid checked successor path for {plan_id}: {path}")
        paths.append(path)
    return paths


def active_records_for_successor(plan_id: str, expected_path: str) -> list[tuple[str, str, str]]:
    if not ACTIVE_INDEX.is_file():
        return []
    related = [
        row
        for row in active_rows(ACTIVE_INDEX.read_text(encoding="utf-8"))
        if row[0] == plan_id or row[1] == expected_path
    ]
    if len(related) > 1:
        raise RestructureError(f"successor has duplicate active index records: {expected_path}")
    if related and related[0][:2] != (plan_id, expected_path):
        raise RestructureError(f"successor active index identity mismatch: {expected_path}")
    return related


def replanned_records_for_id(plan_id: str, expected_path: str) -> list[tuple[str, str]]:
    if not REPLANNED_INDEX.is_file():
        return []
    records: list[tuple[str, str]] = []
    for indexed_id, archive_path, contract_path in replanned_rows(
        REPLANNED_INDEX.read_text(encoding="utf-8")
    ):
        expected_name = Path(expected_path).name
        archive_matches = Path(archive_path).name == expected_name
        if indexed_id != plan_id and not archive_matches:
            continue
        if indexed_id != plan_id or not archive_matches:
            raise RestructureError(
                f"replanned successor index identity mismatch for {expected_path}"
            )
        normalized_path(
            archive_path,
            ARCHIVE_PATH_RE,
            f"replanned successor archive path for {plan_id}",
        )
        normalized_path(
            contract_path,
            CONTRACT_PATH_RE,
            f"replanned successor contract path for {plan_id}",
        )
        records.append((archive_path, contract_path))
    return records


def backlog_paths_for_successor(plan_id: str, expected_path: str) -> list[str]:
    directory = ROOT / "docs/plan/backlog"
    if not directory.is_dir():
        return []
    expected_name = Path(expected_path).name
    paths: list[str] = []
    for entry in sorted(directory.iterdir()):
        if not entry.is_file():
            continue
        name = entry.name
        if not re.fullmatch(r"[0-9]{3}-[a-z0-9][a-z0-9-]*\.md", name):
            continue
        indexed_id = name[:3]
        filename_matches = name == expected_name
        if indexed_id != plan_id and not filename_matches:
            continue
        if indexed_id != plan_id or not filename_matches:
            raise RestructureError(f"backlog successor identity mismatch for {plan_id}")
        paths.append(f"docs/plan/backlog/{name}")
    return paths


def validate_replanned_successor(
    plan_id: str,
    expected_path: str,
    expected_digests: list[str],
    expected_acceptance: list[str],
    expected_preservation: list[str] | None,
    expected_projection: dict[str, Any] | None,
) -> dict[str, str]:
    records = replanned_records_for_id(plan_id, expected_path)
    if len(records) != 1:
        raise RestructureError(
            f"successor has missing or ambiguous replanned record: {expected_path}"
        )
    archive_path, contract_path = records[0]
    reject_symlink_ancestors(archive_path, include_target=True)
    reject_symlink_ancestors(contract_path, include_target=True)
    archive_file = ROOT / archive_path
    contract_file = ROOT / contract_path
    if not archive_file.is_file() or not contract_file.is_file():
        raise RestructureError(
            f"missing replanned successor archive or contract: {expected_path}"
        )
    try:
        contract = json.loads(contract_file.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestructureError(
            f"invalid replanned successor contract: {expected_path}"
        ) from exc
    if isinstance(contract, dict) and contract.get("schema_version") == 3:
        exact_object(
            contract,
            {
                "schema_version",
                "created_at",
                "contract_path",
                "source_head",
                "sources",
                "dirty_product_paths",
                "successors",
                "prerequisite_plans",
                "rebind_record_digests",
            },
            f"replanned schema-3 successor contract {plan_id}",
        )
        if contract["contract_path"] != contract_path:
            raise RestructureError(
                f"replanned successor contract identity mismatch: {expected_path}"
            )
        matching_sources = [
            source
            for source in contract["sources"]
            if isinstance(source, dict) and source.get("path") == expected_path
        ]
        if len(matching_sources) != 1:
            raise RestructureError(
                f"replanned schema-3 source is missing: {expected_path}"
            )
        source = matching_sources[0]
        if (
            source.get("archive_path") != archive_path
            or source.get("acceptance_digests") != expected_digests
            or not isinstance(source.get("original_content"), str)
        ):
            raise RestructureError(
                f"replanned schema-3 source identity mismatch: {expected_path}"
            )
        source_manifest = parse_manifest(source["original_content"])
        stopped_content = source.get("stopped_content")
        if not isinstance(stopped_content, str):
            raise RestructureError(
                f"replanned schema-3 stopped source is missing: {expected_path}"
            )
        stopped_manifest = parse_manifest(stopped_content)
        validate_canonical_stopped_manifest(
            stopped_manifest,
            f"replanned schema-3 stopped source {plan_id}",
            expected_reason_codes=source.get("reason_codes"),
        )
        if (
            items(source_manifest, "inherited_acceptance_digests")
            != expected_digests
            or items(source_manifest, "acceptance") != expected_acceptance
            or items(stopped_manifest, "inherited_acceptance_digests")
            != expected_digests
            or items(stopped_manifest, "acceptance") != expected_acceptance
        ):
            raise RestructureError(
                f"replanned schema-3 source acceptance drift: {expected_path}"
            )
        if expected_preservation is not None and preservation_scope(
            source_manifest,
            f"replanned schema-3 source {plan_id}",
            required=True,
        ) != expected_preservation:
            raise RestructureError(
                f"replanned schema-3 source preservation_scope mismatch: {expected_path}"
            )
        if expected_projection is not None:
            validate_projection(
                expected_projection,
                source_manifest,
                f"replanned schema-3 source {plan_id}",
            )
        archive_manifest = parse_manifest(
            archive_file.read_text(encoding="utf-8")
        )
        if (
            scalar(archive_manifest, "status") != "replanned"
            or expected_path not in items(archive_manifest, "replan_sources")
            or scalar(archive_manifest, "replan_contract") != contract_path
            or items(archive_manifest, "inherited_acceptance_digests")
            != expected_digests
            or items(archive_manifest, "acceptance") != expected_acceptance
        ):
            raise RestructureError(
                f"replanned schema-3 archive lineage mismatch: {expected_path}"
            )
        return {
            "original_content": source["original_content"],
            "stopped_content": stopped_content,
        }
    exact_object(
        contract,
        {
            "schema_version",
            "created_at",
            "contract_path",
            "source",
            "reason_codes",
            "dirty_product_paths",
            "archive_path",
            "successors",
        },
        f"replanned successor contract {plan_id}",
    )
    if contract["schema_version"] not in {1, 2} or contract["contract_path"] != contract_path:
        raise RestructureError(
            f"replanned successor contract identity mismatch: {expected_path}"
        )
    if contract["archive_path"] != archive_path:
        raise RestructureError(
            f"replanned successor contract archive mismatch: {expected_path}"
        )
    source = exact_object(
        contract["source"],
        {"path", "head", "plan_digest", "acceptance", "content"},
        f"replanned successor source {plan_id}",
    )
    if source["path"] != expected_path:
        raise RestructureError(
            f"replanned successor source path mismatch: {expected_path}"
        )
    if (
        not isinstance(source["content"], str)
        or sha256(source["content"].encode()) != source["plan_digest"]
    ):
        raise RestructureError(
            f"replanned successor source digest mismatch: {expected_path}"
        )
    if acceptance_records(source["content"]) != source["acceptance"]:
        raise RestructureError(
            f"replanned successor source acceptance mismatch: {expected_path}"
        )
    source_manifest = parse_manifest(source["content"])
    validate_canonical_stopped_manifest(
        source_manifest,
        f"replanned successor source {plan_id}",
        expected_reason_codes=contract["reason_codes"],
    )
    if items(source_manifest, "inherited_acceptance_digests") != expected_digests:
        raise RestructureError(
            f"replanned successor source lineage mismatch: {expected_path}"
        )
    if items(source_manifest, "acceptance") != expected_acceptance:
        raise RestructureError(
            f"replanned successor source acceptance drift: {expected_path}"
        )
    if expected_preservation is not None and preservation_scope(
        source_manifest, f"replanned successor source {plan_id}", required=True
    ) != expected_preservation:
        raise RestructureError(
            f"replanned successor source preservation_scope mismatch: {expected_path}"
        )
    if expected_projection is not None:
        validate_projection(
            expected_projection,
            source_manifest,
            f"replanned successor source {plan_id}",
        )
    archive_manifest = parse_manifest(archive_file.read_text(encoding="utf-8"))
    if scalar(archive_manifest, "status") != "replanned":
        raise RestructureError(
            f"replanned successor archive status mismatch: {expected_path}"
        )
    if scalar(archive_manifest, "replan_source") != expected_path:
        raise RestructureError(
            f"replanned successor archive lineage mismatch: {expected_path}"
        )
    if scalar(archive_manifest, "replan_contract") != contract_path:
        raise RestructureError(
            f"replanned successor archive contract mismatch: {expected_path}"
        )
    if items(archive_manifest, "inherited_acceptance_digests") != expected_digests:
        raise RestructureError(
            f"replanned successor archive digest mapping mismatch: {expected_path}"
        )
    if items(archive_manifest, "acceptance") != expected_acceptance:
        raise RestructureError(
            f"replanned successor archive acceptance mismatch: {expected_path}"
        )
    if expected_preservation is not None and preservation_scope(
        archive_manifest, f"replanned successor archive {plan_id}", required=True
    ) != expected_preservation:
        raise RestructureError(
            f"replanned successor archive preservation_scope mismatch: {expected_path}"
        )
    return {
        "original_content": source["content"],
        "stopped_content": source["content"],
    }


def validate_plan_entry(
    entry: Any,
    *,
    label: str,
    source_path: str,
    contract_path: str,
    all_plan_paths: list[str],
    source_digests: set[str],
    source_ordered_digests: list[str],
    source_text_by_digest: dict[str, str],
) -> dict[str, Any]:
    obj = exact_object(entry, {"id", "path", "content", "acceptance_digests"}, label)
    plan_id = obj["id"]
    path = normalized_path(obj["path"], PLAN_PATH_RE, f"{label}.path")
    match = PLAN_PATH_RE.fullmatch(path)
    assert match
    if not isinstance(plan_id, str) or plan_id != match.group(1):
        raise RestructureError(f"{label}.id does not match its filename")
    content = obj["content"]
    digests = obj["acceptance_digests"]
    if not isinstance(content, str) or not content.endswith("\n") or len(content.encode()) > 262_144:
        raise RestructureError(f"{label}.content must be bounded UTF-8 text ending in newline")
    if not isinstance(digests, list) or not digests or len(digests) != len(set(digests)):
        raise RestructureError(f"{label}.acceptance_digests must be a non-empty unique list")
    if any(not isinstance(value, str) or value not in source_digests for value in digests):
        raise RestructureError(f"{label}.acceptance_digests contains an unknown source acceptance")
    if digests != [value for value in source_ordered_digests if value in set(digests)]:
        raise RestructureError(f"{label}.acceptance_digests must preserve source order")
    manifest = parse_manifest(content)
    missing_fields = sorted(
        key for key in REQUIRED_PLAN_FIELDS
        if key not in manifest or manifest[key] in ("", [])
    )
    if missing_fields:
        raise RestructureError(f"{label} missing required manifest fields: {', '.join(missing_fields)}")
    status = scalar(manifest, "status")
    if status not in {"in_progress", "deferred"}:
        raise RestructureError(f"{label} must start in status: in_progress or deferred")
    if status == "deferred" and not scalar(manifest, "completion_deferred_reason").strip():
        raise RestructureError(f"{label} deferred plan requires completion_deferred_reason")
    predecessor_paths(manifest, label)
    if scalar(manifest, "replan_source") != source_path:
        raise RestructureError(f"{label} replan_source mismatch")
    if scalar(manifest, "replan_contract") != contract_path:
        raise RestructureError(f"{label} replan_contract mismatch")
    if not scalar(manifest, "primary_invariant").strip():
        raise RestructureError(f"{label} requires primary_invariant")
    if items(manifest, "successor_plans") != all_plan_paths:
        raise RestructureError(f"{label} successor_plans must list every created plan in order")
    if items(manifest, "inherited_acceptance_digests") != digests:
        raise RestructureError(f"{label} inherited_acceptance_digests mismatch")
    if not items(manifest, "integration_gates"):
        raise RestructureError(f"{label} requires integration_gates")
    scope = items(manifest, "write_scope")
    if not scope:
        raise RestructureError(f"{label} requires write_scope")
    if len(scope) != len(set(scope)) or any(
        not entry or entry.startswith("/") or "\\" in entry or ".." in PurePosixPath(entry).parts
        for entry in scope
    ):
        raise RestructureError(f"{label} write_scope must contain unique normalized relative paths")
    if not items(manifest, "acceptance") or len(items(manifest, "acceptance")) != len(
        set(items(manifest, "acceptance"))
    ):
        raise RestructureError(f"{label} acceptance must be non-empty and unique")
    if scalar(manifest, "review_class") not in {"A", "B", "C"}:
        raise RestructureError(f"{label} review_class is invalid")
    if scalar(manifest, "human_design_required") not in {"yes", "no"}:
        raise RestructureError(f"{label} human_design_required is invalid")
    if scalar(manifest, "human_approval_status") not in {"not_required", "pending", "approved"}:
        raise RestructureError(f"{label} human_approval_status is invalid")
    if scalar(manifest, "review_class") == "C" and scalar(manifest, "human_approval_status") != "approved":
        raise RestructureError(f"{label} class C in-progress plan requires approval")
    if scalar(manifest, "human_design_required") == "yes" and scalar(manifest, "review_class") != "C":
        raise RestructureError(f"{label} human design work requires class C")
    expected_acceptance = [source_text_by_digest[mapped_digest] for mapped_digest in digests]
    if items(manifest, "acceptance") != expected_acceptance:
        raise RestructureError(
            f"{label} acceptance must exactly equal mapped source text in source order"
        )
    validate_current_plan_rules(manifest, label)
    projection = validation_projection(
        manifest,
        label,
        require_witness=status == "in_progress",
    )
    preserved = preservation_scope(manifest, label, required=True)
    return {
        **obj,
        "manifest": manifest,
        "preservation_scope": preserved,
        "content_digest": sha256(content.encode("utf-8")),
        "validation_projection": projection,
    }


def manifest_field_ranges(text: str) -> list[tuple[str, int, int]]:
    starts: list[tuple[str, int]] = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip()
        if line.startswith("## "):
            break
        if ":" in line and not line.startswith(" "):
            starts.append((line.split(":", 1)[0].strip(), offset))
        offset += len(raw)
    return [
        (key, start, starts[index + 1][1] if index + 1 < len(starts) else offset)
        for index, (key, start) in enumerate(starts)
    ]


def manifest_body_offset(text: str) -> int:
    offset = 0
    for raw in text.splitlines(keepends=True):
        if raw.rstrip().startswith("## "):
            return offset
        offset += len(raw)
    return len(text)


def project_lifecycle_fields(text: str, fields: set[str]) -> str:
    body_offset = manifest_body_offset(text)
    kept: list[str] = []
    current: str | None = None
    for raw in text[:body_offset].splitlines(keepends=True):
        line = raw.rstrip()
        if not line.strip():
            kept.append(raw)
            continue
        if ":" in line and not line.startswith(" "):
            key, rest = line.split(":", 1)
            key = key.strip()
            current = None if rest.strip() else key
            if key not in fields:
                kept.append(raw)
            continue
        if current and line.lstrip().startswith("- "):
            if current not in fields:
                kept.append(raw)
            continue
        kept.append(raw)
    return "".join(kept) + text[body_offset:]


def remove_manifest_fields(prefix: str, fields: set[str]) -> str:
    ranges: list[tuple[int, int]] = []
    for key, start, end in manifest_field_ranges(prefix):
        if key in fields:
            ranges.append((start, end))
    if not ranges:
        return prefix
    chunks: list[str] = []
    cursor = 0
    for start, end in ranges:
        chunks.append(prefix[cursor:start])
        cursor = end
    chunks.append(prefix[cursor:])
    return "".join(chunks)


def insert_manifest_block(prefix: str, before_field: str, lines: list[str]) -> str:
    matches = [
        start
        for key, start, _ in manifest_field_ranges(prefix)
        if key == before_field
    ]
    if len(matches) != 1:
        raise RestructureError(f"manifest must contain exactly one {before_field} field")
    return prefix[:matches[0]] + "\n".join(lines) + "\n" + prefix[matches[0]:]


def derive_stopped_source_content(text: str, reason_codes: list[str]) -> str:
    body_offset = manifest_body_offset(text)
    prefix = text[:body_offset]
    body = text[body_offset:]
    manifest = parse_manifest(text)
    status = scalar(manifest, "status")
    if status == "replan_required":
        validate_canonical_stopped_manifest(
            manifest,
            "stopped source",
            expected_reason_codes=reason_codes,
        )
        return text
    validate_reason_codes(reason_codes, "stopped source reason codes")
    if status not in {"in_progress", "deferred"}:
        raise RestructureError("dependent source must be active, deferred, or replan_required")
    status_ranges = [
        (start, end)
        for key, start, end in manifest_field_ranges(prefix)
        if key == "status"
    ]
    if len(status_ranges) != 1:
        raise RestructureError("dependent source must have exactly one status field")
    start, end = status_ranges[0]
    first_line = prefix[start:end].splitlines(keepends=True)[0]
    prefix = prefix[:start] + "status: replan_required\n" + prefix[start + len(first_line):]
    prefix = project_lifecycle_fields(
        prefix,
        {"completion_deferred_reason", "replan_reason_codes"},
    )
    prefix = insert_manifest_block(
        prefix,
        "checked_summary_ja",
        [
            "replan_reason_codes:",
            *[f"  - {reason}" for reason in reason_codes],
        ],
    )
    stopped = prefix + body
    before = parse_manifest(text)
    after = parse_manifest(stopped)
    allowed = {"status", "completion_deferred_reason", "replan_reason_codes"}
    for field in set(before) | set(after):
        if field not in allowed and before.get(field) != after.get(field):
            raise RestructureError(
                f"dependent source stopping changed protected field: {field}"
            )
    if text[body_offset:] != stopped[manifest_body_offset(stopped):]:
        raise RestructureError("dependent source stopping changed plan body bytes")
    lifecycle = {"status", "completion_deferred_reason", "replan_reason_codes"}
    if project_lifecycle_fields(text, lifecycle) != project_lifecycle_fields(
        stopped, lifecycle
    ):
        raise RestructureError("dependent source stopping changed protected bytes")
    return stopped


def build_multi_archive(
    stopped_text: str,
    *,
    source_paths: list[str],
    contract_path: str,
    plan_paths: list[str],
    acceptance_digests: list[str],
) -> str:
    body_offset = manifest_body_offset(stopped_text)
    manifest_prefix = stopped_text[:body_offset]
    body_suffix = stopped_text[body_offset:]
    status_ranges = [
        (start, end)
        for key, start, end in manifest_field_ranges(manifest_prefix)
        if key == "status"
    ]
    if len(status_ranges) != 1:
        raise RestructureError("source plan must have exactly one status field")
    status_start, status_end = status_ranges[0]
    status_line = manifest_prefix[status_start:status_end].splitlines(keepends=True)[0]
    updated = (
        manifest_prefix[:status_start]
        + "status: replanned\n"
        + manifest_prefix[status_start + len(status_line):]
    )
    updated = remove_manifest_fields(
        updated,
        {
            "completion_deferred_reason",
            "replan_reason_codes",
            "primary_invariant",
            "replan_source",
            "replan_sources",
            "replan_contract",
            "integration_gates",
            "successor_plans",
            "inherited_acceptance_digests",
            "integration_source_ids",
        },
    )
    block = [
        "primary_invariant: preserve the complete coupled source acceptance baseline",
        "replan_sources:",
        *[f"  - {path}" for path in source_paths],
        f"replan_contract: {contract_path}",
        "integration_gates:",
        "  - combined successors must satisfy every mapped source acceptance item",
        "successor_plans:",
        *[f"  - {path}" for path in plan_paths],
        "inherited_acceptance_digests:",
        *[f"  - {value}" for value in acceptance_digests],
    ]
    return insert_manifest_block(
        updated,
        "checked_summary_ja",
        block,
    ) + body_suffix


def witness_records(
    manifest: dict[str, str | list[str]],
    label: str,
) -> list[dict[str, str]]:
    validation_projection(
        manifest,
        label,
        require_witness=scalar(manifest, "validation_witness_schema") == "1",
        enforce_witness_semantics=False,
    )
    return [json.loads(raw) for raw in items(manifest, "validation_witness_map")]


def projection_digest(projection: dict[str, Any]) -> str:
    return canonical_digest(projection)


def ordered_subsequence(expected: list[str], actual: list[str]) -> bool:
    cursor = 0
    for value in actual:
        if cursor < len(expected) and value == expected[cursor]:
            cursor += 1
    return cursor == len(expected)


def replacement_changes(
    replacements: list[dict[str, Any]],
    field: str,
) -> list[tuple[str, str]]:
    return [
        (replacement["old"], replacement["new"])
        for replacement in replacements
        if replacement["scope"] == "manifest" and replacement["field"] == field
    ]


def transform_values(
    values: list[str],
    replacements: list[dict[str, Any]],
    field: str,
) -> list[str]:
    transformed = list(values)
    for old, new in replacement_changes(replacements, field):
        transformed = [value.replace(old, new) for value in transformed]
    return transformed


def validation_path_changes(
    replacements: list[dict[str, Any]],
    field: str,
    label: str,
) -> list[tuple[str, str]]:
    changes = replacement_changes(replacements, field)
    for old, new in changes:
        old_path = PurePosixPath(old)
        new_path = PurePosixPath(new)
        if (
            not old
            or not new
            or old_path.is_absolute()
            or new_path.is_absolute()
            or "/" not in old
            or "/" not in new
            or any(part in {"", ".", ".."} for part in old_path.parts)
            or any(part in {"", ".", ".."} for part in new_path.parts)
            or any(char not in PATH_TOKEN_CHARACTERS for char in old)
            or any(char not in PATH_TOKEN_CHARACTERS for char in new)
            or old_path.suffix != new_path.suffix
            or (old, new) not in SEMANTIC_VALIDATION_PATH_REBINDINGS
        ):
            raise RestructureError(
                f"{label} {field} replacements must be semantic-preserving path substitutions"
            )
    return changes


def validate_command_substitutions(
    before_commands: list[str],
    after_commands: list[str],
    changes: list[tuple[str, str]],
    label: str,
) -> None:
    expected = list(before_commands)
    for old, new in changes:
        expected = [command.replace(old, new) for command in expected]
    if not ordered_subsequence(expected, after_commands):
        raise RestructureError(f"{label} weakens or removes validation commands")
    module = validation_command_module()
    for original, transformed in zip(before_commands, expected, strict=True):
        try:
            original_argv = module.parse_validation_command(original).argv
            transformed_argv = module.parse_validation_command(transformed).argv
        except Exception as exc:
            raise RestructureError(
                f"{label} contains an invalid validation command transition: {exc}"
            ) from exc
        if len(original_argv) != len(transformed_argv):
            raise RestructureError(
                f"{label} validation substitution changes command structure"
            )
        for original_arg, transformed_arg in zip(
            original_argv,
            transformed_argv,
            strict=True,
        ):
            expected_arg = original_arg
            for old, new in changes:
                expected_arg = expected_arg.replace(old, new)
            if transformed_arg != expected_arg:
                raise RestructureError(
                    f"{label} validation substitution changes command structure"
                )


def validate_validation_transition(
    before: dict[str, str | list[str]],
    after: dict[str, str | list[str]],
    replacements: list[dict[str, Any]],
    *,
    activation: bool,
    label: str,
) -> dict[str, Any]:
    before_projection = validation_projection(
        before,
        f"{label} original",
        require_witness=scalar(before, "validation_witness_schema") == "1",
        enforce_witness_semantics=False,
    )
    after_projection = validation_projection(
        after,
        f"{label} updated",
        require_witness=scalar(after, "validation_witness_schema") == "1",
    )
    if activation:
        if before_projection != after_projection:
            raise RestructureError(f"{label} activation must preserve validation authority")
        return after_projection
    for field in ("focused_validation", "validation"):
        validate_command_substitutions(
            items(before, field),
            items(after, field),
            validation_path_changes(replacements, field, label),
            f"{label} {field}",
        )
    before_witnesses = witness_records(before, f"{label} original")
    after_witnesses = witness_records(after, f"{label} updated")
    if len(before_witnesses) != len(after_witnesses):
        raise RestructureError(f"{label} validation witness coverage drift")
    witness_changes = validation_path_changes(
        replacements,
        "validation_witness_map",
        label,
    )
    for original, updated in zip(before_witnesses, after_witnesses, strict=True):
        expected = dict(original)
        for old, new in witness_changes:
            expected = json.loads(
                json.dumps(expected, sort_keys=True, separators=(",", ":")).replace(
                    old,
                    new,
                )
            )
        if updated != expected:
            raise RestructureError(f"{label} validation witness drift")
    return after_projection


def bounded_occurrences(text: str, old: str, label: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        index = text.find(old, start)
        if index < 0:
            break
        before = text[index - 1] if index else ""
        after_index = index + len(old)
        after = text[after_index] if after_index < len(text) else ""
        if (
            old
            and old[0] in PATH_TOKEN_CHARACTERS
            and before in PATH_TOKEN_CHARACTERS
        ) or (
            old
            and old[-1] in PATH_TOKEN_CHARACTERS
            and after in PATH_TOKEN_CHARACTERS
        ):
            raise RestructureError(f"{label} would replace a substring of a larger token")
        positions.append(index)
        start = index + len(old)
    return positions


def apply_exact_replacements(
    original: str,
    replacements: list[dict[str, Any]],
    *,
    kind: str,
    label: str,
) -> str:
    text = original
    allowed_fields = ACTIVATION_FIELDS if kind == "activation" else REBIND_FIELDS
    seen: set[tuple[str, str, str, str, int]] = set()
    for index, raw in enumerate(replacements, start=1):
        replacement = exact_object(
            raw,
            {"scope", "field", "old", "new", "count"},
            f"{label} replacement {index}",
        )
        scope = replacement["scope"]
        field = replacement["field"]
        old = replacement["old"]
        new = replacement["new"]
        count = replacement["count"]
        if scope not in {"manifest", "body"}:
            raise RestructureError(f"{label} replacement {index} has invalid scope")
        if not isinstance(field, str) or (
            scope == "body" and field != "body"
        ) or (
            scope == "manifest" and field not in allowed_fields
        ):
            raise RestructureError(f"{label} replacement {index} targets an unauthorized field")
        if (
            not isinstance(old, str)
            or not old
            or not isinstance(new, str)
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 1
            or count > 100
        ):
            raise RestructureError(f"{label} replacement {index} is invalid")
        identity = (scope, field, old, new, count)
        if identity in seen:
            raise RestructureError(f"{label} replacement map contains duplicates")
        seen.add(identity)
        if scope == "body":
            start = manifest_body_offset(text)
            segment = text[start:]
            positions = bounded_occurrences(segment, old, f"{label} replacement {index}")
            if len(positions) != count:
                raise RestructureError(
                    f"{label} replacement {index} expected {count} occurrences, found {len(positions)}"
                )
            text = text[:start] + segment.replace(old, new)
            continue
        ranges = [
            (start, end)
            for key, start, end in manifest_field_ranges(text)
            if key == field
        ]
        if len(ranges) != 1:
            raise RestructureError(
                f"{label} replacement {index} requires exactly one {field} field"
            )
        start, end = ranges[0]
        segment = text[start:end]
        positions = bounded_occurrences(segment, old, f"{label} replacement {index}")
        if len(positions) != count:
            raise RestructureError(
                f"{label} replacement {index} expected {count} occurrences, found {len(positions)}"
            )
        text = text[:start] + segment.replace(old, new) + text[end:]
    return text


def build_archive(
    source_text: str,
    *,
    source_path: str,
    contract_path: str,
    plan_paths: list[str],
    acceptance_digests: list[str],
) -> str:
    body_offset = manifest_body_offset(source_text)
    manifest_prefix = source_text[:body_offset]
    body_suffix = source_text[body_offset:]
    status_ranges = [
        (start, end)
        for key, start, end in manifest_field_ranges(manifest_prefix)
        if key == "status"
    ]
    if len(status_ranges) != 1:
        raise RestructureError("source plan must have exactly one status: replan_required field")
    status_start, status_end = status_ranges[0]
    status_line = manifest_prefix[status_start:status_end].splitlines(keepends=True)[0]
    status_line_end = status_start + len(status_line)
    updated = manifest_prefix[:status_start] + "status: replanned\n" + manifest_prefix[status_line_end:]
    updated = remove_manifest_fields(
        updated,
        {
            "primary_invariant",
            "replan_source",
            "replan_contract",
            "integration_gates",
            "successor_plans",
            "inherited_acceptance_digests",
        },
    )
    summary_ranges = [
        (start, end)
        for key, start, end in manifest_field_ranges(updated)
        if key == "checked_summary_ja"
    ]
    if len(summary_ranges) != 1:
        raise RestructureError("source plan lacks checked_summary_ja")
    summary_start = summary_ranges[0][0]
    block = [
        "primary_invariant: preserve the complete source acceptance baseline",
        f"replan_source: {source_path}",
        f"replan_contract: {contract_path}",
        "integration_gates:",
        "  - combined successors must satisfy every source acceptance item",
        "successor_plans:",
        *[f"  - {path}" for path in plan_paths],
        "inherited_acceptance_digests:",
        *[f"  - {digest}" for digest in acceptance_digests],
    ]
    return (
        updated[:summary_start]
        + "\n".join(block)
        + "\n"
        + updated[summary_start:]
        + body_suffix
    )


def validate_created_manifest(
    content: Any,
    label: str,
    *,
    require_preservation: bool,
) -> dict[str, Any]:
    if (
        not isinstance(content, str)
        or not content.endswith("\n")
        or len(content.encode("utf-8")) > 262_144
    ):
        raise RestructureError(
            f"{label}.content must be bounded UTF-8 text ending in newline"
        )
    manifest = parse_manifest(content)
    missing_fields = sorted(
        key
        for key in REQUIRED_PLAN_FIELDS
        if key not in manifest or manifest[key] in ("", [])
    )
    if missing_fields:
        raise RestructureError(
            f"{label} missing required manifest fields: {', '.join(missing_fields)}"
        )
    status = scalar(manifest, "status")
    if status not in {"in_progress", "deferred"}:
        raise RestructureError(f"{label} must start in status: in_progress or deferred")
    if status == "deferred" and not scalar(
        manifest, "completion_deferred_reason"
    ).strip():
        raise RestructureError(
            f"{label} deferred plan requires completion_deferred_reason"
        )
    predecessor_paths(manifest, label)
    if not scalar(manifest, "primary_invariant").strip():
        raise RestructureError(f"{label} requires primary_invariant")
    scope = items(manifest, "write_scope")
    if not scope:
        raise RestructureError(f"{label} requires write_scope")
    if len(scope) != len(set(scope)) or any(
        not entry
        or entry.startswith("/")
        or "\\" in entry
        or ".." in PurePosixPath(entry).parts
        for entry in scope
    ):
        raise RestructureError(
            f"{label} write_scope must contain unique normalized relative paths"
        )
    accepted = items(manifest, "acceptance")
    if not accepted or len(accepted) != len(set(accepted)):
        raise RestructureError(f"{label} acceptance must be non-empty and unique")
    if scalar(manifest, "review_class") not in {"A", "B", "C"}:
        raise RestructureError(f"{label} review_class is invalid")
    if scalar(manifest, "human_design_required") not in {"yes", "no"}:
        raise RestructureError(f"{label} human_design_required is invalid")
    if scalar(manifest, "human_approval_status") not in {
        "not_required",
        "pending",
        "approved",
    }:
        raise RestructureError(f"{label} human_approval_status is invalid")
    if (
        scalar(manifest, "review_class") == "C"
        and scalar(manifest, "human_approval_status") != "approved"
    ):
        raise RestructureError(f"{label} class C in-progress plan requires approval")
    if (
        scalar(manifest, "human_design_required") == "yes"
        and scalar(manifest, "review_class") != "C"
    ):
        raise RestructureError(f"{label} human design work requires class C")
    validate_current_plan_rules(manifest, label)
    projection = validation_projection(
        manifest,
        label,
        require_witness=status == "in_progress",
    )
    preserved = preservation_scope(
        manifest,
        label,
        required=require_preservation,
    )
    return {
        "content": content,
        "manifest": manifest,
        "preservation_scope": preserved,
        "content_digest": sha256(content.encode("utf-8")),
        "validation_projection": projection,
    }


def ordered_unique_acceptance(
    mappings: list[dict[str, Any]],
    source_by_id: dict[str, dict[str, Any]],
    source_ids: list[str],
) -> tuple[list[str], list[str]]:
    digests: list[str] = []
    texts: list[str] = []
    seen: set[str] = set()
    mapping_by_source = {
        mapping["source_id"]: mapping["acceptance_digests"]
        for mapping in mappings
    }
    for source_id in source_ids:
        source = source_by_id[source_id]
        selected = set(mapping_by_source.get(source_id, []))
        for digest_value in source["acceptance_digests"]:
            if digest_value in selected and digest_value not in seen:
                seen.add(digest_value)
                digests.append(digest_value)
                texts.append(source["acceptance_text_by_digest"][digest_value])
    return digests, texts


def validate_schema_three_successor(
    entry: Any,
    *,
    label: str,
    contract_path: str,
    source_infos: list[dict[str, Any]],
    all_plan_paths: list[str],
) -> dict[str, Any]:
    obj = exact_object(
        entry,
        {
            "id",
            "path",
            "content",
            "acceptance_mappings",
            "integration_source_ids",
        },
        label,
    )
    plan_id = obj["id"]
    path = normalized_path(obj["path"], PLAN_PATH_RE, f"{label}.path")
    match = PLAN_PATH_RE.fullmatch(path)
    assert match
    if not isinstance(plan_id, str) or plan_id != match.group(1):
        raise RestructureError(f"{label}.id does not match its filename")
    source_ids = [source["id"] for source in source_infos]
    source_by_id = {source["id"]: source for source in source_infos}
    raw_mappings = obj["acceptance_mappings"]
    if not isinstance(raw_mappings, list) or not raw_mappings:
        raise RestructureError(f"{label}.acceptance_mappings must be non-empty")
    mappings: list[dict[str, Any]] = []
    for index, raw_mapping in enumerate(raw_mappings, start=1):
        mapping = exact_object(
            raw_mapping,
            {"source_id", "acceptance_digests"},
            f"{label}.acceptance_mappings[{index}]",
        )
        source_id = mapping["source_id"]
        digests = mapping["acceptance_digests"]
        if source_id not in source_by_id:
            raise RestructureError(f"{label} maps an unknown source id")
        source = source_by_id[source_id]
        if (
            not isinstance(digests, list)
            or not digests
            or len(digests) != len(set(digests))
            or any(value not in source["acceptance_text_by_digest"] for value in digests)
        ):
            raise RestructureError(f"{label} has an invalid source acceptance mapping")
        if digests != [
            value
            for value in source["acceptance_digests"]
            if value in set(digests)
        ]:
            raise RestructureError(
                f"{label} source acceptance mapping must preserve source order"
            )
        mappings.append(
            {
                "source_id": source_id,
                "acceptance_digests": digests,
            }
        )
    mapped_ids = [mapping["source_id"] for mapping in mappings]
    if (
        len(mapped_ids) != len(set(mapped_ids))
        or mapped_ids != [value for value in source_ids if value in set(mapped_ids)]
    ):
        raise RestructureError(f"{label} source mappings must be unique and ordered")
    integration_source_ids = obj["integration_source_ids"]
    if (
        not isinstance(integration_source_ids, list)
        or len(integration_source_ids) != len(set(integration_source_ids))
        or any(value not in mapped_ids for value in integration_source_ids)
        or integration_source_ids
        != [value for value in source_ids if value in set(integration_source_ids)]
    ):
        raise RestructureError(f"{label}.integration_source_ids is invalid")
    common = validate_created_manifest(
        obj["content"],
        label,
        require_preservation=True,
    )
    manifest = common["manifest"]
    source_paths = [source["path"] for source in source_infos]
    if items(manifest, "replan_sources") != source_paths:
        raise RestructureError(f"{label} replan_sources mismatch")
    if scalar(manifest, "replan_source"):
        raise RestructureError(f"{label} must not use singular replan_source")
    if scalar(manifest, "replan_contract") != contract_path:
        raise RestructureError(f"{label} replan_contract mismatch")
    if items(manifest, "successor_plans") != all_plan_paths:
        raise RestructureError(
            f"{label} successor_plans must list every mapped successor in order"
        )
    expected_digests, expected_acceptance = ordered_unique_acceptance(
        mappings,
        source_by_id,
        source_ids,
    )
    if items(manifest, "inherited_acceptance_digests") != expected_digests:
        raise RestructureError(f"{label} inherited_acceptance_digests mismatch")
    if items(manifest, "acceptance") != expected_acceptance:
        raise RestructureError(
            f"{label} acceptance must exactly equal mapped source text"
        )
    if items(manifest, "integration_source_ids") != integration_source_ids:
        raise RestructureError(f"{label} integration_source_ids mismatch")
    if not items(manifest, "integration_gates"):
        raise RestructureError(f"{label} requires integration_gates")
    return {
        **obj,
        **common,
        "acceptance_mappings": mappings,
        "integration_source_ids": integration_source_ids,
        "acceptance_digests": expected_digests,
    }


def validate_schema_three_integration_coverage(
    successors: list[dict[str, Any]],
    source_infos: list[dict[str, Any]],
) -> None:
    source_by_id = {source["id"]: source for source in source_infos}
    integration_counts = {source_id: 0 for source_id in source_by_id}
    mapped = {source_id: set() for source_id in source_by_id}
    for successor in successors:
        mapping_by_source = {
            mapping["source_id"]: mapping["acceptance_digests"]
            for mapping in successor["acceptance_mappings"]
        }
        for source_id, acceptance_digests in mapping_by_source.items():
            mapped[source_id].update(acceptance_digests)
        for source_id in successor["integration_source_ids"]:
            integration_counts[source_id] += 1
            if (
                mapping_by_source[source_id]
                != source_by_id[source_id]["acceptance_digests"]
            ):
                raise RestructureError(
                    "integration successor does not map every acceptance "
                    f"for source {source_id}"
                )
    for source_id, source in source_by_id.items():
        if mapped[source_id] != set(source["acceptance_digests"]):
            raise RestructureError(
                f"source {source_id} acceptance mapping is incomplete"
            )
        if integration_counts[source_id] != 1:
            raise RestructureError(
                f"source {source_id} must have exactly one integration successor"
            )


def validate_prerequisite_plan(entry: Any, label: str) -> dict[str, Any]:
    obj = exact_object(entry, {"id", "path", "content", "authorization"}, label)
    path = normalized_path(obj["path"], PLAN_PATH_RE, f"{label}.path")
    match = PLAN_PATH_RE.fullmatch(path)
    assert match
    if obj["id"] != match.group(1):
        raise RestructureError(f"{label}.id does not match its filename")
    if obj["authorization"] != "parent_owned_prerequisite":
        raise RestructureError(f"{label} lacks parent-owned prerequisite authorization")
    common = validate_created_manifest(
        obj["content"],
        label,
        require_preservation=True,
    )
    manifest = common["manifest"]
    forbidden = {
        "replan_source",
        "replan_sources",
        "replan_contract",
        "successor_plans",
        "inherited_acceptance_digests",
        "integration_source_ids",
    }
    if any(field in manifest for field in forbidden):
        raise RestructureError(f"{label} must not inherit source lineage")
    return {**obj, **common}


def manifest_identity_values(
    manifest: dict[str, str | list[str]],
) -> dict[str, str | list[str] | None]:
    return {
        field: manifest.get(field)
        for field in REBIND_PROTECTED_FIELDS
    }


def git_path_is_clean(product_path: str) -> bool:
    for args in (
        ("diff", "--quiet", "--", product_path),
        ("diff", "--cached", "--quiet", "--", product_path),
    ):
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode != 0:
            return False
    return True


def checked_commit_produced_path(checked_path: str, product_path: str) -> bool:
    commit = run_git("log", "-1", "--format=%H", "--", checked_path).decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        return False
    try:
        archived = run_git("show", f"{commit}:{checked_path}")
        current = read_regular_file(ROOT / checked_path, checked_path)
        produced = run_git("show", f"{commit}:{product_path}")
    except RestructureError:
        return False
    manifest = parse_manifest(archived.decode("utf-8"))
    if (
        archived != current
        or scalar(manifest, "status") != "checked"
        or not scope_covers(items(manifest, "write_scope"), product_path)
        or not git_path_is_clean(product_path)
    ):
        return False
    try:
        current_product = read_regular_file(ROOT / product_path, product_path)
    except RestructureError:
        return False
    if current_product != produced:
        return False
    parents = run_git("rev-list", "--parents", "-n", "1", commit).decode().split()
    if len(parents) > 1:
        parent = parents[1]
        prior = subprocess.run(
            ["git", "show", f"{parent}:{product_path}"],
            cwd=ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if prior.returncode == 0 and prior.stdout == produced:
            return False
    return True


def resolve_active_references(
    values: list[str],
    pairs: dict[str, str],
    label: str,
) -> list[str]:
    resolved: list[str] = []
    for value in values:
        for active_path in dict.fromkeys(ACTIVE_REFERENCE_RE.findall(value)):
            checked_path = pairs.get(active_path)
            if checked_path is None:
                raise RestructureError(
                    f"{label} lacks the same-ID checked archive for {active_path}"
                )
            value = value.replace(active_path, checked_path)
        resolved.append(value)
    return resolved


def validate_activation_promotion(
    before: dict[str, str | list[str]],
    after: dict[str, str | list[str]],
    promoted_path: str | None,
    label: str,
) -> None:
    before_preservation = preservation_scope(before, f"{label} original", required=True)
    after_preservation = preservation_scope(after, f"{label} updated", required=True)
    before_context = resolve_active_references(
        items(before, "context_files"),
        activation_checked_pairs(),
        label,
    )
    after_context = items(after, "context_files")
    if promoted_path is None:
        if (
            before_preservation != after_preservation
            or before_context != after_context
        ):
            raise RestructureError(
                f"{label} activation changes preservation or context without promotion"
            )
        return
    path = PurePosixPath(promoted_path)
    if (
        not promoted_path
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise RestructureError(f"{label} promotion path is invalid")
    if before_preservation.count(promoted_path) != 1 or promoted_path in after_preservation:
        raise RestructureError(f"{label} promotion must remove one preserved path")
    if after_preservation != [
        value for value in before_preservation if value != promoted_path
    ]:
        raise RestructureError(f"{label} promotion changes unrelated preservation entries")
    if promoted_path in before_context or after_context != [
        *before_context,
        promoted_path,
    ]:
        raise RestructureError(f"{label} promotion must append one context path")
    if scope_covers(items(after, "write_scope"), promoted_path):
        raise RestructureError(f"{label} promotion path remains writable")
    checked_predecessors = [
        value
        for value in predecessor_paths(after, label)
        if CHECKED_PATH_RE.fullmatch(value)
    ]
    producers = [
        predecessor
        for predecessor in checked_predecessors
        if checked_commit_produced_path(predecessor, promoted_path)
    ]
    if len(producers) != 1:
        raise RestructureError(
            f"{label} promotion path lacks one exact checked producer"
        )


def read_spec(path: Path) -> dict[str, Any]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RestructureError("restructure specification must be a regular file")
        data = os.read(descriptor, MAX_SPEC_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(data) > MAX_SPEC_BYTES:
        raise RestructureError("restructure specification exceeds one MiB")
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestructureError(f"invalid restructure specification: {exc}") from exc
    if not isinstance(value, dict):
        raise RestructureError("specification must be a JSON object")
    return value


def validate_single_source_spec(spec: dict[str, Any]) -> dict[str, Any]:
    exact_object(
        spec,
        {
            "schema_version",
            "source",
            "reason_codes",
            "dirty_product_paths",
            "contract_path",
            "archive_path",
            "successors",
            "integration",
        },
        "specification",
    )
    if spec["schema_version"] != 1 or isinstance(spec["schema_version"], bool):
        raise RestructureError("schema_version must be 1")
    source = exact_object(
        spec["source"], {"path", "head", "plan_digest", "acceptance"}, "source"
    )
    source_path = normalized_path(source["path"], PLAN_PATH_RE, "source.path")
    source_match = PLAN_PATH_RE.fullmatch(source_path)
    assert source_match
    source_id = source_match.group(1)
    source_file = ROOT / source_path
    reject_symlink_ancestors(source_path, include_target=True)
    if not source_file.is_file():
        raise RestructureError(f"missing source plan: {source_path}")
    source_bytes = source_file.read_bytes()
    source_text = source_bytes.decode("utf-8")
    manifest = parse_manifest(source_text)
    if scalar(manifest, "status") != "replan_required":
        raise RestructureError("source plan must be status: replan_required")
    if source["head"] != current_head():
        raise RestructureError("source HEAD mismatch")
    if not isinstance(source["head"], str) or not re.fullmatch(r"[0-9a-f]{40}", source["head"]):
        raise RestructureError("source HEAD must be a full object id")
    if not isinstance(source["plan_digest"], str) or not SHA_RE.fullmatch(source["plan_digest"]):
        raise RestructureError("source plan_digest must be sha256:<64 lowercase hex>")
    if source["plan_digest"] != sha256(source_bytes):
        raise RestructureError("source plan digest mismatch")
    expected_acceptance = acceptance_records(source_text)
    if source["acceptance"] != expected_acceptance:
        raise RestructureError("source acceptance text or digest mismatch")
    reason_codes = spec["reason_codes"]
    if (
        not isinstance(reason_codes, list)
        or not reason_codes
        or len(reason_codes) != len(set(reason_codes))
        or any(not isinstance(value, str) or value not in REASON_CODES for value in reason_codes)
    ):
        raise RestructureError("reason_codes must be a non-empty unique bounded list")
    if items(manifest, "replan_reason_codes") != reason_codes:
        raise RestructureError("source replan_reason_codes mismatch")
    validate_canonical_stopped_manifest(
        manifest,
        "source plan",
        expected_reason_codes=reason_codes,
    )
    contract_path = normalized_path(spec["contract_path"], CONTRACT_PATH_RE, "contract_path")
    archive_path = normalized_path(spec["archive_path"], ARCHIVE_PATH_RE, "archive_path")
    archive_match = ARCHIVE_PATH_RE.fullmatch(archive_path)
    assert archive_match
    if archive_match.group(1) != Path(source_path).name:
        raise RestructureError("archive filename must match the source filename")
    today = datetime.now().date()
    expected_half = "01-15" if today.day <= 15 else "16-31"
    expected_prefix = f"docs/plan/replanned/{today.year:04d}/{today.month:02d}/{expected_half}/"
    if not archive_path.startswith(expected_prefix):
        raise RestructureError("archive_path must use the current date partition")
    successors = spec["successors"]
    if not isinstance(successors, list) or not successors or len(successors) > MAX_PLANS - 1:
        raise RestructureError("successors must contain between one and seven plans")
    raw_entries = [*successors, spec["integration"]]
    raw_paths = [
        normalized_path(exact_object(entry, {"id", "path", "content", "acceptance_digests"}, "plan")["path"], PLAN_PATH_RE, "plan.path")
        for entry in raw_entries
    ]
    if len(raw_paths) != len(set(raw_paths)):
        raise RestructureError("created plan paths must be unique")
    ordered_digests = [record["digest"] for record in expected_acceptance]
    source_digests = set(ordered_digests)
    source_text_by_digest = {record["digest"]: record["text"] for record in expected_acceptance}
    entries = [
        validate_plan_entry(
            entry,
            label="integration" if index == len(raw_entries) - 1 else f"successors[{index}]",
            source_path=source_path,
            contract_path=contract_path,
            all_plan_paths=raw_paths,
            source_digests=source_digests,
            source_ordered_digests=ordered_digests,
            source_text_by_digest=source_text_by_digest,
        )
        for index, entry in enumerate(raw_entries)
    ]
    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)) or source_id in ids:
        raise RestructureError("created plan ids must be unique and differ from the source id")
    integration = entries[-1]
    if integration["acceptance_digests"] != ordered_digests:
        raise RestructureError("integration must inherit every acceptance digest in source order")
    if items(integration["manifest"], "acceptance") != [record["text"] for record in expected_acceptance]:
        raise RestructureError("integration must copy every source acceptance item exactly")
    mapped = {digest for entry in entries for digest in entry["acceptance_digests"]}
    if mapped != source_digests:
        raise RestructureError("every source acceptance digest must be mapped")
    actual_dirty = dirty_product_paths()
    declared_dirty = spec["dirty_product_paths"]
    if not isinstance(declared_dirty, list) or declared_dirty != actual_dirty:
        raise RestructureError("dirty_product_paths must exactly match current Git status")
    successor_scopes = [items(entry["manifest"], "write_scope") for entry in entries]
    preserved_paths = [
        path for entry in entries for path in entry["preservation_scope"]
    ]
    if len(preserved_paths) != len(set(preserved_paths)):
        raise RestructureError("preservation_scope paths must be assigned exactly once")
    if sorted(preserved_paths) != actual_dirty:
        raise RestructureError(
            "successor preservation_scope must exactly match dirty_product_paths"
        )
    reject_preservation_write_overlap(
        preserved_paths, successor_scopes, "successor plans"
    )
    active_text = ACTIVE_INDEX.read_text(encoding="utf-8")
    rows = active_rows(active_text)
    if rows.count((source_id, source_path, "replan_required")) != 1:
        raise RestructureError("active index does not exactly map the stopped source plan")
    active_records: dict[str, tuple[str, dict[str, str | list[str]]]] = {}
    for row_id, row_path, row_status in rows:
        if row_id == source_id:
            continue
        row_match = PLAN_PATH_RE.fullmatch(row_path)
        if row_match is None or row_match.group(1) != row_id:
            raise RestructureError(f"active plan identity mismatch: {row_path}")
        active_file = ROOT / row_path
        if not active_file.is_file():
            raise RestructureError(f"missing active plan: {row_path}")
        active_manifest = parse_manifest(active_file.read_text(encoding="utf-8"))
        if scalar(active_manifest, "status") != row_status:
            raise RestructureError(f"active plan status mismatch: {row_path}")
        active_records[row_path] = (row_status, active_manifest)
    active_records.update(
        {
            entry["path"]: (scalar(entry["manifest"], "status"), entry["manifest"])
            for entry in entries
        }
    )
    validate_active_predecessors(active_records)
    replanned_text = (
        REPLANNED_INDEX.read_text(encoding="utf-8")
        if REPLANNED_INDEX.exists()
        else "# Replanned Plan Index\n\nid\tpath\tcontract\n"
    )
    prior_replanned = replanned_rows(replanned_text)
    destinations = [contract_path, archive_path, *raw_paths]
    for destination in destinations:
        reject_symlink_ancestors(destination, include_target=False)
        if (ROOT / destination).exists() or (ROOT / destination).is_symlink():
            raise RestructureError(f"destination already exists: {destination}")
    known_ids: set[str] = set()
    for base in (ROOT / "docs/plan/active", ROOT / "docs/plan/backlog", ROOT / "docs/plan/checked", ROOT / "docs/plan/replanned"):
        if base.exists():
            for path in base.glob("**/[0-9][0-9][0-9]-*.md"):
                if path != source_file:
                    known_ids.add(path.name[:3])
    if known_ids & set(ids):
        raise RestructureError("a created plan id already exists")
    if any(row[0] in ids or row[1] in raw_paths for row in rows):
        raise RestructureError("active index conflicts with a created plan")
    if any(row[0] == source_id or row[1] == archive_path or row[2] == contract_path for row in prior_replanned):
        raise RestructureError("replanned index conflicts with the source transition")
    archive_text = build_archive(
        source_text,
        source_path=source_path,
        contract_path=contract_path,
        plan_paths=raw_paths,
        acceptance_digests=ordered_digests,
    )
    contract = {
        "schema_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "contract_path": contract_path,
        "source": {**source, "content": source_text},
        "reason_codes": reason_codes,
        "dirty_product_paths": actual_dirty,
        "archive_path": archive_path,
        "successors": [
            {
                "id": entry["id"],
                "path": entry["path"],
                "content_digest": entry["content_digest"],
                "content": entry["content"],
                "acceptance_digests": entry["acceptance_digests"],
                "integration": index == len(entries) - 1,
                **entry["validation_projection"],
            }
            for index, entry in enumerate(entries)
        ],
    }
    new_rows = [row for row in rows if row[0] != source_id]
    new_rows.extend(
        (entry["id"], entry["path"], scalar(entry["manifest"], "status"))
        for entry in entries
    )
    new_replanned = [*prior_replanned, (source_id, archive_path, contract_path)]
    return {
        "source_file": source_file,
        "source_text": source_text,
        "active_text": active_text,
        "replanned_text": replanned_text,
        "replanned_existed": REPLANNED_INDEX.exists(),
        "destinations": [
            (contract_path, json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n"),
            (archive_path, archive_text),
            *[(entry["path"], entry["content"]) for entry in entries],
        ],
        "active_new": render_active(new_rows),
        "replanned_new": render_replanned(new_replanned),
        "contract_path": contract_path,
        "expected_dirty_product_paths": actual_dirty,
        "expected_dirty_product_snapshot": dirty_product_snapshot(actual_dirty),
    }


def validate_reason_codes(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or len(value) != len(set(value))
        or any(
            not isinstance(reason, str) or reason not in REASON_CODES
            for reason in value
        )
    ):
        raise RestructureError(f"{label} must be a non-empty unique bounded list")
    return value


def validate_canonical_stopped_manifest(
    manifest: dict[str, str | list[str]],
    label: str,
    *,
    expected_reason_codes: Any = None,
) -> list[str]:
    if scalar(manifest, "status") != "replan_required":
        raise RestructureError(f"{label} must already be canonically stopped")
    if "completion_deferred_reason" in manifest:
        raise RestructureError(
            f"{label} carries stale completion_deferred_reason"
        )
    reasons = validate_reason_codes(
        manifest.get("replan_reason_codes"),
        f"{label} replan_reason_codes",
    )
    if expected_reason_codes is not None:
        validate_reason_codes(expected_reason_codes, f"{label} contract reason_codes")
        if reasons != expected_reason_codes:
            raise RestructureError(
                f"{label} reason codes do not match the canonical source manifest"
            )
    return reasons


def source_dependency_reaches(
    source_path: str,
    earlier_sources: set[str],
    manifests: dict[str, dict[str, str | list[str]]],
) -> bool:
    pending = list(predecessor_paths(manifests[source_path], source_path))
    visited: set[str] = set()
    while pending:
        path = pending.pop()
        if path in earlier_sources:
            return True
        if path in visited or path not in manifests:
            continue
        visited.add(path)
        pending.extend(predecessor_paths(manifests[path], path))
    return False


def validate_direct_active_source(
    *,
    label: str,
    path: str,
    plan_id: str,
    manifest: dict[str, str | list[str]],
    rows: list[tuple[str, str, str]],
    repository_state: dict[str, Any],
) -> None:
    if (
        len([row for row in rows if row[1] == path]) != 1
        or len([row for row in rows if row[0] == plan_id]) != 1
    ):
        raise RestructureError(f"{label} must appear exactly once in the active index")
    if path in repository_state["live_successors"]:
        raise RestructureError(
            f"{label} is already claimed by a verified durable contract"
        )
    if (
        checked_paths_for_successor(plan_id, path)
        or backlog_paths_for_successor(plan_id, path)
        or replanned_records_for_id(plan_id, path)
    ):
        raise RestructureError(f"{label} resolves to more than one lifecycle location")
    claimed = [
        field for field in DIRECT_ACTIVE_LINEAGE_FIELDS if field in manifest
    ]
    if claimed:
        raise RestructureError(
            f"{label} carries replan lineage field: {claimed[0]}"
        )


def current_active_records() -> tuple[
    str,
    list[tuple[str, str, str]],
    dict[str, tuple[str, dict[str, str | list[str]]]],
]:
    active_text = ACTIVE_INDEX.read_text(encoding="utf-8")
    rows = active_rows(active_text)
    records: dict[str, tuple[str, dict[str, str | list[str]]]] = {}
    for plan_id, path, status in rows:
        match = PLAN_PATH_RE.fullmatch(path)
        if match is None or match.group(1) != plan_id:
            raise RestructureError(f"active plan identity mismatch: {path}")
        target = ROOT / path
        if not target.is_file():
            raise RestructureError(f"missing active plan: {path}")
        manifest = parse_manifest(target.read_text(encoding="utf-8"))
        if scalar(manifest, "status") != status:
            raise RestructureError(f"active plan status mismatch: {path}")
        records[path] = (status, manifest)
    return active_text, rows, records


def reference_is_authorized(value: str, authorized_references: set[str]) -> bool:
    return value in authorized_references or any(
        reference.endswith("/") and value.startswith(reference)
        for reference in authorized_references
    )


def reference_token_is_authorized(
    value: str,
    authorized_references: set[str],
) -> bool:
    if reference_is_authorized(value, authorized_references):
        return True
    plan_ids = {
        match.group(1)
        for reference in authorized_references
        for match in [
            PLAN_PATH_RE.fullmatch(reference)
            or CHECKED_PATH_RE.fullmatch(reference)
            or ARCHIVE_PATH_RE.fullmatch(reference)
        ]
        if match is not None
    }
    match = re.fullmatch(r"Plan ([0-9]{3})", value)
    return match is not None and match.group(1) in plan_ids


def exact_reference_tokens(
    value: str,
    *,
    list_field: bool,
    label: str,
) -> list[str]:
    if list_field and "\n" in value:
        tokens: list[str] = []
        for line in value.splitlines():
            if not line:
                continue
            match = re.fullmatch(r"\s*-\s+(\S+)\s*", line)
            if match is None:
                raise RestructureError(
                    f"{label} must contain only exact list-item references"
                )
            tokens.append(match.group(1))
        if tokens:
            return tokens
    if re.fullmatch(r"Plan [0-9]{3}", value):
        return [value]
    path = PurePosixPath(value)
    if (
        value
        and "/" in value
        and not path.is_absolute()
        and not any(part in {"", ".", ".."} for part in path.parts)
        and all(char in PATH_TOKEN_CHARACTERS for char in value)
    ):
        return [value]
    raise RestructureError(f"{label} must replace exact reference tokens only")


def validate_rebind_reference_transition(
    before: dict[str, str | list[str]],
    after: dict[str, str | list[str]],
    replacements: list[dict[str, Any]],
    authorized_old_references: set[str],
    authorized_new_references: set[str],
    label: str,
) -> None:
    for field in ("predecessor_plans", "context_files"):
        before_values = set(items(before, field))
        for value in items(after, field):
            if value not in before_values and not reference_is_authorized(
                value,
                authorized_new_references,
            ):
                raise RestructureError(
                    f"{label} adds an unauthorized {field} reference: {value}"
                )
    for index, replacement in enumerate(replacements, start=1):
        field = replacement["field"]
        list_field = field in {"predecessor_plans", "context_files"}
        old_tokens = exact_reference_tokens(
            replacement["old"],
            list_field=list_field,
            label=f"{label} replacement {index} original",
        )
        new_tokens = exact_reference_tokens(
            replacement["new"],
            list_field=list_field,
            label=f"{label} replacement {index} updated",
        )
        if any(
            not reference_token_is_authorized(
                token,
                authorized_old_references,
            )
            for token in old_tokens
        ) or any(
            not reference_token_is_authorized(
                token,
                authorized_new_references,
            )
            for token in new_tokens
        ):
            raise RestructureError(
                f"{label} replacement {index} is outside the transaction-owned reference map"
            )


def activation_checked_pairs() -> dict[str, str]:
    pairs: dict[str, str] = {}
    for plan_id, checked_path in checked_rows():
        match = CHECKED_PATH_RE.fullmatch(checked_path)
        if match is None or match.group(1) != plan_id:
            continue
        active_path = f"docs/plan/active/{Path(checked_path).name}"
        if active_path in pairs and pairs[active_path] != checked_path:
            raise RestructureError(
                f"activation reference has multiple checked archives: {active_path}"
            )
        target = ROOT / checked_path
        if not target.is_file() or scalar(
            parse_manifest(target.read_text(encoding="utf-8")),
            "status",
        ) != "checked":
            raise RestructureError(
                f"activation checked archive is missing or stale: {checked_path}"
            )
        pairs[active_path] = checked_path
    return pairs


def validate_activation_reference_transition(
    after: dict[str, str | list[str]],
    after_content: str,
    replacements: list[dict[str, Any]],
    promoted_path: str | None,
    label: str,
) -> None:
    pairs = activation_checked_pairs()
    for index, replacement in enumerate(replacements, start=1):
        field = replacement["field"]
        if field in {
            "status",
            "completion_deferred_reason",
            "preservation_scope",
        }:
            continue
        old = replacement["old"]
        new = replacement["new"]
        active_references = list(dict.fromkeys(ACTIVE_REFERENCE_RE.findall(old)))
        if not active_references:
            if (
                field == "context_files"
                and promoted_path is not None
                and promoted_path in new
            ):
                continue
            raise RestructureError(
                f"{label} replacement {index} is not an exact active-to-checked transition"
            )
        expected = old
        for active_path in active_references:
            checked_path = pairs.get(active_path)
            if checked_path is None:
                raise RestructureError(
                    f"{label} replacement {index} lacks the same-ID checked archive"
                )
            expected = expected.replace(active_path, checked_path)
        if new != expected:
            raise RestructureError(
                f"{label} replacement {index} changes more than exact checked references"
            )
    unresolved = [
        value
        for field in ("predecessor_plans", "context_files", "integration_gates")
        for value in items(after, field)
        if ACTIVE_REFERENCE_RE.search(value)
    ]
    unresolved.extend(
        ACTIVE_REFERENCE_RE.findall(
            after_content[manifest_body_offset(after_content):]
        )
    )
    if unresolved:
        raise RestructureError(
            f"{label} activation leaves active plan references unresolved"
        )


def validate_rebinding_specs(
    raw_rebindings: Any,
    *,
    repository_state: dict[str, Any],
    transaction_id: str,
    authorized_old_references: set[str],
    authorized_new_references: set[str],
    allowed_kinds: set[str],
) -> tuple[
    list[dict[str, Any]],
    list[tuple[str, str, str]],
    dict[str, str],
]:
    if not isinstance(raw_rebindings, list):
        raise RestructureError("rebindings must be a list")
    existing_records = repository_state["rebind_records"]
    effective_projections = repository_state["effective_projections"]
    live_successors = repository_state["live_successors"]
    updated_files: list[tuple[str, str, str]] = []
    updated_statuses: dict[str, str] = {}
    records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for index, raw in enumerate(raw_rebindings, start=1):
        spec = exact_object(
            raw,
            {
                "kind",
                "plan_path",
                "owning_contract_path",
                "original_content_digest",
                "prior_effective_projection_digest",
                "updated_content_digest",
                "replacements",
                "promoted_preservation_path",
            },
            f"rebindings[{index}]",
        )
        kind = spec["kind"]
        if kind not in REBIND_KINDS or kind not in allowed_kinds:
            raise RestructureError(
                f"rebindings[{index}] kind is not permitted for this operation"
            )
        plan_path = normalized_path(
            spec["plan_path"],
            PLAN_PATH_RE,
            f"rebindings[{index}].plan_path",
        )
        if plan_path in seen_paths:
            raise RestructureError("one transaction may rebind each live plan once")
        seen_paths.add(plan_path)
        live = live_successors.get(plan_path)
        if live is None or live["lifecycle"] != "active":
            raise RestructureError(
                f"rebindings[{index}] must target one exact active contract successor"
            )
        if spec["owning_contract_path"] != live["contract_path"]:
            raise RestructureError(
                f"rebindings[{index}] owning contract mismatch"
            )
        if (
            not isinstance(spec["original_content_digest"], str)
            or not SHA_RE.fullmatch(spec["original_content_digest"])
            or not isinstance(spec["prior_effective_projection_digest"], str)
            or not SHA_RE.fullmatch(spec["prior_effective_projection_digest"])
            or not isinstance(spec["updated_content_digest"], str)
            or not SHA_RE.fullmatch(spec["updated_content_digest"])
        ):
            raise RestructureError(f"rebindings[{index}] has an invalid digest")
        target = ROOT / plan_path
        original_content = read_regular_file(target, plan_path).decode("utf-8")
        if sha256(original_content.encode("utf-8")) != spec["original_content_digest"]:
            raise RestructureError(
                f"rebindings[{index}] original content is stale"
            )
        prior_projection = effective_projections.get(plan_path)
        if prior_projection is None or projection_digest(prior_projection) != spec[
            "prior_effective_projection_digest"
        ]:
            raise RestructureError(
                f"rebindings[{index}] prior validation projection is stale"
            )
        if not isinstance(spec["replacements"], list) or not spec["replacements"]:
            raise RestructureError(
                f"rebindings[{index}] requires an exact replacement map"
            )
        updated_content = apply_exact_replacements(
            original_content,
            spec["replacements"],
            kind=kind,
            label=f"rebindings[{index}]",
        )
        if sha256(updated_content.encode("utf-8")) != spec["updated_content_digest"]:
            raise RestructureError(
                f"rebindings[{index}] updated content digest mismatch"
            )
        before = parse_manifest(original_content)
        after = parse_manifest(updated_content)
        if kind == "rebind":
            validate_rebind_reference_transition(
                before,
                after,
                spec["replacements"],
                authorized_old_references,
                authorized_new_references,
                f"rebindings[{index}]",
            )
            if manifest_identity_values(before) != manifest_identity_values(after):
                raise RestructureError(
                    f"rebindings[{index}] changes protected plan identity"
                )
            if spec["promoted_preservation_path"] is not None:
                raise RestructureError(
                    f"rebindings[{index}] initial rebind cannot promote preservation"
                )
        else:
            protected = REBIND_PROTECTED_FIELDS - {"status", "preservation_scope"}
            if any(before.get(field) != after.get(field) for field in protected):
                raise RestructureError(
                    f"rebindings[{index}] activation changes protected plan identity"
                )
            if (
                scalar(before, "status") != "deferred"
                or scalar(after, "status") != "in_progress"
                or not scalar(before, "completion_deferred_reason").strip()
                or scalar(after, "completion_deferred_reason")
            ):
                raise RestructureError(
                    f"rebindings[{index}] activation must resolve one deferred plan"
                )
            validate_activation_reference_transition(
                after,
                updated_content,
                spec["replacements"],
                spec["promoted_preservation_path"],
                f"rebindings[{index}]",
            )
            validate_activation_promotion(
                before,
                after,
                spec["promoted_preservation_path"],
                f"rebindings[{index}]",
            )
        validate_current_plan_rules(after, f"rebindings[{index}] updated plan")
        resulting_projection = validate_validation_transition(
            before,
            after,
            spec["replacements"],
            activation=kind == "activation",
            label=f"rebindings[{index}]",
        )
        record = {
            "kind": kind,
            "transaction_id": transaction_id,
            "owning_contract_path": live["contract_path"],
            "owning_contract_digest": live["contract_digest"],
            "plan_path": plan_path,
            "original_content_digest": spec["original_content_digest"],
            "original_content": original_content,
            "prior_effective_projection_digest": spec[
                "prior_effective_projection_digest"
            ],
            "updated_content_digest": spec["updated_content_digest"],
            "updated_content": updated_content,
            "replacements": spec["replacements"],
            "promoted_preservation_path": spec["promoted_preservation_path"],
            "resulting_validation_projection": resulting_projection,
            "record_digest": "",
        }
        record["record_digest"] = canonical_digest(
            {key: value for key, value in record.items() if key != "record_digest"}
        )
        records.append(record)
        updated_files.append((plan_path, original_content, updated_content))
        updated_statuses[plan_path] = scalar(after, "status")
        effective_projections[plan_path] = resulting_projection
    all_records = [*existing_records, *records]
    committed = committed_file_bytes(REBIND_BASELINE_PATH)
    if committed is not None:
        try:
            committed_records = json.loads(committed)["records"]
        except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RestructureError("committed rebind baseline is invalid") from exc
        if all_records[:len(committed_records)] != committed_records:
            raise RestructureError("rebind baseline is not append-only")
    return records, updated_files, updated_statuses


def reference_path_token(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        bool(value)
        and "/" in value
        and not path.is_absolute()
        and not any(part in {"", ".", ".."} for part in path.parts)
        and all(char in PATH_TOKEN_CHARACTERS for char in value)
    )


def manifest_reference_values(
    manifest: dict[str, str | list[str]],
) -> set[str]:
    values: set[str] = set()
    for field in (
        "replan_source",
        "replan_contract",
    ):
        value = scalar(manifest, field)
        if reference_path_token(value):
            values.add(value)
    for field in (
        "replan_sources",
        "successor_plans",
        "predecessor_plans",
        "write_scope",
    ):
        values.update(
            value for value in items(manifest, field)
            if value != "none" and reference_path_token(value)
        )
    return values


def contract_reference_values(contract_path: str) -> set[str]:
    target = ROOT / contract_path
    try:
        contract = json.loads(read_regular_file(target, contract_path))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestructureError(
            f"invalid source ownership contract: {contract_path}"
        ) from exc
    references: set[str] = {contract_path}

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            content = value.get("content")
            if isinstance(content, str) and re.search(
                r"^status:",
                content,
                flags=re.MULTILINE,
            ):
                references.update(
                    manifest_reference_values(parse_manifest(content))
                )
            for key, item in value.items():
                if key != "content":
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, str) and reference_path_token(value):
            references.add(value)

    collect(contract)
    return references


def validate_schema_three_spec(spec: dict[str, Any]) -> dict[str, Any]:
    operation = spec.get("operation")
    if operation == "rebind":
        exact_object(
            spec,
            {"schema_version", "operation", "source_head", "rebindings"},
            "schema-3 rebind specification",
        )
        if spec["source_head"] != current_head():
            raise RestructureError("source HEAD mismatch")
        repository_state = verify_repository_contracts()
        expected_dirty = dirty_product_paths()
        transaction_id = canonical_digest(
            {
                "source_head": spec["source_head"],
                "specification": spec,
            }
        )
        active_text, rows, records_by_path = current_active_records()
        rebind_records, updated_files, updated_statuses = validate_rebinding_specs(
            spec["rebindings"],
            repository_state=repository_state,
            transaction_id=transaction_id,
            authorized_old_references={
                path
                for _, path in checked_rows()
            }
            | set(records_by_path),
            authorized_new_references={
                path
                for _, path in checked_rows()
            }
            | set(records_by_path),
            allowed_kinds={"activation"},
        )
        updated_content = {
            path: content for path, _, content in updated_files
        }
        new_records = dict(records_by_path)
        for path, content in updated_content.items():
            new_records[path] = (
                updated_statuses[path],
                parse_manifest(content),
            )
        validate_active_predecessors(new_records)
        new_rows = [
            (plan_id, path, updated_statuses.get(path, status))
            for plan_id, path, status in rows
        ]
        baseline = {
            "schema_version": 1,
            "records": [
                *repository_state["rebind_records"],
                *rebind_records,
            ],
        }
        return {
            "operation": "rebind",
            "transaction_id": transaction_id,
            "source_head": spec["source_head"],
            "active_text": active_text,
            "active_new": render_active(new_rows),
            "replanned_text": (
                REPLANNED_INDEX.read_text(encoding="utf-8")
                if REPLANNED_INDEX.exists()
                else "# Replanned Plan Index\n\nid\tpath\tcontract\n"
            ),
            "replanned_new": (
                REPLANNED_INDEX.read_text(encoding="utf-8")
                if REPLANNED_INDEX.exists()
                else "# Replanned Plan Index\n\nid\tpath\tcontract\n"
            ),
            "replanned_existed": REPLANNED_INDEX.exists(),
            "source_files": [],
            "destinations": [],
            "updated_files": updated_files,
            "baseline_new": json.dumps(
                baseline,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n",
            "baseline_original": repository_state["rebind_baseline_content"],
            "expected_dirty_product_paths": expected_dirty,
            "expected_dirty_product_snapshot": dirty_product_snapshot(
                expected_dirty
            ),
            "result_path": REBIND_BASELINE_PATH,
            "rebind_record_digests": [
                record["record_digest"] for record in rebind_records
            ],
        }
    exact_object(
        spec,
        {
            "schema_version",
            "operation",
            "source_head",
            "sources",
            "dirty_product_paths",
            "contract_path",
            "successors",
            "prerequisite_plans",
            "rebindings",
        },
        "schema-3 reconstruction specification",
    )
    if operation != "reconstruct":
        raise RestructureError("schema-3 operation must be reconstruct or rebind")
    source_head = spec["source_head"]
    if (
        not isinstance(source_head, str)
        or not re.fullmatch(r"[0-9a-f]{40}", source_head)
        or source_head != current_head()
    ):
        raise RestructureError("source HEAD mismatch")
    repository_state = verify_repository_contracts()
    active_text, rows, active_records = current_active_records()
    raw_sources = spec["sources"]
    if (
        not isinstance(raw_sources, list)
        or not raw_sources
        or len(raw_sources) > MAX_PLANS
    ):
        raise RestructureError("sources must contain between one and eight plans")
    source_infos: list[dict[str, Any]] = []
    source_paths: list[str] = []
    source_ids: list[str] = []
    today = datetime.now().date()
    expected_half = "01-15" if today.day <= 15 else "16-31"
    expected_prefix = (
        f"docs/plan/replanned/{today.year:04d}/{today.month:02d}/{expected_half}/"
    )
    manifests = {
        path: manifest
        for path, (_, manifest) in active_records.items()
    }
    for index, raw_source in enumerate(raw_sources):
        source = exact_object(
            raw_source,
            {
                "path",
                "source_kind",
                "original_plan_digest",
                "stopped_plan_digest",
                "acceptance",
                "reason_codes",
                "archive_path",
            },
            f"sources[{index}]",
        )
        source_kind = source["source_kind"]
        if not isinstance(source_kind, str) or source_kind not in SOURCE_KINDS:
            raise RestructureError(
                f"sources[{index}].source_kind must be contract_successor or direct_active"
            )
        path = normalized_path(
            source["path"],
            PLAN_PATH_RE,
            f"sources[{index}].path",
        )
        match = PLAN_PATH_RE.fullmatch(path)
        assert match
        source_id = match.group(1)
        if path in source_paths or source_id in source_ids:
            raise RestructureError("sources must have unique ordered identities")
        source_paths.append(path)
        source_ids.append(source_id)
        active = active_records.get(path)
        if active is None:
            raise RestructureError(f"sources[{index}] is not an exact active plan")
        status, manifest = active
        if index == 0 and status != "replan_required":
            raise RestructureError("the first coupled source must already be stopped")
        if index > 0 and not source_dependency_reaches(
            path,
            set(source_paths[:index]),
            manifests,
        ):
            raise RestructureError(
                f"sources[{index}] does not depend on an earlier coupled source"
            )
        live = repository_state["live_successors"].get(path)
        if source_kind == "contract_successor":
            if live is None or live["lifecycle"] != "active":
                raise RestructureError(
                    f"sources[{index}] is not an exact live contract successor"
                )
            source_lineage = {
                "source_contract_path": live["contract_path"],
                "source_contract_digest": live["contract_digest"],
            }
        else:
            validate_direct_active_source(
                label=f"sources[{index}]",
                path=path,
                plan_id=source_id,
                manifest=manifest,
                rows=rows,
                repository_state=repository_state,
            )
            source_lineage = {}
        content = read_regular_file(ROOT / path, path).decode("utf-8")
        original_digest = sha256(content.encode("utf-8"))
        if (
            source["original_plan_digest"] != original_digest
            or not SHA_RE.fullmatch(str(source["original_plan_digest"]))
        ):
            raise RestructureError(f"sources[{index}] original digest mismatch")
        reasons = validate_reason_codes(
            source["reason_codes"],
            f"sources[{index}].reason_codes",
        )
        stopped_content = derive_stopped_source_content(content, reasons)
        stopped_digest = sha256(stopped_content.encode("utf-8"))
        if source["stopped_plan_digest"] != stopped_digest:
            raise RestructureError(f"sources[{index}] stopped digest mismatch")
        accepted = acceptance_records(content)
        if source["acceptance"] != accepted:
            raise RestructureError(f"sources[{index}] acceptance mismatch")
        archive_path = normalized_path(
            source["archive_path"],
            ARCHIVE_PATH_RE,
            f"sources[{index}].archive_path",
        )
        if (
            not archive_path.startswith(expected_prefix)
            or Path(archive_path).name != Path(path).name
        ):
            raise RestructureError(
                f"sources[{index}] archive path must use the current partition and basename"
            )
        source_infos.append(
            {
                "id": source_id,
                "path": path,
                "head": source_head,
                "source_kind": source_kind,
                "original_plan_digest": original_digest,
                "original_content": content,
                "stopped_plan_digest": stopped_digest,
                "stopped_content": stopped_content,
                "acceptance": accepted,
                "acceptance_digests": [
                    record["digest"] for record in accepted
                ],
                "acceptance_text_by_digest": {
                    record["digest"]: record["text"] for record in accepted
                },
                "reason_codes": reasons,
                "archive_path": archive_path,
                **source_lineage,
            }
        )
    contract_path = normalized_path(
        spec["contract_path"],
        CONTRACT_PATH_RE,
        "contract_path",
    )
    if not Path(contract_path).name.startswith(source_ids[0] + "-"):
        raise RestructureError("schema-3 contract must use the first source id")
    raw_successors = spec["successors"]
    if (
        not isinstance(raw_successors, list)
        or not raw_successors
        or len(raw_successors) > MAX_PLANS
    ):
        raise RestructureError("successors must contain between one and eight plans")
    raw_successor_paths = [
        normalized_path(
            exact_object(
                entry,
                {
                    "id",
                    "path",
                    "content",
                    "acceptance_mappings",
                    "integration_source_ids",
                },
                f"successors[{index}]",
            )["path"],
            PLAN_PATH_RE,
            f"successors[{index}].path",
        )
        for index, entry in enumerate(raw_successors)
    ]
    if len(raw_successor_paths) != len(set(raw_successor_paths)):
        raise RestructureError("created successor paths must be unique")
    successors = [
        validate_schema_three_successor(
            entry,
            label=f"successors[{index}]",
            contract_path=contract_path,
            source_infos=source_infos,
            all_plan_paths=raw_successor_paths,
        )
        for index, entry in enumerate(raw_successors)
    ]
    validate_schema_three_integration_coverage(successors, source_infos)
    raw_prerequisites = spec["prerequisite_plans"]
    if not isinstance(raw_prerequisites, list):
        raise RestructureError("prerequisite_plans must be a list")
    prerequisites = [
        validate_prerequisite_plan(entry, f"prerequisite_plans[{index}]")
        for index, entry in enumerate(raw_prerequisites)
    ]
    created_entries = [*successors, *prerequisites]
    created_paths = [entry["path"] for entry in created_entries]
    created_ids = [entry["id"] for entry in created_entries]
    if (
        len(created_paths) != len(set(created_paths))
        or len(created_ids) != len(set(created_ids))
        or set(created_ids) & set(source_ids)
    ):
        raise RestructureError("created plan identities conflict")
    prerequisite_paths = {entry["path"] for entry in prerequisites}
    prerequisite_order = {
        entry["path"]: index for index, entry in enumerate(prerequisites)
    }
    prerequisite_dependencies: dict[str, list[str]] = {}
    for prerequisite in prerequisites:
        path = prerequisite["path"]
        dependencies = [
            predecessor
            for predecessor in predecessor_paths(
                prerequisite["manifest"],
                path,
            )
            if predecessor in prerequisite_paths
        ]
        if any(
            prerequisite_order[dependency] >= prerequisite_order[path]
            for dependency in dependencies
        ):
            raise RestructureError(
                "prerequisite plans may depend only on earlier prerequisites"
            )
        prerequisite_dependencies[path] = dependencies
    reachable_prerequisites = {
        predecessor
        for successor in successors
        for predecessor in predecessor_paths(
            successor["manifest"],
            successor["path"],
        )
        if predecessor in prerequisite_paths
    }
    pending = list(reachable_prerequisites)
    while pending:
        path = pending.pop()
        for dependency in prerequisite_dependencies[path]:
            if dependency not in reachable_prerequisites:
                reachable_prerequisites.add(dependency)
                pending.append(dependency)
    if reachable_prerequisites != prerequisite_paths:
        raise RestructureError(
            "every prerequisite plan must reach a mapped successor"
        )
    actual_dirty = dirty_product_paths()
    if spec["dirty_product_paths"] != actual_dirty:
        raise RestructureError(
            "dirty_product_paths must exactly match current Git status"
        )
    preserved = [
        path
        for entry in created_entries
        for path in entry["preservation_scope"]
    ]
    if len(preserved) != len(set(preserved)) or sorted(preserved) != actual_dirty:
        raise RestructureError(
            "created plan preservation_scope must exactly match dirty_product_paths"
        )
    reject_preservation_write_overlap(
        preserved,
        [items(entry["manifest"], "write_scope") for entry in created_entries],
        "created plans",
    )
    destinations = [
        contract_path,
        *[source["archive_path"] for source in source_infos],
        *created_paths,
    ]
    for destination in destinations:
        reject_symlink_ancestors(destination, include_target=False)
        if (ROOT / destination).exists() or (ROOT / destination).is_symlink():
            raise RestructureError(f"destination already exists: {destination}")
    known_ids: set[str] = set()
    for base in (
        ROOT / "docs/plan/active",
        ROOT / "docs/plan/backlog",
        ROOT / "docs/plan/checked",
        ROOT / "docs/plan/replanned",
    ):
        if base.exists():
            for path in base.glob("**/[0-9][0-9][0-9]-*.md"):
                if str(path.relative_to(ROOT)) not in source_paths:
                    known_ids.add(path.name[:3])
    if known_ids & set(created_ids):
        raise RestructureError("a created plan id already exists")
    transaction_id = canonical_digest(
        {
            "source_head": source_head,
            "specification": spec,
        }
    )
    authorized_old_references = {
        reference
        for source in source_infos
        for reference in (
            {
                source["path"],
                *manifest_reference_values(
                    parse_manifest(source["original_content"])
                ),
            }
            | (
                contract_reference_values(source["source_contract_path"])
                if "source_contract_path" in source
                else set()
            )
        )
    }
    authorized_new_references = {
        contract_path,
        *[source["archive_path"] for source in source_infos],
        *created_paths,
        *[
            value
            for entry in created_entries
            for value in items(entry["manifest"], "write_scope")
            if value != "none"
        ],
    }
    rebind_records, updated_files, updated_statuses = validate_rebinding_specs(
        spec["rebindings"],
        repository_state=repository_state,
        transaction_id=transaction_id,
        authorized_old_references=authorized_old_references,
        authorized_new_references=authorized_new_references,
        allowed_kinds={"rebind"},
    )
    updated_content = {
        path: content for path, _, content in updated_files
    }
    future_records = {
        path: value
        for path, value in active_records.items()
        if path not in source_paths
    }
    for entry in created_entries:
        future_records[entry["path"]] = (
            scalar(entry["manifest"], "status"),
            entry["manifest"],
        )
    for path, content in updated_content.items():
        future_records[path] = (
            updated_statuses[path],
            parse_manifest(content),
        )
    validate_active_predecessors(future_records)
    prior_replanned_text = (
        REPLANNED_INDEX.read_text(encoding="utf-8")
        if REPLANNED_INDEX.exists()
        else "# Replanned Plan Index\n\nid\tpath\tcontract\n"
    )
    prior_replanned = replanned_rows(prior_replanned_text)
    if any(
        row[0] in source_ids
        or row[1] in {source["archive_path"] for source in source_infos}
        or row[2] == contract_path
        for row in prior_replanned
    ):
        raise RestructureError("replanned index conflicts with coupled sources")
    contract = {
        "schema_version": 3,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "contract_path": contract_path,
        "source_head": source_head,
        "sources": source_infos,
        "dirty_product_paths": actual_dirty,
        "successors": [
            {
                "id": entry["id"],
                "path": entry["path"],
                "content_digest": entry["content_digest"],
                "content": entry["content"],
                "acceptance_mappings": entry["acceptance_mappings"],
                "integration_source_ids": entry["integration_source_ids"],
                **entry["validation_projection"],
            }
            for entry in successors
        ],
        "prerequisite_plans": [
            {
                "id": entry["id"],
                "path": entry["path"],
                "content_digest": entry["content_digest"],
                "content": entry["content"],
                "authorization": entry["authorization"],
                **entry["validation_projection"],
            }
            for entry in prerequisites
        ],
        "rebind_record_digests": [
            record["record_digest"] for record in rebind_records
        ],
    }
    archives = [
        (
            source["archive_path"],
            build_multi_archive(
                source["stopped_content"],
                source_paths=source_paths,
                contract_path=contract_path,
                plan_paths=raw_successor_paths,
                acceptance_digests=source["acceptance_digests"],
            ),
        )
        for source in source_infos
    ]
    new_rows = [
        (
            plan_id,
            path,
            updated_statuses.get(path, status),
        )
        for plan_id, path, status in rows
        if path not in source_paths
    ]
    new_rows.extend(
        (
            entry["id"],
            entry["path"],
            scalar(entry["manifest"], "status"),
        )
        for entry in created_entries
    )
    new_replanned = [
        *prior_replanned,
        *[
            (source["id"], source["archive_path"], contract_path)
            for source in source_infos
        ],
    ]
    baseline = {
        "schema_version": 1,
        "records": [
            *repository_state["rebind_records"],
            *rebind_records,
        ],
    }
    return {
        "operation": "reconstruct",
        "transaction_id": transaction_id,
        "source_head": source_head,
        "active_text": active_text,
        "active_new": render_active(new_rows),
        "replanned_text": prior_replanned_text,
        "replanned_new": render_replanned(new_replanned),
        "replanned_existed": REPLANNED_INDEX.exists(),
        "source_files": [
            (source["path"], source["original_content"])
            for source in source_infos
        ],
        "destinations": [
            (
                contract_path,
                json.dumps(
                    contract,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n",
            ),
            *archives,
            *[(entry["path"], entry["content"]) for entry in created_entries],
        ],
        "updated_files": updated_files,
        "baseline_new": (
            json.dumps(
                baseline,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
            if rebind_records
            else None
        ),
        "baseline_original": repository_state["rebind_baseline_content"],
        "expected_dirty_product_paths": actual_dirty,
        "expected_dirty_product_snapshot": dirty_product_snapshot(actual_dirty),
        "result_path": contract_path,
        "rebind_record_digests": [
            record["record_digest"] for record in rebind_records
        ],
    }


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    schema_version = spec.get("schema_version")
    if schema_version == 1 and not isinstance(schema_version, bool):
        state = validate_single_source_spec(spec)
        state.update(
            {
                "operation": "single_reconstruct",
                "transaction_id": canonical_digest(
                    {
                        "source_head": current_head(),
                        "specification": spec,
                    }
                ),
                "source_head": current_head(),
                "source_files": [
                    (
                        str(state["source_file"].relative_to(ROOT)),
                        state["source_text"],
                    )
                ],
                "updated_files": [],
                "baseline_new": None,
                "baseline_original": rebind_baseline_content(),
                "result_path": state["contract_path"],
            }
        )
    elif schema_version == 3 and not isinstance(schema_version, bool):
        state = validate_schema_three_spec(spec)
    else:
        raise RestructureError("schema_version must be 1 or 3")
    rows = (
        replanned_rows(REPLANNED_INDEX.read_text(encoding="utf-8"))
        if REPLANNED_INDEX.is_file()
        else []
    )
    state["expected_historical_contract_snapshot"] = (
        historical_contract_snapshot(rows)
    )
    return state


def atomic_write(path: Path, text: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    atomic_replace_text(path, text, mode)


def missing_parent_directories(relative: str) -> list[Path]:
    parents: list[Path] = []
    current = (ROOT / relative).parent
    while current != ROOT and not current.exists():
        parents.append(current)
        current = current.parent
    return parents


def transaction_operation(
    relative: str,
    target_content: str | None,
    *,
    role: str,
    expected_original: str | None | object,
    transaction_id: str,
) -> dict[str, Any]:
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RestructureError(f"transaction path is not normalized: {relative}")
    original_content, original_mode = file_snapshot(relative)
    if (
        expected_original is not _UNSET
        and original_content != expected_original
    ):
        raise RestructureError(f"transaction source changed during preflight: {relative}")
    target_mode = original_mode or 0o644
    if not 0 <= target_mode <= 0o777 or target_mode & 0o002:
        raise RestructureError(
            f"transaction path has an unsafe file mode: {relative}"
        )
    temporary = str(
        PurePosixPath(relative).parent
        / f".{PurePosixPath(relative).name}.{transaction_id[7:23]}.tmp"
    )
    return {
        "path": relative,
        "role": role,
        "original_content": original_content,
        "original_digest": (
            sha256(original_content.encode("utf-8"))
            if original_content is not None
            else None
        ),
        "original_mode": original_mode,
        "target_content": target_content,
        "target_digest": (
            sha256(target_content.encode("utf-8"))
            if target_content is not None
            else None
        ),
        "target_mode": target_mode,
        "temporary_path": temporary,
    }


_UNSET = object()


def build_transaction_operations(state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    transaction_id = state["transaction_id"]
    operations: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(
        relative: str,
        target: str | None,
        role: str,
        expected: str | None | object = _UNSET,
    ) -> None:
        if relative in seen:
            raise RestructureError(f"transaction writes one path more than once: {relative}")
        seen.add(relative)
        operations.append(
            transaction_operation(
                relative,
                target,
                role=role,
                expected_original=expected,
                transaction_id=transaction_id,
            )
        )

    for relative, content in state["destinations"]:
        add(relative, content, "destination", None)
    for relative, original, content in sorted(state["updated_files"]):
        add(relative, content, "rebind", original)
    if state["baseline_new"] is not None:
        add(
            REBIND_BASELINE_PATH,
            state["baseline_new"],
            "rebind_baseline",
            state["baseline_original"],
        )
    if state["active_new"] != state["active_text"]:
        add("docs/plan/plan.md", state["active_new"], "active_index", state["active_text"])
    if state["replanned_new"] != state["replanned_text"]:
        add(
            "docs/plan/replanned.md",
            state["replanned_new"],
            "replanned_index",
            state["replanned_text"] if state["replanned_existed"] else None,
        )
    for relative, content in state["source_files"]:
        add(relative, None, "source_delete", content)
    created_directories = sorted(
        {
            str(path.relative_to(ROOT))
            for operation in operations
            for path in missing_parent_directories(operation["path"])
        },
        key=lambda value: (len(PurePosixPath(value).parts), value),
    )
    return operations, created_directories


def require_transaction_repository_state(
    state: dict[str, Any],
    operations: list[dict[str, Any]],
    *,
    targets_written: bool,
) -> None:
    if current_head() != state["source_head"]:
        raise RestructureError("transaction source HEAD changed during execution")
    dirty_paths = dirty_product_paths()
    if dirty_paths != state["expected_dirty_product_paths"]:
        raise RestructureError("dirty product paths changed during execution")
    if dirty_product_snapshot(dirty_paths) != state[
        "expected_dirty_product_snapshot"
    ]:
        raise RestructureError("dirty product candidates changed during execution")
    require_historical_contract_snapshot(
        state["expected_historical_contract_snapshot"],
        mutable_paths=(
            {
                operation["path"]
                for operation in operations
                if operation["path"] == "docs/plan/replanned.md"
            }
            if targets_written
            else set()
        ),
    )
    digest_key = "target_digest" if targets_written else "original_digest"
    for operation in operations:
        if operation_current_digest(operation) != operation[digest_key]:
            raise RestructureError(
                f"transaction path changed during execution: {operation['path']}"
            )


def overlay_current_worktree(snapshot: Path) -> None:
    paths = run_git("ls-files", "-co", "--exclude-standard", "-z").split(b"\0")
    for raw in paths:
        if not raw:
            continue
        relative = raw.decode("utf-8", "strict")
        source = ROOT / relative
        target = snapshot / relative
        if not source.exists() and not source.is_symlink():
            if target.exists() or target.is_symlink():
                target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.unlink(missing_ok=True)
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            shutil.copy2(source, target, follow_symlinks=False)
        else:
            raise RestructureError(
                f"prospective verification cannot copy path type: {relative}"
            )


def verify_prospective_repository(operations: list[dict[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="plan-restructure-prospective-") as raw:
        snapshot = Path(raw) / "repository"
        completed = subprocess.run(
            ["git", "clone", "-q", "--shared", str(ROOT.resolve()), str(snapshot)],
            cwd=ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            raise RestructureError(
                completed.stderr.decode("utf-8", "replace").strip()
                or "could not create prospective repository"
            )
        overlay_current_worktree(snapshot)
        for operation in operations:
            target = snapshot / operation["path"]
            if operation["target_content"] is None:
                if target.exists() or target.is_symlink():
                    target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(operation["target_content"], encoding="utf-8")
            os.chmod(target, operation["target_mode"], follow_symlinks=False)
        verified = subprocess.run(
            [sys.executable, "scripts/restructure-plan.py", "--verify"],
            cwd=snapshot,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if verified.returncode != 0:
            raise RestructureError(
                "prospective repository verification failed: "
                + (verified.stderr.strip() or verified.stdout.strip())
            )


def git_mutation_lock_paths() -> list[Path]:
    index = git_local_path("index")
    symbolic = subprocess.run(
        ["git", "symbolic-ref", "-q", "HEAD"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    head_target = (
        git_local_path(symbolic.stdout.strip())
        if symbolic.returncode == 0 and symbolic.stdout.strip()
        else git_local_path("HEAD")
    )
    return [
        Path(str(index) + ".lock"),
        Path(str(head_target) + ".lock"),
    ]


@contextmanager
def hold_git_mutation_locks(
    identity: str,
    *,
    allow_existing_owned: bool,
) -> Any:
    lock_paths = git_mutation_lock_paths()
    owned: list[Path] = []
    encoded = (identity + "\n").encode("utf-8")
    try:
        for path in lock_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            reject_filesystem_symlinks(path, include_target=False)
            try:
                descriptor = os.open(
                    path,
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    0o600,
                )
            except FileExistsError:
                if (
                    not allow_existing_owned
                    or read_regular_file(path, str(path), mode_0600=True)
                    != encoded
                ):
                    raise RestructureError(
                        f"Git mutation lock is already held: {path}"
                    )
            else:
                try:
                    os.write(descriptor, encoded)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                fsync_directory(path.parent)
            owned.append(path)
        yield
    finally:
        for path in reversed(owned):
            if path.exists():
                if read_regular_file(path, str(path), mode_0600=True) != encoded:
                    raise RestructureError(
                        f"Git mutation lock identity changed: {path}"
                    )
                path.unlink()
                fsync_directory(path.parent)


def journal_directory() -> Path:
    return git_local_path("project-agent-workflow/restructure-journals")


def journal_file(journal_identity: str) -> Path:
    return journal_directory() / f"{journal_identity[7:39]}.json"


def canonical_journal_identity(payload: dict[str, Any]) -> str:
    return canonical_digest(
        {
            "schema_version": payload["schema_version"],
            "transaction_id": payload["transaction_id"],
            "source_head": payload["source_head"],
            "specification_digest": payload["specification_digest"],
            "operation": payload["operation"],
            "operations": payload["operations"],
            "created_directories": payload["created_directories"],
            "dirty_product_snapshot": payload["dirty_product_snapshot"],
            "historical_contract_snapshot": payload[
                "historical_contract_snapshot"
            ],
            "result_path": payload["result_path"],
        }
    )


def write_new_journal(path: Path, payload: dict[str, Any]) -> None:
    ensure_directories(path.parent)
    reject_filesystem_symlinks(path, include_target=False)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        fsync_directory(path.parent)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def update_journal(path: Path, payload: dict[str, Any], phase: str, next_operation: int) -> None:
    if phase not in JOURNAL_PHASES:
        raise RestructureError(f"unknown transaction phase: {phase}")
    current_phase = payload["phase"]
    if phase not in JOURNAL_TRANSITIONS.get(current_phase, set()):
        raise RestructureError(
            f"invalid transaction phase transition: {current_phase} -> {phase}"
        )
    if (
        phase == current_phase
        and phase in {"applying", "rolling_back", "replaying", "verifying"}
        and next_operation < payload["next_operation"]
    ):
        raise RestructureError("transaction progress cannot move backward")
    payload["phase"] = phase
    payload["next_operation"] = next_operation
    validate_journal_phase_state(payload)
    atomic_replace_text(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        0o600,
    )


def load_journal(path: Path, journal_identity: str) -> dict[str, Any]:
    expected = journal_file(journal_identity)
    if path.absolute() != expected.absolute():
        raise RestructureError("recovery journal identity does not match its Git-local path")
    reject_filesystem_symlinks(path, include_target=True)
    try:
        payload = json.loads(
            read_regular_file(path, "transaction journal", mode_0600=True)
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestructureError("transaction journal is invalid JSON") from exc
    exact_object(
        payload,
        {
            "schema_version",
            "journal_identity",
            "transaction_id",
            "source_head",
            "specification_digest",
            "operation",
            "phase",
            "next_operation",
            "operations",
            "created_directories",
            "dirty_product_snapshot",
            "historical_contract_snapshot",
            "result_path",
            "replacement_identities",
        },
        "transaction journal",
    )
    if (
        payload["schema_version"] != JOURNAL_SCHEMA_VERSION
        or payload["journal_identity"] != journal_identity
        or canonical_journal_identity(payload) != journal_identity
        or payload["phase"] not in JOURNAL_PHASES
        or payload["source_head"] != current_head()
    ):
        raise RestructureError("transaction journal identity or source HEAD is stale")
    if (
        not isinstance(payload["next_operation"], int)
        or isinstance(payload["next_operation"], bool)
        or payload["next_operation"] < 0
        or not isinstance(payload["operations"], list)
        or payload["next_operation"] > len(payload["operations"])
        or not isinstance(payload["created_directories"], list)
        or not isinstance(payload["dirty_product_snapshot"], list)
        or not isinstance(payload["historical_contract_snapshot"], list)
    ):
        raise RestructureError("transaction journal progress is invalid")
    dirty_paths: list[str] = []
    for index, entry in enumerate(payload["dirty_product_snapshot"]):
        if (
            not isinstance(entry, dict)
            or set(entry)
            != {"path", "status_digest", "index_digest", "file"}
            or not isinstance(entry["path"], str)
            or not isinstance(entry["status_digest"], str)
            or not SHA_RE.fullmatch(entry["status_digest"])
            or not isinstance(entry["index_digest"], str)
            or not SHA_RE.fullmatch(entry["index_digest"])
            or not isinstance(entry["file"], dict)
        ):
            raise RestructureError(
                f"transaction dirty snapshot {index} is invalid"
            )
        dirty_paths.append(entry["path"])
    if dirty_paths != sorted(set(dirty_paths)):
        raise RestructureError("transaction dirty snapshot paths are invalid")
    historical_paths: list[str] = []
    for index, entry in enumerate(payload["historical_contract_snapshot"]):
        if (
            not isinstance(entry, dict)
            or set(entry)
            != {
                "path",
                "content_digest",
                "committed_digest",
                "mode",
                "device",
                "inode",
                "link_count",
            }
            or not isinstance(entry["path"], str)
            or not isinstance(entry["content_digest"], str)
            or not SHA_RE.fullmatch(entry["content_digest"])
            or (
                entry["committed_digest"] is not None
                and (
                    not isinstance(entry["committed_digest"], str)
                    or not SHA_RE.fullmatch(entry["committed_digest"])
                )
            )
            or any(
                isinstance(entry[field], bool)
                or not isinstance(entry[field], int)
                for field in ("mode", "device", "inode", "link_count")
            )
        ):
            raise RestructureError(
                f"transaction historical snapshot {index} is invalid"
            )
        historical_paths.append(entry["path"])
    if historical_paths != sorted(set(historical_paths)):
        raise RestructureError(
            "transaction historical snapshot paths are invalid"
        )
    seen: set[str] = set()
    for index, operation in enumerate(payload["operations"]):
        exact_object(
            operation,
            {
                "path",
                "role",
                "original_content",
                "original_digest",
                "original_mode",
                "target_content",
                "target_digest",
                "target_mode",
                "temporary_path",
            },
            f"transaction operation {index}",
        )
        path_value = operation["path"]
        if (
            not isinstance(path_value, str)
            or path_value in seen
            or PurePosixPath(path_value).is_absolute()
            or any(
                part in {"", ".", ".."}
                for part in PurePosixPath(path_value).parts
            )
        ):
            raise RestructureError("transaction journal path is invalid")
        seen.add(path_value)
        for prefix in ("original", "target"):
            content = operation[f"{prefix}_content"]
            digest_value = operation[f"{prefix}_digest"]
            if content is None:
                if digest_value is not None:
                    raise RestructureError("transaction journal digest is invalid")
            elif (
                not isinstance(content, str)
                or digest_value != sha256(content.encode("utf-8"))
            ):
                raise RestructureError("transaction journal content digest mismatch")
        if not isinstance(operation["target_mode"], int):
            raise RestructureError("transaction journal mode is invalid")
        if (
            isinstance(operation["target_mode"], bool)
            or not 0 <= operation["target_mode"] <= 0o777
            or operation["target_mode"] & 0o002
        ):
            raise RestructureError("transaction journal mode is invalid")
    if not isinstance(payload["replacement_identities"], list) or len(
        payload["replacement_identities"]
    ) != len(payload["operations"]):
        raise RestructureError("transaction replacement identities are invalid")
    for index, entry in enumerate(payload["replacement_identities"]):
        if not isinstance(entry, dict) or set(entry) != REPLACEMENT_IDENTITY_KEYS:
            raise RestructureError(
                f"transaction replacement identity {index} is invalid"
            )
        for key in sorted(REPLACEMENT_IDENTITY_KEYS):
            if entry[key] is not None:
                validate_identity_record(
                    entry[key],
                    f"transaction replacement {key} {index}",
                )
    validate_journal_phase_state(payload)
    return payload


def operation_current_digest(operation: dict[str, Any]) -> str | None:
    content, _ = file_snapshot(operation["path"])
    return sha256(content.encode("utf-8")) if content is not None else None


def file_identity(path: Path, label: str, *, expected_mode: int | None = None) -> dict[str, Any]:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise RestructureError(f"{label} must be one unlinked regular file")
        mode = stat.S_IMODE(metadata.st_mode)
        if expected_mode is not None and mode != expected_mode:
            raise RestructureError(f"{label} does not carry its bound target mode")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 65_536)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": mode,
        "link_count": metadata.st_nlink,
        "digest": sha256(b"".join(chunks)),
    }


def optional_file_identity(path: Path, label: str) -> dict[str, Any] | None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except FileNotFoundError:
        if path.is_symlink():
            raise RestructureError(f"symlink target is not allowed: {label}") from None
        return None
    except OSError as exc:
        raise RestructureError(f"{label} is not a readable regular file") from exc
    os.close(descriptor)
    return file_identity(path, label)


def current_file_identity(relative: str, label: str) -> dict[str, Any] | None:
    reject_symlink_ancestors(relative, include_target=True)
    return optional_file_identity(ROOT / relative, label)


def validate_identity_record(value: Any, label: str) -> None:
    if not isinstance(value, dict) or set(value) != IDENTITY_KEYS:
        raise RestructureError(f"{label} identity record is invalid")
    if (
        not isinstance(value["digest"], str)
        or not SHA_RE.fullmatch(value["digest"])
        or any(
            isinstance(value[field], bool) or not isinstance(value[field], int)
            for field in ("device", "inode", "mode", "link_count")
        )
        or value["link_count"] != 1
        or not 0 <= value["mode"] <= 0o777
        or value["mode"] & 0o002
    ):
        raise RestructureError(f"{label} identity record is invalid")


def require_identity_match(
    observed: dict[str, Any] | None,
    expected: dict[str, Any] | None,
    label: str,
) -> None:
    if expected is None:
        raise RestructureError(f"{label} identity is missing")
    if observed is None:
        raise RestructureError(f"{label} identity is absent from disk")
    if observed != expected:
        raise RestructureError(f"{label} identity was externally replaced")


def operation_replaces_content(operation: dict[str, Any]) -> bool:
    return (
        operation["target_content"] is not None
        and operation["original_digest"] != operation["target_digest"]
    )


def require_known_operation_state(
    operation: dict[str, Any],
    identity: dict[str, Any],
) -> None:
    current = operation_current_digest(operation)
    if current not in {
        operation["original_digest"],
        operation["target_digest"],
    }:
        raise RestructureError(
            f"transaction path has ambiguous content: {operation['path']}"
        )
    temporary = ROOT / operation["temporary_path"]
    if temporary.exists() or temporary.is_symlink():
        temporary_bytes = read_regular_file(
            temporary,
            operation["temporary_path"],
        )
        if (
            operation["target_digest"] is None
            or sha256(temporary_bytes) != operation["target_digest"]
        ):
            raise RestructureError(
                f"transaction temporary file is stale: {operation['temporary_path']}"
            )
        if identity["temporary"] is not None:
            require_identity_match(
                file_identity(temporary, operation["temporary_path"]),
                identity["temporary"],
                f"transaction temporary file {operation['temporary_path']}",
            )


def operation_temporary_digest(operation: dict[str, Any]) -> str | None:
    temporary = ROOT / operation["temporary_path"]
    if not temporary.exists() and not temporary.is_symlink():
        return None
    return sha256(read_regular_file(temporary, operation["temporary_path"]))


def validate_operation_identity_state(
    operation: dict[str, Any],
    identity: dict[str, Any],
    phase: str,
    index: int,
    next_operation: int,
    total: int,
    current: str | None,
) -> None:
    label = operation["path"]
    replaces = operation_replaces_content(operation)
    temporary_path = ROOT / operation["temporary_path"]
    observed_temporary = optional_file_identity(
        temporary_path,
        operation["temporary_path"],
    )
    if observed_temporary is not None and identity["temporary"] is not None:
        require_identity_match(
            observed_temporary,
            identity["temporary"],
            f"transaction temporary file {operation['temporary_path']}",
        )
    if phase == "temps_prepared" and operation["target_content"] is not None:
        require_identity_match(
            observed_temporary,
            identity["temporary"],
            f"transaction temporary file {operation['temporary_path']}",
        )
    applied_phases = {"commit_point", "replaying", "verifying", "complete"}
    if replaces and (
        phase in applied_phases
        or (phase == "applying" and index < next_operation)
        or (
            phase == "applying"
            and index == next_operation
            and current == operation["target_digest"]
        )
    ):
        require_identity_match(
            current_file_identity(label, f"transaction target {label}"),
            identity["temporary"],
            f"transaction target {label}",
        )
    if phase == "rolled_back":
        restored_from = 0
    elif phase == "rolling_back":
        restored_from = total - next_operation
    else:
        if identity["restored"] is not None:
            raise RestructureError(
                f"transaction target {label} records an impossible restoration identity"
            )
        return
    if index < restored_from:
        return
    if operation["original_content"] is None:
        if identity["restored"] is not None:
            raise RestructureError(
                f"transaction target {label} records an impossible restoration identity"
            )
        return
    require_identity_match(
        current_file_identity(label, f"restored transaction target {label}"),
        identity["restored"],
        f"restored transaction target {label}",
    )


def validate_journal_phase_state(payload: dict[str, Any]) -> None:
    phase = payload["phase"]
    next_operation = payload["next_operation"]
    operations = payload["operations"]
    if phase in {"prepared", "temps_prepared", "rolled_back"} and next_operation != 0:
        raise RestructureError("transaction phase has invalid progress")
    if phase in {"commit_point", "verifying", "complete"} and next_operation != len(
        operations
    ):
        raise RestructureError("post-commit transaction phase is incomplete")
    for index, operation in enumerate(operations):
        current = operation_current_digest(operation)
        temporary = operation_temporary_digest(operation)
        original = operation["original_digest"]
        target = operation["target_digest"]
        identity = payload["replacement_identities"][index]
        validate_operation_identity_state(
            operation,
            identity,
            phase,
            index,
            next_operation,
            len(operations),
            current,
        )
        if phase == "prepared":
            if current != original or temporary not in {None, target}:
                raise RestructureError("prepared transaction state is inconsistent")
        elif phase == "temps_prepared":
            expected_temporary = target if target is not None else None
            if current != original or temporary != expected_temporary:
                raise RestructureError(
                    "prepared temporary transaction state is inconsistent"
                )
        elif phase == "applying":
            if index < next_operation:
                if current != target:
                    raise RestructureError(
                        "applying transaction progress is inconsistent"
                    )
            elif index > next_operation:
                if current != original:
                    raise RestructureError(
                        "applying transaction progress is inconsistent"
                    )
            else:
                if current not in {original, target}:
                    raise RestructureError(
                        "applying transaction content is inconsistent"
                    )
            expected_temporary = target if current == original and target is not None else None
            if temporary != expected_temporary:
                raise RestructureError(
                    "applying transaction temporary state is inconsistent"
                )
        elif phase == "rolling_back":
            restored_from = len(operations) - next_operation
            if index >= restored_from:
                if current != original or temporary is not None:
                    raise RestructureError(
                        "rolling-back transaction progress is inconsistent"
                    )
            else:
                if current not in {original, target}:
                    raise RestructureError(
                        "rolling-back transaction content is inconsistent"
                    )
                allowed_temporaries = (
                    {None, target}
                    if current == original and target is not None
                    else {None}
                )
                if temporary not in allowed_temporaries:
                    raise RestructureError(
                        "rolling-back transaction temporary state is inconsistent"
                    )
        elif phase in {"commit_point", "replaying", "verifying", "complete"}:
            if current != target or temporary is not None:
                raise RestructureError("post-commit transaction state is inconsistent")
        elif phase == "rolled_back":
            if current != original or temporary is not None:
                raise RestructureError("rolled-back transaction state is inconsistent")


def remove_operation_temporary(
    operation: dict[str, Any],
    identity: dict[str, Any],
) -> None:
    temporary = ROOT / operation["temporary_path"]
    if temporary.exists() or temporary.is_symlink():
        read_regular_file(temporary, operation["temporary_path"])
        temporary.unlink()
        fsync_directory(temporary.parent)


def prepare_operation_temporary(
    operation: dict[str, Any],
    identity: dict[str, Any],
) -> None:
    target = operation["target_content"]
    if target is None:
        identity["temporary"] = None
        return
    temporary = ROOT / operation["temporary_path"]
    ensure_directories(temporary.parent)
    reject_symlink_ancestors(operation["temporary_path"], include_target=False)
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        operation["target_mode"],
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), operation["target_mode"])
            handle.write(target)
            handle.flush()
            os.fsync(handle.fileno())
        fsync_directory(temporary.parent)
        identity["temporary"] = file_identity(
            temporary,
            operation["temporary_path"],
            expected_mode=operation["target_mode"],
        )
        if identity["temporary"]["digest"] != operation["target_digest"]:
            raise RestructureError(
                f"transaction temporary file is stale: {operation['temporary_path']}"
            )
    except BaseException:
        identity["temporary"] = None
        temporary.unlink(missing_ok=True)
        raise


def apply_operation(
    operation: dict[str, Any],
    identity: dict[str, Any],
) -> None:
    relative = operation["path"]
    target = ROOT / relative
    require_known_operation_state(operation, identity)
    if operation["target_content"] is None:
        if target.exists():
            read_regular_file(target, relative)
            target.unlink()
            fsync_directory(target.parent)
        return
    temporary = ROOT / operation["temporary_path"]
    if operation_current_digest(operation) == operation["target_digest"]:
        if operation_replaces_content(operation):
            require_identity_match(
                current_file_identity(relative, f"transaction target {relative}"),
                identity["temporary"],
                f"transaction target {relative}",
            )
        remove_operation_temporary(operation, identity)
        return
    if not temporary.is_file():
        raise RestructureError(
            f"transaction temporary file is missing: {operation['temporary_path']}"
        )
    require_identity_match(
        file_identity(temporary, operation["temporary_path"]),
        identity["temporary"],
        f"transaction temporary file {operation['temporary_path']}",
    )
    os.replace(temporary, target)
    os.chmod(target, operation["target_mode"], follow_symlinks=False)
    fsync_directory(target.parent)
    require_identity_match(
        current_file_identity(relative, f"transaction target {relative}"),
        identity["temporary"],
        f"transaction target {relative}",
    )
    identity["restored"] = None


def restore_operation(
    operation: dict[str, Any],
    identity: dict[str, Any],
) -> None:
    require_known_operation_state(operation, identity)
    target = ROOT / operation["path"]
    if operation["original_content"] is None:
        if target.exists():
            read_regular_file(target, operation["path"])
            target.unlink()
            fsync_directory(target.parent)
        identity["restored"] = None
    else:
        mode = operation["original_mode"] or 0o644
        atomic_replace_text(
            target,
            operation["original_content"],
            mode,
        )
        identity["restored"] = file_identity(
            target,
            operation["path"],
            expected_mode=mode,
        )
        if identity["restored"]["digest"] != operation["original_digest"]:
            raise RestructureError(
                f"restored transaction target {operation['path']} identity is stale"
            )
    remove_operation_temporary(operation, identity)
    identity["temporary"] = None


def rollback_journal(
    path: Path,
    payload: dict[str, Any],
    *,
    crash_phase: str | None = None,
) -> None:
    if payload["phase"] != "rolling_back":
        update_journal(path, payload, "rolling_back", 0)
    start = payload["next_operation"]
    operations = payload["operations"]
    for progress in range(start, len(operations)):
        operation = operations[len(operations) - progress - 1]
        maybe_crash(crash_phase, f"rollback_before_operation_{progress + 1}")
        restore_operation(
            operation,
            payload["replacement_identities"][len(operations) - progress - 1],
        )
        update_journal(path, payload, "rolling_back", progress + 1)
        maybe_crash(crash_phase, f"rollback_after_operation_{progress + 1}")
    for relative in sorted(
        payload["created_directories"],
        key=lambda value: len(PurePosixPath(value).parts),
        reverse=True,
    ):
        directory = ROOT / relative
        try:
            directory.rmdir()
            fsync_directory(directory.parent)
        except OSError:
            pass
    maybe_crash(crash_phase, "rollback_after_directories")
    update_journal(path, payload, "rolled_back", 0)


def roll_forward_journal(
    path: Path,
    payload: dict[str, Any],
    *,
    crash_phase: str | None = None,
) -> None:
    if payload["phase"] == "commit_point":
        update_journal(path, payload, "replaying", 0)
    elif payload["phase"] != "replaying":
        raise RestructureError("roll-forward requires a post-commit replay phase")
    start = payload["next_operation"]
    for index in range(start, len(payload["operations"])):
        operation = payload["operations"][index]
        maybe_crash(crash_phase, f"replay_before_operation_{index + 1}")
        apply_operation(operation, payload["replacement_identities"][index])
        update_journal(path, payload, "replaying", index + 1)
        maybe_crash(crash_phase, f"replay_after_operation_{index + 1}")
    update_journal(path, payload, "verifying", len(payload["operations"]))
    maybe_crash(crash_phase, "replay_before_verify")
    verify_repository_contracts()
    update_journal(path, payload, "complete", len(payload["operations"]))


def maybe_crash(crash_phase: str | None, phase: str) -> None:
    if crash_phase == phase:
        raise SimulatedCrash(f"injected crash at {phase}")


def execute(
    spec_path: Path,
    *,
    fail_after_writes: int = 0,
    crash_phase: str | None = None,
) -> str:
    reject_symlink_ancestors(".agent-artifacts/plan-lifecycle.lock", include_target=True)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    lock_descriptor = os.open(LOCK, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_descriptor, "a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        specification = read_spec(spec_path)
        state = validate_spec(specification)
        legacy_stopped_sources = {
            relative
            for relative, content in state["source_files"]
            if (
                state["operation"] == "single_reconstruct"
                and committed_file_bytes(relative) == content.encode("utf-8")
            )
        }
        verify_repository_contracts(
            legacy_stopped_sources=legacy_stopped_sources,
        )
        operations, created_directories = build_transaction_operations(state)
        verify_prospective_repository(operations)
        payload = {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "journal_identity": "",
            "transaction_id": state["transaction_id"],
            "source_head": state["source_head"],
            "specification_digest": canonical_digest(specification),
            "operation": state["operation"],
            "phase": "prepared",
            "next_operation": 0,
            "operations": operations,
            "created_directories": created_directories,
            "dirty_product_snapshot": state[
                "expected_dirty_product_snapshot"
            ],
            "historical_contract_snapshot": state[
                "expected_historical_contract_snapshot"
            ],
            "result_path": state["result_path"],
            "replacement_identities": [
                {"temporary": None, "restored": None} for _ in operations
            ],
        }
        payload["journal_identity"] = canonical_journal_identity(payload)
        journal_path = journal_file(payload["journal_identity"])
        with hold_git_mutation_locks(
            payload["journal_identity"],
            allow_existing_owned=False,
        ):
            require_transaction_repository_state(
                state,
                operations,
                targets_written=False,
            )
            if journal_path.exists() or journal_path.is_symlink():
                raise RestructureError("transaction journal already exists")
            write_new_journal(journal_path, payload)
            try:
                maybe_crash(crash_phase, "after_journal")
                for index, operation in enumerate(operations):
                    prepare_operation_temporary(
                        operation,
                        payload["replacement_identities"][index],
                    )
                update_journal(journal_path, payload, "temps_prepared", 0)
                maybe_crash(crash_phase, "after_temps")
                require_transaction_repository_state(
                    state,
                    operations,
                    targets_written=False,
                )
                destination_writes = 0
                for index, operation in enumerate(operations):
                    update_journal(journal_path, payload, "applying", index)
                    apply_operation(
                        operation,
                        payload["replacement_identities"][index],
                    )
                    if operation["role"] == "destination":
                        destination_writes += 1
                    if fail_after_writes and destination_writes == fail_after_writes:
                        raise OSError("injected transition write failure")
                    maybe_crash(crash_phase, f"after_operation_{index + 1}")
                require_transaction_repository_state(
                    state,
                    operations,
                    targets_written=True,
                )
                update_journal(
                    journal_path,
                    payload,
                    "commit_point",
                    len(operations),
                )
                maybe_crash(crash_phase, "after_commit_point")
                update_journal(
                    journal_path,
                    payload,
                    "verifying",
                    len(operations),
                )
                verify_repository_contracts()
                update_journal(
                    journal_path,
                    payload,
                    "complete",
                    len(operations),
                )
            except SimulatedCrash:
                raise
            except BaseException:
                if payload["phase"] in {"prepared", "temps_prepared", "applying"}:
                    rollback_journal(journal_path, payload)
                raise
    return state["result_path"]


def recover_transaction(
    path: Path,
    journal_identity: str,
    *,
    crash_phase: str | None = None,
) -> str:
    reject_symlink_ancestors(".agent-artifacts/plan-lifecycle.lock", include_target=True)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    lock_descriptor = os.open(
        LOCK,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
        0o600,
    )
    with os.fdopen(lock_descriptor, "a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with hold_git_mutation_locks(
            journal_identity,
            allow_existing_owned=True,
        ):
            payload = load_journal(path, journal_identity)
            if dirty_product_snapshot(
                [entry["path"] for entry in payload["dirty_product_snapshot"]]
            ) != payload["dirty_product_snapshot"]:
                raise RestructureError(
                    "dirty product candidates changed before recovery"
                )
            require_historical_contract_snapshot(
                payload["historical_contract_snapshot"],
                mutable_paths={
                    operation["path"]
                    for operation in payload["operations"]
                    if operation["path"] == "docs/plan/replanned.md"
                },
            )
            for index, operation in enumerate(payload["operations"]):
                require_known_operation_state(
                    operation,
                    payload["replacement_identities"][index],
                )
            if payload["phase"] in {
                "prepared",
                "temps_prepared",
                "applying",
                "rolling_back",
            }:
                rollback_journal(
                    path,
                    payload,
                    crash_phase=crash_phase,
                )
            elif payload["phase"] in {"commit_point", "replaying"}:
                roll_forward_journal(
                    path,
                    payload,
                    crash_phase=crash_phase,
                )
            elif payload["phase"] == "verifying":
                maybe_crash(crash_phase, "replay_before_verify")
                verify_repository_contracts()
                update_journal(
                    path,
                    payload,
                    "complete",
                    len(payload["operations"]),
                )
            elif payload["phase"] == "complete":
                verify_repository_contracts()
            elif payload["phase"] != "rolled_back":
                raise RestructureError("transaction journal phase is unknown")
    return payload["result_path"]


def validate_repository_active_predecessors() -> None:
    active_records: dict[str, tuple[str, dict[str, str | list[str]]]] = {}
    if ACTIVE_INDEX.is_file():
        for plan_id, path, status in active_rows(ACTIVE_INDEX.read_text(encoding="utf-8")):
            match = PLAN_PATH_RE.fullmatch(path)
            if match is None or match.group(1) != plan_id:
                raise RestructureError(f"active plan identity mismatch: {path}")
            target = ROOT / path
            if not target.is_file():
                raise RestructureError(f"missing active plan: {path}")
            manifest = parse_manifest(target.read_text(encoding="utf-8"))
            if scalar(manifest, "status") != status:
                raise RestructureError(f"active plan status mismatch: {path}")
            active_records[path] = (status, manifest)
    validate_active_predecessors(active_records)


def load_rebind_baseline() -> list[dict[str, Any]]:
    path = ROOT / REBIND_BASELINE_PATH
    committed = committed_file_bytes(REBIND_BASELINE_PATH)
    if not path.exists():
        if committed is not None:
            raise RestructureError("missing published live successor rebind baseline")
        return []
    reject_symlink_ancestors(REBIND_BASELINE_PATH, include_target=True)
    try:
        baseline = json.loads(
            read_regular_file(path, REBIND_BASELINE_PATH)
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestructureError("invalid live successor rebind baseline") from exc
    exact_object(baseline, {"schema_version", "records"}, "rebind baseline")
    records = baseline["records"]
    if baseline["schema_version"] != 1 or not isinstance(records, list):
        raise RestructureError("live successor rebind baseline schema mismatch")
    if committed is not None:
        try:
            committed_baseline = json.loads(committed)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RestructureError("committed rebind baseline is invalid") from exc
        if (
            not isinstance(committed_baseline, dict)
            or committed_baseline.get("schema_version") != 1
            or not isinstance(committed_baseline.get("records"), list)
            or records[:len(committed_baseline["records"])]
            != committed_baseline["records"]
        ):
            raise RestructureError("live successor rebind baseline is not append-only")
    for index, raw in enumerate(records):
        record = exact_object(
            raw,
            {
                "kind",
                "transaction_id",
                "owning_contract_path",
                "owning_contract_digest",
                "plan_path",
                "original_content_digest",
                "original_content",
                "prior_effective_projection_digest",
                "updated_content_digest",
                "updated_content",
                "replacements",
                "promoted_preservation_path",
                "resulting_validation_projection",
                "record_digest",
            },
            f"rebind baseline record {index}",
        )
        if record["kind"] not in REBIND_KINDS:
            raise RestructureError("rebind baseline kind is invalid")
        normalized_path(
            record["plan_path"],
            PLAN_PATH_RE,
            f"rebind baseline record {index} plan path",
        )
        normalized_path(
            record["owning_contract_path"],
            CONTRACT_PATH_RE,
            f"rebind baseline record {index} contract path",
        )
        for field in (
            "transaction_id",
            "owning_contract_digest",
            "original_content_digest",
            "prior_effective_projection_digest",
            "updated_content_digest",
            "record_digest",
        ):
            if not isinstance(record[field], str) or not SHA_RE.fullmatch(record[field]):
                raise RestructureError(f"rebind baseline {field} is invalid")
        if (
            not isinstance(record["original_content"], str)
            or sha256(record["original_content"].encode("utf-8"))
            != record["original_content_digest"]
            or not isinstance(record["updated_content"], str)
            or sha256(record["updated_content"].encode("utf-8"))
            != record["updated_content_digest"]
            or not isinstance(record["replacements"], list)
            or not isinstance(record["resulting_validation_projection"], dict)
        ):
            raise RestructureError("rebind baseline content is invalid")
        if canonical_digest(
            {key: value for key, value in record.items() if key != "record_digest"}
        ) != record["record_digest"]:
            raise RestructureError("rebind baseline record digest mismatch")
    return records


def rebind_baseline_content() -> str | None:
    path = ROOT / REBIND_BASELINE_PATH
    if not path.exists():
        if path.is_symlink():
            raise RestructureError("live successor rebind baseline is a symlink")
        return None
    return read_regular_file(path, REBIND_BASELINE_PATH).decode("utf-8")


def compare_contract_identity(
    original: dict[str, str | list[str]],
    base: dict[str, str | list[str]],
    label: str,
) -> None:
    fields = REBIND_PROTECTED_FIELDS - {"status"}
    changed = sorted(
        field for field in fields if original.get(field) != base.get(field)
    )
    if changed:
        raise RestructureError(
            f"{label} original content already drifted in: {', '.join(changed)}"
        )


def split_validation_notes(
    content: str,
) -> tuple[str, str | None, str]:
    lines = content.splitlines(keepends=True)
    matches = [
        index
        for index, line in enumerate(lines)
        if line.rstrip("\r\n") == "## Validation Notes"
    ]
    if len(matches) > 1:
        raise RestructureError("plan contains multiple Validation Notes sections")
    if not matches:
        return content, None, ""
    start = matches[0]
    prefix_end = start
    while prefix_end and not lines[prefix_end - 1].strip():
        prefix_end -= 1
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].rstrip("\r\n").startswith("## "):
            end = index
            break
    return (
        "".join(lines[:prefix_end]),
        "".join(lines[start + 1:end]),
        "".join(lines[end:]),
    )


def validate_task_checkbox_transition(
    baseline: str,
    live: str,
    label: str,
) -> None:
    baseline_lines = baseline.splitlines(keepends=True)
    live_lines = live.splitlines(keepends=True)
    if len(baseline_lines) != len(live_lines):
        raise RestructureError(f"{label} changes non-validation-note line count")
    checkbox = re.compile(r"^(\s*[-*+]\s+)\[([ xX])\](.*)$")
    for original, updated in zip(baseline_lines, live_lines, strict=True):
        if original == updated:
            continue
        original_newline = original[len(original.rstrip("\r\n")):]
        updated_newline = updated[len(updated.rstrip("\r\n")):]
        original_match = checkbox.fullmatch(original.rstrip("\r\n"))
        updated_match = checkbox.fullmatch(updated.rstrip("\r\n"))
        if (
            original_newline != updated_newline
            or original_match is None
            or updated_match is None
            or original_match.group(1) != updated_match.group(1)
            or original_match.group(3) != updated_match.group(3)
            or original_match.group(2) != " "
            or updated_match.group(2) != "x"
        ):
            raise RestructureError(
                f"{label} changes bytes outside an unchecked-to-checked task marker"
            )


def validate_lifecycle_body_transition(
    baseline_content: str,
    live_content: str,
    label: str,
) -> None:
    baseline_projected = project_lifecycle_fields(
        baseline_content,
        {"status", "completion_deferred_reason", "replan_reason_codes"},
    )
    live_projected = project_lifecycle_fields(
        live_content,
        {"status", "completion_deferred_reason", "replan_reason_codes"},
    )
    baseline_prefix, baseline_notes, baseline_suffix = split_validation_notes(
        baseline_projected
    )
    live_prefix, live_notes, live_suffix = split_validation_notes(live_projected)
    validate_task_checkbox_transition(baseline_prefix, live_prefix, label)
    if baseline_notes is None:
        if live_notes is None:
            if live_suffix:
                raise RestructureError(f"{label} has an invalid section boundary")
            return
        if live_suffix:
            raise RestructureError(
                f"{label} may add Validation Notes only as the final section"
            )
        if len(live_notes.encode("utf-8")) > 65_536:
            raise RestructureError(f"{label} Validation Notes append is too large")
        return
    if live_notes is None:
        raise RestructureError(f"{label} removes Validation Notes")
    validate_task_checkbox_transition(
        baseline_suffix,
        live_suffix,
        label,
    )
    if not live_notes.startswith(baseline_notes):
        raise RestructureError(f"{label} rewrites existing Validation Notes")
    if len(live_notes[len(baseline_notes):].encode("utf-8")) > 65_536:
        raise RestructureError(f"{label} Validation Notes append is too large")


def validate_lifecycle_evolution(
    baseline_content: str,
    live_content: str,
    label: str,
) -> None:
    baseline = parse_manifest(baseline_content)
    live = parse_manifest(live_content)
    baseline_status = scalar(baseline, "status")
    live_status = scalar(live, "status")
    if baseline_status == "deferred" and live_status == "deferred":
        if live_content != baseline_content:
            raise RestructureError(
                f"{label} deferred projection changed without an activation record"
            )
        return
    if baseline_status not in {"in_progress", "deferred"} or live_status not in {
        "in_progress",
        "ready_to_archive",
        "checked",
        "replan_required",
        "backlog",
    }:
        raise RestructureError(f"{label} has an invalid lifecycle transition")
    if baseline_status == "deferred" and live_status not in {"replan_required", "backlog"}:
        raise RestructureError(
            f"{label} deferred projection changed without an activation record"
        )
    if live_status == "replan_required":
        validate_canonical_stopped_manifest(live, label)
    elif (
        scalar(live, "completion_deferred_reason")
        or items(live, "replan_reason_codes")
    ):
        raise RestructureError(f"{label} carries stale stopped-lifecycle fields")
    lifecycle_fields = {"status", "completion_deferred_reason", "replan_reason_codes"}
    for field in sorted(set(baseline) | set(live)):
        if field not in lifecycle_fields and baseline.get(field) != live.get(field):
            raise RestructureError(
                f"{label} changes protected manifest field: {field}"
            )
    validate_lifecycle_body_transition(
        baseline_content,
        live_content,
        label,
    )


def verify_rebind_records(
    records: list[dict[str, Any]],
    live_successors: dict[str, dict[str, Any]],
    contract_digests: dict[str, str],
    legacy_stopped_sources: set[str],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["plan_path"], []).append(record)
    unknown = sorted(set(grouped) - set(live_successors))
    if unknown:
        raise RestructureError(
            "rebind baseline targets unknown live successors: " + ", ".join(unknown)
        )
    effective: dict[str, dict[str, Any]] = {}
    for path, state in live_successors.items():
        projection = state["base_projection"]
        if projection is None:
            raise RestructureError(f"live successor lacks validation authority: {path}")
        chain = grouped.get(path, [])
        if not chain:
            live_manifest = state["live_manifest"]
            if state["expected_preservation"] is not None and preservation_scope(
                live_manifest,
                f"live successor {path}",
                required=True,
            ) != state["expected_preservation"]:
                raise RestructureError(
                    f"live successor preservation_scope mismatch: {path}"
                )
            if state["enforce_projection_semantics"]:
                validate_projection(
                    projection,
                    live_manifest,
                    f"live successor {path}",
                )
            elif validation_projection(
                live_manifest,
                f"live successor {path}",
                require_witness=projection["validation_witness_schema"] == 1,
                enforce_witness_semantics=False,
            ) != projection:
                raise RestructureError(
                    f"live successor {path} validation projection mismatch"
                )
            if (
                state["enforce_projection_semantics"]
                and state["lifecycle"] in {"active", "checked", "backlog"}
            ):
                if (
                    scalar(live_manifest, "status") == "replan_required"
                    and path in legacy_stopped_sources
                ):
                    validate_canonical_stopped_manifest(
                        live_manifest,
                        f"legacy stopped successor {path}",
                    )
                else:
                    validate_lifecycle_evolution(
                        state["base_content"],
                        state["live_content"],
                        f"live successor lifecycle: {path}",
                    )
            effective[path] = projection
            continue
        previous_content: str | None = None
        for index, record in enumerate(chain):
            label = f"rebind baseline {path}/{index}"
            if (
                record["owning_contract_path"] != state["contract_path"]
                or contract_digests.get(record["owning_contract_path"])
                != record["owning_contract_digest"]
            ):
                raise RestructureError(f"{label} owning contract mismatch")
            if (
                previous_content is not None
                and record["original_content"] != previous_content
            ):
                raise RestructureError(f"{label} contains a chain gap or fork")
            before = parse_manifest(record["original_content"])
            after = parse_manifest(record["updated_content"])
            if index == 0:
                compare_contract_identity(
                    before,
                    state["base_manifest"],
                    label,
                )
            if validation_projection(
                before,
                f"{label} original",
                require_witness=scalar(before, "validation_witness_schema") == "1",
                enforce_witness_semantics=False,
            ) != projection:
                raise RestructureError(f"{label} prior validation authority mismatch")
            if record["prior_effective_projection_digest"] != projection_digest(
                projection
            ):
                raise RestructureError(f"{label} prior projection digest mismatch")
            reproduced = apply_exact_replacements(
                record["original_content"],
                record["replacements"],
                kind=record["kind"],
                label=label,
            )
            if reproduced != record["updated_content"]:
                raise RestructureError(f"{label} replacement reproduction mismatch")
            if record["kind"] == "rebind":
                if manifest_identity_values(before) != manifest_identity_values(after):
                    raise RestructureError(f"{label} changes protected plan identity")
                if record["promoted_preservation_path"] is not None:
                    raise RestructureError(f"{label} has an invalid promotion")
            else:
                protected = REBIND_PROTECTED_FIELDS - {"status", "preservation_scope"}
                if any(before.get(field) != after.get(field) for field in protected):
                    raise RestructureError(
                        f"{label} activation changes protected plan identity"
                    )
                if (
                    scalar(before, "status") != "deferred"
                    or scalar(after, "status") != "in_progress"
                    or not scalar(before, "completion_deferred_reason").strip()
                    or scalar(after, "completion_deferred_reason")
                ):
                    raise RestructureError(f"{label} activation state mismatch")
                validate_activation_reference_transition(
                    after,
                    record["updated_content"],
                    record["replacements"],
                    record["promoted_preservation_path"],
                    label,
                )
                validate_activation_promotion(
                    before,
                    after,
                    record["promoted_preservation_path"],
                    label,
                )
            validate_current_plan_rules(after, f"{label} updated")
            projection = validate_validation_transition(
                before,
                after,
                record["replacements"],
                activation=record["kind"] == "activation",
                label=label,
            )
            if projection != record["resulting_validation_projection"]:
                raise RestructureError(f"{label} resulting projection mismatch")
            previous_content = record["updated_content"]
        assert previous_content is not None
        replan_original = state.get("replan_original_content")
        if (
            state["lifecycle"] == "replanned"
            and isinstance(replan_original, str)
            and replan_original != state["live_content"]
        ):
            validate_lifecycle_evolution(
                previous_content,
                replan_original,
                f"rebind baseline final projection: {path}",
            )
            stopped_manifest = parse_manifest(state["live_content"])
            reasons = validate_reason_codes(
                items(stopped_manifest, "replan_reason_codes"),
                f"replanned successor {path} reason codes",
            )
            if derive_stopped_source_content(replan_original, reasons) != state[
                "live_content"
            ]:
                raise RestructureError(
                    f"replanned successor stop projection mismatch: {path}"
                )
        else:
            validate_lifecycle_evolution(
                previous_content,
                state["live_content"],
                f"rebind baseline final projection: {path}",
            )
        live_manifest = parse_manifest(state["live_content"])
        if validation_projection(
            live_manifest,
            f"live rebound successor {path}",
            require_witness=projection["validation_witness_schema"] == 1,
        ) != projection:
            raise RestructureError(
                f"live rebound successor validation projection mismatch: {path}"
            )
        effective[path] = projection
    return effective


def verify_prerequisite_lifecycle(
    entry: dict[str, Any],
    contract_path: str,
) -> dict[str, Any]:
    path = entry["path"]
    plan_id = entry["id"]
    active = active_records_for_successor(plan_id, path)
    checked = checked_paths_for_successor(plan_id, path)
    replanned = replanned_records_for_id(plan_id, path)
    if sum((bool(active), bool(checked), bool(replanned))) != 1:
        raise RestructureError(f"prerequisite plan lifecycle is ambiguous: {path}")
    if active:
        target = ROOT / path
        expected_status = active[0][2]
        lifecycle = "active"
    elif checked:
        target = ROOT / checked[0]
        expected_status = "checked"
        lifecycle = "checked"
    else:
        archive_path, owning_contract = replanned[0]
        target = ROOT / archive_path
        expected_status = "replanned"
        lifecycle = "replanned"
        if owning_contract == contract_path:
            raise RestructureError(f"prerequisite cannot be its own contract source: {path}")
    if not target.is_file():
        raise RestructureError(f"missing prerequisite lifecycle file: {path}")
    live = parse_manifest(target.read_text(encoding="utf-8"))
    base = parse_manifest(entry["content"])
    if scalar(live, "status") != expected_status:
        raise RestructureError(f"prerequisite lifecycle status mismatch: {path}")
    protected = REBIND_PROTECTED_FIELDS - {
        "status",
        "replan_source",
        "replan_sources",
        "replan_contract",
        "successor_plans",
        "inherited_acceptance_digests",
        "integration_source_ids",
    }
    for field in protected:
        if live.get(field) != base.get(field):
            raise RestructureError(f"prerequisite contract drift in {field}: {path}")
    projection = {
        key: entry[key]
        for key in (
            "authoritative_validation",
            "authoritative_validation_digest",
            "validation_witness_schema",
            "validation_witness_map_digest",
        )
    }
    validate_projection(
        projection,
        live,
        f"prerequisite lifecycle {path}",
    )
    return {
        "live_content": target.read_text(encoding="utf-8"),
        "live_manifest": live,
        "lifecycle": lifecycle,
    }


def verify_schema_three_contract(
    contract_path: str,
    contract_bytes: bytes,
    contract: dict[str, Any],
    indexed_rows: list[tuple[str, str, str]],
    rebind_record_digests: set[str],
    live_successors: dict[str, dict[str, Any]],
    contract_digests: dict[str, str],
    direct_active_sources: dict[str, str],
) -> None:
    exact_object(
        contract,
        {
            "schema_version",
            "created_at",
            "contract_path",
            "source_head",
            "sources",
            "dirty_product_paths",
            "successors",
            "prerequisite_plans",
            "rebind_record_digests",
        },
        f"schema-3 contract {contract_path}",
    )
    if contract["contract_path"] != contract_path:
        raise RestructureError("schema-3 contract identity mismatch")
    try:
        datetime.fromisoformat(contract["created_at"])
    except (TypeError, ValueError) as exc:
        raise RestructureError("schema-3 contract timestamp is invalid") from exc
    if (
        not isinstance(contract["source_head"], str)
        or not re.fullmatch(r"[0-9a-f]{40}", contract["source_head"])
    ):
        raise RestructureError("schema-3 contract source HEAD is invalid")
    sources = contract["sources"]
    if not isinstance(sources, list) or not sources:
        raise RestructureError("schema-3 contract has no sources")
    source_infos: list[dict[str, Any]] = []
    source_paths: list[str] = []
    source_ids: list[str] = []
    expected_rows: list[tuple[str, str, str]] = []
    for index, raw_source in enumerate(sources):
        if not isinstance(raw_source, dict):
            raise RestructureError(f"schema-3 source {index} is not an object")
        if "source_kind" in raw_source:
            source_kind = raw_source["source_kind"]
            if not isinstance(source_kind, str) or source_kind not in SOURCE_KINDS:
                raise RestructureError(
                    f"schema-3 source {index} declares an unknown source kind"
                )
            source_fields = SCHEMA_THREE_SOURCE_FIELDS | {"source_kind"}
            if source_kind == "contract_successor":
                source_fields = source_fields | SCHEMA_THREE_CONTRACT_SOURCE_FIELDS
        else:
            source_kind = "contract_successor"
            source_fields = (
                SCHEMA_THREE_SOURCE_FIELDS | SCHEMA_THREE_CONTRACT_SOURCE_FIELDS
            )
        source = exact_object(
            raw_source,
            source_fields,
            f"schema-3 source {index}",
        )
        path = normalized_path(source["path"], PLAN_PATH_RE, "schema-3 source path")
        match = PLAN_PATH_RE.fullmatch(path)
        assert match
        if source["id"] != match.group(1) or source["head"] != contract["source_head"]:
            raise RestructureError("schema-3 source identity mismatch")
        if index == 0:
            validate_canonical_stopped_manifest(
                parse_manifest(source["original_content"]),
                "schema-3 first source",
                expected_reason_codes=source["reason_codes"],
            )
        else:
            validate_reason_codes(
                source["reason_codes"],
                f"schema-3 source {index} reason_codes",
            )
        if (
            sha256(source["original_content"].encode("utf-8"))
            != source["original_plan_digest"]
            or sha256(source["stopped_content"].encode("utf-8"))
            != source["stopped_plan_digest"]
            or derive_stopped_source_content(
                source["original_content"],
                source["reason_codes"],
            )
            != source["stopped_content"]
            or acceptance_records(source["original_content"]) != source["acceptance"]
        ):
            raise RestructureError("schema-3 source content mismatch")
        accepted_digests = [record["digest"] for record in source["acceptance"]]
        accepted_map = {
            record["digest"]: record["text"] for record in source["acceptance"]
        }
        if (
            source["acceptance_digests"] != accepted_digests
            or source["acceptance_text_by_digest"] != accepted_map
        ):
            raise RestructureError("schema-3 source acceptance projection mismatch")
        if source_kind == "contract_successor":
            source_contract_path = normalized_path(
                source["source_contract_path"],
                CONTRACT_PATH_RE,
                "schema-3 source contract path",
            )
            source_contract = ROOT / source_contract_path
            if (
                not source_contract.is_file()
                or sha256(read_regular_file(source_contract, source_contract_path))
                != source["source_contract_digest"]
            ):
                raise RestructureError("schema-3 source contract digest mismatch")
        else:
            if path in direct_active_sources:
                raise RestructureError(
                    f"direct active source is reconstructed twice: {path}"
                )
            direct_active_sources[path] = contract_path
        archive_path = normalized_path(
            source["archive_path"],
            ARCHIVE_PATH_RE,
            "schema-3 source archive path",
        )
        archive_file = ROOT / archive_path
        if not archive_file.is_file():
            raise RestructureError("schema-3 source archive is missing")
        source_paths.append(path)
        source_ids.append(source["id"])
        expected_rows.append((source["id"], archive_path, contract_path))
        source_infos.append(source)
    if (
        len(source_paths) != len(set(source_paths))
        or len(source_ids) != len(set(source_ids))
        or sorted(indexed_rows) != sorted(expected_rows)
    ):
        raise RestructureError("schema-3 source index mapping is incomplete")
    successor_paths = [
        normalized_path(
            raw["path"],
            PLAN_PATH_RE,
            "schema-3 successor path",
        )
        for raw in contract["successors"]
        if isinstance(raw, dict) and "path" in raw
    ]
    if len(successor_paths) != len(contract["successors"]):
        raise RestructureError("schema-3 successor list is invalid")
    for source in source_infos:
        archive = parse_manifest(
            (ROOT / source["archive_path"]).read_text(encoding="utf-8")
        )
        if (
            scalar(archive, "status") != "replanned"
            or items(archive, "replan_sources") != source_paths
            or scalar(archive, "replan_contract") != contract_path
            or items(archive, "successor_plans") != successor_paths
            or items(archive, "inherited_acceptance_digests")
            != source["acceptance_digests"]
            or items(archive, "acceptance")
            != [record["text"] for record in source["acceptance"]]
        ):
            raise RestructureError("schema-3 source archive lineage mismatch")
    validated_successors: list[dict[str, Any]] = []
    for index, raw in enumerate(contract["successors"]):
        successor = exact_object(
            raw,
            {
                "id",
                "path",
                "content_digest",
                "content",
                "acceptance_mappings",
                "integration_source_ids",
                "authoritative_validation",
                "authoritative_validation_digest",
                "validation_witness_schema",
                "validation_witness_map_digest",
            },
            f"schema-3 contract successor {index}",
        )
        validated = validate_schema_three_successor(
            {
                key: successor[key]
                for key in (
                    "id",
                    "path",
                    "content",
                    "acceptance_mappings",
                    "integration_source_ids",
                )
            },
            label=f"schema-3 contract successor {index}",
            contract_path=contract_path,
            source_infos=source_infos,
            all_plan_paths=successor_paths,
        )
        if (
            successor["content_digest"] != validated["content_digest"]
            or {
                key: successor[key]
                for key in (
                    "authoritative_validation",
                    "authoritative_validation_digest",
                    "validation_witness_schema",
                    "validation_witness_map_digest",
                )
            }
            != validated["validation_projection"]
        ):
            raise RestructureError("schema-3 successor projection mismatch")
        validated_successors.append(validated)
    validate_schema_three_integration_coverage(
        validated_successors,
        source_infos,
    )
    contract_preservation: list[str] = []
    contract_scopes: list[list[str]] = []
    for successor in validated_successors:
        path = successor["path"]
        active = active_records_for_successor(successor["id"], path)
        checked = checked_paths_for_successor(successor["id"], path)
        backlog = backlog_paths_for_successor(successor["id"], path)
        replanned = replanned_records_for_id(successor["id"], path)
        if sum((bool(active), bool(checked), bool(backlog), bool(replanned))) != 1:
            raise RestructureError(f"schema-3 successor lifecycle is ambiguous: {path}")
        if active:
            live_file = ROOT / path
            expected_status = active[0][2]
            lifecycle = "active"
            replan_original_content = None
        elif checked:
            live_file = ROOT / checked[0]
            expected_status = "checked"
            lifecycle = "checked"
            replan_original_content = None
        elif backlog:
            reject_symlink_ancestors(backlog[0], include_target=True)
            live_file = ROOT / backlog[0]
            expected_status = "backlog"
            lifecycle = "backlog"
            replan_original_content = None
        else:
            replanned_state = validate_replanned_successor(
                successor["id"],
                path,
                successor["acceptance_digests"],
                items(successor["manifest"], "acceptance"),
                None,
                None,
            )
            live_content = replanned_state["stopped_content"]
            replan_original_content = replanned_state["original_content"]
            live_file = None
            expected_status = "replan_required"
            lifecycle = "replanned"
        if live_file is not None and not live_file.is_file():
            raise RestructureError(f"schema-3 successor file is missing: {path}")
        if live_file is not None:
            live_content = live_file.read_text(encoding="utf-8")
        live_manifest = parse_manifest(live_content)
        if scalar(live_manifest, "status") != expected_status:
            raise RestructureError(f"schema-3 successor lineage mismatch: {path}")
        if lifecycle != "replanned" and (
            items(live_manifest, "replan_sources") != source_paths
            or scalar(live_manifest, "replan_contract") != contract_path
            or items(live_manifest, "inherited_acceptance_digests")
            != successor["acceptance_digests"]
            or items(live_manifest, "acceptance")
            != items(successor["manifest"], "acceptance")
        ):
            raise RestructureError(f"schema-3 successor lineage mismatch: {path}")
        contract_preservation.extend(successor["preservation_scope"])
        contract_scopes.append(items(successor["manifest"], "write_scope"))
        if path in live_successors:
            raise RestructureError(
                f"live successor is owned by multiple contracts: {path}"
            )
        live_successors[path] = {
            "contract_path": contract_path,
            "contract_digest": sha256(contract_bytes),
            "base_manifest": successor["manifest"],
            "base_content": successor["content"],
            "base_projection": successor["validation_projection"],
            "expected_preservation": successor["preservation_scope"],
            "live_manifest": live_manifest,
            "live_content": live_content,
            "lifecycle": lifecycle,
            "replan_original_content": replan_original_content,
            "enforce_projection_semantics": True,
            "role": "successor",
        }
    prerequisites = contract["prerequisite_plans"]
    if not isinstance(prerequisites, list):
        raise RestructureError("schema-3 prerequisite list is invalid")
    prerequisite_paths: set[str] = set()
    validated_prerequisites: list[dict[str, Any]] = []
    for index, raw in enumerate(prerequisites):
        prerequisite = exact_object(
            raw,
            {
                "id",
                "path",
                "content_digest",
                "content",
                "authorization",
                "authoritative_validation",
                "authoritative_validation_digest",
                "validation_witness_schema",
                "validation_witness_map_digest",
            },
            f"schema-3 prerequisite {index}",
        )
        validated = validate_prerequisite_plan(
            {
                key: prerequisite[key]
                for key in ("id", "path", "content", "authorization")
            },
            f"schema-3 prerequisite {index}",
        )
        if (
            prerequisite["content_digest"] != validated["content_digest"]
            or {
                key: prerequisite[key]
                for key in (
                    "authoritative_validation",
                    "authoritative_validation_digest",
                    "validation_witness_schema",
                    "validation_witness_map_digest",
                )
            }
            != validated["validation_projection"]
        ):
            raise RestructureError("schema-3 prerequisite projection mismatch")
        prerequisite_paths.add(prerequisite["path"])
        contract_preservation.extend(validated["preservation_scope"])
        contract_scopes.append(items(validated["manifest"], "write_scope"))
        lifecycle_state = verify_prerequisite_lifecycle(
            prerequisite,
            contract_path,
        )
        if prerequisite["path"] in live_successors:
            raise RestructureError(
                f"prerequisite is owned by multiple contracts: {prerequisite['path']}"
            )
        live_successors[prerequisite["path"]] = {
            "contract_path": contract_path,
            "contract_digest": sha256(contract_bytes),
            "base_manifest": validated["manifest"],
            "base_content": prerequisite["content"],
            "base_projection": validated["validation_projection"],
            "expected_preservation": validated["preservation_scope"],
            **lifecycle_state,
            "enforce_projection_semantics": True,
            "role": "prerequisite",
        }
        validated_prerequisites.append(validated)
    referenced = {
        predecessor
        for successor in validated_successors
        for predecessor in predecessor_paths(
            successor["manifest"],
            successor["path"],
        )
        if predecessor in prerequisite_paths
    }
    prerequisite_order = {
        entry["path"]: index
        for index, entry in enumerate(validated_prerequisites)
    }
    dependencies: dict[str, list[str]] = {}
    for prerequisite in validated_prerequisites:
        path = prerequisite["path"]
        dependencies[path] = [
            predecessor
            for predecessor in predecessor_paths(
                prerequisite["manifest"],
                path,
            )
            if predecessor in prerequisite_paths
        ]
        if any(
            prerequisite_order[dependency] >= prerequisite_order[path]
            for dependency in dependencies[path]
        ):
            raise RestructureError(
                "schema-3 prerequisite ordering is invalid"
            )
    pending = list(referenced)
    while pending:
        path = pending.pop()
        for dependency in dependencies[path]:
            if dependency not in referenced:
                referenced.add(dependency)
                pending.append(dependency)
    if referenced != prerequisite_paths:
        raise RestructureError("schema-3 prerequisite mapping is incomplete")
    if (
        len(contract_preservation) != len(set(contract_preservation))
        or sorted(contract_preservation) != contract["dirty_product_paths"]
    ):
        raise RestructureError("schema-3 preservation mapping is invalid")
    reject_preservation_write_overlap(
        contract_preservation,
        contract_scopes,
        f"schema-3 contract {contract_path}",
    )
    digests = contract["rebind_record_digests"]
    if (
        not isinstance(digests, list)
        or len(digests) != len(set(digests))
        or any(value not in rebind_record_digests for value in digests)
    ):
        raise RestructureError("schema-3 rebind record mapping is invalid")
    contract_digests[contract_path] = sha256(contract_bytes)


def verify_repository_contracts(
    *,
    legacy_stopped_sources: set[str] | None = None,
) -> dict[str, Any]:
    allowed_legacy_stopped_sources = legacy_stopped_sources or set()
    validate_repository_active_predecessors()
    if not REPLANNED_INDEX.is_file():
        raise RestructureError("missing docs/plan/replanned.md")
    rows = replanned_rows(REPLANNED_INDEX.read_text(encoding="utf-8"))
    immutable_history = historical_contract_snapshot(rows)
    baseline_content = rebind_baseline_content()
    rebind_records = load_rebind_baseline()
    rebind_record_digests = {
        record["record_digest"] for record in rebind_records
    }
    first_rebind_original = {
        record["plan_path"]: record["original_content"]
        for record in reversed(rebind_records)
    }
    companion_records: list[dict[str, Any]] = []
    live_successors: dict[str, dict[str, Any]] = {}
    contract_digests: dict[str, str] = {}
    rows_by_contract: dict[str, list[tuple[str, str, str]]] = {}
    for row in rows:
        rows_by_contract.setdefault(row[2], []).append(row)
    verified_schema_three: set[str] = set()
    direct_active_sources: dict[str, str] = {}
    for plan_id, archive_path, contract_path in rows:
        normalized_path(archive_path, ARCHIVE_PATH_RE, "replanned archive path")
        normalized_path(contract_path, CONTRACT_PATH_RE, "replanned contract path")
        reject_symlink_ancestors(archive_path, include_target=True)
        reject_symlink_ancestors(contract_path, include_target=True)
        archive_file = ROOT / archive_path
        contract_file = ROOT / contract_path
        if not archive_file.is_file() or not contract_file.is_file():
            raise RestructureError(f"missing replanned archive or contract for {plan_id}")
        try:
            contract_bytes = contract_file.read_bytes()
            contract = json.loads(contract_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RestructureError(f"invalid durable contract for {plan_id}: {exc}") from exc
        schema_version = contract.get("schema_version") if isinstance(contract, dict) else None
        if schema_version == 3:
            if contract_path in verified_schema_three:
                continue
            verify_schema_three_contract(
                contract_path,
                contract_bytes,
                contract,
                rows_by_contract[contract_path],
                rebind_record_digests,
                live_successors,
                contract_digests,
                direct_active_sources,
            )
            verified_schema_three.add(contract_path)
            continue
        if schema_version not in {1, 2}:
            raise RestructureError(f"contract identity mismatch for {plan_id}")
        if len(rows_by_contract[contract_path]) != 1:
            raise RestructureError(
                f"single-source contract has multiple replanned index rows: {contract_path}"
            )
        exact_object(
            contract,
            {"schema_version", "created_at", "contract_path", "source", "reason_codes", "dirty_product_paths", "archive_path", "successors"},
            f"contract {plan_id}",
        )
        if contract["contract_path"] != contract_path:
            raise RestructureError(f"contract identity mismatch for {plan_id}")
        if contract["archive_path"] != archive_path:
            raise RestructureError(f"contract archive mismatch for {plan_id}")
        try:
            datetime.fromisoformat(contract["created_at"])
        except (TypeError, ValueError) as exc:
            raise RestructureError(f"contract timestamp is invalid for {plan_id}") from exc
        source = exact_object(
            contract["source"], {"path", "head", "plan_digest", "acceptance", "content"}, f"contract source {plan_id}"
        )
        source_path = normalized_path(source["path"], PLAN_PATH_RE, "contract source path")
        source_match = PLAN_PATH_RE.fullmatch(source_path)
        assert source_match
        if source_match.group(1) != plan_id:
            raise RestructureError(f"replanned index and source id mismatch for {plan_id}")
        if Path(archive_path).name != Path(source_path).name:
            raise RestructureError(f"replanned archive basename mismatch for {plan_id}")
        if not isinstance(source["content"], str) or sha256(source["content"].encode()) != source["plan_digest"]:
            raise RestructureError(f"contract source content digest mismatch for {plan_id}")
        if acceptance_records(source["content"]) != source["acceptance"]:
            raise RestructureError(f"contract source acceptance mismatch for {plan_id}")
        source_manifest = parse_manifest(source["content"])
        if scalar(source_manifest, "status") != "replan_required":
            raise RestructureError(f"contract source status mismatch for {plan_id}")
        validate_canonical_stopped_manifest(
            source_manifest,
            f"contract source {plan_id}",
            expected_reason_codes=contract["reason_codes"],
        )
        contract_digest = sha256(contract_bytes)
        contract_digests[contract_path] = contract_digest
        source_records = source["acceptance"]
        source_digests = [record["digest"] for record in source_records]
        source_text_by_digest = {record["digest"]: record["text"] for record in source_records}
        successors = contract["successors"]
        if not isinstance(successors, list) or not successors:
            raise RestructureError(f"contract has no successors for {plan_id}")
        paths: list[str] = []
        mapped: set[str] = set()
        integration_count = 0
        contract_preservation: list[str] = []
        contract_write_scopes: list[list[str]] = []
        preservation_declared = False
        preservation_mode: bool | None = None
        live_companion_successors: list[dict[str, Any]] = []
        for index, raw_successor in enumerate(successors):
            successor_keys = {
                "id",
                "path",
                "content_digest",
                "content",
                "acceptance_digests",
                "integration",
            }
            if schema_version == 2:
                successor_keys.update(
                    {
                        "authoritative_validation",
                        "authoritative_validation_digest",
                        "validation_witness_schema",
                        "validation_witness_map_digest",
                    }
                )
            successor = exact_object(
                raw_successor,
                successor_keys,
                f"contract successor {plan_id}/{index}",
            )
            path = normalized_path(successor["path"], PLAN_PATH_RE, "contract successor path")
            match = PLAN_PATH_RE.fullmatch(path)
            assert match
            if successor["id"] != match.group(1):
                raise RestructureError(f"contract successor id mismatch for {plan_id}")
            if not isinstance(successor["content"], str) or sha256(successor["content"].encode()) != successor["content_digest"]:
                raise RestructureError(f"contract successor content digest mismatch for {plan_id}")
            successor_manifest = parse_manifest(successor["content"])
            projection = (
                {
                    "authoritative_validation": successor["authoritative_validation"],
                    "authoritative_validation_digest": successor[
                        "authoritative_validation_digest"
                    ],
                    "validation_witness_schema": successor[
                        "validation_witness_schema"
                    ],
                    "validation_witness_map_digest": successor[
                        "validation_witness_map_digest"
                    ],
                }
                if schema_version == 2
                else None
            )
            if schema_version == 2:
                validate_projection(
                    projection,
                    successor_manifest,
                    f"contract successor {plan_id}/{index}",
                )
            has_preservation = "preservation_scope" in successor_manifest
            preservation_declared = preservation_declared or has_preservation
            if schema_version == 2:
                if preservation_mode is None:
                    preservation_mode = has_preservation
                elif preservation_mode != has_preservation:
                    raise RestructureError(
                        f"contract successors mix preservation schemas for {plan_id}"
                    )
            expected_preservation = (
                preservation_scope(
                    successor_manifest,
                    f"contract successor {plan_id}/{index}",
                    required=True,
                )
                if has_preservation
                else None
            )
            if expected_preservation is not None:
                contract_preservation.extend(expected_preservation)
                contract_write_scopes.append(items(successor_manifest, "write_scope"))
            digests = successor["acceptance_digests"]
            if not isinstance(digests, list) or not digests or len(digests) != len(set(digests)):
                raise RestructureError(f"contract successor mapping is invalid for {plan_id}")
            if any(digest not in source_text_by_digest for digest in digests):
                raise RestructureError(f"contract successor mapping is unknown for {plan_id}")
            if digests != [digest for digest in source_digests if digest in set(digests)]:
                raise RestructureError(f"contract successor mapping order mismatch for {plan_id}")
            if items(successor_manifest, "inherited_acceptance_digests") != digests:
                raise RestructureError(f"contract successor lineage mismatch for {plan_id}")
            expected_successor_acceptance = [source_text_by_digest[digest] for digest in digests]
            if items(successor_manifest, "acceptance") != expected_successor_acceptance:
                raise RestructureError(f"contract successor acceptance mismatch for {plan_id}")
            reject_symlink_ancestors(path, include_target=True)
            active_file = ROOT / path
            active_records = active_records_for_successor(successor["id"], path)
            checked_paths = checked_paths_for_successor(successor["id"], path)
            backlog_paths = backlog_paths_for_successor(successor["id"], path)
            replanned_records = replanned_records_for_id(successor["id"], path)
            if sum((bool(active_records), bool(checked_paths), bool(backlog_paths), bool(replanned_records))) > 1:
                raise RestructureError(f"successor has ambiguous durable records: {path}")
            if len(checked_paths) > 1:
                raise RestructureError(f"successor has multiple checked index entries: {path}")
            if active_file.is_file() and not active_records:
                raise RestructureError(f"successor has an unindexed active file: {path}")
            if active_records:
                if not active_file.is_file():
                    raise RestructureError(f"missing active successor plan: {path}")
                expected_live_status = active_records[0][2]
                if expected_live_status not in ACTIVE_PLAN_STATUSES:
                    raise RestructureError(f"invalid active successor status: {path}")
                live_successor_file = active_file
                lifecycle = "active"
                replan_original_content = None
            elif checked_paths:
                reject_symlink_ancestors(checked_paths[0], include_target=True)
                live_successor_file = ROOT / checked_paths[0]
                if not live_successor_file.is_file():
                    raise RestructureError(f"missing checked successor plan for {plan_id}: {checked_paths[0]}")
                expected_live_status = "checked"
                lifecycle = "checked"
                replan_original_content = None
            elif backlog_paths:
                reject_symlink_ancestors(backlog_paths[0], include_target=True)
                live_successor_file = ROOT / backlog_paths[0]
                if not live_successor_file.is_file():
                    raise RestructureError(f"missing backlog successor plan for {plan_id}: {backlog_paths[0]}")
                expected_live_status = "backlog"
                lifecycle = "backlog"
                replan_original_content = None
            elif replanned_records:
                replanned_state = validate_replanned_successor(
                    successor["id"],
                    path,
                    digests,
                    expected_successor_acceptance,
                    None,
                    None,
                )
                live_content = replanned_state["stopped_content"]
                replan_original_content = replanned_state["original_content"]
                live_successor_file = None
                expected_live_status = "replan_required"
                lifecycle = "replanned"
            else:
                raise RestructureError(f"missing live successor plan for {plan_id}: {path}")
            if live_successor_file is not None:
                live_content = live_successor_file.read_text(encoding="utf-8")
            live_successor_manifest = parse_manifest(live_content)
            if scalar(live_successor_manifest, "status") != expected_live_status:
                raise RestructureError(f"live successor status mismatch for {plan_id}: {path}")
            if items(live_successor_manifest, "inherited_acceptance_digests") != digests:
                raise RestructureError(f"live successor lineage mismatch for {plan_id}: {path}")
            if items(live_successor_manifest, "acceptance") != expected_successor_acceptance:
                raise RestructureError(f"live successor acceptance mismatch for {plan_id}: {path}")
            state_projection = projection
            if schema_version == 1:
                projection_content = first_rebind_original.get(path, live_content)
                projection_manifest = parse_manifest(projection_content)
                state_projection = validation_projection(
                    projection_manifest,
                    f"live successor {plan_id}/{index}",
                    require_witness=(
                        scalar(
                            projection_manifest,
                            "validation_witness_schema",
                        )
                        == "1"
                    ),
                    enforce_witness_semantics=False,
                )
                if (
                    lifecycle != "replanned"
                    and scalar(
                        projection_manifest,
                        "validation_witness_schema",
                    )
                    == "1"
                ):
                    live_companion_successors.append(
                        {
                            "path": path,
                            "acceptance_digests": digests,
                            **state_projection,
                        }
                    )
            if path in live_successors:
                raise RestructureError(
                    f"live successor is owned by multiple contracts: {path}"
                )
            live_successors[path] = {
                "contract_path": contract_path,
                "contract_digest": contract_digest,
                "base_manifest": successor_manifest,
                "base_content": successor["content"],
                "base_projection": state_projection,
                "expected_preservation": expected_preservation,
                "live_manifest": live_successor_manifest,
                "live_content": live_content,
                "lifecycle": lifecycle,
                "replan_original_content": replan_original_content,
                "enforce_projection_semantics": schema_version == 2,
                "role": "successor",
            }
            mapped.update(digests)
            paths.append(path)
            if successor["integration"] is True:
                integration_count += 1
                if digests != source_digests or items(successor_manifest, "acceptance") != [record["text"] for record in source_records]:
                    raise RestructureError(f"contract integration baseline mismatch for {plan_id}")
            elif successor["integration"] is not False:
                raise RestructureError(f"contract integration flag is invalid for {plan_id}")
        if len(paths) != len(set(paths)) or mapped != set(source_digests) or integration_count != 1:
            raise RestructureError(f"contract mapping is incomplete or ambiguous for {plan_id}")
        if preservation_declared:
            dirty_paths = contract["dirty_product_paths"]
            if (
                not isinstance(dirty_paths, list)
                or sorted(set(contract_preservation)) != dirty_paths
                or (
                    schema_version == 2
                    and len(contract_preservation) != len(set(contract_preservation))
                )
            ):
                raise RestructureError(
                    f"contract preservation_scope does not match dirty paths for {plan_id}"
                )
            reject_preservation_write_overlap(
                contract_preservation,
                contract_write_scopes,
                f"contract {plan_id}",
            )
        archive_text = archive_file.read_text(encoding="utf-8")
        archive_manifest = parse_manifest(archive_text)
        if scalar(archive_manifest, "status") != "replanned":
            raise RestructureError(f"archive status mismatch for {plan_id}")
        if scalar(archive_manifest, "replan_source") != source["path"]:
            raise RestructureError(f"archive source lineage mismatch for {plan_id}")
        if scalar(archive_manifest, "replan_contract") != contract_path:
            raise RestructureError(f"archive contract lineage mismatch for {plan_id}")
        if items(archive_manifest, "successor_plans") != paths:
            raise RestructureError(f"archive successor lineage mismatch for {plan_id}")
        if items(archive_manifest, "inherited_acceptance_digests") != source_digests:
            raise RestructureError(f"archive acceptance lineage mismatch for {plan_id}")
        if items(archive_manifest, "acceptance") != [record["text"] for record in source_records]:
            raise RestructureError(f"archive acceptance text mismatch for {plan_id}")
        if schema_version == 1 and live_companion_successors:
            companion_records.append(
                {
                    "contract_path": contract_path,
                    "contract_digest": contract_digest,
                    "successors": live_companion_successors,
                }
            )
    verify_companion_baseline(companion_records)
    claimed_direct_sources = sorted(
        set(direct_active_sources) & set(live_successors)
    )
    if claimed_direct_sources:
        raise RestructureError(
            "direct active source is also a contract successor: "
            f"{claimed_direct_sources[0]}"
        )
    effective_projections = verify_rebind_records(
        rebind_records,
        live_successors,
        contract_digests,
        allowed_legacy_stopped_sources,
    )
    return {
        "rebind_records": rebind_records,
        "live_successors": live_successors,
        "contract_digests": contract_digests,
        "effective_projections": effective_projections,
        "rebind_baseline_content": baseline_content,
        "historical_contract_snapshot": immutable_history,
    }


def companion_publication_recorded() -> bool:
    return bool(
        run_git("log", "--all", "--format=%H", "--", COMPANION_PATH).strip()
    )


def companion_absence_allowed() -> bool:
    if companion_publication_recorded() or not ACTIVE_INDEX.is_file():
        return False
    publisher_records = [
        row for row in active_rows(ACTIVE_INDEX.read_text(encoding="utf-8"))
        if row[0] == "190" or row[1] == COMPANION_PLAN_PATH
    ]
    if len(publisher_records) != 1:
        return False
    plan_id, path, status = publisher_records[0]
    if (
        (plan_id, path) != ("190", COMPANION_PLAN_PATH)
        or status not in {"deferred", "in_progress"}
    ):
        return False
    publisher = ROOT / path
    if not publisher.is_file():
        return False
    publisher_manifest = parse_manifest(publisher.read_text(encoding="utf-8"))
    if (
        scalar(publisher_manifest, "status") != status
        or COMPANION_PATH not in items(publisher_manifest, "write_scope")
    ):
        return False
    for row_id, row_path, _ in active_rows(ACTIVE_INDEX.read_text(encoding="utf-8")):
        target = ROOT / row_path
        if not target.is_file():
            return False
        manifest = parse_manifest(target.read_text(encoding="utf-8"))
        if row_id != "190" and COMPANION_PATH in items(manifest, "write_scope"):
            return False
        if COMPANION_PATH in items(manifest, "context_files"):
            return False
    return True


def verify_companion_baseline(records: list[dict[str, Any]]) -> None:
    path = ROOT / COMPANION_PATH
    if not path.exists():
        if not records or companion_absence_allowed():
            return
        raise RestructureError("missing live validation successor companion baseline")
    reject_symlink_ancestors(COMPANION_PATH, include_target=True)
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestructureError("invalid live validation successor companion baseline") from exc
    exact_object(baseline, {"schema_version", "records"}, "companion baseline")
    if baseline["schema_version"] != 1 or baseline["records"] != records:
        raise RestructureError("live validation successor companion baseline mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("specification", type=Path, nargs="?")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--recover", type=Path)
    parser.add_argument("--journal-id")
    args = parser.parse_args()
    try:
        selected = sum(
            (
                bool(args.verify),
                args.recover is not None,
                args.specification is not None,
            )
        )
        if selected != 1:
            raise RestructureError(
                "select exactly one specification, --verify, or --recover"
            )
        if args.recover is not None:
            if not args.journal_id or not SHA_RE.fullmatch(args.journal_id):
                raise RestructureError("--recover requires one exact --journal-id")
            print(recover_transaction(args.recover, args.journal_id))
        elif args.verify:
            if args.specification is not None:
                raise RestructureError("--verify does not accept a specification")
            if args.journal_id:
                raise RestructureError("--verify does not accept --journal-id")
            verify_repository_contracts()
            print("replanned contracts verified")
        else:
            if args.specification is None:
                raise RestructureError("missing restructure specification")
            if args.journal_id:
                raise RestructureError("a specification does not accept --journal-id")
            print(execute(args.specification))
    except (OSError, UnicodeError, RestructureError) as exc:
        print(f"plan restructuring failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
