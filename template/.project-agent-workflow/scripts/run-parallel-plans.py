#!/usr/bin/env python3
"""Parent-owned grouped execution adapter for admitted parallel plan members.

Candidate generation for an admitted execution group member may run in
parallel, but only the parent assembles, reviews, validates, and publishes one
exact result. This adapter separates those responsibilities into distinct
operations so no model completion callback can reach the source target:

* ``dispatch`` starts one isolated member candidate through the existing
  sandboxed worker and returns an immutable readiness artifact.
* ``assemble`` combines one admitted candidate with the *current* target
  commit inside a disposable clone and emits a parent-owned assembly record.
* ``publish`` performs one serialized, journalled, expected-target
  fast-forward of the reviewed commit under the publication lease.
* ``publish-recover`` finalizes or refuses an interrupted publication.

Mutable group authority stays in ``parallel-plan-state.py``. This adapter only
reads and advances that record through its published operations.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any


ADAPTER_VERSION = 1
READINESS_SCHEMA_VERSION = 1
ASSEMBLY_SCHEMA_VERSION = 1
PUBLICATION_JOURNAL_SCHEMA_VERSION = 1

MAX_RECORD_BYTES = 1024 * 1024
MAX_PATCH_BYTES = 128 * 1024 * 1024

RESOLUTION_KINDS = ("unchanged_application", "parent_adjusted")

JOURNAL_STATES = ("intended", "completed", "aborted")


class AdapterError(RuntimeError):
    """One bounded adapter failure that never leaves a partial source effect."""


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_digest(value: Any) -> str:
    return digest_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    )


def sanitized_git_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_") or key in {"GIT_EXEC_PATH", "GIT_SSL_CAINFO"}
    }
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["HOME"] = environment.get("HOME", "/nonexistent")
    return environment


def git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=sanitized_git_environment(),
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise AdapterError(f"git {' '.join(arguments)} failed: {detail}")
    return completed


def git_text(root: Path, *arguments: str) -> str:
    return git(root, *arguments).stdout.decode("utf-8").strip()


def load_sibling_module(name: str, filename: str) -> ModuleType:
    path = Path(__file__).resolve().with_name(filename)
    if not path.is_file():
        raise AdapterError(f"required sibling command is unavailable: {filename}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AdapterError(f"could not load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_AUTHORITY: ModuleType | None = None


def authority() -> ModuleType:
    global _AUTHORITY
    if _AUTHORITY is None:
        _AUTHORITY = load_sibling_module(
            "parallel_plans_authority", "parallel-plan-state.py"
        )
    return _AUTHORITY


def repository_root() -> Path:
    return authority().repository_root()


def require_private_regular_file(path: Path, label: str, maximum: int) -> bytes:
    """Read one bounded regular non-symlink file without following components."""

    absolute = path if path.is_absolute() else (Path.cwd() / path).absolute()
    authority().reject_symlink_ancestors(absolute, include_target=True)
    descriptor = os.open(absolute, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise AdapterError(f"{label} must be a regular file")
        if metadata.st_size > maximum:
            raise AdapterError(f"{label} exceeds its byte bound")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    data = b"".join(chunks)
    if len(data) > maximum:
        raise AdapterError(f"{label} exceeds its byte bound")
    return data


def write_private_artifact(path: Path, value: dict[str, Any], *, mode: int = 0o600) -> str:
    """Write one bounded parent-owned artifact atomically outside the repository."""

    authority().require_outside_repository(path, "adapter artifact", repository_root())
    authority().reject_symlink_ancestors(path, include_target=True)
    if path.exists() or path.is_symlink():
        raise AdapterError(f"adapter artifact already exists: {path}")
    payload = (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    if len(payload) > MAX_RECORD_BYTES:
        raise AdapterError("adapter artifact exceeds its byte bound")
    directory = path.parent
    descriptor, temporary = tempfile.mkstemp(dir=directory, prefix=".adapter-")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return digest_bytes(payload)


def write_private_bytes(path: Path, data: bytes, *, mode: int = 0o600) -> str:
    """Write one bounded parent-owned binary artifact outside the repository."""

    authority().require_outside_repository(path, "adapter artifact", repository_root())
    authority().reject_symlink_ancestors(path, include_target=True)
    if path.exists() or path.is_symlink():
        raise AdapterError(f"adapter artifact already exists: {path}")
    if len(data) > MAX_PATCH_BYTES:
        raise AdapterError("adapter artifact exceeds its byte bound")
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".adapter-")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return digest_bytes(data)


def read_private_artifact(path: Path, label: str) -> dict[str, Any]:
    raw = require_private_regular_file(path, label, MAX_RECORD_BYTES)
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise AdapterError(f"{label} must contain a JSON object")
    return document


def verified_member(
    state_path: Path, permit_path: Path | None, plan: str, operation: str
) -> dict[str, Any]:
    """Recheck committed group bytes, the live record, and the member permit."""

    module = authority()
    root = repository_root()
    try:
        module.require_group_permit(
            root,
            plan,
            operation,
            permit=str(permit_path) if permit_path is not None else None,
            state=str(state_path),
        )
    except module.GroupError as exc:
        raise AdapterError(str(exc)) from exc
    state = module.read_state(state_path)
    try:
        module.require_live_group(root, state)
        member = module.require_member(state, plan)
    except module.GroupError as exc:
        raise AdapterError(str(exc)) from exc
    permit = None
    if permit_path is not None:
        try:
            permit = module.verify_permit_document(root, str(permit_path))
        except module.GroupError as exc:
            raise AdapterError(str(exc)) from exc
    return {"state": state, "member": member, "permit": permit, "root": root}


def run_authority(state_path: Path, arguments: list[str]) -> str:
    """Advance the shared authority through its own command surface."""

    command = [
        sys.executable,
        str(Path(__file__).resolve().with_name("parallel-plan-state.py")),
        *arguments,
    ]
    completed = subprocess.run(
        command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise AdapterError(detail or "the group authority rejected the operation")
    return completed.stdout.decode("utf-8", "replace").strip()


def plan_write_scope(root: Path, plan_rel: str) -> list[str]:
    values = authority().parse_manifest_text(
        (root / plan_rel).read_text(encoding="utf-8")
    )
    scope = values.get("write_scope") or []
    normalized: list[str] = []
    for entry in scope:
        text = str(entry).strip()
        if not text or text.endswith("/") or text.startswith("/"):
            raise AdapterError(f"{plan_rel} declares an unusable write scope entry")
        candidate = PurePosixPath(text)
        if ".." in candidate.parts:
            raise AdapterError(f"{plan_rel} declares an unusable write scope entry")
        normalized.append(str(candidate))
    if not normalized:
        raise AdapterError(f"{plan_rel} declares no write scope")
    return sorted(set(normalized))


def require_paths_in_scope(paths: list[str], scope: list[str], label: str) -> None:
    allowed = set(scope)
    outside = sorted(path for path in paths if path not in allowed)
    if outside:
        raise AdapterError(
            f"{label} changes paths outside the member write scope: {', '.join(outside)}"
        )


def stage_worktree(root: Path) -> None:
    """Stage every applied change so additions and removals are visible.

    ``git apply`` leaves a newly created file untracked, and an unstaged
    comparison would silently drop it from both the scope check and the
    assembled patch. Staging first makes the index the single description of
    the assembled result, exactly as the worker builds a candidate.
    """

    git(root, "add", "--all")


def freeze_worktree_tree(root: Path) -> str:
    """Freeze the staged member result into one immutable Git tree object.

    Both the scope check and the handoff patch must describe exactly the same
    bytes. Reading the index twice would let a concurrent stage in the same
    live session widen the patch after the scope check already passed.
    """

    return git_text(root, "write-tree")


def changed_paths_in(root: Path, base: str) -> list[str]:
    output = git_text(root, "diff", "--cached", "--name-only", "-z", base)
    return sorted(entry for entry in output.split("\0") if entry)


def changed_paths_in_tree(root: Path, base: str, tree: str) -> list[str]:
    output = git_text(root, "diff", "--name-only", "-z", base, tree)
    return sorted(entry for entry in output.split("\0") if entry)


def tree_diff(root: Path, base: str, tree: str) -> bytes:
    completed = git(
        root,
        "-c",
        "core.abbrev=40",
        "diff",
        "--binary",
        "--full-index",
        "--no-color",
        "--no-ext-diff",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        base,
        tree,
    )
    return completed.stdout


def worktree_diff(root: Path, base: str) -> bytes:
    completed = git(
        root,
        "-c",
        "core.abbrev=40",
        "diff",
        "--cached",
        "--binary",
        "--full-index",
        "--no-color",
        "--no-ext-diff",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        base,
    )
    return completed.stdout


def commit_range_diff(root: Path, base: str, head: str) -> bytes:
    completed = git(
        root,
        "-c",
        "core.abbrev=40",
        "diff",
        "--binary",
        "--full-index",
        "--no-color",
        "--no-ext-diff",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        base,
        head,
    )
    return completed.stdout


def disposable_clone(root: Path, commit: str, workspace: Path) -> Path:
    """Create one credential-free local clone checked out at an exact commit."""

    clone = workspace / "assembly"
    completed = subprocess.run(
        [
            "git",
            "clone",
            "--no-hardlinks",
            "--quiet",
            "--no-checkout",
            "--local",
            str(root),
            str(clone),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=sanitized_git_environment(),
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise AdapterError(f"disposable clone failed: {detail}")
    git(clone, "remote", "remove", "origin", check=False)
    git(clone, "checkout", "--detach", "--force", commit)
    git(clone, "config", "user.name", "parallel plan adapter")
    git(clone, "config", "user.email", "adapter@example.invalid")
    return clone


def require_ancestor(root: Path, ancestor: str, descendant: str, label: str) -> None:
    completed = git(
        root, "merge-base", "--is-ancestor", ancestor, descendant, check=False
    )
    if completed.returncode != 0:
        raise AdapterError(label)


def resolve_commit(root: Path, revision: str, label: str) -> str:
    completed = git(root, "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}", check=False)
    if completed.returncode != 0:
        raise AdapterError(f"{label} does not name a commit in this repository")
    return completed.stdout.decode("utf-8").strip()


def ref_checkout(root: Path, target_ref: str) -> Path | None:
    """Return the worktree that currently has the target ref checked out."""

    listing = git_text(root, "worktree", "list", "--porcelain")
    current_path: Path | None = None
    for line in listing.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line[len("worktree ") :])
        elif line.startswith("branch ") and current_path is not None:
            if line[len("branch ") :].strip() == target_ref:
                return current_path
    return None


WORKTREE_GUARD_MODULE_NAME = "worktree_guard"
WORKTREE_GUARD_CANDIDATES = (
    "scripts/project_workflow/worktree_guard.py",
    ".project-agent-workflow/scripts/worktree_guard.py",
)


def load_worktree_guard(repository: Path) -> ModuleType | None:
    """Load the worktree guard this member repository ships, once per process.

    The cache is keyed by the resolved guard path so one member repository's
    guard never governs another that ships none.
    """

    resolved = None
    for relative in WORKTREE_GUARD_CANDIDATES:
        candidate = repository / relative
        if candidate.is_file():
            resolved = candidate.resolve()
            break
    if resolved is None:
        return None
    cached = sys.modules.get(WORKTREE_GUARD_MODULE_NAME)
    if cached is not None and Path(getattr(cached, "__file__", "") or "/").resolve() == resolved:
        return cached
    spec = importlib.util.spec_from_file_location(WORKTREE_GUARD_MODULE_NAME, resolved)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require_member_worktree(worktree: Path, plan: str) -> None:
    """Require this member to run in the managed worktree bound to its own plan.

    Two members of one group must not share a checkout, and neither may be the
    pre-existing checkout, because the dispatched worker writes where it starts.
    The binding names its exact plan, so a permit for one member cannot dispatch
    work into another member's worktree.
    """

    guard = load_worktree_guard(worktree)
    if guard is None:
        return
    try:
        guard.require_task_worktree(
            worktree,
            kind=guard.PLAN_TASK,
            plan=plan,
            action=f"dispatching group member {plan}",
        )
    except guard.GuardError as exc:
        raise AdapterError(str(exc)) from exc


def require_clean_checkout(worktree: Path) -> None:
    status = git_text(worktree, "status", "--porcelain")
    if status:
        raise AdapterError(
            f"the target checkout {worktree} has uncommitted work; publication is "
            "deferred instead of discarding user changes"
        )


# ---------------------------------------------------------------------------
# adapter-version
# ---------------------------------------------------------------------------


def command_adapter_version(args: argparse.Namespace) -> None:
    print(json.dumps({"adapter_version": ADAPTER_VERSION}, sort_keys=True))


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


def command_dispatch(args: argparse.Namespace) -> None:
    state_path = Path(args.state)
    permit_path = Path(args.permit)
    context = verified_member(state_path, permit_path, args.plan, "run")
    member = context["member"]
    permit = context["permit"]
    root = context["root"]
    worktree = Path(args.worktree).resolve()
    if not (worktree / ".git").exists():
        raise AdapterError("member worktree is not a Git working tree")
    worktree_head = git_text(worktree, "rev-parse", "HEAD")
    if worktree_head != permit["base_commit"]:
        raise AdapterError(
            "member worktree HEAD does not match the permitted member baseline"
        )
    require_clean_checkout(worktree)
    require_member_worktree(worktree, args.plan)

    worker = Path(args.worker_bin) if args.worker_bin else Path(__file__).resolve().with_name(
        "run-sandboxed-plan-worker.py"
    )
    if not worker.is_file():
        raise AdapterError("the sandboxed plan worker is unavailable")
    command = [
        sys.executable,
        str(worker),
        "run",
        args.plan,
        "--group-permit",
        str(permit_path),
        "--group-state",
        str(state_path),
        *args.worker_arg,
    ]
    completed = subprocess.run(
        command,
        check=False,
        cwd=str(worktree),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    readiness = {
        "schema_version": READINESS_SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "group_id": permit["group_id"],
        "group_description_digest": permit["group_description_digest"],
        "plan_path": args.plan,
        "permit_id": permit["permit_id"],
        "baseline_generation": permit["baseline_generation"],
        "base_commit": permit["base_commit"],
        "logical_member_id": member["logical_member_id"],
        "worktree_path": str(worktree),
        "worker_returncode": completed.returncode,
        "worker_stdout_digest": digest_bytes(completed.stdout),
        "worker_stderr_digest": digest_bytes(completed.stderr),
        "candidate_ready": completed.returncode == 0,
        # Readiness is parent-visible evidence only. It is not acceptance, not
        # a review result, not validation, and never authorizes publication.
        "acceptance": "not_accepted",
    }
    if args.candidate_manifest:
        manifest_path = Path(args.candidate_manifest)
        raw = require_private_regular_file(
            manifest_path, "candidate manifest", MAX_RECORD_BYTES
        )
        readiness["candidate_manifest_path"] = str(manifest_path)
        readiness["candidate_manifest_digest"] = digest_bytes(raw)
    output = Path(args.output)
    write_private_artifact(output, readiness, mode=0o400)
    sys.stderr.write(completed.stderr.decode("utf-8", "replace"))
    print(json.dumps({"readiness_record": str(output), "candidate_ready": readiness["candidate_ready"]}, sort_keys=True))
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


# ---------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------


def load_candidate_manifest(path: Path, plan: str) -> dict[str, Any]:
    raw = require_private_regular_file(path, "candidate manifest", MAX_RECORD_BYTES)
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError("candidate manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise AdapterError("candidate manifest must contain a JSON object")
    if manifest.get("plan_path") != plan:
        raise AdapterError("candidate manifest names a different plan")
    for field in ("source_head", "patch_path", "patch_digest", "changed_paths"):
        if field not in manifest:
            raise AdapterError(f"candidate manifest is missing {field}")
    manifest["_manifest_digest"] = digest_bytes(raw)
    return manifest


def candidate_patch_bytes(manifest_path: Path, manifest: dict[str, Any]) -> bytes:
    patch_path = Path(str(manifest["patch_path"])).expanduser()
    if not patch_path.is_absolute():
        patch_path = (manifest_path.parent / patch_path).absolute()
    patch = require_private_regular_file(patch_path, "candidate patch", MAX_PATCH_BYTES)
    if hashlib.sha256(patch).hexdigest() != manifest["patch_digest"]:
        raise AdapterError("candidate patch digest no longer matches its manifest")
    if not patch:
        raise AdapterError("candidate patch is empty")
    return patch


def apply_patch(clone: Path, patch: bytes, label: str) -> None:
    check = subprocess.run(
        ["git", "-C", str(clone), "apply", "--check", "--whitespace=nowarn", "-"],
        input=patch,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=sanitized_git_environment(),
    )
    if check.returncode != 0:
        detail = check.stderr.decode("utf-8", "replace").strip()
        raise AdapterError(f"{label} does not apply to the current baseline: {detail}")
    applied = subprocess.run(
        ["git", "-C", str(clone), "apply", "--whitespace=nowarn", "-"],
        input=patch,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=sanitized_git_environment(),
    )
    if applied.returncode != 0:
        detail = applied.stderr.decode("utf-8", "replace").strip()
        raise AdapterError(f"{label} failed to apply: {detail}")


def load_member_handoff(path: Path, plan: str) -> dict[str, Any]:
    """Read one immutable parent-direct member handoff record.

    A member session freezes its result with ``member-ready``. The private
    record it leaves behind is the only description integration accepts: it
    names the exact member baseline, result tree, session identity and patch,
    and it declares that nothing has been accepted yet.
    """

    record = read_private_artifact(path, "member handoff record")
    if record.get("schema_version") != HANDOFF_SCHEMA_VERSION:
        raise AdapterError("member handoff record must declare schema_version 1")
    if record.get("handoff_mode") != HANDOFF_MODE:
        raise AdapterError("member handoff record names another handoff mode")
    if record.get("plan_path") != plan:
        raise AdapterError("member handoff record names a different plan")
    if record.get("acceptance") != "not_accepted":
        raise AdapterError(
            "a member handoff record never carries acceptance; members report "
            "readiness and integration owns acceptance"
        )
    for field in (
        "base_commit",
        "member_head",
        "result_tree",
        "session_digest",
        "session_generation",
        "patch_path",
        "patch_digest",
        "changed_paths",
        "changed_paths_digest",
        "write_scope",
        "record_digest",
    ):
        if field not in record:
            raise AdapterError(f"member handoff record is missing {field}")
    expected = canonical_digest(
        {key: value for key, value in record.items() if key != "record_digest"}
    )
    if expected != record["record_digest"]:
        raise AdapterError("member handoff record digest verification failed")
    return record


def handoff_patch_bytes(record_path: Path, record: dict[str, Any]) -> bytes:
    patch_path = Path(str(record["patch_path"])).expanduser()
    if not patch_path.is_absolute():
        patch_path = (record_path.parent / patch_path).absolute()
    patch = require_private_regular_file(patch_path, "member patch", MAX_PATCH_BYTES)
    if not patch:
        raise AdapterError("member patch is empty")
    if digest_bytes(patch) != record["patch_digest"]:
        raise AdapterError("member patch digest no longer matches its handoff record")
    return patch


def resolve_candidate_input(args: argparse.Namespace) -> dict[str, Any]:
    """Resolve the sandboxed-worker candidate handoff mode."""

    context = verified_member(
        Path(args.state), Path(args.permit), args.plan, "execution"
    )
    state = context["state"]
    member = context["member"]
    permit = context["permit"]
    root = context["root"]
    current_target = resolve_commit(root, state["target_ref"], "group target ref")
    if permit["base_commit"] != current_target:
        raise AdapterError(
            "the member permit is bound to a superseded baseline; transfer the "
            "member baseline to the current target before assembling"
        )
    manifest_path = Path(args.manifest)
    manifest = load_candidate_manifest(manifest_path, args.plan)
    original_head = str(manifest["source_head"])
    resolve_commit(root, original_head, "candidate source head")
    require_ancestor(
        root,
        original_head,
        current_target,
        "the candidate baseline is not an ancestor of the current target; the "
        "candidate cannot be assembled onto this target",
    )
    return {
        "handoff_mode": "candidate",
        "state": state,
        "member": member,
        "root": root,
        "current_target": current_target,
        "patch": candidate_patch_bytes(manifest_path, manifest),
        "adjustment_permit_id": permit["permit_id"],
        "incoming_digest": manifest["_manifest_digest"],
        "provenance": {
            "permit_id": permit["permit_id"],
            "baseline_generation": permit["baseline_generation"],
            "original_source_head": original_head,
            "original_manifest_path": str(manifest_path),
            "original_manifest_digest": manifest["_manifest_digest"],
            "original_patch_digest": "sha256:" + str(manifest["patch_digest"]),
            "original_worker_receipt_digest": (
                "sha256:" + str(manifest["worker_completion_receipt_digest"])
                if isinstance(manifest.get("worker_completion_receipt_digest"), str)
                else ""
            ),
            "original_member_head": "",
            "original_result_tree": "",
            "original_session_digest": "",
            "original_session_generation": -1,
            "original_worktree_path": "",
            "original_branch_ref": "",
            "original_handoff_path": "",
            "original_handoff_record_digest": "",
            "original_changed_paths_digest": "",
        },
        "group_id": permit["group_id"],
        "group_description_digest": permit["group_description_digest"],
    }


def resolve_handoff_input(args: argparse.Namespace) -> dict[str, Any]:
    """Resolve the parent-direct member-session handoff mode."""

    context = verified_session_member(Path(args.state), args.plan)
    state = context["state"]
    member = context["member"]
    root = context["root"]
    submitted = member["handoff"]
    if submitted is None:
        raise AdapterError(
            f"member {args.plan} has submitted no handoff; run member-ready in "
            "the member session before integration assembles its result"
        )
    record_path = Path(args.handoff)
    record = load_member_handoff(record_path, args.plan)
    # Stale evidence: the private record must still be the exact artifact the
    # authority accepted, and the authority binding must still describe the
    # member's current baseline and plan bytes.
    for field, label in (
        ("record_digest", "record digest"),
        ("patch_digest", "patch digest"),
        ("changed_paths_digest", "changed-path digest"),
        ("base_commit", "baseline"),
        ("plan_digest", "plan digest"),
    ):
        if submitted[field] != record[field]:
            raise AdapterError(
                f"the submitted member handoff names another {label}; the private "
                "record is stale or was replaced"
            )
    if submitted["generation"] != record["session_generation"]:
        raise AdapterError(
            "the submitted member handoff names another session generation"
        )
    if submitted["session_digest"] != record["session_digest"]:
        raise AdapterError("the submitted member handoff names another session")
    if member["base_commit"] != record["base_commit"]:
        raise AdapterError(
            "the member baseline moved after this handoff; transfer the baseline "
            "and take a fresh handoff before assembling"
        )
    if record["group_id"] != state["group_id"]:
        raise AdapterError("the member handoff record names another group")
    if record["group_description_digest"] != state["group_description_digest"]:
        raise AdapterError(
            "the member handoff record names another committed group description"
        )
    current_target = resolve_commit(root, state["target_ref"], "group target ref")
    resolve_commit(root, record["base_commit"], "member handoff baseline")
    require_ancestor(
        root,
        record["base_commit"],
        current_target,
        "the member baseline is not an ancestor of the current target; transfer "
        "the member baseline to the current target before assembling",
    )
    return {
        "handoff_mode": HANDOFF_MODE,
        "state": state,
        "member": member,
        "root": root,
        "current_target": current_target,
        "patch": handoff_patch_bytes(record_path, record),
        "adjustment_permit_id": record["record_digest"],
        "incoming_digest": record["record_digest"],
        "provenance": {
            "permit_id": "",
            "baseline_generation": member["baseline_generation"],
            "original_source_head": record["base_commit"],
            "original_manifest_path": "",
            "original_manifest_digest": "",
            "original_patch_digest": record["patch_digest"],
            "original_worker_receipt_digest": "",
            "original_member_head": record["member_head"],
            "original_result_tree": record["result_tree"],
            "original_session_digest": record["session_digest"],
            "original_session_generation": record["session_generation"],
            "original_worktree_path": str(record["worktree_path"]),
            "original_branch_ref": str(record["branch_ref"]),
            "original_handoff_path": str(record_path.absolute()),
            "original_handoff_record_digest": record["record_digest"],
            "original_changed_paths_digest": record["changed_paths_digest"],
        },
        "group_id": record["group_id"],
        "group_description_digest": record["group_description_digest"],
    }


def command_assemble(args: argparse.Namespace) -> None:
    if bool(args.manifest) == bool(args.handoff):
        raise AdapterError(
            "assemble one handoff mode: pass --manifest with --permit for a "
            "sandboxed candidate, or --handoff for a parent-direct member result"
        )
    if args.manifest and not args.permit:
        raise AdapterError("a candidate assembly requires its member permit")
    if args.handoff and args.permit:
        raise AdapterError(
            "a parent-direct member handoff carries no candidate permit"
        )
    source = (
        resolve_candidate_input(args)
        if args.manifest
        else resolve_handoff_input(args)
    )
    state_path = Path(args.state)
    state = source["state"]
    member = source["member"]
    root = source["root"]

    target_ref = state["target_ref"]
    current_target = source["current_target"]
    patch = source["patch"]
    scope = plan_write_scope(root, args.plan)

    resolution_patch: bytes | None = None
    if args.resolution:
        resolution_path = Path(args.resolution)
        resolution_patch = require_private_regular_file(
            resolution_path, "parent resolution patch", MAX_PATCH_BYTES
        )
        if not resolution_patch:
            raise AdapterError("parent resolution patch is empty")

    workspace = Path(tempfile.mkdtemp(prefix="parallel-plan-assembly-"))
    os.chmod(workspace, 0o700)
    try:
        clone = disposable_clone(root, current_target, workspace)
        direct_failure: str | None = None
        try:
            apply_patch(clone, patch, "the admitted candidate patch")
            resolution_kind = "unchanged_application"
        except AdapterError as exc:
            direct_failure = str(exc)
            resolution_kind = "parent_adjusted"
        if resolution_kind == "parent_adjusted":
            if resolution_patch is None:
                raise AdapterError(
                    f"{direct_failure}; supply --resolution with a parent-authored "
                    "patch against the current target after reserving the parent "
                    "adjustment slot"
                )
            adjustment = member["parent_adjustment"]
            if adjustment["state"] != "reserved":
                raise AdapterError(
                    "a substantive parent conflict edit requires the reserved "
                    "parent adjustment slot from the group authority"
                )
            if adjustment["permit_id"] != source["adjustment_permit_id"]:
                raise AdapterError(
                    "the reserved parent adjustment names a different member result"
                )
            if adjustment["incoming_candidate_digest"] != source["incoming_digest"]:
                raise AdapterError(
                    "the reserved parent adjustment is bound to a different "
                    "incoming candidate"
                )
            git(clone, "checkout", "--force", "--detach", current_target)
            apply_patch(clone, resolution_patch, "the parent resolution patch")
        elif resolution_patch is not None:
            raise AdapterError(
                "the admitted candidate applies unchanged; a parent resolution "
                "patch would silently replace the worker result"
            )

        stage_worktree(clone)
        changed = changed_paths_in(clone, current_target)
        if not changed:
            raise AdapterError("the assembled result changes nothing")
        require_paths_in_scope(changed, scope, "the assembled result")
        final_patch = worktree_diff(clone, current_target)
        if not final_patch:
            raise AdapterError("the assembled result produced an empty patch")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    output = Path(args.output)
    authority().require_outside_repository(output, "assembly record", root)
    patch_output = output.parent / f"{output.name}.patch"
    if patch_output.exists() or patch_output.is_symlink():
        raise AdapterError(f"assembled patch already exists: {patch_output}")
    descriptor = os.open(
        patch_output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400
    )
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(final_patch)

    record = {
        "schema_version": ASSEMBLY_SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "handoff_mode": source["handoff_mode"],
        "group_id": source["group_id"],
        "group_description_digest": source["group_description_digest"],
        "plan_path": args.plan,
        "logical_member_id": member["logical_member_id"],
        "target_ref": target_ref,
        "base_commit": current_target,
        **source["provenance"],
        "resolution_kind": resolution_kind,
        # A parent-resolved result is parent-authored evidence. It never claims
        # that the worker produced or validated these revised bytes.
        "result_author": "worker" if resolution_kind == "unchanged_application" else "parent",
        "assembled_patch_path": str(patch_output),
        "assembled_patch_digest": digest_bytes(final_patch),
        "changed_paths": changed,
        "write_scope": scope,
        "plan_digest": member["plan_digest"],
        "review_required": True,
        "validation_required": True,
    }
    record["record_digest"] = canonical_digest(record)
    write_private_artifact(output, record, mode=0o400)
    if resolution_kind == "parent_adjusted":
        run_authority(
            state_path,
            [
                "adjust-close",
                str(state_path),
                "--member",
                args.plan,
                "--permit-id",
                source["adjustment_permit_id"],
                "--incoming-candidate-digest",
                source["incoming_digest"],
                "--patch-digest",
                record["assembled_patch_digest"],
            ],
        )
    print(
        json.dumps(
            {
                "assembly_record": str(output),
                "assembled_patch": str(patch_output),
                "handoff_mode": source["handoff_mode"],
                "resolution_kind": resolution_kind,
                "base_commit": current_target,
            },
            sort_keys=True,
        )
    )


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------


def load_assembly_record(path: Path, plan: str) -> dict[str, Any]:
    record = read_private_artifact(path, "assembly record")
    if record.get("schema_version") != ASSEMBLY_SCHEMA_VERSION:
        raise AdapterError("assembly record must declare schema_version 1")
    if record.get("plan_path") != plan:
        raise AdapterError("assembly record names a different plan")
    expected = canonical_digest(
        {key: value for key, value in record.items() if key != "record_digest"}
    )
    if expected != record.get("record_digest"):
        raise AdapterError("assembly record digest verification failed")
    return record


def reviews_of_assembly(state: dict[str, Any], plan: str, record_digest: str) -> int:
    """Count independent reviews of one exact assembled artifact.

    Publication needs evidence about the result it is about to publish, not
    merely a review that happened earlier at the same baseline. A review of a
    superseded assembly therefore never admits a different assembled result,
    and a baseline transfer discards every earlier review target.
    """

    count = 0
    for event in state["events"]:
        detail = event.get("detail") or {}
        if detail.get("plan_path") != plan:
            continue
        if event["event_type"] == "member_baseline_transferred":
            count = 0
        elif (
            event["event_type"] == "member_review_recorded"
            and detail.get("assembly_record_digest") == record_digest
        ):
            count += 1
    return count


def command_publish(args: argparse.Namespace) -> None:
    state_path = Path(args.state)
    record = load_assembly_record(Path(args.assembly), args.plan)
    parent_direct = record.get("handoff_mode") == HANDOFF_MODE
    if parent_direct:
        if args.permit:
            raise AdapterError(
                "a parent-direct member publication carries no candidate permit"
            )
        context = verified_session_member(state_path, args.plan)
        permit = None
    else:
        if not args.permit:
            raise AdapterError("a candidate publication requires its member permit")
        context = verified_member(state_path, Path(args.permit), args.plan, "apply")
        permit = context["permit"]
    state = context["state"]
    member = context["member"]
    root = context["root"]

    if state["publication_lease"]["owner"] != args.owner:
        raise AdapterError(
            "publication requires the exclusive publication lease for this parent"
        )
    if state["publication_lease"]["plan_path"] != args.plan:
        raise AdapterError("the publication lease was acquired for another member")
    if member["publication"]["published"]:
        raise AdapterError("this member already published its accepted result")

    if parent_direct:
        submitted = member["handoff"]
        if submitted is None:
            raise AdapterError(
                "the member withdrew its handoff; integration publishes only a "
                "submitted member result"
            )
        if record["original_handoff_record_digest"] != submitted["record_digest"]:
            raise AdapterError("the assembly record names another member handoff")
    elif record["permit_id"] != permit["permit_id"]:
        raise AdapterError("the assembly record names a superseded member permit")
    if reviews_of_assembly(state, args.plan, record["record_digest"]) < 1:
        raise AdapterError(
            "publication requires one qualifying independent review of the exact "
            "assembled result at the current baseline"
        )

    target_ref = state["target_ref"]
    expected_old = record["base_commit"]
    current_target = resolve_commit(root, target_ref, "group target ref")
    if current_target != expected_old:
        raise AdapterError(
            "the publication target moved after review and validation; the "
            "proposed publication is invalid for the new target"
        )

    new_commit = resolve_commit(root, args.commit, "reviewed commit")
    require_ancestor(
        root,
        expected_old,
        new_commit,
        "the reviewed commit is not a descendant of the reviewed baseline; only a "
        "checked fast-forward may advance the target",
    )
    if new_commit == expected_old:
        raise AdapterError("the reviewed commit does not advance the target")
    produced = commit_range_diff(root, expected_old, new_commit)
    if digest_bytes(produced) != record["assembled_patch_digest"]:
        raise AdapterError(
            "the reviewed commit's complete product diff differs from the admitted "
            "assembled patch"
        )

    checkout = ref_checkout(root, target_ref)
    if checkout is not None:
        require_clean_checkout(checkout)

    journal_path = Path(args.journal)
    journal = {
        "schema_version": PUBLICATION_JOURNAL_SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "state": "intended",
        "group_id": state["group_id"],
        "plan_path": args.plan,
        "handoff_mode": record.get("handoff_mode", "candidate"),
        "permit_id": permit["permit_id"] if permit is not None else "",
        "handoff_record_digest": (
            record["original_handoff_record_digest"] if parent_direct else ""
        ),
        "integration_session_id": args.integration_session_id or "",
        "integration_session_pid": (
            args.integration_session_pid if args.integration_session_pid else 0
        ),
        "member_worktree_path": (
            record["original_worktree_path"] if parent_direct else ""
        ),
        "member_branch_ref": record["original_branch_ref"] if parent_direct else "",
        "member_head": record["original_member_head"] if parent_direct else "",
        "member_result_tree": record["original_result_tree"] if parent_direct else "",
        "owner": args.owner,
        "target_ref": target_ref,
        "expected_old_commit": expected_old,
        "new_commit": new_commit,
        "assembly_record_path": str(Path(args.assembly).absolute()),
        "assembled_patch_digest": record["assembled_patch_digest"],
        "assembly_record_digest": record["record_digest"],
        "target_checkout": str(checkout) if checkout is not None else "",
        "state_path": str(state_path.absolute()),
    }
    journal["journal_digest"] = canonical_digest(journal)
    write_private_artifact(journal_path, journal, mode=0o600)

    advance_target(root, journal)
    finalize_publication(state_path, journal_path, journal, root)
    retirement = retire_member_worktree(root, journal_path, journal)
    print(
        json.dumps(
            {
                "published_commit": new_commit,
                "target_ref": target_ref,
                "plan_path": args.plan,
                "member_retirement": retirement,
            },
            sort_keys=True,
        )
    )


def retire_member_worktree(
    root: Path, journal_path: Path, journal: dict[str, Any]
) -> str:
    """Retire the member worktree only after its result reached the target.

    The member session owns no retirement authority, so integration writes the
    exact evidence it verified — group, plan, worktree, branch, frozen member
    head, and the published commit — and the worktree manager rechecks every
    one of those facts before it removes anything. A failed retirement leaves a
    published result and a preserved worktree, which the same authorization
    finishes on the next attempt.
    """

    if journal.get("handoff_mode") != HANDOFF_MODE:
        return "not_applicable"
    authorization = {
        "schema_version": 1,
        "adapter_version": ADAPTER_VERSION,
        "authorization_kind": "parallel_group_member_retirement",
        "repository_identity": authority()
        .worktree_manager()
        .guard.repository_identity(root),
        "group_id": journal["group_id"],
        "plan_path": journal["plan_path"],
        "member_worktree_path": journal["member_worktree_path"],
        "member_branch_ref": journal["member_branch_ref"],
        "member_head": journal["member_head"],
        "member_result_tree": journal["member_result_tree"],
        "target_ref": journal["target_ref"],
        "published_commit": journal["new_commit"],
        "assembly_record_digest": journal["assembly_record_digest"],
        "assembled_patch_digest": journal["assembled_patch_digest"],
        "handoff_record_digest": journal["handoff_record_digest"],
    }
    authorization["authorization_digest"] = canonical_digest(authorization)
    authorization_path = journal_path.parent / f"{journal_path.name}.retirement"
    if authorization_path.exists() or authorization_path.is_symlink():
        authorization_path.unlink()
    write_private_artifact(authorization_path, authorization, mode=0o600)
    command = [
        sys.executable,
        str(Path(__file__).resolve().with_name("manage-plan-worktrees.py")),
        "retire",
        journal["plan_path"],
        "--owner-id",
        journal["owner"],
        "--integration-authorization",
        str(authorization_path),
    ]
    completed = subprocess.run(
        command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise AdapterError(
            "the member result is published, but its worktree retirement was "
            f"refused and the worktree is preserved: {detail}"
        )
    return "retired"


def advance_target(root: Path, journal: dict[str, Any]) -> None:
    """Advance the target ref by one checked fast-forward, never a merge."""

    checkout = journal["target_checkout"]
    if checkout:
        worktree = Path(checkout)
        require_clean_checkout(worktree)
        head = git_text(worktree, "rev-parse", "HEAD")
        if head != journal["expected_old_commit"]:
            raise AdapterError("the target checkout moved before publication")
        git(worktree, "merge", "--ff-only", journal["new_commit"])
        return
    git(
        root,
        "update-ref",
        journal["target_ref"],
        journal["new_commit"],
        journal["expected_old_commit"],
    )


def rewrite_journal(path: Path, journal: dict[str, Any], new_state: str) -> None:
    if new_state not in JOURNAL_STATES:
        raise AdapterError(f"unknown publication journal state: {new_state}")
    updated = dict(journal)
    updated["state"] = new_state
    updated.pop("journal_digest", None)
    updated["journal_digest"] = canonical_digest(
        {**updated, "state": "intended"}
    )
    payload = (
        json.dumps(updated, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".journal-")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def finalize_publication(
    state_path: Path, journal_path: Path, journal: dict[str, Any], root: Path
) -> None:
    identity = (
        [
            "--handoff-digest",
            journal["handoff_record_digest"],
            "--integration-session-id",
            journal["integration_session_id"],
            "--integration-session-pid",
            str(journal["integration_session_pid"]),
        ]
        if journal.get("handoff_mode") == HANDOFF_MODE
        else ["--permit-id", journal["permit_id"]]
    )
    run_authority(
        state_path,
        [
            "publication-record",
            str(state_path),
            "--member",
            journal["plan_path"],
            *identity,
            "--commit",
            journal["new_commit"],
            "--assembly-digest",
            journal["assembly_record_digest"],
        ],
    )
    rewrite_journal(journal_path, journal, "completed")


def command_publish_recover(args: argparse.Namespace) -> None:
    journal_path = Path(args.journal)
    journal = read_private_artifact(journal_path, "publication journal")
    if journal.get("schema_version") != PUBLICATION_JOURNAL_SCHEMA_VERSION:
        raise AdapterError("publication journal must declare schema_version 1")
    expected = canonical_digest(
        {
            **{key: value for key, value in journal.items() if key != "journal_digest"},
            "state": "intended",
        }
    )
    if expected != journal.get("journal_digest"):
        raise AdapterError("publication journal identity verification failed")
    if journal["state"] != "intended":
        print(json.dumps({"recovery": "noop", "state": journal["state"]}, sort_keys=True))
        return

    root = repository_root()
    state_path = Path(journal["state_path"])
    current = resolve_commit(root, journal["target_ref"], "group target ref")
    if current == journal["new_commit"]:
        checkout = journal["target_checkout"]
        if checkout:
            worktree = Path(checkout)
            require_clean_checkout(worktree)
            if git_text(worktree, "rev-parse", "HEAD") != journal["new_commit"]:
                raise AdapterError(
                    "the interrupted publication left an inconsistent target "
                    "checkout; the target is preserved and completion is refused"
                )
        finalize_publication(state_path, journal_path, journal, root)
        retirement = retire_member_worktree(root, journal_path, journal)
        print(
            json.dumps(
                {
                    "recovery": "finalized",
                    "commit": journal["new_commit"],
                    "member_retirement": retirement,
                },
                sort_keys=True,
            )
        )
        return
    if current == journal["expected_old_commit"]:
        rewrite_journal(journal_path, journal, "aborted")
        print(json.dumps({"recovery": "aborted", "commit": current}, sort_keys=True))
        return
    raise AdapterError(
        "the target is neither the expected old commit nor the planned new "
        "commit; the target is preserved and publication is not replayed"
    )


HANDOFF_SCHEMA_VERSION = 1
HANDOFF_MODE = "parent_direct"


def verified_session_member(state_path: Path, plan: str) -> dict[str, Any]:
    """Recheck the committed schema-2 group and resolve one parent-direct member."""

    module = authority()
    root = repository_root()
    try:
        enrolled = module.session_enrolment(root, plan)
    except module.GroupError as exc:
        raise AdapterError(str(exc)) from exc
    if enrolled is None:
        raise AdapterError(
            f"{plan} is not enrolled in a committed schema-2 parent-direct group"
        )
    try:
        state = module.read_state(state_path)
        module.require_session_state(root, state_path, state)
        member = module.require_member(state, plan)
        module.require_active_member(member)
    except module.GroupError as exc:
        raise AdapterError(str(exc)) from exc
    if state["group_id"] != enrolled["group_id"]:
        raise AdapterError("the member session state belongs to a different group")
    return {"state": state, "member": member, "root": root, "enrolled": enrolled}


def require_open_member_writing(member: dict[str, Any], plan: str) -> None:
    if member["handoff"] is not None:
        raise AdapterError(
            f"member {plan} closed its writing claim with a submitted handoff; "
            "integration owns the result and members never publish"
        )


def require_bound_member_session(
    member: dict[str, Any], session_id: str, session_pid: int
) -> dict[str, Any]:
    """Require the exact live session and process this member is bound to."""

    module = authority()
    binding = member["session_binding"]
    if binding is None or binding["state"] != "bound":
        raise AdapterError("member session has no completed live worktree binding")
    try:
        if binding["session_digest"] != module.session_identity(session_id):
            raise AdapterError("member operation belongs to a different session")
        observed = module.require_session_process(session_pid)
        if observed != binding["process_identity"]:
            raise AdapterError("member operation belongs to a stale session process")
    except module.GroupError as exc:
        raise AdapterError(str(exc)) from exc
    return binding


def run_member_preparation(args: argparse.Namespace, *, operation: str) -> None:
    """Bind or rebind one operator-started member session to its exact checkout.

    The adapter never starts an agent. It delegates to the managed worktree
    command, rechecks the resulting binding against the group record, and
    returns the exact checkout that operator-started session must write in.
    """

    state_path = Path(args.state)
    context = verified_session_member(state_path, args.plan)
    member = context["member"]
    require_open_member_writing(member, args.plan)
    binding = member["session_binding"]
    if operation == "prepare" and binding is not None and binding["state"] == "bound":
        raise AdapterError(
            "member session already started; use member-resume after the prior "
            "session stopped writing"
        )
    if operation == "resume" and binding is None:
        raise AdapterError("member has no prior session to resume")
    command = [
        sys.executable,
        str(Path(__file__).resolve().with_name("manage-plan-worktrees.py")),
        operation,
        args.plan,
        "--session-id",
        args.session_id,
        "--session-pid",
        str(args.session_pid),
    ]
    if args.allowed_root:
        command += ["--allowed-root", args.allowed_root]
    if operation == "resume":
        # The managed command requires an owner identifier, and the session
        # path replaces it with the group-derived member owner.
        command += ["--owner-id", "parent"]
    completed = subprocess.run(
        command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise AdapterError(detail or "member session preparation was refused")
    try:
        result = json.loads(completed.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise AdapterError("member session preparation returned no usable record") from exc
    refreshed = verified_session_member(state_path, args.plan)
    bound = require_bound_member_session(
        refreshed["member"], args.session_id, args.session_pid
    )
    worktree = Path(bound["worktree_path"])
    if not isinstance(result, dict) or result.get("worktree") != str(worktree):
        raise AdapterError(
            "the prepared worktree differs from the recorded member session binding"
        )
    require_member_worktree(worktree, args.plan)
    print(json.dumps({
        "operation": operation,
        "adapter_version": ADAPTER_VERSION,
        "group_id": refreshed["state"]["group_id"],
        "plan_path": args.plan,
        "logical_member_id": refreshed["member"]["logical_member_id"],
        "worktree": str(worktree),
        "branch_ref": bound["branch_ref"],
        "base_commit": refreshed["member"]["base_commit"],
        "session_generation": bound["generation"],
        "member_writing_open": True,
        "review_authority": "integration",
        "publication_enabled": False,
    }, sort_keys=True))


def command_member_start(args: argparse.Namespace) -> None:
    run_member_preparation(args, operation="prepare")


def command_member_resume(args: argparse.Namespace) -> None:
    run_member_preparation(args, operation="resume")


def command_member_ready(args: argparse.Namespace) -> None:
    """Freeze one member result into a parent-direct handoff and close writing.

    The handoff carries the member's plan identity, ownership generation,
    admitted baseline, and the full Git diff of its checkout against that
    baseline, including staged, unstaged, added, and deleted product paths. It
    is evidence for integration only: it is not acceptance, not review, not
    validation, and it never authorizes member publication.
    """

    state_path = Path(args.state)
    output = Path(args.output).resolve()
    context = verified_session_member(state_path, args.plan)
    state = context["state"]
    member = context["member"]
    root = context["root"]
    require_open_member_writing(member, args.plan)
    binding = require_bound_member_session(member, args.session_id, args.session_pid)
    worktree = Path(args.worktree).resolve()
    if binding["worktree_path"] != str(worktree):
        raise AdapterError(
            "member readiness names a different worktree than its session binding"
        )
    if not (worktree / ".git").exists():
        raise AdapterError("member worktree is not a Git working tree")
    require_member_worktree(worktree, args.plan)
    base = member["base_commit"]
    head = git_text(worktree, "rev-parse", "HEAD")
    require_ancestor(worktree, base, head, "the member baseline")
    # Staging is what makes new and deleted files part of one frozen
    # description. It changes no file content in the member checkout.
    stage_worktree(worktree)
    tree = freeze_worktree_tree(worktree)
    changed = changed_paths_in_tree(worktree, base, tree)
    if not changed:
        raise AdapterError("the member result changes nothing")
    scope = plan_write_scope(root, args.plan)
    require_paths_in_scope(changed, scope, "the member result")
    patch = tree_diff(worktree, base, tree)
    if not patch:
        raise AdapterError("the member result produced an empty patch")
    patch_path = output.with_name(output.name + ".patch")
    patch_digest = write_private_bytes(patch_path, patch)
    record = {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "handoff_mode": HANDOFF_MODE,
        "group_id": state["group_id"],
        "group_description_digest": state["group_description_digest"],
        "plan_path": args.plan,
        "plan_digest": member["plan_digest"],
        "logical_member_id": member["logical_member_id"],
        "base_commit": base,
        "member_head": head,
        "result_tree": tree,
        "session_digest": binding["session_digest"],
        "session_generation": binding["generation"],
        "worktree_path": binding["worktree_path"],
        "branch_ref": binding["branch_ref"],
        "patch_path": str(patch_path),
        "patch_digest": patch_digest,
        "changed_paths": changed,
        "changed_paths_digest": canonical_digest(changed),
        "write_scope": scope,
        "result_author": "member",
        "review_required": True,
        "validation_required": True,
        "acceptance": "not_accepted",
        "record_digest": "",
    }
    record["record_digest"] = canonical_digest(
        {key: value for key, value in record.items() if key != "record_digest"}
    )
    write_private_artifact(output, record)
    try:
        run_authority(state_path, [
            "session-handoff",
            str(state_path),
            "--member",
            args.plan,
            "--session-id",
            args.session_id,
            "--generation",
            str(binding["generation"]),
            "--base-commit",
            base,
            "--plan-digest",
            member["plan_digest"],
            "--patch-digest",
            patch_digest,
            "--changed-paths-digest",
            record["changed_paths_digest"],
            "--record-digest",
            record["record_digest"],
            "--record",
            str(output),
        ])
    except BaseException:
        # The authority refused, so no handoff exists. Remove the artifacts this
        # call just created instead of leaving a record nothing can consume.
        output.unlink(missing_ok=True)
        patch_path.unlink(missing_ok=True)
        raise
    print(json.dumps({
        "operation": "member-ready",
        "adapter_version": ADAPTER_VERSION,
        "plan_path": args.plan,
        "handoff_record": str(output),
        "record_digest": record["record_digest"],
        "patch_digest": patch_digest,
        "changed_paths": changed,
        "member_writing_open": False,
        "acceptance": "not_accepted",
        "publication_enabled": False,
    }, sort_keys=True))


# ---------------------------------------------------------------------------
# group-status
# ---------------------------------------------------------------------------


def command_group_status(args: argparse.Namespace) -> None:
    module = authority()
    state = module.read_state(Path(args.state))
    root = repository_root()
    try:
        module.require_live_group(root, state)
    except module.GroupError as exc:
        raise AdapterError(str(exc)) from exc
    members = {
        plan: {
            "state": member["state"],
            "stop_reason": member["stop_reason"],
            "baseline_generation": member["baseline_generation"],
            "base_commit": member["base_commit"],
            "published": member["publication"]["published"],
            "published_commit": member["publication"]["commit"],
            "counters": member["counters"],
        }
        for plan, member in sorted(state["members"].items())
    }
    complete = all(member["published"] for member in members.values())
    print(
        json.dumps(
            {
                "adapter_version": ADAPTER_VERSION,
                "group_id": state["group_id"],
                "target_ref": state["target_ref"],
                "members": members,
                "group_complete": complete,
            },
            sort_keys=True,
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    version = sub.add_parser(
        "adapter-version", help="report the installed grouped execution adapter version"
    )
    version.set_defaults(handler=command_adapter_version)

    dispatch = sub.add_parser(
        "dispatch", help="start one isolated member candidate and record readiness"
    )
    dispatch.add_argument("--state", required=True)
    dispatch.add_argument("--permit", required=True)
    dispatch.add_argument("--plan", required=True)
    dispatch.add_argument("--worktree", required=True)
    dispatch.add_argument("--output", required=True)
    dispatch.add_argument("--candidate-manifest")
    dispatch.add_argument("--worker-bin")
    dispatch.add_argument("--worker-arg", action="append", default=[])
    dispatch.set_defaults(handler=command_dispatch)

    assemble = sub.add_parser(
        "assemble", help="assemble one admitted candidate against the current target"
    )
    assemble.add_argument("--state", required=True)
    assemble.add_argument("--permit")
    assemble.add_argument("--plan", required=True)
    assemble.add_argument("--manifest")
    assemble.add_argument("--handoff")
    assemble.add_argument("--output", required=True)
    assemble.add_argument("--resolution")
    assemble.set_defaults(handler=command_assemble)

    publish = sub.add_parser(
        "publish", help="publish one reviewed commit to the still-current target"
    )
    publish.add_argument("--state", required=True)
    publish.add_argument("--permit")
    publish.add_argument("--plan", required=True)
    publish.add_argument("--assembly", required=True)
    publish.add_argument("--commit", required=True)
    publish.add_argument("--owner", required=True)
    publish.add_argument("--journal", required=True)
    publish.add_argument("--integration-session-id")
    publish.add_argument("--integration-session-pid", type=int)
    publish.set_defaults(handler=command_publish)

    recover = sub.add_parser(
        "publish-recover", help="finalize or refuse one interrupted publication"
    )
    recover.add_argument("--journal", required=True)
    recover.set_defaults(handler=command_publish_recover)

    status = sub.add_parser("group-status", help="report bounded group publication state")
    status.add_argument("--state", required=True)
    status.set_defaults(handler=command_group_status)

    for name, handler, summary in (
        ("member-start", command_member_start, "bind one operator-started member session"),
        ("member-resume", command_member_resume, "rebind one stopped member session"),
    ):
        member = sub.add_parser(name, help=summary)
        member.add_argument("--state", required=True)
        member.add_argument("--plan", required=True)
        member.add_argument("--session-id", required=True)
        member.add_argument("--session-pid", type=int, required=True)
        member.add_argument("--allowed-root")
        member.set_defaults(handler=handler)

    ready = sub.add_parser(
        "member-ready", help="freeze one member result and close its writing claim"
    )
    ready.add_argument("--state", required=True)
    ready.add_argument("--plan", required=True)
    ready.add_argument("--session-id", required=True)
    ready.add_argument("--session-pid", type=int, required=True)
    ready.add_argument("--worktree", required=True)
    ready.add_argument("--output", required=True)
    ready.set_defaults(handler=command_member_ready)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except AdapterError as exc:
        fail(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
