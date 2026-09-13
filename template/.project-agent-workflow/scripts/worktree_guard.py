#!/usr/bin/env python3
"""Shared task-worktree assertion for every supported repository write.

Every repository-changing task performs its writes in one exact task-bound
linked worktree. This module owns the primitives that boundary needs: the
hardened path and record checks, the disjoint plan and direct-task
identities, and the read-only assertion that reproduces a live binding from
the current working directory.

The module never mutates Git or an ownership record. It reproduces bound
facts and fails closed. It cannot stop an unrestricted same-user process
that bypasses every supported entrypoint, and it does not claim to.

The root copy and the generated copy are byte-identical. Every repository
path this module needs is probed at run time so that neither copy carries a
layout-specific string.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import pwd
import re
import stat
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 2
MAX_RECORD_BYTES = 65_536
MAX_LEASE_SECONDS = 86_400
MAX_RECORDS_SCANNED = 512
# Retired records carry no count limit. The live limit exists because an
# implausible count there means the directory is wrong, and failing closed
# costs one repository. A large retired directory is ordinary, and refusing on
# it would stop completion checks for every repository on the account, which is
# the systemic failure this command exists to remove. It would also push the
# operator to move aside the only evidence that a retirement was wrong.
RETIRED_DIRECTORY_NAME = "retired"
# The refusal stops every guarded command, so it carries its own remedy rather
# than leaving the reader to discover which command clears the directory. The
# command is named without a directory because this module is shipped verbatim
# to generated projects, where it sits under a different prefix.
IMPLAUSIBLE_RECORD_COUNT_MESSAGE = (
    "ownership-record directory holds an implausible record count; "
    "run retire-stale-worktree-records.py scan to see which records "
    "no repository can reach, then apply-local to move them aside"
)

PLAN_TASK = "plan"
DIRECT_TASK = "direct"
TASK_KINDS = (PLAN_TASK, DIRECT_TASK)

OWNER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
OID_RE = re.compile(r"[0-9a-f]{40,64}")
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
BRANCH_REF_RE = re.compile(r"refs/heads/[^\x00-\x20~^:?*\\\[]+")
PLAN_PATH_RE = re.compile(r"docs/plan/active/[0-9]{3}-[a-z0-9][a-z0-9-]*\.md")
DIRECT_TASK_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,63}")

RECORD_KEYS = {
    "schema_version",
    "repository_identity",
    "task",
    "start_commit",
    "accepted_tip",
    "source_ref",
    "branch_ref",
    "allowed_root",
    "worktree_path",
    "worktree_identity",
    "owner",
    "content_digest",
}
REPOSITORY_KEYS = {
    "origin_identity",
    "common_git_dir",
    "common_git_dir_device",
    "common_git_dir_inode",
}
TASK_KEYS = {"kind", "identity"}
PLAN_IDENTITY_KEYS = {"path", "digest", "blob_oid"}
DIRECT_IDENTITY_KEYS = {"id", "purpose"}
OWNER_KEYS = {"id", "lease_expires_at"}
WORKTREE_IDENTITY_KEYS = {
    "git_dir",
    "git_dir_device",
    "git_dir_inode",
    "worktree_device",
    "worktree_inode",
    "worktree_owner",
    "worktree_mode",
}

STATE_RELATIVE_DIRECTORY = ".local/state/project-agent-workflow/parent-worktrees"
DEFAULT_ROOT_RELATIVE_DIRECTORY = ".local/state/project-agent-workflow/task-worktrees"

# The manager is a sibling of this module in a generated project and lives
# one directory above it in this repository. Probing both keeps the root and
# generated copies of every caller byte-identical.
MANAGER_CANDIDATES = (
    ".project-agent-workflow/scripts/manage-plan-worktrees.py",
    "scripts/manage-plan-worktrees.py",
)
GUARD_CANDIDATES = (
    "worktree_guard.py",
    "project_workflow/worktree_guard.py",
)


class WorktreeError(ValueError):
    """A fail-closed managed-worktree error."""


class GuardError(WorktreeError):
    """A supported write was attempted outside its bound task worktree."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def digest_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            environment.pop(name, None)
    environment.update(
        {
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_GRAFT_FILE": os.devnull,
            "GIT_OPTIONAL_LOCKS": "0",
            "LC_ALL": "C",
        }
    )
    return environment


def git(
    repository: Path,
    *arguments: str,
    check: bool = True,
    pass_fds: tuple[int, ...] = (),
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            f"core.excludesFile={os.devnull}",
            "-C",
            str(repository),
            *arguments,
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_environment(),
        pass_fds=pass_fds,
    )
    if check and completed.returncode != 0:
        raise WorktreeError(f"Git command failed: {' '.join(arguments)}")
    return completed


def git_text(repository: Path, *arguments: str, check: bool = True) -> str:
    return git(repository, *arguments, check=check).stdout.decode("utf-8", "strict").strip()


def has_symlink_component(path: Path) -> bool:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            return True
    return False


def canonical_directory(raw: str, *, label: str) -> Path:
    path = Path(raw)
    if has_symlink_component(path):
        raise WorktreeError(f"{label} contains a symlink component")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise WorktreeError(f"{label} cannot be resolved") from exc
    if not resolved.is_dir():
        raise WorktreeError(f"{label} must be a directory")
    return resolved


def require_owned_directory(path: Path, *, label: str, private: bool = False) -> Path:
    resolved = canonical_directory(str(path), label=label)
    metadata = resolved.stat()
    if metadata.st_uid != os.getuid():
        raise WorktreeError(f"{label} must be owned by the current user")
    forbidden_mode = 0o077 if private else 0o022
    if stat.S_IMODE(metadata.st_mode) & forbidden_mode:
        requirement = "mode 0700" if private else "not be group- or world-writable"
        raise WorktreeError(f"{label} must {requirement}")
    return resolved


def directory_identity(path: Path) -> tuple[int, int]:
    metadata = path.stat()
    return metadata.st_dev, metadata.st_ino


def path_is_strict_descendant(path: Path, parent: Path) -> bool:
    try:
        relative = path.relative_to(parent)
    except ValueError:
        return False
    return relative != Path(".")


def account_home() -> Path:
    """Return the operating-system account home, never caller-controlled HOME."""

    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def state_directory() -> Path:
    return account_home() / STATE_RELATIVE_DIRECTORY


def default_allowed_root() -> Path:
    return account_home() / DEFAULT_ROOT_RELATIVE_DIRECTORY


def normalize_plan_path(raw: str) -> str:
    value = PurePosixPath(raw)
    if (
        value.is_absolute()
        or raw in {"", "."}
        or any(part in {"", ".", ".."} for part in value.parts)
        or PLAN_PATH_RE.fullmatch(raw) is None
    ):
        raise WorktreeError("plan path must name one normalized active numbered plan")
    return raw


def normalize_direct_task(raw: str) -> str:
    if DIRECT_TASK_RE.fullmatch(raw) is None:
        raise WorktreeError(
            "direct task id must be 3 to 64 lowercase letters, digits, or hyphens"
        )
    if PLAN_PATH_RE.fullmatch(raw) is not None or re.fullmatch(r"[0-9]{3}(-.*)?", raw):
        raise WorktreeError("direct task id must not imitate a numbered plan identity")
    return raw


def plan_task(identity: dict[str, str]) -> dict[str, Any]:
    return {"kind": PLAN_TASK, "identity": dict(identity)}


def direct_task(task_id: str, purpose: str) -> dict[str, Any]:
    return {
        "kind": DIRECT_TASK,
        "identity": {"id": normalize_direct_task(task_id), "purpose": purpose},
    }


def task_label(task: dict[str, Any]) -> str:
    if task["kind"] == PLAN_TASK:
        return task["identity"]["path"]
    return f"direct:{task['identity']['id']}"


def task_selector(task: dict[str, Any]) -> dict[str, str]:
    """Return the immutable key material that names one task.

    The plan and direct variants are disjoint by construction: they never
    share a key name, so a direct task can never derive a plan record path.
    """

    if task["kind"] == PLAN_TASK:
        return {"plan": task["identity"]["path"]}
    return {"direct_task": task["identity"]["id"]}


def canonical_origin(repository: Path) -> str:
    from urllib.parse import urlsplit, urlunsplit

    origin = git_text(repository, "remote", "get-url", "origin")
    if re.fullmatch(r"[^/@:\s]+@[^/:\s]+:[^:\s]+", origin):
        _, host_path = origin.split("@", 1)
        host, path = host_path.split(":", 1)
        return f"ssh://{host.lower()}/{path.removesuffix('.git')}"
    parsed = urlsplit(origin)
    if parsed.scheme not in {"https", "ssh", "git"} or not parsed.hostname:
        raise WorktreeError("remote.origin.url must be a canonical network URL")
    port = f":{parsed.port}" if parsed.port is not None else ""
    path = parsed.path.removesuffix(".git")
    if not path or path == "/":
        raise WorktreeError("remote.origin.url does not identify a repository")
    return urlunsplit((parsed.scheme, f"{parsed.hostname.lower()}{port}", path, "", ""))


def repository_root(cwd: Path | None = None) -> Path:
    root = git_text(cwd or Path.cwd(), "rev-parse", "--show-toplevel")
    return canonical_directory(root, label="Git worktree root")


def repository_identity(repository: Path) -> dict[str, Any]:
    common = canonical_directory(
        git_text(repository, "rev-parse", "--path-format=absolute", "--git-common-dir"),
        label="common Git directory",
    )
    metadata = common.stat()
    return {
        "origin_identity": digest_bytes(canonical_origin(repository).encode("utf-8")),
        "common_git_dir": str(common),
        "common_git_dir_device": metadata.st_dev,
        "common_git_dir_inode": metadata.st_ino,
    }


def metadata_paths(identity: dict[str, Any], task: dict[str, Any]) -> dict[str, Path]:
    key = hashlib.sha256(
        canonical_json(
            {
                "common_git_dir": identity["common_git_dir"],
                "common_git_dir_device": identity["common_git_dir_device"],
                "common_git_dir_inode": identity["common_git_dir_inode"],
                **task_selector(task),
            }
        )
    ).hexdigest()
    directory = state_directory()
    return {
        "directory": directory,
        "record": directory / f"{key}.json",
        "journal": directory / f"{key}.journal.json",
        # The publication transaction keeps its own journal. Sharing the create
        # and resume journal path let one interrupted publication make every
        # supported command refuse the task, because each side validates the
        # other's schema. The name still ends in `.journal.json`, so ownership
        # record enumeration continues to skip it.
        "publication": directory / f"{key}.publish.journal.json",
        "lock": directory / f"{key}.lock",
        "retired_record": directory / RETIRED_DIRECTORY_NAME / f"{key}.json",
    }


def ensure_metadata_directory(path: Path) -> None:
    if has_symlink_component(path):
        raise WorktreeError("ownership-record directory contains a symlink component")
    if path.exists():
        canonical = require_owned_directory(
            path, label="ownership-record directory", private=True
        )
        if canonical != path:
            raise WorktreeError("ownership-record directory is not canonical")
    else:
        path.mkdir(mode=0o700, parents=True)
    path.chmod(0o700)
    require_owned_directory(path, label="ownership-record directory", private=True)


def locked_file(path: Path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    os.fchmod(descriptor, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    return os.fdopen(descriptor, "r+", encoding="utf-8")


def add_content_digest(record: dict[str, Any]) -> dict[str, Any]:
    unsigned = dict(record)
    unsigned.pop("content_digest", None)
    return {**unsigned, "content_digest": digest_bytes(canonical_json(unsigned))}


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WorktreeError(f"ownership record contains a duplicate JSON key: {key}")
        result[key] = value
    return result


def read_record(path: Path) -> dict[str, Any]:
    if has_symlink_component(path) or path.is_symlink() or not path.is_file():
        raise WorktreeError("ownership record must be a regular non-symlink file")
    metadata = path.stat()
    if stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_nlink != 1:
        raise WorktreeError("ownership record must be single-linked mode 0600")
    data = path.read_bytes()
    if len(data) > MAX_RECORD_BYTES:
        raise WorktreeError("ownership record exceeds the size limit")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=reject_duplicate_json_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorktreeError("ownership record is not valid UTF-8 JSON") from exc
    validate_record(value, allow_pending=path.name.endswith(".journal.json"))
    return value


def validate_task(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != TASK_KEYS:
        raise WorktreeError("ownership record task identity is invalid")
    kind = value["kind"]
    identity = value["identity"]
    if kind not in TASK_KINDS or not isinstance(identity, dict):
        raise WorktreeError("ownership record task kind is invalid")
    if kind == PLAN_TASK:
        if set(identity) != PLAN_IDENTITY_KEYS:
            raise WorktreeError("ownership record plan identity is invalid")
        if not isinstance(identity["path"], str):
            raise WorktreeError("ownership record plan identity is invalid")
        normalize_plan_path(identity["path"])
        if not isinstance(identity["digest"], str) or DIGEST_RE.fullmatch(
            identity["digest"]
        ) is None:
            raise WorktreeError("ownership record plan digest is invalid")
        if not isinstance(identity["blob_oid"], str) or OID_RE.fullmatch(
            identity["blob_oid"]
        ) is None:
            raise WorktreeError("ownership record plan blob is invalid")
        return
    if set(identity) != DIRECT_IDENTITY_KEYS:
        raise WorktreeError("ownership record direct-task identity is invalid")
    if not isinstance(identity["id"], str):
        raise WorktreeError("ownership record direct-task identity is invalid")
    normalize_direct_task(identity["id"])
    purpose = identity["purpose"]
    if not isinstance(purpose, str) or not purpose.strip() or len(purpose.encode("utf-8")) > 400:
        raise WorktreeError("ownership record direct-task purpose is invalid")


def validate_record(value: Any, *, allow_pending: bool = False) -> None:
    if not isinstance(value, dict) or set(value) != RECORD_KEYS:
        raise WorktreeError("ownership record schema is invalid")
    if value["schema_version"] != SCHEMA_VERSION:
        raise WorktreeError("ownership record version is unsupported")
    if not isinstance(value["repository_identity"], dict) or set(
        value["repository_identity"]
    ) != REPOSITORY_KEYS:
        raise WorktreeError("ownership record repository identity is invalid")
    validate_task(value["task"])
    if not isinstance(value["owner"], dict) or set(value["owner"]) != OWNER_KEYS:
        raise WorktreeError("ownership record owner lease is invalid")
    worktree_identity_value = value["worktree_identity"]
    if (
        not isinstance(worktree_identity_value, dict)
        or set(worktree_identity_value) != WORKTREE_IDENTITY_KEYS
    ):
        raise WorktreeError("ownership record worktree identity is invalid")
    identity_values = tuple(worktree_identity_value.values())
    empty_identity = all(item is None for item in identity_values)
    target_identity = (
        type(worktree_identity_value["worktree_device"]) is int
        and type(worktree_identity_value["worktree_inode"]) is int
        and type(worktree_identity_value["worktree_owner"]) is int
        and type(worktree_identity_value["worktree_mode"]) is int
    )
    pending_identity = (
        all(
            worktree_identity_value[key] is None
            for key in ("git_dir", "git_dir_device", "git_dir_inode")
        )
        and target_identity
    )
    complete_identity = (
        isinstance(worktree_identity_value["git_dir"], str)
        and Path(worktree_identity_value["git_dir"]).is_absolute()
        and type(worktree_identity_value["git_dir_device"]) is int
        and type(worktree_identity_value["git_dir_inode"]) is int
        and target_identity
    )
    if not (complete_identity or (allow_pending and (empty_identity or pending_identity))):
        raise WorktreeError("ownership record worktree identity values are invalid")
    if (
        not isinstance(value["owner"]["id"], str)
        or OWNER_RE.fullmatch(value["owner"]["id"]) is None
    ):
        raise WorktreeError("ownership record owner id is invalid")
    if type(value["owner"]["lease_expires_at"]) is not int:
        raise WorktreeError("ownership record lease expiry is invalid")
    for key in ("start_commit", "accepted_tip"):
        if not isinstance(value[key], str) or OID_RE.fullmatch(value[key]) is None:
            raise WorktreeError(f"ownership record {key} is invalid")
    for key in ("branch_ref", "source_ref"):
        if not isinstance(value[key], str) or BRANCH_REF_RE.fullmatch(value[key]) is None:
            raise WorktreeError(f"ownership record {key} is invalid")
    if value["branch_ref"] == value["source_ref"]:
        raise WorktreeError("ownership record task branch must differ from its source ref")
    for key in ("allowed_root", "worktree_path"):
        if not isinstance(value[key], str) or not Path(value[key]).is_absolute():
            raise WorktreeError(f"ownership record {key} is invalid")
    if not isinstance(value["content_digest"], str) or DIGEST_RE.fullmatch(
        value["content_digest"]
    ) is None:
        raise WorktreeError("ownership record digest is invalid")
    unsigned = dict(value)
    observed = unsigned.pop("content_digest")
    if observed != digest_bytes(canonical_json(unsigned)):
        raise WorktreeError("ownership record digest does not match its content")


def parse_worktrees(repository: Path) -> list[dict[str, Any]]:
    payload = git(repository, "worktree", "list", "--porcelain", "-z").stdout
    records: list[dict[str, Any]] = []
    for raw_record in payload.split(b"\0\0"):
        if not raw_record:
            continue
        record: dict[str, Any] = {}
        for raw_field in raw_record.split(b"\0"):
            if not raw_field:
                continue
            field = raw_field.decode("utf-8", "strict")
            key, separator, item = field.partition(" ")
            if key in record:
                raise WorktreeError(f"duplicate Git worktree field: {key}")
            record[key] = item if separator else True
        records.append(record)
    return records


def registered_worktree_path(record: dict[str, Any]) -> Path:
    raw = str(record.get("worktree", ""))
    path = Path(raw)
    if not path.is_absolute() or Path(os.path.normpath(raw)) != path:
        raise WorktreeError("Git reported an invalid worktree path")
    if path.exists() or path.is_symlink():
        return canonical_directory(raw, label="registered worktree")
    return path


def find_registered_worktree(
    records: list[dict[str, Any]], target: Path
) -> dict[str, Any] | None:
    matches = [
        record
        for record in records
        if Path(str(record.get("worktree", ""))).absolute() == target
    ]
    if len(matches) > 1:
        raise WorktreeError("Git reported duplicate worktree registrations")
    return matches[0] if matches else None


def primary_worktree(repository: Path) -> Path:
    records = parse_worktrees(repository)
    if not records:
        raise WorktreeError("Git reported no registered worktrees")
    return canonical_directory(str(records[0].get("worktree", "")), label="primary worktree")


def worktree_identity(worktree: Path) -> dict[str, Any]:
    git_dir = canonical_directory(
        git_text(worktree, "rev-parse", "--path-format=absolute", "--git-dir"),
        label="worktree Git directory",
    )
    metadata = git_dir.stat()
    return {
        "git_dir": str(git_dir),
        "git_dir_device": metadata.st_dev,
        "git_dir_inode": metadata.st_ino,
        **target_directory_identity(worktree),
    }


def target_directory_identity(worktree: Path) -> dict[str, int]:
    metadata = worktree.stat()
    return {
        "worktree_device": metadata.st_dev,
        "worktree_inode": metadata.st_ino,
        "worktree_owner": metadata.st_uid,
        "worktree_mode": stat.S_IMODE(metadata.st_mode),
    }


def exact_ref_tip(repository: Path, ref: str) -> str | None:
    completed = git(repository, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
    if completed.returncode != 0:
        return None
    value = completed.stdout.decode("ascii", "strict").strip()
    return value if OID_RE.fullmatch(value) else None


def is_ancestor(repository: Path, ancestor: str, descendant: str) -> bool:
    return (
        git(repository, "merge-base", "--is-ancestor", ancestor, descendant, check=False).returncode
        == 0
    )


def manager_command(repository: Path) -> str:
    for candidate in MANAGER_CANDIDATES:
        if (repository / candidate).is_file():
            return candidate
    return MANAGER_CANDIDATES[-1]


def preparation_guidance(repository: Path, task_hint: str | None = None) -> str:
    command = manager_command(repository)
    selector = task_hint or "<docs/plan/active/NNN-slug.md | --direct-task <id>>"
    return (
        f"Run `python3 {command} prepare {selector}` from the repository root, "
        "then repeat this write inside the reported task worktree."
    )


class TaskBinding:
    """One verified live binding between a task identity and its worktree."""

    __slots__ = ("record", "record_path", "worktree", "repository", "current_tip")

    def __init__(
        self,
        record: dict[str, Any],
        record_path: Path,
        worktree: Path,
        repository: Path,
        current_tip: str,
    ) -> None:
        self.record = record
        self.record_path = record_path
        self.worktree = worktree
        self.repository = repository
        self.current_tip = current_tip

    @property
    def kind(self) -> str:
        return self.record["task"]["kind"]

    @property
    def task(self) -> dict[str, Any]:
        return self.record["task"]

    @property
    def label(self) -> str:
        return task_label(self.record["task"])

    @property
    def branch_ref(self) -> str:
        return self.record["branch_ref"]

    @property
    def source_ref(self) -> str:
        return self.record["source_ref"]

    def summary(self) -> dict[str, Any]:
        return {
            "task_kind": self.kind,
            "task": self.label,
            "worktree": str(self.worktree),
            "branch_ref": self.branch_ref,
            "source_ref": self.source_ref,
            "start_commit": self.record["start_commit"],
            "current_tip": self.current_tip,
            "owner": self.record["owner"]["id"],
            "lease_expires_at": self.record["owner"]["lease_expires_at"],
            "record": str(self.record_path),
        }


def candidate_record_paths() -> list[Path]:
    directory = state_directory()
    if not directory.is_dir() or has_symlink_component(directory):
        return []
    paths = sorted(
        path
        for path in directory.iterdir()
        if path.name.endswith(".json") and not path.name.endswith(".journal.json")
    )
    if len(paths) > MAX_RECORDS_SCANNED:
        raise WorktreeError(IMPLAUSIBLE_RECORD_COUNT_MESSAGE)
    return paths


def retired_record_paths() -> list[Path]:
    """Enumerate records moved aside as unreachable.

    A retired record that matches a live repository indicates the retirement was
    wrong, because a correct one names a repository that no longer exists.
    Reading them therefore surfaces mistakes without reviving finished work. A
    reused device and inode at the same path can also produce a match, so a
    match is a prompt to look, not a proof on its own.

    A retired directory that exists but cannot be read is an error, never an
    empty answer: reporting no retired records would hide exactly the mistakes
    this enumeration exists to show.
    """

    directory = state_directory() / RETIRED_DIRECTORY_NAME
    if not directory.exists() and not directory.is_symlink():
        return []
    if has_symlink_component(directory) or directory.is_symlink():
        raise WorktreeError("retired ownership-record directory is reached through a symlink")
    if not directory.is_dir():
        raise WorktreeError("retired ownership-record path is not a directory")
    return sorted(
        path
        for path in directory.iterdir()
        if path.name.endswith(".json") and not path.name.endswith(".journal.json")
    )


def verify_binding(
    repository: Path,
    record: dict[str, Any],
    record_path: Path,
    *,
    now: int | None = None,
) -> TaskBinding:
    """Reproduce every bound fact for one record, or fail closed."""

    moment = int(time.time()) if now is None else now
    identity = repository_identity(repository)
    if record["repository_identity"] != identity:
        raise GuardError("task binding belongs to another repository or clone")
    allowed_root = canonical_directory(record["allowed_root"], label="allowed root")
    target = canonical_directory(record["worktree_path"], label="task worktree")
    if not path_is_strict_descendant(target, allowed_root):
        raise GuardError("task worktree left its allowed root")
    records = parse_worktrees(repository)
    registered = find_registered_worktree(records, target)
    if registered is None:
        raise GuardError("task worktree is no longer registered with this repository")
    if registered.get("branch") != record["branch_ref"]:
        raise GuardError("task worktree branch changed or became detached")
    tip = exact_ref_tip(repository, record["branch_ref"])
    if tip is None or registered.get("HEAD") != tip:
        raise GuardError("task branch tip is unavailable or ambiguous")
    if git_text(target, "rev-parse", "--show-toplevel") != str(target):
        raise GuardError("task worktree root changed or mismatched")
    if record["worktree_identity"] != worktree_identity(target):
        raise GuardError("task worktree registration was replaced")
    if not is_ancestor(repository, record["start_commit"], tip):
        raise GuardError("task branch no longer contains its bound start commit")
    if record["owner"]["lease_expires_at"] <= moment:
        raise GuardError("task worktree owner lease expired")
    return TaskBinding(record, record_path, target, repository, tip)


def find_binding(
    cwd: Path | None = None, *, now: int | None = None
) -> TaskBinding | None:
    """Return the verified binding that owns the current worktree, if any."""

    try:
        repository = repository_root(cwd)
    except WorktreeError:
        return None
    identity = repository_identity(repository)
    for path in candidate_record_paths():
        try:
            record = read_record(path)
        except (OSError, WorktreeError):
            continue
        if record["repository_identity"] != identity:
            continue
        if Path(record["worktree_path"]) != repository:
            continue
        return verify_binding(repository, record, path, now=now)
    return None


def outstanding_tasks(cwd: Path | None = None, *, now: int | None = None) -> list[dict[str, Any]]:
    """Report every live task binding this repository still owes retirement for.

    Retired records are included and labelled. One that matches this repository
    indicates the retirement was wrong, so hiding it would let a completion
    check pass while a real task was still unfinished.

    A binding is owed by the repository, not by the directory the caller happens
    to stand in. `find_binding` answers only for the current worktree, so a
    completion check asked from the pre-existing checkout would see nothing
    while a task worktree and its temporary branch were still present. This
    enumerates by repository identity instead, and reports a record whose lease
    has expired too: an expired lease retires nothing.
    """

    repository = repository_root(cwd)
    identity = repository_identity(repository)
    outstanding: list[dict[str, Any]] = []
    # Read in three passes, because a record can move between the live and the
    # retired directory while this runs. Scanning each directory once misses a
    # record that moves out of the one already read, and no single order is
    # safe in both directions. Taking the union of live, retired and live
    # again cannot lose a record to one move either way.
    live = {path.name for path in candidate_record_paths()}
    retired = {path.name for path in retired_record_paths()}
    live |= {path.name for path in candidate_record_paths()}
    directory = state_directory()
    for name in sorted(live | retired):
        # Both locations are derived from the name rather than taken from a
        # scan, so a record read here is found wherever it now sits, not only
        # where it sat when its directory was listed.
        record = None
        source = None
        # The live location is tried again after the retired one, because a
        # restore can move the record back between the two reads and leave
        # both of them looking at an empty path.
        live_path = directory / name
        for candidate in (live_path, directory / RETIRED_DIRECTORY_NAME / name, live_path):
            try:
                record = read_record(candidate)
            except (OSError, WorktreeError):
                # An unreadable record cannot be attributed to this repository,
                # so it is left to the manager's own actionable diagnostics. A
                # record that moved after its scan is read from the other side.
                continue
            source = candidate
            break
        if record is None:
            continue
        if record["repository_identity"] != identity:
            continue
        outstanding.append(
            {
                "retired": source.parent.name == RETIRED_DIRECTORY_NAME,
                "task": task_label(record["task"]),
                "worktree_path": record["worktree_path"],
                "branch_ref": record["branch_ref"],
                "source_ref": record["source_ref"],
                "worktree_present": Path(record["worktree_path"]).exists(),
                "lease_expired": record["owner"]["lease_expires_at"] <= (
                    int(time.time()) if now is None else now
                ),
            }
        )
    outstanding.sort(key=lambda entry: entry["worktree_path"])
    return outstanding


def assert_task_worktree(
    cwd: Path | None = None,
    *,
    kind: str | None = None,
    plan: str | None = None,
    now: int | None = None,
    action: str = "this repository write",
) -> TaskBinding:
    """Require that the caller runs inside its exact bound task worktree."""

    repository = repository_root(cwd)
    if repository == primary_worktree(repository):
        raise GuardError(
            f"{action} must not run in the pre-existing checkout. "
            + preparation_guidance(repository, plan)
        )
    binding = find_binding(repository, now=now)
    if binding is None:
        raise GuardError(
            f"{action} has no live task-worktree binding. "
            + preparation_guidance(repository, plan)
        )
    if kind is not None and binding.kind != kind:
        raise GuardError(
            f"{action} requires a {kind} task worktree but this worktree is bound to "
            f"{binding.label}. " + preparation_guidance(repository, plan)
        )
    if plan is not None:
        if binding.kind != PLAN_TASK or binding.task["identity"]["path"] != plan:
            raise GuardError(
                f"{action} is bound to {binding.label}, not {plan}. "
                + preparation_guidance(repository, plan)
            )
    return binding


# --- shared plan-identifier allocation across every linked worktree ---
#
# A worktree-local lock cannot serialize two linked checkouts of the same
# repository, and a worktree-local file scan sees neither another checkout's
# unpublished plan nor its in-flight allocation. Both the lock and the
# reservation ledger therefore live under the common Git directory, which every
# linked worktree of one repository shares and which is never a tracked path.
# Allocation reads the exact published source state plus live reservations, so
# two checkouts that hold the same published commit derive the same answer and
# the lock decides the race. A reservation is consumed only once its identifier
# appears in the published state, so an unpublished plan cannot lose its
# identifier to a later allocation merely because its lease aged.

SHARED_STATE_DIRECTORY_NAME = "project-agent-workflow"
PLAN_LOCK_NAME = "plan-lifecycle.lock"
RESERVATION_LEDGER_NAME = "plan-id-reservations.json"
RESERVATION_SCHEMA_VERSION = 1
RESERVATION_LEASE_SECONDS = 86_400
MAX_RESERVATIONS = 128
MAX_RESERVATION_BYTES = 262_144
MAX_PLAN_ID = 999
RESERVATION_KEYS = {
    "plan_id",
    "input_digest",
    "relative_path",
    "worktree_path",
    "owner",
    "reserved_at",
    "lease_expires_at",
    "written",
}
PLAN_ID_PREFIX_RE = re.compile(r"[0-9]{3}")
PLAN_FILE_RE = re.compile(r"docs/plan/(active|backlog|shelved)/([0-9]{3})-[^/]*\.md")
NESTED_PLAN_FILE_RE = re.compile(r"docs/plan/(checked|replanned)/.*?([0-9]{3})-[^/]*\.md")
CHECKED_INDEX_ROW_RE = re.compile(r"^([0-9]{3})\s")


def common_git_directory(repository: Path) -> Path:
    """Return the one directory every linked worktree of this repository shares."""

    return canonical_directory(
        git_text(repository, "rev-parse", "--path-format=absolute", "--git-common-dir"),
        label="common Git directory",
    )


def shared_lifecycle_directory(repository: Path) -> Path:
    """Return the private per-repository directory that holds shared lifecycle state."""

    directory = common_git_directory(repository) / SHARED_STATE_DIRECTORY_NAME
    if has_symlink_component(directory):
        raise WorktreeError("shared lifecycle directory contains a symlink component")
    if not directory.exists():
        directory.mkdir(mode=0o700, parents=True)
    require_owned_directory(directory, label="shared lifecycle directory")
    return directory


PLAN_LOCK_WAIT_SECONDS = 120
PLAN_LOCK_POLL_SECONDS = 0.05

_HELD_PLAN_LOCKS: dict[str, list[Any]] = {}


def acquire_plan_lock(path: Path, *, wait_seconds: int = PLAN_LOCK_WAIT_SECONDS):
    """Take the shared lock within a bounded wait instead of blocking forever.

    This lock is now shared by every linked worktree, so an unbounded wait would
    let one stuck checkout hang plan authoring everywhere with no explanation.
    A bounded wait reports which lock is held instead.
    """

    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise WorktreeError(
                        f"the shared plan lifecycle lock stayed held for {wait_seconds}s: {path}. "
                        "Another checkout of this repository is still holding it."
                    ) from None
                time.sleep(PLAN_LOCK_POLL_SECONDS)
    except BaseException:
        os.close(descriptor)
        raise
    return os.fdopen(descriptor, "r+", encoding="utf-8")


@contextlib.contextmanager
def plan_lifecycle_lock(repository: Path):
    """Hold the exclusive plan lifecycle lock shared by every linked worktree.

    `flock` is held per open file description, so a second `open` of the same
    lock inside one process would block against itself rather than nest. A
    lifecycle command that allocates an identifier while already holding the
    lock is ordinary, so re-entry in the same process reuses the held
    description and releases it only when the outermost holder exits.
    """

    key = str(shared_lifecycle_directory(repository) / PLAN_LOCK_NAME)
    held = _HELD_PLAN_LOCKS.get(key)
    if held is not None:
        held[0] += 1
        try:
            yield
        finally:
            held[0] -= 1
        return
    handle = acquire_plan_lock(Path(key))
    _HELD_PLAN_LOCKS[key] = [1, handle]
    try:
        yield
    finally:
        del _HELD_PLAN_LOCKS[key]
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def plan_ids_in_commit(repository: Path, commit: str) -> set[int]:
    """Return every plan identifier present in one exact published commit."""

    ids: set[int] = set()
    listing = git(
        repository, "ls-tree", "-r", "--name-only", "-z", commit, "--", "docs/plan", check=False
    )
    if listing.returncode != 0:
        return ids
    for name in listing.stdout.decode("utf-8", "replace").split("\0"):
        if not name:
            continue
        match = PLAN_FILE_RE.fullmatch(name) or NESTED_PLAN_FILE_RE.fullmatch(name)
        if match is not None:
            ids.add(int(match.group(2)))
    index = git(repository, "show", f"{commit}:docs/plan/checked.md", check=False)
    if index.returncode == 0:
        for line in index.stdout.decode("utf-8", "replace").splitlines():
            match = CHECKED_INDEX_ROW_RE.match(line)
            if match is not None:
                ids.add(int(match.group(1)))
    return ids


def published_source_commit(repository: Path) -> str | None:
    """Return the commit whose plan state a new identifier must not collide with.

    A bound task worktree allocates against its recorded source ref, which is the
    branch its work will publish to. Any other checkout allocates against its own
    committed HEAD. Neither reads the working tree, so an uncommitted or
    unpublished local file never silently claims an identifier without a
    reservation.
    """

    try:
        binding = find_binding(repository)
    except WorktreeError:
        binding = None
    if binding is not None:
        tip = exact_ref_tip(repository, binding.record["source_ref"])
        if tip is not None:
            return tip
    head = git(repository, "rev-parse", "--verify", "--quiet", "HEAD^{commit}", check=False)
    resolved = head.stdout.decode("utf-8", "replace").strip()
    return resolved if head.returncode == 0 and OID_RE.fullmatch(resolved) else None


def reservation_ledger_path(repository: Path) -> Path:
    return shared_lifecycle_directory(repository) / RESERVATION_LEDGER_NAME


def read_reservations(path: Path) -> list[dict[str, Any]]:
    """Return the recorded reservations, refusing a malformed or oversized ledger."""

    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file():
        raise WorktreeError("plan-id reservation ledger must be a regular non-symlink file")
    metadata = path.stat()
    if metadata.st_nlink != 1:
        raise WorktreeError("plan-id reservation ledger must be single-linked")
    if metadata.st_size > MAX_RESERVATION_BYTES:
        raise WorktreeError("plan-id reservation ledger is too large")
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_json_keys
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorktreeError(f"plan-id reservation ledger is unreadable: {exc}") from exc
    if not isinstance(document, dict) or document.get("schema_version") != RESERVATION_SCHEMA_VERSION:
        raise WorktreeError("plan-id reservation ledger schema is not supported")
    entries = document.get("reservations")
    if not isinstance(entries, list) or len(entries) > MAX_RESERVATIONS:
        raise WorktreeError("plan-id reservation ledger is malformed")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != RESERVATION_KEYS:
            raise WorktreeError("plan-id reservation entry is malformed")
        if PLAN_ID_PREFIX_RE.fullmatch(str(entry["plan_id"])) is None:
            raise WorktreeError("plan-id reservation entry carries a malformed identifier")
        if DIGEST_RE.fullmatch(str(entry["input_digest"])) is None:
            raise WorktreeError("plan-id reservation entry carries a malformed input digest")
        if not isinstance(entry["reserved_at"], int) or not isinstance(
            entry["lease_expires_at"], int
        ):
            raise WorktreeError("plan-id reservation entry carries a malformed lease")
        if not isinstance(entry["written"], bool):
            raise WorktreeError("plan-id reservation entry carries a malformed written flag")
    return entries


def write_reservations(path: Path, entries: list[dict[str, Any]]) -> None:
    atomic_write(
        path,
        {"schema_version": RESERVATION_SCHEMA_VERSION, "reservations": entries},
    )


def live_reservations(
    repository: Path, entries: list[dict[str, Any]], published: set[int], now: int
) -> list[dict[str, Any]]:
    """Drop reservations that publication consumed or that no live holder owns.

    A written but unpublished plan keeps its identifier while its holding
    worktree is still registered, because the plan file exists and would
    otherwise lose its number to a later allocation. A reservation that never
    became a plan file is kept only for its lease: the pre-existing checkout is
    always registered, so retaining unwritten reservations by registration alone
    would let a read-only re-check leak an identifier permanently and eventually
    fill the ledger.
    """

    registered = {
        str(registered_worktree_path(record)) for record in parse_worktrees(repository)
    }
    retained: list[dict[str, Any]] = []
    for entry in entries:
        if int(entry["plan_id"]) in published:
            continue
        if entry["lease_expires_at"] > now:
            retained.append(entry)
            continue
        relative_path = entry["relative_path"]
        materialized = False
        if relative_path and entry["worktree_path"] in registered:
            candidate = Path(entry["worktree_path"]) / relative_path
            try:
                metadata = os.lstat(candidate)
            except OSError:
                pass
            else:
                materialized = stat.S_ISREG(metadata.st_mode)
        if (
            entry["worktree_path"] in registered
            and (entry["written"] or materialized)
        ):
            retained.append(entry)
    return retained


def smallest_available_plan_id(taken: set[int]) -> str:
    value = 1
    while value in taken:
        value += 1
    if value > MAX_PLAN_ID:
        raise WorktreeError("no plan identifier remains available")
    return f"{value:03d}"


def reservation_relative_path(plan_id: str, lifecycle: str, slug: str) -> str:
    """Describe the plan path a reservation is held for, or nothing when unknown."""

    if not lifecycle or not slug:
        return ""
    candidate = f"docs/plan/{lifecycle}/{plan_id}-{slug}.md"
    return candidate if len(candidate) <= 256 else ""


def reserve_plan_id(
    repository: Path,
    *,
    input_digest: str,
    lifecycle: str = "",
    slug: str = "",
    owner: str | None = None,
    now: int | None = None,
    lease_seconds: int = RESERVATION_LEASE_SECONDS,
) -> dict[str, Any]:
    """Reserve the smallest free identifier for one exact checked authoring input.

    The reservation is keyed by the checked input bytes, so the identifier a
    check reports is the identifier its own write consumes. Re-reserving the same
    input from the same worktree renews rather than advances, which keeps check
    and write idempotent while a competing worktree still cannot take that
    identifier.
    """

    if DIGEST_RE.fullmatch(input_digest) is None:
        raise WorktreeError("plan-id reservation requires a sha256:<64 hex> input digest")
    moment = int(time.time()) if now is None else now
    if not 0 < lease_seconds <= MAX_LEASE_SECONDS:
        raise WorktreeError("plan-id reservation lease is out of range")
    ledger = reservation_ledger_path(repository)
    with plan_lifecycle_lock(repository):
        commit = published_source_commit(repository)
        published = plan_ids_in_commit(repository, commit) if commit is not None else set()
        entries = live_reservations(repository, read_reservations(ledger), published, moment)
        holder = str(repository)
        mine = [
            entry
            for entry in entries
            if entry["input_digest"] == input_digest
            and entry["worktree_path"] == holder
            and not entry["written"]
        ]
        if mine:
            reservation = dict(mine[0])
            reservation["lease_expires_at"] = moment + lease_seconds
            entries = [entry for entry in entries if entry not in mine]
        else:
            taken = published | {int(entry["plan_id"]) for entry in entries}
            reservation = {
                "plan_id": smallest_available_plan_id(taken),
                "input_digest": input_digest,
                "relative_path": "",
                "worktree_path": holder,
                "owner": owner or f"pid:{os.getpid()}",
                "reserved_at": moment,
                "lease_expires_at": moment + lease_seconds,
                "written": False,
            }
        reservation["relative_path"] = (
            reservation_relative_path(reservation["plan_id"], lifecycle, slug)
            or reservation["relative_path"]
        )
        entries.append(reservation)
        if len(entries) > MAX_RESERVATIONS:
            raise WorktreeError("plan-id reservation ledger is full")
        write_reservations(ledger, sorted(entries, key=lambda entry: entry["plan_id"]))
    return reservation


def mark_plan_id_written(
    repository: Path, *, input_digest: str, plan_id: str, now: int | None = None
) -> None:
    """Record that a reservation produced its plan file in the working tree.

    The identifier stays reserved so no other linked worktree can take it before
    publication, but it stops answering for its authoring input: a later check of
    the same input must allocate a new identifier rather than name the plan that
    already exists.
    """

    moment = int(time.time()) if now is None else now
    ledger = reservation_ledger_path(repository)
    with plan_lifecycle_lock(repository):
        commit = published_source_commit(repository)
        published = plan_ids_in_commit(repository, commit) if commit is not None else set()
        entries = live_reservations(repository, read_reservations(ledger), published, moment)
        holder = str(repository)
        matches = 0
        for entry in entries:
            if (
                entry["input_digest"] == input_digest
                and entry["worktree_path"] == holder
                and entry["plan_id"] == plan_id
            ):
                matches += 1
                entry["written"] = True
        if matches != 1:
            raise WorktreeError(
                "no unique plan-id reservation matches the written plan"
            )
        if matches:
            write_reservations(ledger, sorted(entries, key=lambda item: item["plan_id"]))


def require_plan_id_reservation(
    repository: Path,
    *,
    input_digest: str,
    plan_id: str,
    relative_path: str,
    now: int | None = None,
) -> None:
    """Require one live reservation bound to this worktree and successor path."""

    if DIGEST_RE.fullmatch(input_digest) is None:
        raise WorktreeError("plan-id reservation requires a sha256:<64 hex> input digest")
    if re.fullmatch(r"[0-9]{3}", plan_id) is None:
        raise WorktreeError("plan-id reservation carries an invalid plan identifier")
    moment = int(time.time()) if now is None else now
    ledger = reservation_ledger_path(repository)
    with plan_lifecycle_lock(repository):
        commit = published_source_commit(repository)
        published = plan_ids_in_commit(repository, commit) if commit is not None else set()
        entries = live_reservations(repository, read_reservations(ledger), published, moment)
        matches = [
            entry
            for entry in entries
            if entry["input_digest"] == input_digest
            and entry["plan_id"] == plan_id
            and entry["relative_path"] == relative_path
            and entry["worktree_path"] == str(repository)
            and not entry["written"]
        ]
    if len(matches) != 1:
        raise WorktreeError(
            "no live plan-id reservation matches this worktree, input, and successor path"
        )


def claim_plan_id_reservations(
    repository: Path,
    *,
    reservations: list[dict[str, str]],
    now: int | None = None,
) -> None:
    """Atomically make checked successor reservations durable before repository writes."""

    moment = int(time.time()) if now is None else now
    ledger = reservation_ledger_path(repository)
    with plan_lifecycle_lock(repository):
        commit = published_source_commit(repository)
        published = plan_ids_in_commit(repository, commit) if commit is not None else set()
        entries = live_reservations(repository, read_reservations(ledger), published, moment)
        selected: list[dict[str, Any]] = []
        for reservation in reservations:
            matches = [
                entry
                for entry in entries
                if entry["input_digest"] == reservation["input_digest"]
                and entry["worktree_path"] == str(repository)
                and entry["plan_id"] == reservation["id"]
                and entry["relative_path"] == reservation["path"]
            ]
            if len(matches) != 1:
                raise WorktreeError(
                    "no unique live plan-id reservation matches the transaction claim"
                )
            selected.append(matches[0])
        if len({entry["plan_id"] for entry in selected}) != len(selected):
            raise WorktreeError("transaction claims a duplicate plan-id reservation")
        for entry in selected:
            entry["written"] = True
        if selected:
            write_reservations(ledger, sorted(entries, key=lambda item: item["plan_id"]))


def release_plan_id_reservations(
    repository: Path,
    *,
    reservations: list[dict[str, str]],
    now: int | None = None,
) -> None:
    """Atomically return rolled-back transaction claims to renewable leases."""

    moment = int(time.time()) if now is None else now
    ledger = reservation_ledger_path(repository)
    with plan_lifecycle_lock(repository):
        commit = published_source_commit(repository)
        published = plan_ids_in_commit(repository, commit) if commit is not None else set()
        entries = live_reservations(repository, read_reservations(ledger), published, moment)
        selected: list[dict[str, Any]] = []
        missing = 0
        for reservation in reservations:
            matches = [
                entry
                for entry in entries
                if entry["input_digest"] == reservation["input_digest"]
                and entry["worktree_path"] == str(repository)
                and entry["plan_id"] == reservation["id"]
                and entry["relative_path"] == reservation["path"]
            ]
            if not matches:
                missing += 1
                continue
            if len(matches) != 1:
                raise WorktreeError(
                    "no unique plan-id reservation matches the rollback claim"
                )
            selected.append(matches[0])
        if missing:
            if missing == len(reservations):
                return
            raise WorktreeError(
                "rollback claims only a partial successor reservation set"
            )
        for entry in selected:
            entry["written"] = False
            entry["lease_expires_at"] = moment + RESERVATION_LEASE_SECONDS
        if selected:
            write_reservations(ledger, sorted(entries, key=lambda item: item["plan_id"]))


def release_plan_id_reservation(
    repository: Path,
    *,
    input_digest: str,
    plan_id: str,
    now: int | None = None,
) -> None:
    """Return a pre-commit reservation claim to a renewable unwritten lease."""

    moment = int(time.time()) if now is None else now
    ledger = reservation_ledger_path(repository)
    with plan_lifecycle_lock(repository):
        commit = published_source_commit(repository)
        published = plan_ids_in_commit(repository, commit) if commit is not None else set()
        entries = live_reservations(repository, read_reservations(ledger), published, moment)
        matches = 0
        for entry in entries:
            if (
                entry["input_digest"] == input_digest
                and entry["worktree_path"] == str(repository)
                and entry["plan_id"] == plan_id
            ):
                matches += 1
                entry["written"] = False
                entry["lease_expires_at"] = moment + RESERVATION_LEASE_SECONDS
        if matches != 1:
            raise WorktreeError(
                "no unique plan-id reservation matches the rollback claim"
            )
        write_reservations(ledger, sorted(entries, key=lambda item: item["plan_id"]))


def reserved_plan_ids(repository: Path, *, now: int | None = None) -> set[int]:
    """Return the identifiers currently held by a live reservation."""

    moment = int(time.time()) if now is None else now
    with plan_lifecycle_lock(repository):
        commit = published_source_commit(repository)
        published = plan_ids_in_commit(repository, commit) if commit is not None else set()
        entries = live_reservations(repository, read_reservations(reservation_ledger_path(repository)), published, moment)
    return {int(entry["plan_id"]) for entry in entries}


# --- enforcement scope ---
#
# A binding names a repository by its canonical remote.origin.url, so a
# repository without one can neither carry an ownership record nor ever satisfy
# the boundary. Enforcing there would refuse every write unconditionally rather
# than govern the repository, which is why an unidentifiable repository reports
# itself ungoverned instead of failing closed. That is a property of the binding
# mechanism, not a convenience switch: the environment can only raise
# enforcement, never lower it, and a repository that does have an identity is
# always governed.

REQUIRE_TASK_WORKTREE_VARIABLE = "PROJECT_AGENT_WORKFLOW_REQUIRE_TASK_WORKTREE"


def enforcement_scope(repository: Path) -> tuple[bool, str]:
    """Report whether this repository can be governed by a task binding."""

    try:
        repository_identity(repository)
    except (OSError, UnicodeError, WorktreeError) as exc:
        if os.environ.get(REQUIRE_TASK_WORKTREE_VARIABLE) == "1":
            return True, f"{REQUIRE_TASK_WORKTREE_VARIABLE}=1 requires enforcement"
        return False, f"repository cannot carry a task binding: {exc}"
    return True, "repository identity is resolvable"


def require_task_worktree(
    cwd: Path | None = None,
    *,
    kind: str | None = None,
    plan: str | None = None,
    now: int | None = None,
    action: str = "this repository write",
) -> TaskBinding | None:
    """Assert the task-worktree boundary wherever the repository is governed.

    Returns the verified binding, or ``None`` when the repository is outside
    enforcement scope. Callers that must distinguish the two report the reason
    from :func:`enforcement_scope` rather than treating ``None`` as success.
    """

    try:
        repository = repository_root(cwd)
    except (OSError, UnicodeError, WorktreeError):
        # A directory that is not a Git worktree cannot carry a binding, which
        # is the same reason an unnameable repository is left alone.
        return None
    governed, _ = enforcement_scope(repository)
    if not governed:
        return None
    return assert_task_worktree(repository, kind=kind, plan=plan, now=now, action=action)


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    command = arguments[0] if arguments else "check"
    if command not in {"check", "describe", "require", "outstanding"}:
        print(
            "usage: worktree_guard.py [check|describe|require|outstanding] "
            "[--plan PATH] [--action TEXT]",
            file=sys.stderr,
        )
        return 2
    action = "this repository write"
    if "--action" in arguments:
        index = arguments.index("--action")
        if index + 1 >= len(arguments):
            print("worktree guard failed: --action needs a value", file=sys.stderr)
            return 2
        action = arguments[index + 1]
    plan = None
    if "--plan" in arguments:
        index = arguments.index("--plan")
        if index + 1 >= len(arguments):
            print("worktree guard failed: --plan needs a value", file=sys.stderr)
            return 2
        plan = arguments[index + 1]
    try:
        if command == "outstanding":
            # A repository that cannot name itself can never hold a record, so
            # asking it what it owes must answer "nothing" rather than fail.
            # The completion gate treats a failure as a refusal, and refusing
            # here would block every turn of a project that this guard has
            # deliberately left outside enforcement. A directory that is not a
            # Git worktree at all is the same case: `copier copy` produces one
            # before the project runs `git init`.
            try:
                governed, reason = enforcement_scope(repository_root())
            except (OSError, UnicodeError, WorktreeError) as exc:
                governed, reason = False, f"not a Git worktree: {exc}"
            if not governed:
                print(
                    json.dumps(
                        {"outstanding": [], "enforced": False, "reason": reason},
                        sort_keys=True,
                    )
                )
                return 0
            entries = outstanding_tasks()
            print(json.dumps({"outstanding": entries, "enforced": True}, sort_keys=True))
            return 0
        if command == "describe":
            binding = find_binding()
            print(json.dumps({"bound": binding is not None} | (binding.summary() if binding else {}), sort_keys=True))
            return 0
        if command == "require":
            binding = require_task_worktree(action=action, plan=plan)
            if binding is None:
                try:
                    _, reason = enforcement_scope(repository_root())
                except (OSError, UnicodeError, WorktreeError) as exc:
                    reason = f"not a Git worktree: {exc}"
                print(json.dumps({"enforced": False, "reason": reason}, sort_keys=True))
                return 0
            print(json.dumps({"enforced": True} | binding.summary(), sort_keys=True))
            return 0
        binding = assert_task_worktree(plan=plan, action=action)
    except (OSError, UnicodeError, WorktreeError) as exc:
        print(f"worktree guard failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(binding.summary(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
