#!/usr/bin/env python3
"""Create, inspect, and resume parent-owned Git worktrees."""

from __future__ import annotations

import argparse
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
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = 1
MAX_RECORD_BYTES = 65_536
MAX_LEASE_SECONDS = 86_400
OWNER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
OID_RE = re.compile(r"[0-9a-f]{40,64}")
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
BRANCH_REF_RE = re.compile(r"refs/heads/[^\x00-\x20~^:?*\\\[]+")
RECORD_KEYS = {
    "schema_version",
    "repository_identity",
    "plan",
    "start_commit",
    "accepted_tip",
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
PLAN_KEYS = {"path", "digest", "blob_oid"}
OWNER_KEYS = {"id", "lease_expires_at"}
WORKTREE_IDENTITY_KEYS = {"git_dir", "git_dir_device", "git_dir_inode"}
WORKTREE_IDENTITY_KEYS |= {
    "worktree_device",
    "worktree_inode",
    "worktree_owner",
    "worktree_mode",
}


class WorktreeError(ValueError):
    """A fail-closed managed-worktree error."""


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


def validate_allowed_root(raw: str, repository: Path) -> Path:
    allowed_root = require_owned_directory(Path(raw), label="allowed root")
    worktrees = parse_worktrees(repository)
    if not worktrees:
        raise WorktreeError("Git reported no registered worktrees")
    primary = canonical_directory(str(worktrees[0].get("worktree", "")), label="primary worktree")
    forbidden = {
        Path("/").resolve(),
        Path(pwd.getpwuid(os.getuid()).pw_dir).resolve(),
        primary,
    }
    if (
        allowed_root in forbidden
        or path_is_strict_descendant(allowed_root, primary)
        or path_is_strict_descendant(primary, allowed_root)
    ):
        raise WorktreeError("allowed root is a forbidden broad or repository path")
    for record in worktrees:
        registered = registered_worktree_path(record)
        if allowed_root == registered or path_is_strict_descendant(
            allowed_root, registered
        ):
            raise WorktreeError("allowed root must not be a registered worktree or its descendant")
    return allowed_root


def normalize_plan_path(raw: str) -> str:
    value = PurePosixPath(raw)
    if (
        value.is_absolute()
        or raw in {"", "."}
        or any(part in {"", ".", ".."} for part in value.parts)
        or not re.fullmatch(r"docs/plan/active/[0-9]{3}-[a-z0-9][a-z0-9-]*\.md", raw)
    ):
        raise WorktreeError("plan path must name one normalized active numbered plan")
    return raw


def normalize_branch(raw: str, repository: Path) -> tuple[str, str]:
    if raw.startswith("refs/heads/"):
        short = raw.removeprefix("refs/heads/")
    else:
        short = raw
    if not short or git(repository, "check-ref-format", "--branch", short, check=False).returncode:
        raise WorktreeError("branch name is not a valid exact local branch")
    branch_ref = f"refs/heads/{short}"
    if BRANCH_REF_RE.fullmatch(branch_ref) is None:
        raise WorktreeError("branch name is not a valid exact local branch")
    return short, branch_ref


def canonical_origin(repository: Path) -> str:
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


def repository_root() -> Path:
    root = git_text(Path.cwd(), "rev-parse", "--show-toplevel")
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


def committed_plan(repository: Path, raw_plan: str, start_commit: str) -> dict[str, str]:
    plan = normalize_plan_path(raw_plan)
    plan_path = repository / plan
    if has_symlink_component(plan_path) or plan_path.is_symlink() or not plan_path.is_file():
        raise WorktreeError("plan must be a regular non-symlink file")
    committed = plan_identity_at_commit(repository, plan, start_commit)
    if committed["digest"] != digest_bytes(plan_path.read_bytes()):
        raise WorktreeError("plan must match its committed bytes at the selected start commit")
    return committed


def plan_identity_at_commit(
    repository: Path, plan: str, start_commit: str
) -> dict[str, str]:
    blob_oid = git_text(repository, "rev-parse", f"{start_commit}:{plan}")
    if not OID_RE.fullmatch(blob_oid):
        raise WorktreeError("committed plan blob is unavailable")
    blob = git(repository, "cat-file", "blob", blob_oid).stdout
    return {
        "path": plan,
        "digest": digest_bytes(blob),
        "blob_oid": blob_oid,
    }


def validate_target(
    raw: str,
    allowed_root: Path,
    *,
    must_exist: bool,
    allow_existing: bool = False,
) -> Path:
    target = Path(raw)
    if not target.is_absolute():
        raise WorktreeError("worktree path must be absolute")
    normalized = Path(os.path.normpath(str(target)))
    if normalized != target or has_symlink_component(target):
        raise WorktreeError("worktree path must be normalized and symlink-free")
    if not path_is_strict_descendant(target, allowed_root):
        raise WorktreeError("worktree path must be a strict descendant of the allowed root")
    if must_exist:
        return canonical_directory(str(target), label="managed worktree")
    if target.exists() or target.is_symlink():
        if not allow_existing:
            raise WorktreeError("new worktree path already exists")
        existing = canonical_directory(str(target), label="interrupted worktree")
        if existing != target:
            raise WorktreeError("interrupted worktree path is not canonical")
    parent = canonical_directory(str(target.parent), label="worktree parent")
    if not path_is_strict_descendant(parent, allowed_root) and parent != allowed_root:
        raise WorktreeError("worktree parent is outside the allowed root")
    current = parent
    while True:
        require_owned_directory(current, label="worktree parent")
        if current == allowed_root:
            break
        current = current.parent
    return target


def metadata_paths(identity: dict[str, Any], plan_path: str) -> dict[str, Path]:
    key = hashlib.sha256(
        canonical_json(
            {
                "common_git_dir": identity["common_git_dir"],
                "common_git_dir_device": identity["common_git_dir_device"],
                "common_git_dir_inode": identity["common_git_dir_inode"],
                "plan": plan_path,
            }
        )
    ).hexdigest()
    account_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    directory = account_home / ".local/state/project-agent-workflow/parent-worktrees"
    return {
        "directory": directory,
        "record": directory / f"{key}.json",
        "journal": directory / f"{key}.journal.json",
        "lock": directory / f"{key}.lock",
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


def validate_record(value: Any, *, allow_pending: bool = False) -> None:
    if not isinstance(value, dict) or set(value) != RECORD_KEYS:
        raise WorktreeError("ownership record schema is invalid")
    if value["schema_version"] != SCHEMA_VERSION:
        raise WorktreeError("ownership record version is unsupported")
    if not isinstance(value["repository_identity"], dict) or set(
        value["repository_identity"]
    ) != REPOSITORY_KEYS:
        raise WorktreeError("ownership record repository identity is invalid")
    if not isinstance(value["plan"], dict) or set(value["plan"]) != PLAN_KEYS:
        raise WorktreeError("ownership record plan identity is invalid")
    if not isinstance(value["owner"], dict) or set(value["owner"]) != OWNER_KEYS:
        raise WorktreeError("ownership record owner lease is invalid")
    worktree_identity = value["worktree_identity"]
    if not isinstance(worktree_identity, dict) or set(worktree_identity) != WORKTREE_IDENTITY_KEYS:
        raise WorktreeError("ownership record worktree identity is invalid")
    identity_values = tuple(worktree_identity.values())
    empty_identity = all(item is None for item in identity_values)
    target_identity = (
        type(worktree_identity["worktree_device"]) is int
        and type(worktree_identity["worktree_inode"]) is int
        and type(worktree_identity["worktree_owner"]) is int
        and type(worktree_identity["worktree_mode"]) is int
    )
    pending_identity = (
        all(
            worktree_identity[key] is None
            for key in ("git_dir", "git_dir_device", "git_dir_inode")
        )
        and target_identity
    )
    complete_identity = (
        isinstance(worktree_identity["git_dir"], str)
        and Path(worktree_identity["git_dir"]).is_absolute()
        and type(worktree_identity["git_dir_device"]) is int
        and type(worktree_identity["git_dir_inode"]) is int
        and target_identity
    )
    if not (
        complete_identity
        or (allow_pending and (empty_identity or pending_identity))
    ):
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
    if not isinstance(value["branch_ref"], str) or BRANCH_REF_RE.fullmatch(
        value["branch_ref"]
    ) is None:
        raise WorktreeError("ownership record branch is invalid")
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


def exact_ref_tip(repository: Path, branch_ref: str) -> str | None:
    completed = git(repository, "rev-parse", "--verify", f"{branch_ref}^{{commit}}", check=False)
    if completed.returncode != 0:
        return None
    value = completed.stdout.decode("ascii", "strict").strip()
    return value if OID_RE.fullmatch(value) else None


def is_ancestor(repository: Path, ancestor: str, descendant: str) -> bool:
    return (
        git(repository, "merge-base", "--is-ancestor", ancestor, descendant, check=False).returncode
        == 0
    )


def reject_registered_worktree_ancestry(
    records: list[dict[str, Any]], target: Path
) -> None:
    for record in records:
        registered = registered_worktree_path(record)
        if target == registered or path_is_strict_descendant(target, registered):
            raise WorktreeError(
                "worktree path must not be a registered worktree or its descendant"
            )


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


def status_digest(worktree: Path) -> str:
    index_path = Path(
        git_text(worktree, "rev-parse", "--path-format=absolute", "--git-path", "index")
    )
    return digest_bytes(index_path.read_bytes() + b"\0" + raw_worktree_digest(worktree))


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


def reject_checkout_filters(repository: Path, start_commit: str) -> None:
    if git_text(repository, "rev-parse", "--is-shallow-repository") != "false":
        raise WorktreeError("managed worktree creation rejects shallow repositories")
    common = Path(
        git_text(repository, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve(strict=True)
    if (common / "info/grafts").exists():
        raise WorktreeError("managed worktree creation rejects grafted history")
    tree_paths = git(repository, "ls-tree", "-r", "--name-only", "-z", start_commit).stdout
    if not tree_paths:
        return
    attributes = subprocess.run(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-C",
            str(repository),
            "check-attr",
            "-z",
            f"--source={start_commit}",
            "--stdin",
            "filter",
        ],
        input=tree_paths,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_environment(),
    )
    if attributes.returncode != 0:
        raise WorktreeError("Git could not inspect checkout filter attributes")
    fields = attributes.stdout.split(b"\0")
    for index in range(0, len(fields) - 2, 3):
        value = fields[index + 2]
        if value not in {b"", b"unspecified", b"unset"}:
            raise WorktreeError("managed worktree creation rejects checkout filters")


def verify_history(repository: Path, start: str, accepted: str, tip: str) -> None:
    if not is_ancestor(repository, start, accepted) or not is_ancestor(
        repository, accepted, tip
    ):
        raise WorktreeError("managed branch history no longer contains the bound commits")
    payload = git_text(repository, "rev-list", "--parents", f"{accepted}..{tip}")
    for line in payload.splitlines():
        fields = line.split()
        for parent in fields[1:]:
            if not is_ancestor(repository, start, parent):
                raise WorktreeError("managed branch contains unrelated merged history")


def validate_lease(owner: dict[str, Any], requested_owner: str, now: int) -> None:
    if owner["id"] != requested_owner and owner["lease_expires_at"] > now:
        raise WorktreeError("managed worktree already has a different active owner")


def verify_record_context(
    repository: Path,
    allowed_root: Path,
    record: dict[str, Any],
) -> tuple[Path, str]:
    identity = repository_identity(repository)
    if record["repository_identity"] != identity:
        raise WorktreeError("ownership record belongs to another repository or clone")
    if record["allowed_root"] != str(allowed_root):
        raise WorktreeError("ownership record allowed root changed or mismatched")
    target = validate_target(record["worktree_path"], allowed_root, must_exist=True)
    records = parse_worktrees(repository)
    registered = find_registered_worktree(records, target)
    if registered is None:
        raise WorktreeError("managed worktree is no longer registered")
    if registered.get("branch") != record["branch_ref"]:
        raise WorktreeError("managed worktree branch changed or became detached")
    tip = exact_ref_tip(repository, record["branch_ref"])
    if tip is None or registered.get("HEAD") != tip:
        raise WorktreeError("managed branch tip is unavailable or ambiguous")
    if git_text(target, "rev-parse", "--show-toplevel") != str(target):
        raise WorktreeError("managed worktree root changed or mismatched")
    if record["worktree_identity"] != worktree_identity(target):
        raise WorktreeError("managed worktree registration was replaced")
    return target, tip


def create_record(
    repository: Path,
    allowed_root: Path,
    target: Path,
    plan: dict[str, str],
    branch_ref: str,
    start_commit: str,
    owner_id: str,
    lease_seconds: int,
    bound_worktree_identity: dict[str, Any],
) -> dict[str, Any]:
    return add_content_digest(
        {
            "schema_version": SCHEMA_VERSION,
            "repository_identity": repository_identity(repository),
            "plan": plan,
            "start_commit": start_commit,
            "accepted_tip": start_commit,
            "branch_ref": branch_ref,
            "allowed_root": str(allowed_root),
            "worktree_path": str(target),
            "worktree_identity": bound_worktree_identity,
            "owner": {
                "id": owner_id,
                "lease_expires_at": int(time.time()) + lease_seconds,
            },
        }
    )


def raw_path_digest(path: Path) -> bytes:
    metadata = path.lstat()
    hasher = hashlib.sha256()
    hasher.update(str(stat.S_IFMT(metadata.st_mode)).encode("ascii"))
    hasher.update(b"\0")
    hasher.update(str(stat.S_IMODE(metadata.st_mode)).encode("ascii"))
    hasher.update(b"\0")
    if stat.S_ISREG(metadata.st_mode):
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                hasher.update(chunk)
    elif stat.S_ISLNK(metadata.st_mode):
        hasher.update(os.readlink(path).encode("utf-8", "surrogateescape"))
    elif stat.S_ISDIR(metadata.st_mode):
        if (path / ".git").exists():
            index_digest, worktree_digest = snapshot_source(path)
            hasher.update(b"git-worktree\0")
            hasher.update(index_digest)
            hasher.update(b"\0")
            hasher.update(worktree_digest)
        else:
            hasher.update(b"directory")
    else:
        raise WorktreeError("tracked or untracked source path has an unsupported file type")
    return hasher.digest()


def raw_worktree_digest(repository: Path) -> bytes:
    payload = git(
        repository,
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    ).stdout
    hasher = hashlib.sha256()
    for raw in sorted(item for item in payload.split(b"\0") if item):
        relative = raw.decode("utf-8", "surrogateescape")
        candidate = PurePosixPath(relative)
        if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
            raise WorktreeError("Git reported an unsafe source path")
        path = repository / relative
        hasher.update(raw)
        hasher.update(b"\0")
        if path.exists() or path.is_symlink():
            hasher.update(raw_path_digest(path))
        else:
            hasher.update(b"missing")
        hasher.update(b"\0")
    return hasher.digest()


def snapshot_source(repository: Path) -> tuple[bytes, bytes]:
    index_path = Path(
        git_text(repository, "rev-parse", "--path-format=absolute", "--git-path", "index")
    )
    index_digest = digest_bytes(index_path.read_bytes()).encode("ascii")
    return (
        index_digest,
        raw_worktree_digest(repository),
    )


def create(args: argparse.Namespace) -> None:
    repository = repository_root()
    allowed_root = validate_allowed_root(args.allowed_root, repository)
    target = validate_target(
        args.worktree,
        allowed_root,
        must_exist=False,
        allow_existing=True,
    )
    start_commit = git_text(repository, "rev-parse", "--verify", "HEAD^{commit}")
    plan = committed_plan(repository, args.plan, start_commit)
    reject_checkout_filters(repository, start_commit)
    branch_short, branch_ref = normalize_branch(args.branch, repository)
    identity = repository_identity(repository)
    paths = metadata_paths(identity, plan["path"])
    ensure_metadata_directory(paths["directory"])
    allowed_identity = directory_identity(allowed_root)
    parent_identity = directory_identity(target.parent)
    with locked_file(paths["lock"]):
        if paths["record"].exists():
            raise WorktreeError("an ownership record already exists for this plan")
        journal = add_content_digest(
            {
                "schema_version": SCHEMA_VERSION,
                "repository_identity": identity,
                "plan": plan,
                "start_commit": start_commit,
                "accepted_tip": start_commit,
                "branch_ref": branch_ref,
                "allowed_root": str(allowed_root),
                "worktree_path": str(target),
                "worktree_identity": {
                    "git_dir": None,
                    "git_dir_device": None,
                    "git_dir_inode": None,
                    "worktree_device": None,
                    "worktree_inode": None,
                    "worktree_owner": None,
                    "worktree_mode": None,
                },
                "owner": {
                    "id": args.owner_id,
                    "lease_expires_at": int(time.time()) + args.lease_seconds,
                },
            }
        )
        existing_journal: dict[str, Any] | None = None
        if paths["journal"].exists():
            existing_journal = read_record(paths["journal"])
            old_target = Path(existing_journal["worktree_path"])
            old_registered = find_registered_worktree(
                parse_worktrees(repository), old_target
            )
            if (
                existing_journal["owner"]["lease_expires_at"] <= int(time.time())
                and all(
                    value is None
                    for value in existing_journal["worktree_identity"].values()
                )
                and not old_target.exists()
                and not old_target.is_symlink()
                and old_registered is None
            ):
                paths["journal"].unlink()
                existing_journal = None
        if existing_journal is not None:
            immutable_fields = (
                "schema_version",
                "repository_identity",
                "plan",
                "start_commit",
                "accepted_tip",
                "branch_ref",
                "allowed_root",
                "worktree_path",
            )
            if (
                any(
                    existing_journal[field] != journal[field]
                    for field in immutable_fields
                )
                or existing_journal["owner"]["id"] != args.owner_id
            ):
                raise WorktreeError("an interrupted create journal has different bound facts")
        else:
            if target.exists() or target.is_symlink():
                raise WorktreeError("new worktree path already exists")
            existing_journal = journal
        records = parse_worktrees(repository)
        registered = find_registered_worktree(records, target)
        existing_identity = existing_journal["worktree_identity"]
        target_already_bound = target.exists() or target.is_symlink()
        bind_existing_target = False
        if target_already_bound:
            target = require_owned_directory(
                target, label="interrupted worktree", private=True
            )
            if all(value is None for value in existing_identity.values()):
                if any(target.iterdir()):
                    raise WorktreeError(
                        "interrupted create journal does not bind the nonempty worktree"
                    )
                bind_existing_target = True
            elif any(
                existing_identity[key] != value
                for key, value in target_directory_identity(target).items()
            ):
                raise WorktreeError("interrupted worktree identity changed")
        elif any(value is not None for value in existing_identity.values()):
            raise WorktreeError("interrupted worktree disappeared")
        if registered is not None:
            recovered_identity = worktree_identity(target)
            reject_registered_worktree_ancestry(
                [
                    item
                    for item in records
                    if registered_worktree_path(item) != target
                ],
                target,
            )
            if (
                not target_already_bound
                or registered.get("branch") != branch_ref
                or registered.get("HEAD") != start_commit
                or exact_ref_tip(repository, branch_ref) != start_commit
                or (
                    existing_identity["git_dir"] is not None
                    and recovered_identity != existing_identity
                )
            ):
                raise WorktreeError("interrupted worktree registration is inconsistent")
            record = create_record(
                repository,
                allowed_root,
                target,
                plan,
                branch_ref,
                start_commit,
                args.owner_id,
                args.lease_seconds,
                recovered_identity,
            )
            atomic_write(paths["record"], record)
            paths["journal"].unlink()
            print(
                json.dumps(
                    {"operation": "create", "record": str(paths["record"]), **record},
                    sort_keys=True,
                )
            )
            return
        if existing_identity["git_dir"] is not None:
            raise WorktreeError("interrupted worktree registration disappeared")
        if exact_ref_tip(repository, branch_ref) is not None:
            raise WorktreeError("requested branch already exists")
        reject_registered_worktree_ancestry(records, target)
        if (
            directory_identity(allowed_root) != allowed_identity
            or directory_identity(target.parent) != parent_identity
            or has_symlink_component(target)
        ):
            raise WorktreeError("allowed root or worktree parent changed before creation")
        if not paths["journal"].exists():
            atomic_write(paths["journal"], existing_journal)
        parent_descriptor = os.open(
            target.parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        target_descriptor = -1
        try:
            parent_metadata = os.fstat(parent_descriptor)
            if (parent_metadata.st_dev, parent_metadata.st_ino) != parent_identity:
                raise WorktreeError("worktree parent changed before creation")
            if not target_already_bound:
                os.mkdir(target.name, mode=0o700, dir_fd=parent_descriptor)
            target_descriptor = os.open(
                target.name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent_descriptor,
            )
            os.fchmod(target_descriptor, 0o700)
            target_metadata = os.fstat(target_descriptor)
            if (
                target_metadata.st_uid != os.getuid()
                or stat.S_IMODE(target_metadata.st_mode) != 0o700
            ):
                raise WorktreeError("new worktree must be an owner-private directory")
            target_identity = (target_metadata.st_dev, target_metadata.st_ino)
            bound_identity = {
                "git_dir": None,
                "git_dir_device": None,
                "git_dir_inode": None,
                "worktree_device": target_metadata.st_dev,
                "worktree_inode": target_metadata.st_ino,
                "worktree_owner": target_metadata.st_uid,
                "worktree_mode": stat.S_IMODE(target_metadata.st_mode),
            }
            if not target_already_bound or bind_existing_target:
                journal["worktree_identity"] = bound_identity
                journal = add_content_digest(journal)
                atomic_write(paths["journal"], journal)
            before = snapshot_source(repository)
            git(
                repository,
                "worktree",
                "add",
                "-b",
                branch_short,
                f"/proc/self/fd/{target_descriptor}",
                start_commit,
                pass_fds=(target_descriptor,),
            )
        finally:
            if target_descriptor >= 0:
                os.close(target_descriptor)
            os.close(parent_descriptor)
        if snapshot_source(repository) != before:
            raise WorktreeError("ordinary checkout state changed during worktree creation")
        if (
            directory_identity(allowed_root) != allowed_identity
            or directory_identity(target.parent) != parent_identity
            or directory_identity(target) != target_identity
            or has_symlink_component(target)
        ):
            raise WorktreeError("allowed root, worktree parent or target changed during creation")
        reject_registered_worktree_ancestry(
            [
                record
                for record in parse_worktrees(repository)
                if Path(str(record.get("worktree", ""))).absolute() != target
            ],
            target,
        )
        record = create_record(
            repository,
            allowed_root,
            target,
            plan,
            branch_ref,
            start_commit,
            args.owner_id,
            args.lease_seconds,
            worktree_identity(target),
        )
        atomic_write(paths["record"], record)
        paths["journal"].unlink()
    print(json.dumps({"operation": "create", "record": str(paths["record"]), **record}, sort_keys=True))


def load_bound_record(
    repository: Path,
    raw_allowed_root: str,
    raw_plan: str,
    *,
    allow_resume_journal: bool = False,
) -> tuple[Path, dict[str, Any], dict[str, Path]]:
    allowed_root = validate_allowed_root(raw_allowed_root, repository)
    plan_path = normalize_plan_path(raw_plan)
    identity = repository_identity(repository)
    paths = metadata_paths(identity, plan_path)
    if paths["journal"].exists():
        if not paths["record"].exists():
            raise WorktreeError("managed worktree has an interrupted create journal")
        if not allow_resume_journal:
            raise WorktreeError("managed worktree has an interrupted resume journal")
    record = read_record(paths["record"])
    if record["plan"]["path"] != plan_path:
        raise WorktreeError("ownership record plan path changed or mismatched")
    if record["plan"] != plan_identity_at_commit(
        repository, plan_path, record["start_commit"]
    ):
        raise WorktreeError("ownership record plan identity changed or mismatched")
    return allowed_root, record, paths


def inspect_record(args: argparse.Namespace) -> None:
    repository = repository_root()
    allowed_root, record, paths = load_bound_record(
        repository,
        args.allowed_root,
        args.plan,
        allow_resume_journal=True,
    )
    target, tip = verify_record_context(repository, allowed_root, record)
    verify_history(repository, record["start_commit"], record["accepted_tip"], tip)
    pending_resume = paths["journal"].exists()
    if pending_resume:
        pending = read_record(paths["journal"])
        immutable_keys = RECORD_KEYS - {"accepted_tip", "owner", "content_digest"}
        if any(pending[key] != record[key] for key in immutable_keys):
            raise WorktreeError("interrupted resume journal has different bound facts")
    print(
        json.dumps(
            {
                "operation": "inspect",
                "record": record,
                "current_tip": tip,
                "status_digest": status_digest(target),
                "lease_active": record["owner"]["lease_expires_at"] > int(time.time()),
                "pending_resume": pending_resume,
            },
            sort_keys=True,
        )
    )


def resume(args: argparse.Namespace) -> None:
    repository = repository_root()
    allowed_root, record, paths = load_bound_record(
        repository,
        args.allowed_root,
        args.plan,
        allow_resume_journal=True,
    )
    with locked_file(paths["lock"]):
        record = read_record(paths["record"])
        now = int(time.time())
        if paths["journal"].exists():
            pending = read_record(paths["journal"])
            immutable_keys = RECORD_KEYS - {"accepted_tip", "owner", "content_digest"}
            if any(pending[key] != record[key] for key in immutable_keys):
                raise WorktreeError("interrupted resume journal has different bound facts")
            if pending["owner"]["id"] != args.owner_id:
                if record["owner"]["lease_expires_at"] > now:
                    raise WorktreeError("interrupted resume belongs to a different owner")
                paths["journal"].unlink()
            else:
                paths["journal"].unlink()
        validate_lease(record["owner"], args.owner_id, now)
        target, tip = verify_record_context(repository, allowed_root, record)
        verify_history(repository, record["start_commit"], record["accepted_tip"], tip)
        plan_at_start = plan_identity_at_commit(
            repository, record["plan"]["path"], record["start_commit"]
        )
        if plan_at_start != record["plan"]:
            raise WorktreeError("bound plan identity changed or mismatched")
        updated = dict(record)
        updated["accepted_tip"] = tip
        updated["owner"] = {
            "id": args.owner_id,
            "lease_expires_at": now + args.lease_seconds,
        }
        updated = add_content_digest(updated)
        atomic_write(paths["journal"], updated)
        atomic_write(paths["record"], updated)
        paths["journal"].unlink()
    print(
        json.dumps(
            {
                "operation": "resume",
                "record": str(paths["record"]),
                "worktree": str(target),
                "branch_ref": updated["branch_ref"],
                "accepted_tip": tip,
                "status_digest": status_digest(target),
            },
            sort_keys=True,
        )
    )


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("plan")
    parser.add_argument("--allowed-root", required=True)


def add_owner_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--lease-seconds", type=int, default=14_400)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    create_parser = sub.add_parser("create")
    add_common_arguments(create_parser)
    add_owner_arguments(create_parser)
    create_parser.add_argument("--worktree", required=True)
    create_parser.add_argument("--branch", required=True)
    create_parser.set_defaults(handler=create)
    inspect_parser = sub.add_parser("inspect")
    add_common_arguments(inspect_parser)
    inspect_parser.set_defaults(handler=inspect_record)
    resume_parser = sub.add_parser("resume")
    add_common_arguments(resume_parser)
    add_owner_arguments(resume_parser)
    resume_parser.set_defaults(handler=resume)
    return root


def validate_arguments(args: argparse.Namespace) -> None:
    if hasattr(args, "owner_id") and OWNER_RE.fullmatch(args.owner_id) is None:
        raise WorktreeError("owner id is invalid")
    if hasattr(args, "lease_seconds") and not 60 <= args.lease_seconds <= MAX_LEASE_SECONDS:
        raise WorktreeError(f"lease seconds must be between 60 and {MAX_LEASE_SECONDS}")


def main() -> int:
    args = parser().parse_args()
    try:
        validate_arguments(args)
        args.handler(args)
    except (OSError, UnicodeError, WorktreeError) as exc:
        print(f"manage plan worktrees failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
