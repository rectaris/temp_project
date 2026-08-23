#!/usr/bin/env python3
"""Capture and verify pre-schema validation-witness migration provenance.

Copying repository and Git-local files without the original live guardian fails; an unrestricted same-user actor that can replace every local process and file is outside this guarantee.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
MIGRATION_VERSION = "v1.4.5"
OPERATION = "validation_witness_migration_snapshot"
PROTOCOL_VERSION = 1
COMMITMENT_DOMAIN = b"project-agent-workflow/validation-witness-guardian/commitment-v1"
RESPONSE_DOMAIN = b"project-agent-workflow/validation-witness-guardian/response-v1"
ACK_DOMAIN = b"project-agent-workflow/validation-witness-guardian/consume-ack-v1"
FINAL_DOMAIN = b"project-agent-workflow/validation-witness-guardian/final-v1"
RECORD_PATH = PurePosixPath(
    ".project-agent-workflow-migration/validation-witness-provenance-v1.json"
)
ANSWERS_PATH = ".copier-answers.yml"
POLICY_PATH = ".project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
POLICY_MARKER = b"validation-witness-migration-provenance-schema: 1"
PLAN_PREFIX = "docs/plan/active/"
MAX_PLAN_BYTES = 256 * 1024
MAX_CONTRACT_BYTES = 1024 * 1024
MAX_POLICY_BYTES = 256 * 1024
MAX_ANSWERS_BYTES = 64 * 1024
MAX_RECORD_BYTES = 512 * 1024
MAX_CAPTURED_PLANS = 64
MAX_PLAN_LISTING_BYTES = 512 * 1024
MAX_ATTEMPT_STATE_BYTES = 16 * 1024
MAX_PROTOCOL_MESSAGE_BYTES = 16 * 1024
CAPABILITY_BYTES = 32
CHALLENGE_BYTES = 32
DEFAULT_GUARDIAN_LIFETIME_SECONDS = 60 * 60
THREAT_BOUNDARY = (
    "Copying repository and Git-local files without the original live guardian fails; "
    "an unrestricted same-user actor that can replace every local process and file is "
    "outside this guarantee."
)
ATTEMPT_STATE_PATH = PurePosixPath(
    "project-agent-workflow/validation-witness-provenance-v1.attempt.json"
)
PREPARING_STATE_PATH = ATTEMPT_STATE_PATH.with_name(
    f".{ATTEMPT_STATE_PATH.name}.preparing"
)
RECOVERY_TOMBSTONE_PATH = ATTEMPT_STATE_PATH.with_name(
    f".{ATTEMPT_STATE_PATH.name}.recovering"
)
GUARDIAN_LOCK_PATH = ATTEMPT_STATE_PATH.with_name(
    "validation-witness-provenance-v1.guardian.lock"
)
SOCKET_DIRECTORY = PurePosixPath(
    "project-agent-workflow/validation-witness-provenance-v1.guardian"
)
ATTEMPT_STATES = {"prepared", "pending", "consumed", "recovering"}
TEST_FAILPOINTS = {
    "after_prepared",
    "after_listen",
    "after_snapshot",
    "after_pending",
    "after_consumed",
    "drop_final_response",
    "delay_after_final_revalidation",
    "recover_after_state",
    "recover_after_snapshot",
    "recover_after_lock",
}


class ProvenanceError(RuntimeError):
    """The migration provenance could not be established safely."""


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def git_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment["LC_ALL"] = "C"
    environment["LANG"] = "C"
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_COUNT"] = "0"
    return environment


def git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=git_environment(),
        )
    except OSError as exc:
        raise ProvenanceError(f"could not execute Git: {exc}") from exc


def require_git(repository: Path, *arguments: str) -> bytes:
    result = git(repository, *arguments)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ProvenanceError(
            f"Git inspection failed for `git {' '.join(arguments)}`: "
            f"{detail or f'exit {result.returncode}'}"
        )
    return result.stdout


def require_git_bounded(
    repository: Path, maximum: int, label: str, *arguments: str
) -> bytes:
    try:
        process = subprocess.Popen(
            ["git", "-C", str(repository), *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=git_environment(),
        )
    except OSError as exc:
        raise ProvenanceError(f"could not execute Git: {exc}") from exc
    assert process.stdout is not None and process.stderr is not None
    raw = process.stdout.read(maximum + 1)
    if len(raw) > maximum:
        process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()
        raise ProvenanceError(f"{label} exceeds its {maximum}-byte bound")
    stderr = process.stderr.read(MAX_PROTOCOL_MESSAGE_BYTES + 1)
    returncode = process.wait()
    process.stdout.close()
    process.stderr.close()
    if returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()
        raise ProvenanceError(
            f"Git inspection failed for bounded {label}: {detail or f'exit {returncode}'}"
        )
    return raw


def require_repository_root(repository: Path) -> None:
    inside = require_git(repository, "rev-parse", "--is-inside-work-tree").strip()
    if inside != b"true":
        raise ProvenanceError("destination is not a Git worktree")
    raw = require_git(repository, "rev-parse", "--show-toplevel")
    reported = Path(raw.decode("utf-8", errors="strict").strip()).resolve()
    if reported != repository:
        raise ProvenanceError(
            f"destination is not the Git repository root: {repository} "
            f"(Git reported {reported})"
        )


def require_clean(repository: Path) -> None:
    status = require_git(
        repository, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    )
    if status:
        raise ProvenanceError(
            "the before-update provenance snapshot requires a clean committed worktree"
        )


def require_recovery_clean(repository: Path) -> None:
    status = require_git(
        repository, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    )
    entries = [entry for entry in status.split(b"\0") if entry]
    allowed = {f"?? {RECORD_PATH.as_posix()}".encode("utf-8")}
    if any(entry not in allowed for entry in entries):
        raise ProvenanceError(
            "stale recovery requires the unchanged clean source plus only its exact snapshot"
        )


def normalize_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 4096:
        raise ProvenanceError(f"{label} must be a bounded non-empty path")
    if "\\" in value or "\0" in value:
        raise ProvenanceError(f"{label} is not a normalized repository-relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix() or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise ProvenanceError(f"{label} is not a normalized repository-relative path")
    return value


def committed_file(
    repository: Path, revision: str, path: str, maximum: int, label: str
) -> bytes:
    normalized = normalize_path(path, label)
    listing = require_git(repository, "ls-tree", "-z", revision, "--", normalized)
    entries = [entry for entry in listing.split(b"\0") if entry]
    if len(entries) != 1:
        raise ProvenanceError(f"{label} is missing from committed HEAD: {normalized}")
    metadata, separator, raw_path = entries[0].partition(b"\t")
    fields = metadata.split()
    if separator != b"\t" or len(fields) != 3 or raw_path != normalized.encode("utf-8"):
        raise ProvenanceError(f"could not establish the committed identity of {label}")
    mode, object_type, object_id = fields
    if object_type != b"blob" or mode not in {b"100644", b"100755"}:
        raise ProvenanceError(f"{label} must be a committed non-symlink regular file")
    try:
        size = int(require_git(repository, "cat-file", "-s", object_id.decode("ascii")))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProvenanceError(f"could not establish the committed size of {label}") from exc
    if size > maximum:
        raise ProvenanceError(f"{label} exceeds its {maximum}-byte bound")
    raw = require_git(repository, "cat-file", "blob", object_id.decode("ascii"))
    if len(raw) != size:
        raise ProvenanceError(f"{label} changed while its committed blob was read")
    return raw


def top_scalar(text: str, key: str, label: str) -> str | None:
    matches = re.findall(rf"^{re.escape(key)}:\s*(.*?)\s*$", text, re.MULTILINE)
    if len(matches) > 1:
        raise ProvenanceError(f"{label} declares {key} more than once")
    return matches[0] if matches else None


def top_list(text: str, key: str, label: str) -> list[str]:
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if line == f"{key}:"]
    if len(starts) != 1:
        raise ProvenanceError(f"{label} must declare exactly one {key} list")
    values: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if line.startswith("  - "):
            value = line[4:]
            if not value:
                raise ProvenanceError(f"{label} contains an empty {key} item")
            values.append(value)
            continue
        if line.startswith(" ") or not line:
            if not line and values:
                break
            if line:
                raise ProvenanceError(f"{label} contains unsupported nested {key} data")
            continue
        break
    if not values:
        raise ProvenanceError(f"{label} contains no {key} items")
    return values


def parse_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProvenanceError(f"{label} is not bounded UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ProvenanceError(f"{label} must contain a JSON object")
    return value


def acceptance_records(values: list[str]) -> list[dict[str, str]]:
    return [{"sha256": digest(value.encode("utf-8")), "text": value} for value in values]


def require_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ProvenanceError(f"{label} must be a string list")
    return list(value)


def capture_plan(repository: Path, revision: str, path: str) -> dict[str, Any] | None:
    raw = committed_file(repository, revision, path, MAX_PLAN_BYTES, "active plan")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProvenanceError(f"active plan is not UTF-8: {path}") from exc
    if top_scalar(text, "status", path) != "in_progress":
        return None
    if top_scalar(text, "validation_witness_schema", path) is not None:
        return None
    contract_path_value = top_scalar(text, "replan_contract", path)
    if contract_path_value is None:
        return None
    contract_path = normalize_path(contract_path_value, f"{path} replan_contract")
    contract_raw = committed_file(
        repository, revision, contract_path, MAX_CONTRACT_BYTES, "replan contract"
    )
    contract = parse_json(contract_raw, f"replan contract {contract_path}")
    if contract.get("schema_version") != 1:
        raise ProvenanceError(
            f"pre-schema plan {path} does not use supported replan contract schema 1"
        )
    if contract.get("contract_path") != contract_path:
        raise ProvenanceError(f"replan contract path identity mismatch for {path}")
    successors = contract.get("successors")
    if not isinstance(successors, list):
        raise ProvenanceError(f"replan contract has no successor list for {path}")
    matches = [
        value
        for value in successors
        if isinstance(value, dict) and value.get("path") == path
    ]
    if len(matches) != 1:
        raise ProvenanceError(
            f"pre-schema plan {path} does not match exactly one contract successor"
        )
    successor = matches[0]
    try:
        contract_content = successor["content"].encode("utf-8")
    except (KeyError, AttributeError, UnicodeEncodeError) as exc:
        raise ProvenanceError(f"contract successor content is invalid for {path}") from exc
    if contract_content != raw or successor.get("content_digest") != digest(raw):
        raise ProvenanceError(f"contract successor bytes do not match committed plan {path}")
    acceptance = acceptance_records(top_list(text, "acceptance", path))
    if require_string_list(
        successor.get("acceptance_digests"), f"{path} successor acceptance_digests"
    ) != [item["sha256"] for item in acceptance]:
        raise ProvenanceError(f"contract acceptance identities do not match plan {path}")
    if successor.get("integration") is not True:
        return None
    archive_path = normalize_path(contract.get("archive_path"), "replanned source archive")
    archive_raw = committed_file(
        repository, revision, archive_path, MAX_PLAN_BYTES, "replanned source archive"
    )
    try:
        archive_text = archive_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProvenanceError("replanned source archive is not UTF-8") from exc
    if top_scalar(archive_text, "status", archive_path) != "replanned":
        raise ProvenanceError(
            f"replanned source archive is not terminal replanned: {archive_path}"
        )
    validation = top_list(text, "validation", path)
    return {
        "acceptance": acceptance,
        "path": path,
        "plan_sha256": digest(raw),
        "replan_contract": {
            "path": contract_path,
            "schema_version": 1,
            "sha256": digest(contract_raw),
        },
        "replanned_source": {
            "path": archive_path,
            "sha256": digest(archive_raw),
        },
        "validation": validation,
        "validation_sha256": digest(canonical_json(validation)),
    }


def previous_template_ref(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProvenanceError("committed Copier answers are not UTF-8") from exc
    matches = re.findall(r"^_commit:\s*([^\s#]+)\s*$", text, re.MULTILINE)
    if len(matches) != 1:
        raise ProvenanceError("committed Copier answers must declare exactly one _commit")
    value = matches[0].strip("\"'")
    if not value or len(value.encode("utf-8")) > 256:
        raise ProvenanceError("committed Copier _commit is empty or exceeds its bound")
    return value


def build_record(repository: Path, source_head: str) -> dict[str, Any]:
    answers = committed_file(
        repository, source_head, ANSWERS_PATH, MAX_ANSWERS_BYTES, "Copier answers"
    )
    policy = committed_file(
        repository, source_head, POLICY_PATH, MAX_POLICY_BYTES, "orchestration policy"
    )
    if POLICY_MARKER in policy:
        raise ProvenanceError(
            "the committed project already contains the validation-witness migration boundary"
        )
    listed = require_git_bounded(
        repository,
        MAX_PLAN_LISTING_BYTES,
        "active-plan inventory",
        "ls-tree",
        "-r",
        "--name-only",
        "-z",
        source_head,
        "--",
        PLAN_PREFIX,
    )
    paths = sorted(
        raw.decode("utf-8", errors="strict")
        for raw in listed.split(b"\0")
        if raw and raw.endswith(b".md")
    )
    captured = [
        record
        for path in paths
        if (record := capture_plan(repository, source_head, path))
    ]
    if len(captured) > MAX_CAPTURED_PLANS:
        raise ProvenanceError(
            f"migration provenance exceeds the {MAX_CAPTURED_PLANS}-plan bound"
        )
    return {
        "copier_answers": {
            "path": ANSWERS_PATH,
            "previous_template_ref": previous_template_ref(answers),
            "sha256": digest(answers),
        },
        "migration_version": MIGRATION_VERSION,
        "operation": OPERATION,
        "plans": captured,
        "pre_update_policy": {"path": POLICY_PATH, "sha256": digest(policy)},
        "schema_version": SCHEMA_VERSION,
        "source_head": source_head,
    }


def current_head(repository: Path) -> str:
    return require_git(repository, "rev-parse", "--verify", "HEAD^{commit}").decode(
        "ascii"
    ).strip()


def git_directory(repository: Path) -> Path:
    raw = require_git(repository, "rev-parse", "--path-format=absolute", "--absolute-git-dir")
    directory = Path(raw.decode("utf-8", errors="strict").strip()).resolve()
    try:
        descriptor = os.open(
            directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
        )
    except OSError as exc:
        raise ProvenanceError(f"Git metadata directory is unavailable: {directory}")
    else:
        os.close(descriptor)
    return directory


def repository_identity(repository: Path, git_dir: Path) -> str:
    repository_status = os.stat(repository, follow_symlinks=False)
    git_status = os.stat(git_dir, follow_symlinks=False)
    if not stat.S_ISDIR(repository_status.st_mode) or not stat.S_ISDIR(git_status.st_mode):
        raise ProvenanceError("repository identity does not name two directories")
    return digest(
        canonical_json(
            {
                "git_dir_device": git_status.st_dev,
                "git_dir_inode": git_status.st_ino,
                "git_dir_path": str(git_dir),
                "repository_device": repository_status.st_dev,
                "repository_inode": repository_status.st_ino,
                "repository_path": str(repository),
            }
        )
    )


def open_relative_parent(
    root: Path, relative: PurePosixPath, *, create: bool, directory_mode: int
) -> int:
    normalized = normalize_path(relative.as_posix(), "local artifact path")
    relative = PurePosixPath(normalized)
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        for part in relative.parts[:-1]:
            created = False
            if create:
                try:
                    os.mkdir(part, mode=directory_mode, dir_fd=descriptor)
                    os.fsync(descriptor)
                    created = True
                except FileExistsError:
                    pass
            next_descriptor = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            opened = os.fstat(next_descriptor)
            if directory_mode == 0o700 and (
                opened.st_uid != os.getuid()
                or stat.S_IMODE(opened.st_mode) != 0o700
            ):
                os.close(next_descriptor)
                raise ProvenanceError(
                    "private Git-metadata directory has unsafe ownership or mode: "
                    f"path-component={part} mode={oct(stat.S_IMODE(opened.st_mode))}"
                )
            if created:
                os.fsync(next_descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def read_relative_regular(
    root: Path,
    relative: PurePosixPath,
    maximum: int,
    label: str,
    *,
    required_mode: int | None = None,
    directory_mode: int = 0o755,
) -> bytes:
    parent = open_relative_parent(
        root, relative, create=False, directory_mode=directory_mode
    )
    file_descriptor = -1
    try:
        file_descriptor = os.open(
            relative.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent,
        )
        before = os.fstat(file_descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ProvenanceError(f"{label} must be a single-link regular file")
        if required_mode is not None and stat.S_IMODE(before.st_mode) != required_mode:
            raise ProvenanceError(f"{label} has unsafe permissions")
        if before.st_size > maximum:
            raise ProvenanceError(f"{label} exceeds its {maximum}-byte bound")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(file_descriptor, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(file_descriptor)
        if len(raw) > maximum:
            raise ProvenanceError(f"{label} exceeds its {maximum}-byte bound")
        if len(raw) != before.st_size:
            raise ProvenanceError(f"{label} changed while it was read")
        if (
            (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
            or before.st_ctime_ns != after.st_ctime_ns
            or before.st_size != after.st_size
            or after.st_nlink != 1
        ):
            raise ProvenanceError(f"{label} changed while it was read")
        return raw
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        os.close(parent)


def final_entry_exists(
    root: Path, relative: PurePosixPath, *, directory_mode: int
) -> bool:
    parent = open_relative_parent(
        root, relative, create=False, directory_mode=directory_mode
    )
    try:
        try:
            os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True
    finally:
        os.close(parent)


def write_exclusive(
    root: Path,
    relative: PurePosixPath,
    raw: bytes,
    maximum: int,
    label: str,
    *,
    mode: int,
    directory_mode: int,
) -> None:
    if len(raw) > maximum:
        raise ProvenanceError(f"{label} exceeds its {maximum}-byte bound")
    parent = open_relative_parent(
        root, relative, create=True, directory_mode=directory_mode
    )
    descriptor = -1
    try:
        descriptor = os.open(
            relative.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            mode,
            dir_fd=parent,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)
    except FileExistsError as exc:
        raise ProvenanceError(f"{label} already exists and cannot be replayed") from exc
    except OSError as exc:
        if descriptor >= 0:
            os.close(descriptor)
        raise ProvenanceError(f"could not write {label}: {exc}") from exc
    finally:
        os.close(parent)


def replace_exact(
    root: Path,
    relative: PurePosixPath,
    expected: bytes,
    replacement: bytes,
    maximum: int,
    label: str,
    *,
    mode: int,
    directory_mode: int,
    temporary_name: str,
) -> None:
    if len(replacement) > maximum:
        raise ProvenanceError(f"{label} exceeds its {maximum}-byte bound")
    parent = open_relative_parent(
        root, relative, create=False, directory_mode=directory_mode
    )
    descriptor = -1
    try:
        actual = read_relative_regular(
            root,
            relative,
            maximum,
            label,
            required_mode=mode,
            directory_mode=directory_mode,
        )
        if actual != expected:
            raise ProvenanceError(f"{label} changed before its durable transition")
        descriptor = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            mode,
            dir_fd=parent,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(
            temporary_name,
            relative.name,
            src_dir_fd=parent,
            dst_dir_fd=parent,
        )
        os.fsync(parent)
    except OSError as exc:
        if descriptor >= 0:
            os.close(descriptor)
        raise ProvenanceError(f"could not transition {label}: {exc}") from exc
    finally:
        os.close(parent)


def read_record(repository: Path) -> bytes:
    try:
        return read_relative_regular(
            repository, RECORD_PATH, MAX_RECORD_BYTES, "migration provenance"
        )
    except OSError as exc:
        raise ProvenanceError(f"migration provenance is missing or unsafe: {RECORD_PATH}") from exc


def current_policy_has_marker(repository: Path) -> bool:
    try:
        raw = read_relative_regular(
            repository, PurePosixPath(POLICY_PATH), MAX_POLICY_BYTES, "updated policy"
        )
    except OSError as exc:
        raise ProvenanceError(f"could not inspect updated orchestration policy: {exc}") from exc
    return POLICY_MARKER in raw


def attempt_state_raw(git_dir: Path) -> bytes:
    try:
        return read_relative_regular(
            git_dir,
            ATTEMPT_STATE_PATH,
            MAX_ATTEMPT_STATE_BYTES,
            "validation-witness migration attempt state",
            required_mode=0o600,
            directory_mode=0o700,
        )
    except OSError as exc:
        raise ProvenanceError("validation-witness migration attempt state is missing") from exc


def state_temporary_name(attempt_id: str) -> str:
    if re.fullmatch(r"[0-9a-f]{64}", attempt_id) is None:
        raise ProvenanceError("migration attempt identifier is malformed")
    return f".{ATTEMPT_STATE_PATH.name}.{attempt_id}.tmp"


def parse_attempt_state(raw: bytes) -> dict[str, Any]:
    value = parse_json(raw, "validation-witness migration attempt state")
    expected_keys = {
        "attempt_id",
        "capability_commitment",
        "expires_at_unix_ns",
        "guardian_pid",
        "migration_version",
        "operation",
        "protocol_version",
        "record_path",
        "repository_identity",
        "schema_version",
        "snapshot_sha256",
        "socket_path",
        "source_head",
        "state",
    }
    if set(value) != expected_keys or canonical_json(value) != raw:
        raise ProvenanceError("migration attempt state has a non-canonical schema")
    if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
        raise ProvenanceError("migration attempt state schema is unsupported")
    if (
        type(value["protocol_version"]) is not int
        or value["protocol_version"] != PROTOCOL_VERSION
    ):
        raise ProvenanceError("migration attempt protocol is unsupported")
    if (
        not isinstance(value["migration_version"], str)
        or not isinstance(value["operation"], str)
        or value["migration_version"] != MIGRATION_VERSION
        or value["operation"] != OPERATION
    ):
        raise ProvenanceError("migration attempt identity is invalid")
    if not isinstance(value["state"], str) or value["state"] not in ATTEMPT_STATES:
        raise ProvenanceError("migration attempt state is invalid")
    if not isinstance(value["attempt_id"], str) or re.fullmatch(
        r"[0-9a-f]{64}", value["attempt_id"]
    ) is None:
        raise ProvenanceError("migration attempt identifier is malformed")
    if not isinstance(value["source_head"], str) or re.fullmatch(
        r"[0-9a-f]{40,64}", value["source_head"]
    ) is None:
        raise ProvenanceError("migration attempt source HEAD is malformed")
    for key in ("snapshot_sha256", "capability_commitment"):
        if not isinstance(value[key], str) or re.fullmatch(
            r"sha256:[0-9a-f]{64}", value[key]
        ) is None:
            raise ProvenanceError(f"migration attempt {key} is malformed")
    if not isinstance(value["repository_identity"], str) or re.fullmatch(
        r"sha256:[0-9a-f]{64}", value["repository_identity"]
    ) is None:
        raise ProvenanceError("migration attempt repository identity is malformed")
    record_path = normalize_path(value["record_path"], "migration snapshot path")
    if record_path != RECORD_PATH.as_posix():
        raise ProvenanceError("migration snapshot path identity is invalid")
    socket_path = normalize_path(value["socket_path"], "guardian socket path")
    expected_socket = (
        SOCKET_DIRECTORY / f"{value['attempt_id']}.sock"
    ).as_posix()
    if socket_path != expected_socket:
        raise ProvenanceError("guardian socket path identity is invalid")
    if (
        not isinstance(value["guardian_pid"], int)
        or isinstance(value["guardian_pid"], bool)
        or value["guardian_pid"] <= 0
    ):
        raise ProvenanceError("guardian PID field is malformed")
    if (
        not isinstance(value["expires_at_unix_ns"], int)
        or isinstance(value["expires_at_unix_ns"], bool)
        or value["expires_at_unix_ns"] <= 0
    ):
        raise ProvenanceError("guardian expiry is malformed")
    return value


def commitment_payload(
    attempt_id: str,
    source_head: str,
    snapshot_sha256: str,
    repository_identity_sha256: str,
    capability: bytes,
) -> bytes:
    if len(capability) != CAPABILITY_BYTES:
        raise ProvenanceError("guardian capability has the wrong length")
    return b"\0".join(
        (
            COMMITMENT_DOMAIN,
            str(PROTOCOL_VERSION).encode("ascii"),
            attempt_id.encode("ascii"),
            source_head.encode("ascii"),
            snapshot_sha256.encode("ascii"),
            repository_identity_sha256.encode("ascii"),
            capability,
        )
    )


def capability_commitment(
    attempt_id: str,
    source_head: str,
    snapshot_sha256: str,
    repository_identity_sha256: str,
    capability: bytes,
) -> str:
    return digest(
        commitment_payload(
            attempt_id,
            source_head,
            snapshot_sha256,
            repository_identity_sha256,
            capability,
        )
    )


def protocol_mac(capability: bytes, domain: bytes, *values: str) -> str:
    payload = b"\0".join((domain, *(value.encode("ascii") for value in values)))
    return hmac.new(capability, payload, hashlib.sha256).hexdigest()


def state_for_status(base: dict[str, Any], status: str) -> bytes:
    if status not in ATTEMPT_STATES:
        raise ProvenanceError("migration attempt transition target is invalid")
    return canonical_json({**base, "state": status})


def state_base(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "state"}


def publish_prepared_state(git_dir: Path, raw: bytes) -> None:
    parse_attempt_state(raw)
    write_exclusive(
        git_dir,
        PREPARING_STATE_PATH,
        raw,
        MAX_ATTEMPT_STATE_BYTES,
        "validation-witness migration attempt state",
        mode=0o600,
        directory_mode=0o700,
    )
    parent = open_relative_parent(
        git_dir, ATTEMPT_STATE_PATH, create=False, directory_mode=0o700
    )
    try:
        try:
            os.stat(ATTEMPT_STATE_PATH.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ProvenanceError("validation-witness migration attempt already exists")
        os.rename(
            PREPARING_STATE_PATH.name,
            ATTEMPT_STATE_PATH.name,
            src_dir_fd=parent,
            dst_dir_fd=parent,
        )
        os.fsync(parent)
    finally:
        os.close(parent)


def acquire_guardian_lock(git_dir: Path, *, create: bool = True) -> int:
    parent = open_relative_parent(
        git_dir, GUARDIAN_LOCK_PATH, create=create, directory_mode=0o700
    )
    descriptor = -1
    try:
        created = False
        if create:
            try:
                descriptor = os.open(
                    GUARDIAN_LOCK_PATH.name,
                    os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent,
                )
                created = True
            except FileExistsError:
                pass
        if descriptor < 0:
            descriptor = os.open(
                GUARDIAN_LOCK_PATH.name,
                os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent,
            )
        status = os.fstat(descriptor)
        if (
            not stat.S_ISREG(status.st_mode)
            or status.st_nlink != 1
            or status.st_uid != os.getuid()
            or stat.S_IMODE(status.st_mode) != 0o600
        ):
            raise ProvenanceError("guardian liveness lock is unsafe")
        if created:
            os.fsync(descriptor)
            os.fsync(parent)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ProvenanceError("original validation-witness guardian is still live") from exc
        return descriptor
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        raise
    finally:
        os.close(parent)


def transition_state(git_dir: Path, expected: bytes, replacement: bytes) -> None:
    expected_value = parse_attempt_state(expected)
    replacement_value = parse_attempt_state(replacement)
    if state_base(expected_value) != state_base(replacement_value):
        raise ProvenanceError("migration attempt transition changed its bound identity")
    allowed = {
        ("prepared", "pending"),
        ("pending", "consumed"),
        ("prepared", "recovering"),
        ("pending", "recovering"),
    }
    if (expected_value["state"], replacement_value["state"]) not in allowed:
        raise ProvenanceError("migration attempt transition is not allowed")
    replace_exact(
        git_dir,
        ATTEMPT_STATE_PATH,
        expected,
        replacement,
        MAX_ATTEMPT_STATE_BYTES,
        "validation-witness migration attempt state",
        mode=0o600,
        directory_mode=0o700,
        temporary_name=state_temporary_name(expected_value["attempt_id"]),
    )


def compact_json(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("ascii")


def send_message(channel: socket.socket, value: dict[str, Any]) -> None:
    raw = compact_json(value)
    if len(raw) > MAX_PROTOCOL_MESSAGE_BYTES:
        raise ProvenanceError("guardian protocol message exceeds its byte bound")
    channel.sendall(raw)


def receive_message(channel: socket.socket, label: str) -> dict[str, Any]:
    raw = b""
    while b"\n" not in raw and len(raw) <= MAX_PROTOCOL_MESSAGE_BYTES:
        chunk = channel.recv(min(4096, MAX_PROTOCOL_MESSAGE_BYTES + 1 - len(raw)))
        if not chunk:
            break
        raw += chunk
    if len(raw) > MAX_PROTOCOL_MESSAGE_BYTES:
        raise ProvenanceError(f"{label} exceeds its byte bound")
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise ProvenanceError(f"{label} is incomplete or has trailing data")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProvenanceError(f"{label} is not JSON") from exc
    if not isinstance(value, dict) or compact_json(value) != raw:
        raise ProvenanceError(f"{label} is not canonical")
    return value


def require_keys(value: dict[str, Any], keys: set[str], label: str) -> None:
    if set(value) != keys:
        raise ProvenanceError(f"{label} has an invalid schema")


def require_peer_uid(channel: socket.socket) -> None:
    if not hasattr(socket, "SO_PEERCRED"):
        raise ProvenanceError("guardian peer credentials are unavailable")
    raw = channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    _pid, uid, _gid = struct.unpack("3i", raw)
    if uid != os.getuid():
        raise ProvenanceError("guardian peer credentials do not match the repository owner")


def socket_lstat(git_dir: Path, relative: PurePosixPath) -> tuple[int, os.stat_result]:
    parent = open_relative_parent(git_dir, relative, create=False, directory_mode=0o700)
    try:
        return parent, os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
    except Exception:
        os.close(parent)
        raise


def bind_guardian_socket(git_dir: Path, relative: PurePosixPath) -> tuple[socket.socket, tuple[int, int, int]]:
    parent = open_relative_parent(git_dir, relative, create=True, directory_mode=0o700)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    saved_cwd = os.open(".", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        try:
            os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ProvenanceError("guardian socket path already exists")
        os.fchdir(parent)
        listener.bind(relative.name)
        os.chmod(relative.name, 0o600, dir_fd=parent)
        current = os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISSOCK(current.st_mode):
            raise ProvenanceError("guardian listener did not create a socket")
        listener.listen(4)
        return listener, (current.st_dev, current.st_ino, current.st_ctime_ns)
    except Exception:
        listener.close()
        raise
    finally:
        os.fchdir(saved_cwd)
        os.close(saved_cwd)
        os.close(parent)


def connect_guardian_socket(git_dir: Path, relative: PurePosixPath) -> socket.socket:
    parent, before = socket_lstat(git_dir, relative)
    channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    saved_cwd = os.open(".", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        if not stat.S_ISSOCK(before.st_mode):
            raise ProvenanceError("guardian socket path is not a socket")
        os.fchdir(parent)
        channel.connect(relative.name)
        channel.settimeout(5)
        after = os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
        if (
            not stat.S_ISSOCK(after.st_mode)
            or (before.st_dev, before.st_ino, before.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_ctime_ns)
        ):
            raise ProvenanceError("guardian socket path changed while connecting")
        require_peer_uid(channel)
        return channel
    except Exception:
        channel.close()
        raise
    finally:
        os.fchdir(saved_cwd)
        os.close(saved_cwd)
        os.close(parent)


def unlink_bound_socket(
    git_dir: Path, relative: PurePosixPath, identity: tuple[int, int, int]
) -> None:
    try:
        parent, current = socket_lstat(git_dir, relative)
    except FileNotFoundError:
        return
    try:
        if (
            stat.S_ISSOCK(current.st_mode)
            and (current.st_dev, current.st_ino, current.st_ctime_ns) == identity
        ):
            os.unlink(relative.name, dir_fd=parent)
            os.fsync(parent)
    finally:
        os.close(parent)


def validate_snapshot(repository: Path, state: dict[str, Any], raw: bytes) -> None:
    git_dir = git_directory(repository)
    if state["repository_identity"] != repository_identity(repository, git_dir):
        raise ProvenanceError("migration attempt belongs to another repository clone")
    if digest(raw) != state["snapshot_sha256"]:
        raise ProvenanceError("migration snapshot digest differs from its attempt state")
    if state["source_head"] != current_head(repository):
        raise ProvenanceError("migration provenance source HEAD is stale")
    expected = canonical_json(build_record(repository, state["source_head"]))
    if raw != expected:
        raise ProvenanceError(
            "migration provenance does not exactly match the committed pre-update baseline"
        )


def guardian_revalidate(
    repository: Path,
    git_dir: Path,
    expected_base: dict[str, Any],
    request_state_digest: str,
    consumed_state_digest: str | None,
    deadline_monotonic: float,
) -> tuple[bytes, dict[str, Any]]:
    if time.monotonic() >= deadline_monotonic:
        raise ProvenanceError("validation-witness guardian lifetime expired")
    raw = attempt_state_raw(git_dir)
    value = parse_attempt_state(raw)
    if state_base(value) != expected_base or digest(raw) != request_state_digest:
        raise ProvenanceError("guardian request does not match the durable attempt state")
    if value["state"] not in {"pending", "consumed"}:
        raise ProvenanceError("guardian request requires a pending or consumed attempt")
    if value["state"] == "consumed" and digest(raw) != consumed_state_digest:
        raise ProvenanceError("consumed attempt is not owned by this live guardian")
    if not current_policy_has_marker(repository):
        raise ProvenanceError("updated orchestration policy lacks the migration schema marker")
    snapshot = read_record(repository)
    validate_snapshot(repository, value, snapshot)
    return raw, value


def require_guardian_deadline(deadline_monotonic: float) -> None:
    if time.monotonic() >= deadline_monotonic:
        raise ProvenanceError("validation-witness guardian lifetime expired")


class GuardianStop(Exception):
    pass


def failpoint(name: str | None, expected: str) -> None:
    if name == expected:
        os._exit(91)


def guardian_connection(
    channel: socket.socket,
    repository: Path,
    git_dir: Path,
    capability: bytes,
    expected_base: dict[str, Any],
    consumed_state_digest: str | None,
    configured_failpoint: str | None,
    deadline_monotonic: float,
) -> tuple[str | None, bool]:
    require_peer_uid(channel)
    request = receive_message(channel, "guardian request")
    require_keys(
        request,
        {"attempt_id", "challenge", "protocol_version", "state_sha256", "type"},
        "guardian request",
    )
    if (
        request["type"] != "challenge"
        or type(request["protocol_version"]) is not int
        or request["protocol_version"] != PROTOCOL_VERSION
    ):
        raise ProvenanceError("guardian request identity is invalid")
    if (
        not isinstance(request["attempt_id"], str)
        or request["attempt_id"] != expected_base["attempt_id"]
    ):
        raise ProvenanceError("guardian request attempt differs from the live attempt")
    if not isinstance(request["challenge"], str) or re.fullmatch(
        r"[0-9a-f]{64}", request["challenge"]
    ) is None:
        raise ProvenanceError("guardian challenge must be exactly 32 bytes")
    if not isinstance(request["state_sha256"], str) or re.fullmatch(
        r"sha256:[0-9a-f]{64}", request["state_sha256"]
    ) is None:
        raise ProvenanceError("guardian request state digest is malformed")
    current_raw, current = guardian_revalidate(
        repository,
        git_dir,
        expected_base,
        request["state_sha256"],
        consumed_state_digest,
        deadline_monotonic,
    )
    require_guardian_deadline(deadline_monotonic)
    response_proof = protocol_mac(
        capability,
        RESPONSE_DOMAIN,
        request["challenge"],
        request["state_sha256"],
    )
    send_message(
        channel,
        {
            "capability": capability.hex(),
            "proof": response_proof,
            "type": "challenge_response",
        },
    )
    acknowledgement = receive_message(channel, "guardian consume acknowledgement")
    require_keys(acknowledgement, {"proof", "type"}, "guardian consume acknowledgement")
    expected_ack = protocol_mac(
        capability,
        ACK_DOMAIN,
        request["challenge"],
        request["state_sha256"],
    )
    if acknowledgement["type"] != "consume_ack" or not hmac.compare_digest(
        acknowledgement["proof"] if isinstance(acknowledgement["proof"], str) else "",
        expected_ack,
    ):
        raise ProvenanceError("guardian consume acknowledgement is invalid")
    current_raw, current = guardian_revalidate(
        repository,
        git_dir,
        expected_base,
        request["state_sha256"],
        consumed_state_digest,
        deadline_monotonic,
    )
    if configured_failpoint == "delay_after_final_revalidation":
        time.sleep(max(0, deadline_monotonic - time.monotonic()) + 0.05)
        configured_failpoint = None
    require_guardian_deadline(deadline_monotonic)
    if current["state"] == "pending":
        require_guardian_deadline(deadline_monotonic)
        consumed_raw = state_for_status(expected_base, "consumed")
        transition_state(git_dir, current_raw, consumed_raw)
        consumed_state_digest = digest(consumed_raw)
        failpoint(configured_failpoint, "after_consumed")
    assert consumed_state_digest is not None
    if configured_failpoint == "drop_final_response":
        configured_failpoint = None
        return consumed_state_digest, True
    final_proof = protocol_mac(
        capability,
        FINAL_DOMAIN,
        request["challenge"],
        consumed_state_digest,
    )
    send_message(
        channel,
        {
            "proof": final_proof,
            "state_sha256": consumed_state_digest,
            "type": "consumed",
        },
    )
    return consumed_state_digest, False


def guardian_process(
    repository: Path,
    source_head: str,
    snapshot_sha256: str,
    lifetime_seconds: float,
    ready_fd: int,
    configured_failpoint: str | None,
) -> None:
    ready = os.fdopen(ready_fd, "wb", closefd=True)
    listener: socket.socket | None = None
    lock_descriptor = -1
    socket_identity: tuple[int, int, int] | None = None
    socket_path: PurePosixPath | None = None

    def stop_guardian(_signum: int, _frame: object) -> None:
        raise GuardianStop()

    signal.signal(signal.SIGTERM, stop_guardian)
    signal.signal(signal.SIGINT, stop_guardian)
    try:
        require_repository_root(repository)
        require_clean(repository)
        if current_head(repository) != source_head:
            raise ProvenanceError("committed HEAD changed before guardian start")
        snapshot = canonical_json(build_record(repository, source_head))
        if digest(snapshot) != snapshot_sha256 or len(snapshot) > MAX_RECORD_BYTES:
            raise ProvenanceError("guardian snapshot differs from the validated preflight")
        capability = secrets.token_bytes(CAPABILITY_BYTES)
        attempt_id = secrets.token_hex(32)
        socket_path = SOCKET_DIRECTORY / f"{attempt_id}.sock"
        deadline = time.monotonic() + lifetime_seconds
        expires_at = time.time_ns() + int(lifetime_seconds * 1_000_000_000)
        git_dir = git_directory(repository)
        clone_identity = repository_identity(repository, git_dir)
        base = {
            "attempt_id": attempt_id,
            "capability_commitment": capability_commitment(
                attempt_id,
                source_head,
                snapshot_sha256,
                clone_identity,
                capability,
            ),
            "expires_at_unix_ns": expires_at,
            "guardian_pid": os.getpid(),
            "migration_version": MIGRATION_VERSION,
            "operation": OPERATION,
            "protocol_version": PROTOCOL_VERSION,
            "record_path": RECORD_PATH.as_posix(),
            "repository_identity": clone_identity,
            "schema_version": SCHEMA_VERSION,
            "snapshot_sha256": snapshot_sha256,
            "socket_path": socket_path.as_posix(),
            "source_head": source_head,
        }
        lock_descriptor = acquire_guardian_lock(git_dir)
        prepared_raw = state_for_status(base, "prepared")
        publish_prepared_state(git_dir, prepared_raw)
        failpoint(configured_failpoint, "after_prepared")
        listener, socket_identity = bind_guardian_socket(git_dir, socket_path)
        failpoint(configured_failpoint, "after_listen")
        write_exclusive(
            repository,
            RECORD_PATH,
            snapshot,
            MAX_RECORD_BYTES,
            "migration provenance",
            mode=0o644,
            directory_mode=0o755,
        )
        failpoint(configured_failpoint, "after_snapshot")
        pending_raw = state_for_status(base, "pending")
        transition_state(git_dir, prepared_raw, pending_raw)
        failpoint(configured_failpoint, "after_pending")
        ready.write(compact_json({"attempt_id": attempt_id, "status": "ready"}))
        ready.flush()
        ready.close()
        listener.settimeout(0.25)
        consumed_state_digest: str | None = None
        while time.monotonic() < deadline:
            try:
                channel, _address = listener.accept()
            except socket.timeout:
                continue
            with channel:
                channel.settimeout(5)
                try:
                    consumed_state_digest, dropped = guardian_connection(
                        channel,
                        repository,
                        git_dir,
                        capability,
                        base,
                        consumed_state_digest,
                        configured_failpoint,
                        deadline,
                    )
                    if dropped:
                        configured_failpoint = None
                except (OSError, UnicodeError, ProvenanceError):
                    try:
                        send_message(channel, {"type": "error"})
                    except OSError:
                        pass
    except GuardianStop:
        pass
    except (OSError, UnicodeError, ProvenanceError) as exc:
        if not ready.closed:
            ready.write(compact_json({"error": str(exc), "status": "error"}))
            ready.flush()
    finally:
        if not ready.closed:
            ready.close()
        if listener is not None:
            listener.close()
        if socket_path is not None and socket_identity is not None:
            try:
                unlink_bound_socket(git_directory(repository), socket_path, socket_identity)
            except (OSError, UnicodeError, ProvenanceError):
                pass
        if lock_descriptor >= 0:
            os.close(lock_descriptor)


def preflight_capture(repository: Path) -> tuple[str, str]:
    try:
        read_record(repository)
    except ProvenanceError as exc:
        if "missing or unsafe" not in str(exc):
            raise
    else:
        raise ProvenanceError(
            f"migration provenance already exists and cannot be replayed: {RECORD_PATH}"
        )
    git_dir = git_directory(repository)
    try:
        attempt_state_raw(git_dir)
    except ProvenanceError as exc:
        if "is missing" not in str(exc):
            raise
    else:
        raise ProvenanceError("validation-witness migration attempt already exists")
    require_clean(repository)
    source_head = current_head(repository)
    snapshot = canonical_json(build_record(repository, source_head))
    if len(snapshot) > MAX_RECORD_BYTES:
        raise ProvenanceError(f"migration record exceeds its {MAX_RECORD_BYTES}-byte bound")
    if current_head(repository) != source_head:
        raise ProvenanceError("committed HEAD changed while provenance was captured")
    require_clean(repository)
    return source_head, digest(snapshot)


def start_guardian(
    repository: Path, lifetime_seconds: float, configured_failpoint: str | None
) -> None:
    source_head, snapshot_sha256 = preflight_capture(repository)
    read_fd, write_fd = os.pipe()
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--destination",
        str(repository),
        "--guardian",
        "--guardian-source-head",
        source_head,
        "--guardian-snapshot-digest",
        snapshot_sha256,
        "--guardian-lifetime-seconds",
        str(lifetime_seconds),
        "--guardian-ready-fd",
        str(write_fd),
    ]
    if configured_failpoint:
        command.extend(("--test-failpoint", configured_failpoint))
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            pass_fds=(write_fd,),
            start_new_session=True,
        )
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        raise ProvenanceError(f"could not start validation-witness guardian: {exc}") from exc
    os.close(write_fd)
    raw = b""
    readiness_deadline = time.monotonic() + 10
    try:
        while len(raw) <= MAX_PROTOCOL_MESSAGE_BYTES:
            remaining = readiness_deadline - time.monotonic()
            if remaining <= 0 or not select.select([read_fd], [], [], remaining)[0]:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                raise ProvenanceError("guardian readiness timed out")
            chunk = os.read(read_fd, MAX_PROTOCOL_MESSAGE_BYTES + 1 - len(raw))
            if not chunk:
                break
            raw += chunk
    finally:
        os.close(read_fd)
    if len(raw) > MAX_PROTOCOL_MESSAGE_BYTES:
        raise ProvenanceError("guardian readiness message exceeds its byte bound")
    try:
        status = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        process.poll()
        raise ProvenanceError("guardian exited before publishing a readiness result") from exc
    if not isinstance(status, dict) or compact_json(status) != raw:
        raise ProvenanceError("guardian readiness result is not canonical")
    if status.get("status") != "ready":
        raise ProvenanceError(f"guardian did not become ready: {status.get('error', 'unknown error')}")


def verify_with_guardian(repository: Path) -> None:
    if not current_policy_has_marker(repository):
        raise ProvenanceError("updated orchestration policy lacks the migration schema marker")
    git_dir = git_directory(repository)
    state_raw = attempt_state_raw(git_dir)
    state = parse_attempt_state(state_raw)
    if state["state"] not in {"pending", "consumed"}:
        raise ProvenanceError("migration attempt is not ready for after-stage verification")
    snapshot = read_record(repository)
    validate_snapshot(repository, state, snapshot)
    if time.time_ns() >= state["expires_at_unix_ns"]:
        raise ProvenanceError("validation-witness guardian lifetime expired")
    challenge = secrets.token_bytes(CHALLENGE_BYTES).hex()
    socket_path = PurePosixPath(state["socket_path"])
    try:
        channel = connect_guardian_socket(git_dir, socket_path)
    except OSError as exc:
        raise ProvenanceError("original validation-witness guardian is not reachable") from exc
    with channel:
        send_message(
            channel,
            {
                "attempt_id": state["attempt_id"],
                "challenge": challenge,
                "protocol_version": PROTOCOL_VERSION,
                "state_sha256": digest(state_raw),
                "type": "challenge",
            },
        )
        response = receive_message(channel, "guardian challenge response")
        require_keys(response, {"capability", "proof", "type"}, "guardian challenge response")
        if response["type"] != "challenge_response":
            raise ProvenanceError("original guardian rejected the challenge")
        try:
            capability = bytes.fromhex(response["capability"])
        except (TypeError, ValueError) as exc:
            raise ProvenanceError("guardian capability response is malformed") from exc
        if len(capability) != CAPABILITY_BYTES:
            raise ProvenanceError("guardian capability response has the wrong length")
        actual_commitment = capability_commitment(
            state["attempt_id"],
            state["source_head"],
            state["snapshot_sha256"],
            state["repository_identity"],
            capability,
        )
        if not hmac.compare_digest(actual_commitment, state["capability_commitment"]):
            raise ProvenanceError("guardian response does not match the durable commitment")
        expected_response = protocol_mac(
            capability, RESPONSE_DOMAIN, challenge, digest(state_raw)
        )
        if not hmac.compare_digest(
            response["proof"] if isinstance(response["proof"], str) else "",
            expected_response,
        ):
            raise ProvenanceError("guardian challenge response proof is invalid")
        send_message(
            channel,
            {
                "proof": protocol_mac(capability, ACK_DOMAIN, challenge, digest(state_raw)),
                "type": "consume_ack",
            },
        )
        try:
            final = receive_message(channel, "guardian consume result")
        except ProvenanceError as exc:
            raise ProvenanceError(
                "guardian response was lost; retry while the same guardian remains live"
            ) from exc
        require_keys(final, {"proof", "state_sha256", "type"}, "guardian consume result")
        if (
            final["type"] != "consumed"
            or not isinstance(final["state_sha256"], str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", final["state_sha256"])
            is None
        ):
            raise ProvenanceError("guardian consume result is invalid")
        expected_final = protocol_mac(
            capability, FINAL_DOMAIN, challenge, final["state_sha256"]
        )
        if not hmac.compare_digest(
            final["proof"] if isinstance(final["proof"], str) else "", expected_final
        ):
            raise ProvenanceError("guardian consume result proof is invalid")
    consumed_raw = attempt_state_raw(git_dir)
    consumed = parse_attempt_state(consumed_raw)
    if (
        state_base(consumed) != state_base(state)
        or consumed["state"] != "consumed"
        or digest(consumed_raw) != final["state_sha256"]
    ):
        raise ProvenanceError("durable consumed state differs from the guardian result")


def unlink_relative(
    root: Path, relative: PurePosixPath, *, directory_mode: int = 0o755
) -> None:
    parent = open_relative_parent(
        root, relative, create=False, directory_mode=directory_mode
    )
    try:
        os.unlink(relative.name, dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(parent)


def recover_stale(repository: Path, configured_failpoint: str | None) -> None:
    require_recovery_clean(repository)
    if current_policy_has_marker(repository):
        raise ProvenanceError("stale recovery is forbidden after the migration boundary appears")
    git_dir = git_directory(repository)
    try:
        lock_descriptor = acquire_guardian_lock(git_dir, create=False)
    except FileNotFoundError:
        try:
            provisional_raw = attempt_state_raw(git_dir)
            provisional = parse_attempt_state(provisional_raw)
        except ProvenanceError as exc:
            if "is missing" not in str(exc):
                raise
            try:
                read_relative_regular(
                    git_dir,
                    RECOVERY_TOMBSTONE_PATH,
                    MAX_ATTEMPT_STATE_BYTES,
                    "interrupted stale-recovery tombstone",
                    required_mode=0o600,
                    directory_mode=0o700,
                )
            except FileNotFoundError:
                raise ProvenanceError(
                    "stale recovery lacks its original guardian lock"
                ) from exc
        else:
            if provisional["state"] != "recovering":
                raise ProvenanceError("stale recovery lacks its original guardian lock")
        lock_descriptor = acquire_guardian_lock(git_dir, create=True)
    try:
        try:
            state_raw = attempt_state_raw(git_dir)
        except ProvenanceError as exc:
            if "is missing" not in str(exc):
                raise
            if final_entry_exists(
                git_dir, ATTEMPT_STATE_PATH, directory_mode=0o700
            ):
                raise ProvenanceError(
                    "validation-witness migration attempt state is unsafe"
                ) from exc
            preparing_path: PurePosixPath | None = None
            for candidate in (RECOVERY_TOMBSTONE_PATH, PREPARING_STATE_PATH):
                try:
                    read_relative_regular(
                        git_dir,
                        candidate,
                        MAX_ATTEMPT_STATE_BYTES,
                        "interrupted prepared-state publication",
                        required_mode=0o600,
                        directory_mode=0o700,
                    )
                except FileNotFoundError:
                    continue
                preparing_path = candidate
                break
            try:
                read_record(repository)
            except ProvenanceError as record_exc:
                if "missing or unsafe" not in str(record_exc):
                    raise
            else:
                raise ProvenanceError(
                    "interrupted prepared-state publication unexpectedly has a snapshot"
                )
            if preparing_path == PREPARING_STATE_PATH:
                parent = open_relative_parent(
                    git_dir,
                    PREPARING_STATE_PATH,
                    create=False,
                    directory_mode=0o700,
                )
                try:
                    os.rename(
                        PREPARING_STATE_PATH.name,
                        RECOVERY_TOMBSTONE_PATH.name,
                        src_dir_fd=parent,
                        dst_dir_fd=parent,
                    )
                    os.fsync(parent)
                finally:
                    os.close(parent)
                preparing_path = RECOVERY_TOMBSTONE_PATH
            failpoint(configured_failpoint, "recover_after_state")
            unlink_relative(git_dir, GUARDIAN_LOCK_PATH, directory_mode=0o700)
            failpoint(configured_failpoint, "recover_after_lock")
            if preparing_path is not None:
                unlink_relative(git_dir, preparing_path, directory_mode=0o700)
            return

        state = parse_attempt_state(state_raw)
        if state["state"] == "consumed":
            raise ProvenanceError(
                "consumed migration attempt is terminal and cannot be recovered"
            )
        if state["repository_identity"] != repository_identity(repository, git_dir):
            raise ProvenanceError("stale migration attempt belongs to another repository clone")
        if state["source_head"] != current_head(repository):
            raise ProvenanceError("stale migration attempt source HEAD changed")
        expected_snapshot = canonical_json(build_record(repository, state["source_head"]))
        if digest(expected_snapshot) != state["snapshot_sha256"]:
            raise ProvenanceError("stale migration attempt snapshot identity changed")
        try:
            actual_snapshot = read_record(repository)
        except ProvenanceError as exc:
            if "missing or unsafe" not in str(exc):
                raise
            actual_snapshot = None
        if actual_snapshot is not None and actual_snapshot != expected_snapshot:
            if state["state"] not in {"prepared", "recovering"} or not expected_snapshot.startswith(
                actual_snapshot
            ):
                raise ProvenanceError("stale migration snapshot does not match the clean source")
        if state["state"] == "pending" and actual_snapshot is None:
            raise ProvenanceError("pending stale attempt is missing its durable snapshot")

        temporary = ATTEMPT_STATE_PATH.with_name(
            state_temporary_name(state["attempt_id"])
        )
        try:
            temporary_raw = read_relative_regular(
                git_dir,
                temporary,
                MAX_ATTEMPT_STATE_BYTES,
                "interrupted migration state publication",
                required_mode=0o600,
                directory_mode=0o700,
            )
        except FileNotFoundError:
            pass
        else:
            possible_targets = {
                state_for_status(state_base(state), target)
                for target in ("pending", "consumed", "recovering")
            }
            try:
                temporary_value = parse_attempt_state(temporary_raw)
            except ProvenanceError:
                if not any(target.startswith(temporary_raw) for target in possible_targets):
                    raise
            else:
                if state_base(temporary_value) != state_base(state) or canonical_json(
                    temporary_value
                ) not in possible_targets:
                    raise ProvenanceError(
                        "interrupted migration transition changed its bound identity"
                    )
            unlink_relative(git_dir, temporary, directory_mode=0o700)

        if state["state"] != "recovering":
            recovering_raw = state_for_status(state_base(state), "recovering")
            transition_state(git_dir, state_raw, recovering_raw)
            state_raw = recovering_raw
            state = parse_attempt_state(state_raw)
        failpoint(configured_failpoint, "recover_after_state")

        socket_path = PurePosixPath(state["socket_path"])
        try:
            parent, socket_status = socket_lstat(git_dir, socket_path)
        except FileNotFoundError:
            parent = -1
        else:
            try:
                if not stat.S_ISSOCK(socket_status.st_mode):
                    raise ProvenanceError("stale guardian pathname was replaced unsafely")
                try:
                    probe = connect_guardian_socket(git_dir, socket_path)
                except (ConnectionRefusedError, FileNotFoundError):
                    current = os.stat(
                        socket_path.name, dir_fd=parent, follow_symlinks=False
                    )
                    if (current.st_dev, current.st_ino, current.st_ctime_ns) != (
                        socket_status.st_dev,
                        socket_status.st_ino,
                        socket_status.st_ctime_ns,
                    ):
                        raise ProvenanceError(
                            "stale guardian socket changed during recovery"
                        )
                    os.unlink(socket_path.name, dir_fd=parent)
                    os.fsync(parent)
                else:
                    probe.close()
                    raise ProvenanceError(
                        "a process is still listening on the guardian socket"
                    )
            finally:
                os.close(parent)
        if actual_snapshot is not None:
            unlink_relative(repository, RECORD_PATH)
        failpoint(configured_failpoint, "recover_after_snapshot")
        unlink_relative(git_dir, GUARDIAN_LOCK_PATH, directory_mode=0o700)
        failpoint(configured_failpoint, "recover_after_lock")
        unlink_relative(git_dir, ATTEMPT_STATE_PATH, directory_mode=0o700)
    finally:
        os.close(lock_descriptor)


def validate_lifetime(value: float) -> float:
    if not (0 < value <= DEFAULT_GUARDIAN_LIFETIME_SECONDS):
        raise ProvenanceError(
            "guardian lifetime must be positive and no greater than one hour"
        )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("."))
    parser.add_argument("--stage", choices=("before", "after", "recover"))
    parser.add_argument(
        "--guardian-lifetime-seconds",
        type=float,
        default=DEFAULT_GUARDIAN_LIFETIME_SECONDS,
    )
    parser.add_argument("--test-failpoint", choices=sorted(TEST_FAILPOINTS))
    parser.add_argument("--guardian", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--guardian-source-head", help=argparse.SUPPRESS)
    parser.add_argument("--guardian-snapshot-digest", help=argparse.SUPPRESS)
    parser.add_argument("--guardian-ready-fd", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    repository = args.destination.resolve()
    try:
        if not repository.is_dir():
            raise ProvenanceError(f"destination is not a directory: {repository}")
        lifetime = validate_lifetime(args.guardian_lifetime_seconds)
        if args.test_failpoint and os.environ.get("PROJECT_AGENT_WORKFLOW_TESTING") != "1":
            raise ProvenanceError("test failpoints require the explicit test environment")
        if args.guardian:
            if args.stage is not None:
                raise ProvenanceError("internal guardian mode does not accept a stage")
            if (
                not args.guardian_source_head
                or not args.guardian_snapshot_digest
                or args.guardian_ready_fd is None
            ):
                raise ProvenanceError("internal guardian mode is missing its bounded inputs")
            guardian_process(
                repository,
                args.guardian_source_head,
                args.guardian_snapshot_digest,
                lifetime,
                args.guardian_ready_fd,
                args.test_failpoint,
            )
            return 0
        if args.stage is None:
            raise ProvenanceError("one migration stage is required")
        require_repository_root(repository)
        if args.stage == "before":
            start_guardian(repository, lifetime, args.test_failpoint)
        elif args.stage == "after":
            verify_with_guardian(repository)
        else:
            recover_stale(repository, args.test_failpoint)
    except (OSError, UnicodeError, ProvenanceError) as exc:
        print(f"validation-witness provenance migration failed: {exc}", file=sys.stderr)
        return 1
    print(f"validation-witness provenance {args.stage} stage passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
