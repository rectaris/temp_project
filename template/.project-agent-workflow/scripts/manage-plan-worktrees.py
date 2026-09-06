#!/usr/bin/env python3
"""Create, inspect, prepare, resume, and retire parent-owned task worktrees.

Every repository-changing task performs its writes in one exact task-bound
linked worktree. This command owns the mutating half of that boundary. The
read-only assertion every other supported surface shares lives in the
worktree guard module this command imports.

A task identity is exactly one of a committed numbered plan or a bounded
direct task. The two variants never share ownership-record key material, so
a direct task can never impersonate a plan.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import json
import stat
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any


def load_worktree_guard():
    """Load the shared guard from either supported layout.

    The root repository keeps imported modules under a package directory and
    a generated project keeps them beside this command. Probing both keeps
    the root and generated copies of this command byte-identical.
    """

    base = Path(__file__).resolve().parent
    for candidate in ("worktree_guard.py", "project_workflow/worktree_guard.py"):
        path = base / candidate
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("worktree_guard", path)
        if spec is None or spec.loader is None:
            break
        module = importlib.util.module_from_spec(spec)
        sys.modules["worktree_guard"] = module
        spec.loader.exec_module(module)
        return module
    raise SystemExit("manage plan worktrees failed: the shared worktree guard is missing")


guard = load_worktree_guard()

WorktreeError = guard.WorktreeError
GuardError = guard.GuardError
SCHEMA_VERSION = guard.SCHEMA_VERSION
MAX_RECORD_BYTES = guard.MAX_RECORD_BYTES
MAX_LEASE_SECONDS = guard.MAX_LEASE_SECONDS
OWNER_RE = guard.OWNER_RE
OID_RE = guard.OID_RE
DIGEST_RE = guard.DIGEST_RE
BRANCH_REF_RE = guard.BRANCH_REF_RE
RECORD_KEYS = guard.RECORD_KEYS
REPOSITORY_KEYS = guard.REPOSITORY_KEYS
TASK_KEYS = guard.TASK_KEYS
OWNER_KEYS = guard.OWNER_KEYS
WORKTREE_IDENTITY_KEYS = guard.WORKTREE_IDENTITY_KEYS
PLAN_TASK = guard.PLAN_TASK
DIRECT_TASK = guard.DIRECT_TASK

canonical_json = guard.canonical_json
digest_bytes = guard.digest_bytes
git_environment = guard.git_environment
git = guard.git
git_text = guard.git_text
has_symlink_component = guard.has_symlink_component
canonical_directory = guard.canonical_directory
require_owned_directory = guard.require_owned_directory
directory_identity = guard.directory_identity
path_is_strict_descendant = guard.path_is_strict_descendant
account_home = guard.account_home
normalize_plan_path = guard.normalize_plan_path
normalize_direct_task = guard.normalize_direct_task
plan_task = guard.plan_task
direct_task = guard.direct_task
task_label = guard.task_label
task_selector = guard.task_selector
canonical_origin = guard.canonical_origin
repository_root = guard.repository_root
repository_identity = guard.repository_identity
metadata_paths = guard.metadata_paths
ensure_metadata_directory = guard.ensure_metadata_directory
locked_file = guard.locked_file
add_content_digest = guard.add_content_digest
atomic_write = guard.atomic_write
read_record = guard.read_record
validate_record = guard.validate_record
parse_worktrees = guard.parse_worktrees
registered_worktree_path = guard.registered_worktree_path
find_registered_worktree = guard.find_registered_worktree
primary_worktree = guard.primary_worktree
worktree_identity = guard.worktree_identity
target_directory_identity = guard.target_directory_identity
exact_ref_tip = guard.exact_ref_tip
is_ancestor = guard.is_ancestor


def validate_allowed_root(raw: str, repository: Path) -> Path:
    allowed_root = require_owned_directory(Path(raw), label="allowed root")
    worktrees = parse_worktrees(repository)
    if not worktrees:
        raise WorktreeError("Git reported no registered worktrees")
    primary = canonical_directory(str(worktrees[0].get("worktree", "")), label="primary worktree")
    forbidden = {
        Path("/").resolve(),
        account_home().resolve(),
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
        if allowed_root == registered or path_is_strict_descendant(allowed_root, registered):
            raise WorktreeError("allowed root must not be a registered worktree or its descendant")
    return allowed_root


def ensure_default_allowed_root(repository: Path) -> Path:
    """Create the account-home default placement root without a further prompt."""

    root = guard.default_allowed_root()
    if has_symlink_component(root):
        raise WorktreeError("default allowed root contains a symlink component")
    if not root.exists():
        root.mkdir(mode=0o700, parents=True)
    root.chmod(0o700)
    require_owned_directory(root, label="default allowed root", private=True)
    return validate_allowed_root(str(root), repository)


def resolve_allowed_root(repository: Path, raw: str | None) -> Path:
    if raw is None:
        return ensure_default_allowed_root(repository)
    return validate_allowed_root(raw, repository)


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


def current_source_ref(repository: Path, raw: str | None) -> str:
    """Resolve the exact local branch a finished task publishes to."""

    if raw is not None:
        return normalize_branch(raw, repository)[1]
    primary = primary_worktree(repository)
    head = git_text(primary, "symbolic-ref", "--quiet", "HEAD", check=False)
    if not head or BRANCH_REF_RE.fullmatch(head) is None:
        raise WorktreeError(
            "the pre-existing checkout is not on a branch; pass --source-ref explicitly"
        )
    return head


def committed_plan(repository: Path, raw_plan: str, start_commit: str) -> dict[str, str]:
    plan = normalize_plan_path(raw_plan)
    plan_path = repository / plan
    if has_symlink_component(plan_path) or plan_path.is_symlink() or not plan_path.is_file():
        raise WorktreeError("plan must be a regular non-symlink file")
    committed = plan_identity_at_commit(repository, plan, start_commit)
    if committed["digest"] != digest_bytes(plan_path.read_bytes()):
        raise WorktreeError("plan must match its committed bytes at the selected start commit")
    return committed


def plan_identity_at_commit(repository: Path, plan: str, start_commit: str) -> dict[str, str]:
    blob_oid = git_text(repository, "rev-parse", f"{start_commit}:{plan}")
    if not OID_RE.fullmatch(blob_oid):
        raise WorktreeError("committed plan blob is unavailable")
    blob = git(repository, "cat-file", "blob", blob_oid).stdout
    return {
        "path": plan,
        "digest": digest_bytes(blob),
        "blob_oid": blob_oid,
    }


def resolve_task(repository: Path, args: argparse.Namespace, start_commit: str) -> dict[str, Any]:
    """Accept exactly one of a committed plan or a bounded direct task."""

    plan_selected = getattr(args, "plan", None)
    direct_selected = getattr(args, "direct_task", None)
    if bool(plan_selected) == bool(direct_selected):
        raise WorktreeError(
            "select exactly one of a committed active plan or --direct-task <id>"
        )
    if plan_selected:
        return plan_task(committed_plan(repository, plan_selected, start_commit))
    purpose = getattr(args, "purpose", None) or "bounded direct task"
    return direct_task(direct_selected, purpose)


def task_at_commit(repository: Path, task: dict[str, Any], start_commit: str) -> dict[str, Any]:
    if task["kind"] != PLAN_TASK:
        return task
    return plan_task(plan_identity_at_commit(repository, task["identity"]["path"], start_commit))


def default_placement(task: dict[str, Any], allowed_root: Path) -> tuple[Path, str]:
    """Derive one stable directory and branch name from the task identity."""

    if task["kind"] == PLAN_TASK:
        slug = PurePosixPath(task["identity"]["path"]).stem
        return allowed_root / slug, f"plan/{slug}"
    identifier = task["identity"]["id"]
    return allowed_root / f"direct-{identifier}", f"task/{identifier}"


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


def reject_registered_worktree_ancestry(records: list[dict[str, Any]], target: Path) -> None:
    for record in records:
        registered = registered_worktree_path(record)
        if target == registered or path_is_strict_descendant(target, registered):
            raise WorktreeError(
                "worktree path must not be a registered worktree or its descendant"
            )


def status_digest(worktree: Path) -> str:
    index_path = Path(
        git_text(worktree, "rev-parse", "--path-format=absolute", "--git-path", "index")
    )
    return digest_bytes(index_path.read_bytes() + b"\0" + raw_worktree_digest(worktree))


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
    if not is_ancestor(repository, start, accepted) or not is_ancestor(repository, accepted, tip):
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
    task: dict[str, Any],
    branch_ref: str,
    source_ref: str,
    start_commit: str,
    owner_id: str,
    lease_seconds: int,
    bound_worktree_identity: dict[str, Any],
) -> dict[str, Any]:
    return add_content_digest(
        {
            "schema_version": SCHEMA_VERSION,
            "repository_identity": repository_identity(repository),
            "task": task,
            "start_commit": start_commit,
            "accepted_tip": start_commit,
            "source_ref": source_ref,
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
    import hashlib

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
    import hashlib

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
    return (index_digest, raw_worktree_digest(repository))


def create_worktree(
    repository: Path,
    allowed_root: Path,
    target: Path,
    task: dict[str, Any],
    branch_short: str,
    branch_ref: str,
    source_ref: str,
    start_commit: str,
    owner_id: str,
    lease_seconds: int,
    paths: dict[str, Path],
    identity: dict[str, Any],
) -> dict[str, Any]:
    """Create one linked checkout under an exclusive ownership lock."""

    allowed_identity = directory_identity(allowed_root)
    parent_identity = directory_identity(target.parent)
    if paths["record"].exists():
        raise WorktreeError("an ownership record already exists for this task")
    journal = add_content_digest(
        {
            "schema_version": SCHEMA_VERSION,
            "repository_identity": identity,
            "task": task,
            "start_commit": start_commit,
            "accepted_tip": start_commit,
            "source_ref": source_ref,
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
                "id": owner_id,
                "lease_expires_at": int(time.time()) + lease_seconds,
            },
        }
    )
    existing_journal: dict[str, Any] | None = None
    if paths["journal"].exists():
        existing_journal = read_record(paths["journal"])
        old_target = Path(existing_journal["worktree_path"])
        old_registered = find_registered_worktree(parse_worktrees(repository), old_target)
        if (
            existing_journal["owner"]["lease_expires_at"] <= int(time.time())
            and all(value is None for value in existing_journal["worktree_identity"].values())
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
            "task",
            "start_commit",
            "accepted_tip",
            "source_ref",
            "branch_ref",
            "allowed_root",
            "worktree_path",
        )
        if (
            any(existing_journal[field] != journal[field] for field in immutable_fields)
            or existing_journal["owner"]["id"] != owner_id
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
        target = require_owned_directory(target, label="interrupted worktree", private=True)
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
            [item for item in records if registered_worktree_path(item) != target],
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
            task,
            branch_ref,
            source_ref,
            start_commit,
            owner_id,
            lease_seconds,
            recovered_identity,
        )
        atomic_write(paths["record"], record)
        paths["journal"].unlink()
        return record
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
        task,
        branch_ref,
        source_ref,
        start_commit,
        owner_id,
        lease_seconds,
        worktree_identity(target),
    )
    atomic_write(paths["record"], record)
    paths["journal"].unlink()
    return record


def create(args: argparse.Namespace) -> None:
    repository = repository_root()
    allowed_root = resolve_allowed_root(repository, args.allowed_root)
    target = validate_target(args.worktree, allowed_root, must_exist=False, allow_existing=True)
    start_commit = git_text(repository, "rev-parse", "--verify", "HEAD^{commit}")
    task = resolve_task(repository, args, start_commit)
    source_ref = current_source_ref(repository, args.source_ref)
    reject_checkout_filters(repository, start_commit)
    branch_short, branch_ref = normalize_branch(args.branch, repository)
    if branch_ref == source_ref:
        raise WorktreeError("task branch must differ from the source ref")
    identity = repository_identity(repository)
    paths = metadata_paths(identity, task)
    ensure_metadata_directory(paths["directory"])
    with locked_file(paths["lock"]):
        record = create_worktree(
            repository,
            allowed_root,
            target,
            task,
            branch_short,
            branch_ref,
            source_ref,
            start_commit,
            args.owner_id,
            args.lease_seconds,
            paths,
            identity,
        )
    print(
        json.dumps(
            {"operation": "create", "record": str(paths["record"]), **record},
            sort_keys=True,
        )
    )


def refresh_lease(
    repository: Path,
    allowed_root: Path,
    record: dict[str, Any],
    paths: dict[str, Path],
    owner_id: str,
    lease_seconds: int,
) -> tuple[dict[str, Any], Path, str]:
    """Rebind an existing task worktree to the requesting owner."""

    now = int(time.time())
    if paths["journal"].exists():
        pending = read_record(paths["journal"])
        immutable_keys = RECORD_KEYS - {"accepted_tip", "owner", "content_digest"}
        if any(pending[key] != record[key] for key in immutable_keys):
            raise WorktreeError("interrupted resume journal has different bound facts")
        if pending["owner"]["id"] != owner_id and record["owner"]["lease_expires_at"] > now:
            raise WorktreeError("interrupted resume belongs to a different owner")
        paths["journal"].unlink()
    validate_lease(record["owner"], owner_id, now)
    target, tip = verify_record_context(repository, allowed_root, record)
    verify_history(repository, record["start_commit"], record["accepted_tip"], tip)
    bound_task = task_at_commit(repository, record["task"], record["start_commit"])
    if bound_task != record["task"]:
        raise WorktreeError("bound task identity changed or mismatched")
    updated = dict(record)
    updated["accepted_tip"] = tip
    updated["owner"] = {"id": owner_id, "lease_expires_at": now + lease_seconds}
    updated = add_content_digest(updated)
    atomic_write(paths["journal"], updated)
    atomic_write(paths["record"], updated)
    paths["journal"].unlink()
    return updated, target, tip


def prepare(args: argparse.Namespace) -> None:
    """Create or resume the task worktree without another owner prompt."""

    repository = repository_root()
    allowed_root = resolve_allowed_root(repository, args.allowed_root)
    start_commit = git_text(repository, "rev-parse", "--verify", "HEAD^{commit}")
    task = resolve_task(repository, args, start_commit)
    source_ref = current_source_ref(repository, args.source_ref)
    identity = repository_identity(repository)
    paths = metadata_paths(identity, task)
    ensure_metadata_directory(paths["directory"])
    with locked_file(paths["lock"]):
        if paths["record"].exists():
            record = read_record(paths["record"])
            updated, target, tip = refresh_lease(
                repository,
                canonical_directory(record["allowed_root"], label="allowed root"),
                record,
                paths,
                args.owner_id,
                args.lease_seconds,
            )
            print(
                json.dumps(
                    {
                        "operation": "prepare",
                        "outcome": "resumed",
                        "record": str(paths["record"]),
                        "worktree": updated["worktree_path"],
                        "branch_ref": updated["branch_ref"],
                        "source_ref": updated["source_ref"],
                        "task": task_label(updated["task"]),
                        "accepted_tip": tip,
                    },
                    sort_keys=True,
                )
            )
            return
        default_target, default_branch = default_placement(task, allowed_root)
        target = validate_target(
            args.worktree or str(default_target),
            allowed_root,
            must_exist=False,
            allow_existing=True,
        )
        branch_short, branch_ref = normalize_branch(args.branch or default_branch, repository)
        if branch_ref == source_ref:
            raise WorktreeError("task branch must differ from the source ref")
        reject_checkout_filters(repository, start_commit)
        record = create_worktree(
            repository,
            allowed_root,
            target,
            task,
            branch_short,
            branch_ref,
            source_ref,
            start_commit,
            args.owner_id,
            args.lease_seconds,
            paths,
            identity,
        )
    print(
        json.dumps(
            {
                "operation": "prepare",
                "outcome": "created",
                "record": str(paths["record"]),
                "worktree": record["worktree_path"],
                "branch_ref": record["branch_ref"],
                "source_ref": record["source_ref"],
                "task": task_label(record["task"]),
                "accepted_tip": record["accepted_tip"],
            },
            sort_keys=True,
        )
    )


def load_bound_record(
    repository: Path,
    args: argparse.Namespace,
    *,
    allow_resume_journal: bool = False,
) -> tuple[Path, dict[str, Any], dict[str, Path]]:
    identity = repository_identity(repository)
    plan_selected = getattr(args, "plan", None)
    direct_selected = getattr(args, "direct_task", None)
    if bool(plan_selected) == bool(direct_selected):
        raise WorktreeError(
            "select exactly one of a committed active plan or --direct-task <id>"
        )
    if plan_selected:
        selector_task = {
            "kind": PLAN_TASK,
            "identity": {"path": normalize_plan_path(plan_selected)},
        }
    else:
        selector_task = {
            "kind": DIRECT_TASK,
            "identity": {"id": normalize_direct_task(direct_selected)},
        }
    paths = metadata_paths(identity, selector_task)
    if paths["journal"].exists():
        if not paths["record"].exists():
            raise WorktreeError("managed worktree has an interrupted create journal")
        if not allow_resume_journal:
            raise WorktreeError("managed worktree has an interrupted resume journal")
    record = read_record(paths["record"])
    if task_selector(record["task"]) != task_selector(selector_task):
        raise WorktreeError("ownership record task identity changed or mismatched")
    if task_at_commit(repository, record["task"], record["start_commit"]) != record["task"]:
        raise WorktreeError("ownership record task identity changed or mismatched")
    allowed_root = resolve_allowed_root(repository, args.allowed_root or record["allowed_root"])
    return allowed_root, record, paths


def inspect_record(args: argparse.Namespace) -> None:
    repository = repository_root()
    allowed_root, record, paths = load_bound_record(
        repository, args, allow_resume_journal=True
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
        repository, args, allow_resume_journal=True
    )
    with locked_file(paths["lock"]):
        record = read_record(paths["record"])
        updated, target, tip = refresh_lease(
            repository, allowed_root, record, paths, args.owner_id, args.lease_seconds
        )
    print(
        json.dumps(
            {
                "operation": "resume",
                "record": str(paths["record"]),
                "worktree": str(target),
                "branch_ref": updated["branch_ref"],
                "source_ref": updated["source_ref"],
                "accepted_tip": tip,
                "status_digest": status_digest(target),
            },
            sort_keys=True,
        )
    )


def add_task_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("plan", nargs="?")
    parser.add_argument("--direct-task")
    parser.add_argument("--allowed-root")


def add_owner_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--lease-seconds", type=int, default=14_400)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)

    create_parser = sub.add_parser("create")
    add_task_arguments(create_parser)
    add_owner_arguments(create_parser)
    create_parser.add_argument("--purpose")
    create_parser.add_argument("--source-ref")
    create_parser.add_argument("--worktree", required=True)
    create_parser.add_argument("--branch", required=True)
    create_parser.set_defaults(handler=create)

    prepare_parser = sub.add_parser("prepare")
    add_task_arguments(prepare_parser)
    prepare_parser.add_argument("--owner-id", default="parent")
    prepare_parser.add_argument("--lease-seconds", type=int, default=14_400)
    prepare_parser.add_argument("--purpose")
    prepare_parser.add_argument("--source-ref")
    prepare_parser.add_argument("--worktree")
    prepare_parser.add_argument("--branch")
    prepare_parser.set_defaults(handler=prepare)

    inspect_parser = sub.add_parser("inspect")
    add_task_arguments(inspect_parser)
    inspect_parser.set_defaults(handler=inspect_record)

    resume_parser = sub.add_parser("resume")
    add_task_arguments(resume_parser)
    add_owner_arguments(resume_parser)
    resume_parser.set_defaults(handler=resume)
    return root


def validate_arguments(args: argparse.Namespace) -> None:
    if getattr(args, "owner_id", None) is not None and OWNER_RE.fullmatch(args.owner_id) is None:
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
