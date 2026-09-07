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

    cached = sys.modules.get("worktree_guard")
    if cached is not None:
        return cached
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
    # A publication journal only ever describes an in-flight publication for a
    # live record. No record exists here, so any journal left under this key is
    # the residue of a publication that already lost its record and would
    # otherwise refuse the next publication of this same task identity forever.
    paths["publication"].unlink(missing_ok=True)
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
        atomic_write(paths["journal"], record)
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
    # The journal is rewritten from the final record before the record itself,
    # as `refresh_lease` already does. The journal was first written with a
    # pending worktree identity, so a crash between the record write and this
    # unlink would otherwise leave a journal that can never match its own
    # record on an immutable field, which every command refuses and only a
    # publication can clear.
    atomic_write(paths["journal"], record)
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


def read_task_record(paths: dict[str, Path]) -> dict:
    """Read the ownership record for this task, or explain why it cannot be used.

    An ownership record is parent-owned state outside the repository, so an
    unreadable or superseded one is never rewritten or removed automatically: a
    live worktree may still depend on it. The operator is told the exact record
    path instead, so the retirement workflow can settle the worktree it names
    before a new binding is created.
    """

    try:
        return read_record(paths["record"])
    except WorktreeError as exc:
        raise WorktreeError(
            f"{exc}: {paths['record']}. Settle the worktree this record names with the "
            "explicit retirement workflow, then remove the record before preparing again."
        ) from exc


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
            record = read_task_record(paths)
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
    record = read_task_record(paths)
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
        record = read_task_record(paths)
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


EVIDENCE_DIRECTORIES = (".agent-logs", ".agent-artifacts")
PUBLICATION_KEYS = {
    "operation",
    "repository_identity",
    "task",
    "source_ref",
    "branch_ref",
    "worktree_path",
    "source_tip_before",
    "accepted_commit",
}


def worktree_is_clean(worktree: Path) -> bool:
    payload = git(worktree, "status", "--porcelain", "--untracked-files=all", "-z").stdout
    return payload.strip(b"\0") == b""


def load_restructure_module():
    path = Path(__file__).resolve().with_name("restructure-plan.py")
    spec = importlib.util.spec_from_file_location("managed_restructure_plan", path)
    if spec is None or spec.loader is None:
        raise WorktreeError("cannot load the restructuring validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_retained_replan_transition(
    target: Path,
    record: dict[str, Any],
    journal_path: Path,
    accepted_commit: str,
    source_tip: str,
) -> None:
    """Authorize publishing only the completed plan transition while retaining dirty bytes."""

    if record["task"]["kind"] != PLAN_TASK:
        raise WorktreeError("retained replan transition requires a numbered source plan")
    module = load_restructure_module()
    try:
        raw = json.loads(journal_path.read_text(encoding="utf-8"))
        journal_identity = raw["journal_identity"]
        payload = module.load_journal(
            journal_path,
            journal_identity,
            expected_source_head=source_tip,
        )
    except (OSError, UnicodeError, KeyError, json.JSONDecodeError, module.RestructureError) as exc:
        raise WorktreeError(f"invalid retained-transition journal: {exc}") from exc
    if payload["phase"] != "complete":
        raise WorktreeError("retained replan transition requires a complete journal")
    if payload["source_head"] != source_tip:
        raise WorktreeError("retained replan transition source changed")
    snapshot = payload["dirty_product_snapshot"]
    dirty_paths = [entry["path"] for entry in snapshot]
    if not dirty_paths or module.dirty_product_snapshot(dirty_paths) != snapshot:
        raise WorktreeError("retained dirty product bytes differ from the journal")
    contract_path = payload["result_path"]
    contract_file = target / contract_path
    try:
        contract = json.loads(contract_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorktreeError(f"retained replan contract is unreadable: {exc}") from exc
    if (
        contract.get("schema_version") != 4
        or contract.get("dirty_product_paths") != dirty_paths
        or contract.get("promoted_dirty_paths") != dirty_paths
    ):
        raise WorktreeError(
            "retained replan transition must promote the complete dirty product snapshot"
        )
    successors = contract.get("successors")
    if not isinstance(successors, list) or len(successors) != 1:
        raise WorktreeError("retained replan transition requires exactly one successor")
    successor_content = successors[0].get("content")
    if (
        not isinstance(successor_content, str)
        or "\nimplementation_mode: parent_direct\n" not in f"\n{successor_content}"
    ):
        raise WorktreeError(
            "retained replan successor must require parent-direct implementation"
        )
    operation_paths = {operation["path"] for operation in payload["operations"]}
    changed = {
        item.decode("utf-8", "surrogateescape")
        for item in git(
            target,
            "diff",
            "--name-only",
            "--no-renames",
            "-z",
            source_tip,
            accepted_commit,
        ).stdout.split(b"\0")
        if item
    }
    if changed != operation_paths:
        raise WorktreeError(
            "retained transition commit does not exactly match the completed reconstruction"
        )
    if changed & set(dirty_paths):
        raise WorktreeError("retained transition commit includes promoted product bytes")
    operation_status = git(
        target,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "-z",
        "--",
        *sorted(operation_paths),
    ).stdout
    if operation_status.strip(b"\0"):
        raise WorktreeError("retained transition operation paths differ from the accepted commit")
    for operation in payload["operations"]:
        relative = operation["path"]
        expected_content = operation["target_content"]
        probe = git(
            target,
            "cat-file",
            "-e",
            f"{accepted_commit}:{relative}",
            check=False,
        )
        if expected_content is None:
            if probe.returncode == 0:
                raise WorktreeError(
                    f"retained transition commit did not delete {relative}"
                )
            continue
        if probe.returncode != 0:
            raise WorktreeError(
                f"retained transition commit is missing {relative}"
            )
        committed = git(
            target,
            "show",
            f"{accepted_commit}:{relative}",
        ).stdout
        if committed != expected_content.encode("utf-8"):
            raise WorktreeError(
                f"retained transition commit bytes differ for {relative}"
            )
        tree = git(
            target,
            "ls-tree",
            "-z",
            accepted_commit,
            "--",
            relative,
        ).stdout
        rows = [row for row in tree.split(b"\0") if row]
        expected_mode = b"100755" if operation["target_mode"] & 0o111 else b"100644"
        if len(rows) != 1 or rows[0].split(b" ", 1)[0] != expected_mode:
            raise WorktreeError(
                f"retained transition commit mode differs for {relative}"
            )


def untracked_paths(worktree: Path) -> list[str]:
    payload = git(
        worktree, "ls-files", "-z", "--others", "--exclude-standard"
    ).stdout
    return [item.decode("utf-8", "surrogateescape") for item in payload.split(b"\0") if item]


def source_checkout(repository: Path, source_ref: str) -> Path:
    """Return the single registered checkout that holds the source branch."""

    matches = [
        registered_worktree_path(record)
        for record in parse_worktrees(repository)
        if record.get("branch") == source_ref
    ]
    if not matches:
        raise WorktreeError(
            f"no registered checkout has {source_ref} checked out; publication needs one"
        )
    if len(matches) > 1:
        raise WorktreeError(f"more than one registered checkout holds {source_ref}")
    return matches[0]


def relocate_evidence(target: Path, destination_root: Path, slug: str) -> list[str]:
    """Move ignored local evidence out of a worktree that is about to vanish."""

    import shutil

    relocated: list[str] = []
    for name in EVIDENCE_DIRECTORIES:
        source = target / name
        if not source.is_dir() or source.is_symlink() or not any(source.iterdir()):
            continue
        destination = destination_root / name / "retired-tasks" / slug
        if destination.exists():
            raise WorktreeError(f"relocated evidence already exists at {destination}")
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        relocated.append(str(destination))
    return relocated


def publication_journal(
    record: dict[str, Any], accepted_commit: str, source_tip_before: str
) -> dict[str, Any]:
    return {
        "operation": "publish",
        "repository_identity": record["repository_identity"],
        "task": record["task"],
        "source_ref": record["source_ref"],
        "branch_ref": record["branch_ref"],
        "worktree_path": record["worktree_path"],
        "source_tip_before": source_tip_before,
        "accepted_commit": accepted_commit,
    }


def read_publication_journal(path: Path) -> dict[str, Any]:
    if has_symlink_component(path) or path.is_symlink() or not path.is_file():
        raise WorktreeError("publication journal must be a regular non-symlink file")
    metadata = path.stat()
    if stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_nlink != 1:
        raise WorktreeError("publication journal must be single-linked mode 0600")
    data = path.read_bytes()
    if len(data) > MAX_RECORD_BYTES:
        raise WorktreeError("publication journal exceeds the size limit")
    value = json.loads(data.decode("utf-8"), object_pairs_hook=guard.reject_duplicate_json_keys)
    unsigned = dict(value)
    observed = unsigned.pop("content_digest", None)
    if set(unsigned) != PUBLICATION_KEYS:
        raise WorktreeError("publication journal schema is invalid")
    if observed != digest_bytes(canonical_json(unsigned)):
        raise WorktreeError("publication journal digest does not match its content")
    return unsigned


def retire_worktree(
    repository: Path,
    target: Path,
    branch_ref: str,
    branch_short: str,
    *,
    anchor: Path | None = None,
    published: bool = False,
) -> None:
    """Remove the exact task worktree and its temporary local branch.

    Every command runs from a checkout that outlives the removal. Running them
    from the worktree being deleted leaves the transaction unable to prune its
    own registration or delete its branch, which strands the ownership record
    and blocks the next preparation for the same task.

    A publication passes the source checkout it already verified and sets
    ``published``. `git branch -d` measures merge status against the anchor's
    own HEAD, so a source branch checked out anywhere other than the anchor
    would refuse a branch this transaction proved reachable from the published
    source ref. That proof is the stronger fact, so publication deletes by
    reachability rather than by the anchor's HEAD.
    """

    anchor = guard.primary_worktree(repository) if anchor is None else anchor
    if anchor == target:
        raise WorktreeError("refusing to retire the pre-existing checkout")
    if target.exists():
        if not worktree_is_clean(target):
            raise WorktreeError("task worktree still holds uncommitted or untracked work")
        git(anchor, "worktree", "remove", str(target))
    git(anchor, "worktree", "prune")
    if target.exists() or target.is_symlink():
        raise WorktreeError("task worktree directory remains after removal")
    if find_registered_worktree(parse_worktrees(anchor), target) is not None:
        raise WorktreeError("task worktree registration remains after removal")
    if exact_ref_tip(anchor, branch_ref) is not None:
        git(anchor, "branch", "-D" if published else "-d", branch_short)
    if exact_ref_tip(anchor, branch_ref) is not None:
        raise WorktreeError("temporary task branch remains after deletion")


def publish(args: argparse.Namespace) -> None:
    """Publish the accepted commit, then retire this exact task worktree.

    The transaction journals its intent first, so an interrupted run resumes
    from the exact same bound facts instead of replaying a merge. It never
    touches a dirty or drifted source checkout, and it never removes a task
    worktree that still holds work.
    """

    repository = repository_root()
    allowed_root, record, paths = load_bound_record(repository, args, allow_resume_journal=True)
    with locked_file(paths["lock"]):
        record = read_task_record(paths)
        now = int(time.time())
        validate_lease(record["owner"], args.owner_id, now)
        target, tip = verify_record_context(repository, allowed_root, record)
        verify_history(repository, record["start_commit"], record["accepted_tip"], tip)
        source_ref = record["source_ref"]
        branch_ref = record["branch_ref"]
        branch_short = branch_ref.removeprefix("refs/heads/")
        accepted_commit = args.accepted_commit or tip
        if accepted_commit != tip:
            raise WorktreeError("the accepted commit must be the exact task branch tip")
        if accepted_commit == record["start_commit"]:
            raise WorktreeError("the task branch holds no commit to publish")
        retaining_transition = bool(args.retain_worktree)
        if retaining_transition:
            if not args.transition_journal:
                raise WorktreeError(
                    "--retain-worktree requires --transition-journal"
                )
        elif args.transition_journal:
            raise WorktreeError(
                "--transition-journal requires --retain-worktree"
            )
        if not worktree_is_clean(target) and not retaining_transition:
            raise WorktreeError(
                "task worktree is dirty; commit or resolve its work before publication"
            )
        checkout = source_checkout(repository, source_ref)
        source_tip = exact_ref_tip(repository, source_ref)
        if source_tip is None:
            raise WorktreeError(f"source ref {source_ref} is unavailable")
        journal_path = paths["publication"]
        resumed = None
        if journal_path.exists():
            resumed = read_publication_journal(journal_path)
            if resumed["accepted_commit"] != accepted_commit or (
                resumed["branch_ref"] != branch_ref
                or resumed["source_ref"] != source_ref
                or resumed["worktree_path"] != record["worktree_path"]
                or resumed["repository_identity"] != record["repository_identity"]
            ):
                raise WorktreeError("an interrupted publication has different bound facts")
        if retaining_transition:
            validate_retained_replan_transition(
                target,
                record,
                Path(args.transition_journal),
                accepted_commit,
                resumed["source_tip_before"] if resumed is not None else source_tip,
            )
        published_already = is_ancestor(repository, accepted_commit, source_tip)
        if not published_already:
            if not is_ancestor(repository, source_tip, accepted_commit):
                raise WorktreeError(
                    f"{source_ref} moved to unrelated history; this publication is not a "
                    "fast-forward and the source state is preserved unchanged"
                )
            if not worktree_is_clean(checkout):
                raise WorktreeError(
                    "the source checkout has uncommitted or untracked changes; "
                    "its state is preserved unchanged"
                )
            if git_text(checkout, "rev-parse", "HEAD") != source_tip:
                raise WorktreeError("the source checkout drifted from its branch tip")
            if resumed is None:
                atomic_write(
                    journal_path,
                    add_content_digest(
                        publication_journal(record, accepted_commit, source_tip)
                    ),
                )
            git(checkout, "merge", "--ff-only", accepted_commit)
        observed = exact_ref_tip(repository, source_ref)
        if observed != accepted_commit and not (
            observed is not None and is_ancestor(repository, accepted_commit, observed)
        ):
            raise WorktreeError("the source ref does not contain the accepted commit")
        if git_text(checkout, "rev-parse", "HEAD") != observed:
            raise WorktreeError("the source checkout does not reflect the published commit")
        if retaining_transition:
            updated = dict(record)
            updated["accepted_tip"] = accepted_commit
            updated["owner"] = {
                "id": args.owner_id,
                "lease_expires_at": now + 14_400,
            }
            atomic_write(paths["record"], add_content_digest(updated))
            journal_path.unlink(missing_ok=True)
            print(
                json.dumps(
                    {
                        "operation": "publish-transition",
                        "task": task_label(record["task"]),
                        "source_ref": source_ref,
                        "published_commit": accepted_commit,
                        "worktree_removed": False,
                        "branch_removed": False,
                    },
                    sort_keys=True,
                )
            )
            return
        relocated = relocate_evidence(
            target, checkout, PurePosixPath(record["worktree_path"]).name
        )
        retire_worktree(
            repository, target, branch_ref, branch_short, anchor=checkout, published=True
        )
        journal_path.unlink(missing_ok=True)
        # `publish` is the one command that runs with a resume journal present,
        # so it is also the one that can leave a journal behind with no record
        # to explain it. Nothing then clears it, and the next task with this
        # identity refuses on bound facts that no longer describe anything.
        paths["journal"].unlink(missing_ok=True)
        paths["record"].unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "operation": "publish",
                "task": task_label(record["task"]),
                "source_ref": source_ref,
                "published_commit": accepted_commit,
                "relocated_evidence": relocated,
                "worktree_removed": True,
                "branch_removed": True,
            },
            sort_keys=True,
        )
    )


def recover_stranded_record(
    repository: Path,
    allowed_root: Path,
    record: dict[str, Any],
    paths: dict[str, Path],
    *,
    stopped: bool,
) -> None:
    """Finish a retirement whose task worktree is already gone.

    Retirement is not atomic. A crash after `git worktree remove` and before the
    record is unlinked leaves a record that names a directory no longer there.
    Every other command resolves that directory first, so `publish`, `retire`,
    `prepare`, `resume` and `inspect` all refuse it, while the completion gate
    keeps reporting the task as outstanding. Without this path the repository
    reaches a state no supported command can clear, which no crash should be
    able to produce.

    This finishes exactly the interrupted retirement and nothing more: it prunes
    the stale registration, deletes the temporary branch only once its commits
    are reachable from the source ref or the caller has acknowledged their loss,
    and removes the record and its journals.
    """

    raw = Path(record["worktree_path"])
    if not raw.is_absolute() or Path(os.path.normpath(str(raw))) != raw:
        raise WorktreeError("recorded worktree path is not absolute and normalized")
    if not path_is_strict_descendant(raw, allowed_root):
        raise WorktreeError("recorded worktree path is outside the allowed root")
    if raw.exists() or raw.is_symlink():
        raise WorktreeError("the recorded task worktree still exists")

    branch_ref = record["branch_ref"]
    branch_short = branch_ref.removeprefix("refs/heads/")
    anchor = guard.primary_worktree(repository)
    tip = exact_ref_tip(repository, branch_ref)
    source_tip = exact_ref_tip(repository, record["source_ref"])
    published = tip is None or (
        source_tip is not None and is_ancestor(repository, tip, source_tip)
    )
    if not published and not stopped:
        raise WorktreeError(
            f"the task worktree is gone but {branch_ref} is not reachable from "
            f"{record['source_ref']}; publish those commits from a fresh checkout of "
            "that branch, or pass --stopped to discard them explicitly"
        )

    git(anchor, "worktree", "prune")
    if find_registered_worktree(parse_worktrees(anchor), raw) is not None:
        raise WorktreeError("task worktree registration remains after pruning")
    if exact_ref_tip(anchor, branch_ref) is not None:
        # Reachability, or the caller's explicit acknowledgement, is the fact
        # that justifies the delete. `-d` would instead measure merge status
        # against the anchor's own HEAD, which this recovery cannot assume.
        git(anchor, "branch", "-D", branch_short)
    if exact_ref_tip(anchor, branch_ref) is not None:
        raise WorktreeError("temporary task branch remains after deletion")
    paths["journal"].unlink(missing_ok=True)
    paths["publication"].unlink(missing_ok=True)
    paths["record"].unlink(missing_ok=True)


def retire(args: argparse.Namespace) -> None:
    """Retire a task worktree the current transaction did not publish.

    Retirement outside a successful publication stays explicit. A stopped
    task keeps its recoverable state unless its owner acknowledges the loss.
    """

    repository = repository_root()
    # A stranded record may also carry a leftover resume journal, and both are
    # ordinary interruptions. Refusing on the journal before the stranded case
    # is even considered would keep the exact lockout this recovery exists to
    # clear, so the journal is admitted here and re-refused below for every
    # task whose worktree is still present.
    allowed_root, record, paths = load_bound_record(
        repository, args, allow_resume_journal=True
    )
    with locked_file(paths["lock"]):
        record = read_task_record(paths)
        validate_lease(record["owner"], args.owner_id, int(time.time()))
        if record["repository_identity"] != repository_identity(repository):
            raise WorktreeError("ownership record belongs to another repository or clone")
        if record["allowed_root"] != str(allowed_root):
            raise WorktreeError("ownership record allowed root changed or mismatched")
        stranded = not Path(record["worktree_path"]).exists()
        if not stranded and paths["journal"].exists():
            raise WorktreeError("managed worktree has an interrupted resume journal")
        if stranded:
            recover_stranded_record(
                repository, allowed_root, record, paths, stopped=args.stopped
            )
            print(
                json.dumps(
                    {
                        "operation": "retire",
                        "task": task_label(record["task"]),
                        "recovered": True,
                        "relocated_evidence": [],
                    },
                    sort_keys=True,
                )
            )
            return
        target, tip = verify_record_context(repository, allowed_root, record)
        branch_ref = record["branch_ref"]
        branch_short = branch_ref.removeprefix("refs/heads/")
        source_tip = exact_ref_tip(repository, record["source_ref"])
        published = source_tip is not None and is_ancestor(repository, tip, source_tip)
        if not published and not args.stopped:
            raise WorktreeError(
                f"{branch_ref} is not reachable from {record['source_ref']}; publish it "
                "first, or pass --stopped to retire unpublished work explicitly"
            )
        if not published:
            if tip != record["start_commit"]:
                raise WorktreeError(
                    "a stopped task with unpublished commits keeps its recoverable "
                    "state; remove it with the explicit retirement workflow instead"
                )
            if not worktree_is_clean(target):
                raise WorktreeError("stopped task worktree still holds uncommitted work")
        checkout = source_checkout(repository, record["source_ref"])
        relocated = relocate_evidence(
            target, checkout, PurePosixPath(record["worktree_path"]).name
        )
        retire_worktree(repository, target, branch_ref, branch_short)
        paths["journal"].unlink(missing_ok=True)
        paths["publication"].unlink(missing_ok=True)
        paths["record"].unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "operation": "retire",
                "task": task_label(record["task"]),
                "published": published,
                "relocated_evidence": relocated,
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

    publish_parser = sub.add_parser("publish")
    add_task_arguments(publish_parser)
    publish_parser.add_argument("--owner-id", default="parent")
    publish_parser.add_argument("--accepted-commit")
    publish_parser.add_argument("--retain-worktree", action="store_true")
    publish_parser.add_argument("--transition-journal")
    publish_parser.set_defaults(handler=publish)

    retire_parser = sub.add_parser("retire")
    add_task_arguments(retire_parser)
    retire_parser.add_argument("--owner-id", default="parent")
    retire_parser.add_argument("--stopped", action="store_true")
    retire_parser.set_defaults(handler=retire)
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
