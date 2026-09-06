#!/usr/bin/env python3
"""Parent-owned authority for independent parallel plan execution.

The committed group description under ``docs/plan/execution-groups/`` declares an
exact finite member set. This module owns the mutable runtime authority for that
set: exclusive member permits, one upstream claim, one publication lease, the
single parent-adjustment slot, source-baseline transfers, and every member's
cumulative budgets and stop state. The runtime record lives outside the
repository; the committed description carries no runtime authority by itself.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


GROUP_DESCRIPTION_SCHEMA_VERSION = 1
GROUP_STATE_SCHEMA_VERSION = 1
GROUP_PERMIT_SCHEMA_VERSION = 1

# The grouped runner adapter is supplied by the integration plan. Until it is
# installed no production operation may proceed for an enrolled member, with or
# without a otherwise valid permit.
GROUPED_ADAPTER_VERSION: int | None = None

EXECUTION_GROUP_DIR = "docs/plan/execution-groups"
GROUP_MEMBER_COUNT = 2
MEMBER_INITIAL_GENERATION_LIMIT = 1
MEMBER_CORRECTION_LIMIT = 1
MEMBER_REVIEW_LIMIT = 2
MEMBER_PARENT_ADJUSTMENT_LIMIT = 1
MAX_GROUP_EVENTS = 64
TERMINAL_EVENT_RESERVE = 4
TERMINAL_EVENT_TYPES = frozenset({"member_stopped"})
MAX_BYTES = 65_536
GROUP_STATE_MAX_BYTES = 131_072
MAX_INDEPENDENCE_BYTES = 400

GROUP_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
PLAN_PATH_RE = re.compile(r"docs/plan/active/([0-9]{3})-[a-z0-9][a-z0-9-]*\.md")
GROUP_PATH_RE = re.compile(
    r"docs/plan/execution-groups/[a-z0-9][a-z0-9-]*\.json"
)
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
TARGET_REF_RE = re.compile(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]{0,127}")

GROUP_DESCRIPTION_KEYS = {
    "schema_version",
    "group_id",
    "target_ref",
    "declared_independence",
    "members",
}
GROUP_MEMBER_KEYS = {
    "plan_id",
    "plan_path",
    "plan_digest",
    "write_scope_digest",
}

# A delegated worker never owns validation or specification authority, so a
# member write scope that reaches one of these paths is refused before the group
# can be admitted. Both the root and generated namespaces are listed because the
# module is installed unchanged in a generated project.
GROUP_AUTHORITY_DENY_PATHS = (
    "AGENTS.md",
    "docs/agent/",
    "docs/plan/execution-groups/",
    "scripts/lint-project-workflow.sh",
    "scripts/plan_validation_commands.py",
    "scripts/plan-execution-state.py",
    "scripts/parallel-plan-state.py",
    "scripts/run-sandboxed-plan-worker.py",
    "tests/smoke.sh",
    ".project-agent-workflow/docs/agent/",
    ".project-agent-workflow/scripts/lint-project-workflow.sh",
    ".project-agent-workflow/scripts/plan_validation_commands.py",
    ".project-agent-workflow/scripts/plan-execution-state.py",
    ".project-agent-workflow/scripts/parallel-plan-state.py",
    ".project-agent-workflow/scripts/run-sandboxed-plan-worker.py",
)

GATED_OPERATIONS = (
    "run",
    "correct",
    "validate",
    "apply",
    "execution",
    "completion",
    "finalization",
    "archive",
)

MEMBER_STOP_REASONS = {
    "diagnosis_required",
    "repair_required",
    "replan_required",
    "descope_pending",
    "owner_stop",
    "authority_drift",
}

SCALAR_MANIFEST_KEYS = {"status", "plan_purpose", "execution_group"}
LIST_MANIFEST_KEYS = {
    "write_scope",
    "predecessor_plans",
    "context_files",
    "integration_gates",
}


class GroupError(ValueError):
    """A parallel group authority rule was violated."""


def digest(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical_digest(value: Any) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")))


def sanitized_git_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_") or key in {"GIT_EXEC_PATH", "GIT_SSL_CAINFO"}
    }


def git_output(root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=sanitized_git_environment(),
    )
    if completed.returncode != 0:
        raise GroupError(
            "git command failed: " + " ".join(arguments)
        )
    return completed.stdout


def repository_root(start: Path | None = None) -> Path:
    completed = subprocess.run(
        ["git", "-C", str(start or Path.cwd()), "rev-parse", "--show-toplevel"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=sanitized_git_environment(),
    )
    if completed.returncode != 0:
        raise GroupError("current directory is not a Git repository")
    return Path(completed.stdout.strip()).resolve()


def reject_symlink_ancestors(path: Path, *, include_target: bool) -> None:
    absolute = path.absolute()
    parts = absolute.parts
    current = Path(parts[0])
    limit = len(parts) if include_target else len(parts) - 1
    for part in parts[1:limit]:
        current /= part
        if current.is_symlink():
            raise GroupError(f"symlink path component is not allowed: {current}")


def require_outside_repository(path: Path, label: str, root: Path | None = None) -> None:
    resolved = root if root is not None else repository_root()
    # Normalize ".." and symlinked components so a traversal spelling cannot
    # place the mutable authority record inside the working tree.
    candidate = Path(os.path.realpath(path.absolute()))
    for target in {candidate, Path(os.path.realpath(candidate.parent)) / candidate.name}:
        try:
            target.relative_to(resolved)
        except ValueError:
            continue
        raise GroupError(f"{label} must be outside the repository")


def require_digest(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if allow_empty and value == "":
        return ""
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise GroupError(f"{label} must be sha256:<64 lowercase hex>")
    return value


def require_commit(value: Any, label: str) -> str:
    if not isinstance(value, str) or not COMMIT_RE.fullmatch(value):
        raise GroupError(f"{label} must be a full 40-character commit id")
    return value


def require_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
        raise GroupError(f"{label} must be a bounded identifier")
    return value


def exact_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GroupError(f"{label} must be an object")
    if set(value) != keys:
        missing = sorted(keys - set(value))
        extra = sorted(set(value) - keys)
        raise GroupError(
            f"{label} has unexpected keys (missing: {missing}, unexpected: {extra})"
        )
    return value


def read_bounded_bytes(path: Path, label: str, maximum: int = MAX_BYTES) -> bytes:
    reject_symlink_ancestors(path, include_target=True)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise GroupError(f"{label} must be a regular file")
        if metadata.st_nlink != 1:
            raise GroupError(f"{label} must not be hard linked")
        data = os.read(descriptor, maximum + 1)
    finally:
        os.close(descriptor)
    if len(data) > maximum:
        raise GroupError(f"{label} exceeds size limit")
    return data


def read_bounded_json(path: Path, label: str, maximum: int = MAX_BYTES) -> Any:
    data = read_bounded_bytes(path, label, maximum)
    try:
        return json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GroupError(f"{label} is invalid JSON") from exc


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    reject_symlink_ancestors(path, include_target=False)
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if len(data) > GROUP_STATE_MAX_BYTES:
        raise GroupError("group execution state exceeds size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    directory_descriptor = os.open(path.parent, directory_flags)
    temporary_name = f".{path.name}.{secrets.token_hex(16)}.tmp"
    descriptor = -1
    try:
        descriptor = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_descriptor,
        )
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(
            temporary_name,
            path.name,
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
        )
        os.fsync(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary_name, dir_fd=directory_descriptor)
        except FileNotFoundError:
            pass
        os.close(directory_descriptor)


def with_lock(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    reject_symlink_ancestors(lock_path, include_target=True)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    directory_descriptor = os.open(
        lock_path.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        descriptor = os.open(
            lock_path.name,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_descriptor,
        )
    finally:
        os.close(directory_descriptor)
    return os.fdopen(descriptor, "a", encoding="utf-8")


def parse_manifest_text(text: str) -> dict[str, Any]:
    values: dict[str, Any] = {key: [] for key in LIST_MANIFEST_KEYS}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            break
        if not line.strip():
            continue
        if ":" in line and not line.startswith(" "):
            key, rest = line.split(":", 1)
            key = key.strip()
            rest = rest.strip()
            current = None
            if key in SCALAR_MANIFEST_KEYS:
                values[key] = rest
            elif key in LIST_MANIFEST_KEYS:
                current = key
                if rest:
                    values[key].append(rest)
            continue
        if current and line.lstrip().startswith("- "):
            values[current].append(line.lstrip()[2:].strip())
    return values


def normalized_scope_path(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise GroupError("write scope entries must be nonblank")
    candidate = candidate.rstrip("/")
    if not candidate:
        raise GroupError("write scope entries must be nonblank")
    if candidate.startswith("/") or "\\" in candidate:
        raise GroupError(
            f"write scope entries must be repository-relative POSIX paths: {value!r}"
        )
    parts = candidate.split("/")
    if any(part in ("", ".", "..") for part in parts):
        # Independence and deny-list checks are prefix comparisons, so a
        # non-canonical spelling of the same path must never be admitted.
        raise GroupError(
            f"write scope entries must be canonical paths without '.', '..' or "
            f"empty components: {value!r}"
        )
    return candidate


def scopes_overlap(left: str, right: str) -> bool:
    first = normalized_scope_path(left)
    second = normalized_scope_path(right)
    if first == second:
        return True
    return first.startswith(second + "/") or second.startswith(first + "/")


def scope_reaches_authority(entry: str) -> bool:
    candidate = normalized_scope_path(entry)
    for denied in GROUP_AUTHORITY_DENY_PATHS:
        stripped = denied.rstrip("/")
        if candidate == stripped or candidate.startswith(stripped + "/"):
            return True
        if denied.endswith("/") and stripped.startswith(candidate + "/"):
            return True
    return False


def validate_group_description(
    data: Any,
    *,
    description_bytes: bytes,
    label: str,
) -> dict[str, Any]:
    """Validate the committed shape of one execution group description."""

    description = exact_object(data, GROUP_DESCRIPTION_KEYS, label)
    if description["schema_version"] != GROUP_DESCRIPTION_SCHEMA_VERSION:
        raise GroupError(f"{label} must declare schema_version 1")
    group_id = description["group_id"]
    if not isinstance(group_id, str) or not GROUP_ID_RE.fullmatch(group_id):
        raise GroupError(f"{label} group_id must be a bounded lowercase slug")
    target_ref = description["target_ref"]
    if not isinstance(target_ref, str) or not TARGET_REF_RE.fullmatch(target_ref):
        raise GroupError(f"{label} target_ref must name one exact local branch ref")
    independence = description["declared_independence"]
    if (
        not isinstance(independence, str)
        or not independence.strip()
        or len(independence.encode("utf-8")) > MAX_INDEPENDENCE_BYTES
    ):
        raise GroupError(
            f"{label} declared_independence must be bounded nonblank text"
        )
    members = description["members"]
    if not isinstance(members, list) or len(members) != GROUP_MEMBER_COUNT:
        raise GroupError(
            f"{label} must declare exactly {GROUP_MEMBER_COUNT} independent members"
        )
    own_digest = digest(description_bytes)
    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, raw in enumerate(members, start=1):
        member = exact_object(raw, GROUP_MEMBER_KEYS, f"{label} member {index}")
        plan_path = member["plan_path"]
        if not isinstance(plan_path, str):
            raise GroupError(f"{label} member {index} plan_path must be text")
        matched = PLAN_PATH_RE.fullmatch(plan_path)
        if matched is None:
            raise GroupError(
                f"{label} member {index} must name a numbered active plan path"
            )
        plan_id = member["plan_id"]
        if plan_id != matched.group(1):
            raise GroupError(
                f"{label} member {index} plan_id does not match its plan path"
            )
        plan_digest = require_digest(
            member["plan_digest"], f"{label} member {index} plan_digest"
        )
        scope_digest = require_digest(
            member["write_scope_digest"],
            f"{label} member {index} write_scope_digest",
        )
        if own_digest in {plan_digest, scope_digest}:
            raise GroupError(
                f"{label} must not contain a digest of itself"
            )
        if plan_id in seen_ids or plan_path in seen_paths:
            raise GroupError(f"{label} declares a duplicate member")
        seen_ids.add(plan_id)
        seen_paths.add(plan_path)
        validated.append(member)
    for value in json.dumps(description, sort_keys=True).split('"'):
        if COMMIT_RE.fullmatch(value):
            raise GroupError(f"{label} must not name its own containing commit")
    description["members"] = validated
    return description


def resolve_group_members(
    root: Path,
    description: dict[str, Any],
    label: str,
) -> dict[str, dict[str, Any]]:
    """Bind each declared member to its live plan and check independence."""

    resolved: dict[str, dict[str, Any]] = {}
    for member in description["members"]:
        plan_path = member["plan_path"]
        plan_file = root / plan_path
        if not plan_file.is_file():
            raise GroupError(f"{label} names a missing member plan: {plan_path}")
        plan_bytes = read_bounded_bytes(plan_file, f"{label} member plan", MAX_BYTES * 8)
        if digest(plan_bytes) != member["plan_digest"]:
            raise GroupError(
                f"{label} member plan digest does not match live bytes: {plan_path}"
            )
        manifest = parse_manifest_text(plan_bytes.decode("utf-8"))
        write_scope = [normalized_scope_path(entry) for entry in manifest["write_scope"]]
        if not write_scope:
            raise GroupError(f"{label} member plan declares no write scope: {plan_path}")
        if canonical_digest(write_scope) != member["write_scope_digest"]:
            raise GroupError(
                f"{label} member write scope digest does not match the plan: {plan_path}"
            )
        for entry in write_scope:
            if scope_reaches_authority(entry):
                raise GroupError(
                    f"{label} member write scope reaches validation or specification "
                    f"authority: {plan_path} -> {entry}"
                )
        resolved[plan_path] = {
            "member": member,
            "manifest": manifest,
            "write_scope": write_scope,
        }
    paths = sorted(resolved)
    first, second = paths[0], paths[1]
    for left in resolved[first]["write_scope"]:
        for right in resolved[second]["write_scope"]:
            if scopes_overlap(left, right):
                raise GroupError(
                    f"{label} members declare overlapping write scope: {left} / {right}"
                )
    for path in paths:
        manifest = resolved[path]["manifest"]
        others = [other for other in paths if other != path]
        for other in others:
            if other in manifest["predecessor_plans"]:
                raise GroupError(
                    f"{label} declares a member-to-member predecessor edge: {path}"
                )
            if other in manifest["context_files"]:
                raise GroupError(
                    f"{label} member declares dependence on unfinished member output: "
                    f"{path}"
                )
            for gate in manifest["integration_gates"]:
                if other in gate:
                    raise GroupError(
                        f"{label} member gate depends on another member: {path}"
                    )
        declared = manifest.get("execution_group")
        if declared and declared != label:
            raise GroupError(
                f"{label} member names a different execution group: {path}"
            )
    return resolved


def _git_path_set(root: Path, arguments: list[str], label: str) -> set[str]:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=sanitized_git_environment(),
    )
    if completed.returncode != 0:
        raise GroupError(f"could not list {label}")
    return {
        entry.decode("utf-8", "surrogateescape")
        for entry in completed.stdout.split(b"\0")
        if entry
    }


def tracked_description_labels(root: Path) -> set[str]:
    """Return group descriptions committed at HEAD or present in the index.

    HEAD is authoritative: a committed description keeps enrolling its members
    until its removal is itself committed, so a staged ``git rm`` cannot silently
    un-enrol a member.
    """

    labels: set[str] = set()
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "--quiet", "HEAD"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=sanitized_git_environment(),
    )
    if head.returncode == 0:
        labels |= _git_path_set(
            root,
            ["ls-tree", "-z", "-r", "--name-only", "HEAD", "--", EXECUTION_GROUP_DIR],
            "committed execution group descriptions",
        )
    labels |= _git_path_set(
        root,
        ["ls-files", "-z", "--", EXECUTION_GROUP_DIR],
        "tracked execution group descriptions",
    )
    return labels


def group_description_labels(root: Path) -> list[str]:
    """Union committed, staged and worktree descriptions so deletions fail closed."""

    labels = tracked_description_labels(root)
    directory = root / EXECUTION_GROUP_DIR
    if directory.is_dir():
        # Only description-shaped worktree files join the union. A stray editor
        # swapfile must not break the serial lifecycle of ungrouped plans;
        # directory hygiene stays with the root and generated static lint.
        for path in sorted(directory.glob("*.json")):
            if path.is_file():
                labels.add(path.relative_to(root).as_posix())
    return sorted(labels)


def require_committed_description(root: Path, label: str, raw: bytes) -> None:
    """Refuse a description that is untracked or differs from committed bytes."""

    if label not in tracked_description_labels(root):
        raise GroupError(f"{label} is not a committed group description")
    try:
        committed = git_output(root, "show", f"HEAD:{label}")
    except GroupError as exc:
        raise GroupError(f"{label} is not a committed group description") from exc
    if committed != raw:
        raise GroupError(
            f"{label} differs from its committed bytes; commit the group description first"
        )


def load_group_descriptions(root: Path) -> dict[str, dict[str, Any]]:
    """Load and validate every committed group description in the repository."""

    groups: dict[str, dict[str, Any]] = {}
    enrolled: dict[str, str] = {}
    seen_ids: set[str] = set()
    for label in group_description_labels(root):
        if not GROUP_PATH_RE.fullmatch(label):
            raise GroupError(f"invalid execution group description path: {label}")
        path = root / label
        if not path.is_file():
            raise GroupError(
                f"{label} is tracked but missing from the working tree; restore or "
                "commit its removal before running grouped or serial execution"
            )
        raw = read_bounded_bytes(path, label)
        require_committed_description(root, label, raw)
        try:
            data = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GroupError(f"{label} is invalid JSON") from exc
        description = validate_group_description(
            data, description_bytes=raw, label=label
        )
        if description["group_id"] in seen_ids:
            raise GroupError(f"{label} reuses an existing group_id")
        seen_ids.add(description["group_id"])
        resolved = resolve_group_members(root, description, label)
        for plan_path in resolved:
            if plan_path in enrolled:
                raise GroupError(
                    f"{plan_path} is enrolled in more than one execution group"
                )
            enrolled[plan_path] = label
        groups[label] = {
            "description_path": label,
            "description_digest": digest(raw),
            "description": description,
            "members": resolved,
        }
    return groups


def enrolled_member(root: Path, plan_path: str) -> dict[str, Any] | None:
    """Return the group enrolment for one plan path, or None when ungrouped."""

    normalized = plan_path.strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    for label, group in load_group_descriptions(root).items():
        if normalized in group["members"]:
            return {
                "group_label": label,
                "group_id": group["description"]["group_id"],
                "description_digest": group["description_digest"],
                "plan_path": normalized,
            }
    return None


def require_group_permit(
    root: Path,
    plan_path: str,
    operation: str,
    *,
    permit: str | None = None,
    state: str | None = None,
) -> None:
    """Fail closed for an enrolled member without grouped runner support.

    An ungrouped plan is unaffected. An enrolled member is refused before any
    worker prerequisite, validation, apply, or lifecycle write. Supplying a
    permit does not weaken the refusal while the grouped adapter is absent.
    """

    if operation not in GATED_OPERATIONS:
        raise GroupError(f"unknown gated operation: {operation}")
    enrolment = enrolled_member(root, plan_path)
    if enrolment is None:
        return
    if permit is None:
        raise GroupError(
            f"{plan_path} is enrolled in execution group "
            f"{enrolment['group_id']}; the legacy serial {operation} path is "
            "refused without a verified group member permit"
        )
    verified = verify_permit_document(root, permit)
    if verified["plan_path"] != plan_path:
        raise GroupError("group member permit names a different plan")
    if verified["group_id"] != enrolment["group_id"]:
        raise GroupError("group member permit names a different execution group")
    if state is not None:
        require_permit_is_current(root, Path(state), verified)
    if GROUPED_ADAPTER_VERSION is None:
        raise GroupError(
            f"{plan_path} requires the grouped execution adapter, which is not "
            f"installed; the {operation} path stays closed"
        )


def require_permit_is_current(root: Path, state_path: Path, permit: dict[str, Any]) -> None:
    """Bind a permit to the live runtime record, not only to committed bytes.

    A released, superseded, stopped, foreign-repository, or stale-state permit
    is refused here so no caller can act on obsolete member authority.
    """

    with with_lock(state_path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
        state = read_state(state_path)
        require_live_group(root, state)
        if state["repository_identity"] != permit["repository_identity"]:
            raise GroupError("group member permit belongs to a different repository")
        if state["group_id"] != permit["group_id"]:
            raise GroupError("group member permit names a different execution group")
        if state["group_description_digest"] != permit["group_description_digest"]:
            raise GroupError("group member permit is bound to a superseded group description")
        member = require_member(state, permit["plan_path"])
        require_active_member(member)
        if not member["permit"]["open"] or member["permit"]["permit_id"] != permit["permit_id"]:
            raise GroupError(
                "group member permit is not the current open permit for this member"
            )
        if member["baseline_generation"] != permit["baseline_generation"]:
            raise GroupError("group member permit is bound to a superseded baseline")
        if member["base_commit"] != permit["base_commit"]:
            raise GroupError("group member permit is bound to a different base commit")


def verify_permit_document(root: Path, permit_path: str) -> dict[str, Any]:
    path = Path(permit_path)
    require_outside_repository(path, "group member permit", root)
    document = read_bounded_json(path, "group member permit")
    permit = exact_object(
        document,
        {
            "schema_version",
            "group_id",
            "group_description_digest",
            "plan_path",
            "permit_id",
            "baseline_generation",
            "base_commit",
            "repository_identity",
            "state_digest",
        },
        "group member permit",
    )
    if permit["schema_version"] != GROUP_PERMIT_SCHEMA_VERSION:
        raise GroupError("group member permit must declare schema_version 1")
    require_identifier(permit["permit_id"], "group member permit permit_id")
    require_digest(
        permit["group_description_digest"], "group member permit description digest"
    )
    require_commit(permit["base_commit"], "group member permit base_commit")
    if not isinstance(permit["baseline_generation"], int) or isinstance(
        permit["baseline_generation"], bool
    ):
        raise GroupError("group member permit baseline_generation must be an integer")
    groups = load_group_descriptions(root)
    matching = [
        group
        for group in groups.values()
        if group["description"]["group_id"] == permit["group_id"]
    ]
    if len(matching) != 1:
        raise GroupError("group member permit does not resolve to one committed group")
    if matching[0]["description_digest"] != permit["group_description_digest"]:
        raise GroupError("group member permit is bound to different committed bytes")
    if permit["plan_path"] not in matching[0]["members"]:
        raise GroupError("group member permit names a plan outside its group")
    return permit


def canonical_repository_origin(origin: str) -> str:
    candidate = origin.strip()
    if not candidate:
        raise GroupError("repository origin must not be empty")
    if "://" not in candidate:
        if candidate.startswith("/") or candidate.startswith("."):
            raise GroupError("group authority requires a canonical network origin")
        if ":" not in candidate:
            raise GroupError("group authority requires a canonical network origin")
        head, path = candidate.split(":", 1)
        host = head.rsplit("@", 1)[-1].lower()
    else:
        scheme, rest = candidate.split("://", 1)
        if scheme.lower() not in {"https", "ssh", "git"}:
            raise GroupError("group authority requires a canonical network origin")
        authority, _, path = rest.partition("/")
        host = authority.rsplit("@", 1)[-1].lower()
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not host or not path or any(
        part in {"", ".", ".."} for part in PurePosixPath(path).parts
    ):
        raise GroupError("repository origin has an invalid repository path")
    return f"{host}/{path}"


def repository_identity(root: Path) -> str:
    try:
        origin = git_output(root, "config", "--get", "remote.origin.url").decode("utf-8")
    except GroupError as exc:
        raise GroupError(
            "group authority requires a canonical remote.origin.url"
        ) from exc
    canonical = canonical_repository_origin(origin)
    common = git_output(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    common_path = Path(common.decode("utf-8").strip()).resolve()
    return canonical_digest(
        {"origin": canonical, "git_common_dir": str(common_path)}
    )


def current_head(root: Path) -> str:
    return git_output(root, "rev-parse", "HEAD").decode("utf-8").strip()


def require_clean_repository(root: Path) -> None:
    if git_output(root, "status", "--porcelain=1", "--untracked-files=all"):
        raise GroupError("group admission requires a clean repository")


def require_committed_bytes(root: Path, commit: str, relative: str, expected: str) -> None:
    blob = git_output(root, "show", f"{commit}:{relative}")
    if digest(blob) != expected:
        raise GroupError(
            f"{relative} does not match its committed bytes at the start commit"
        )


def empty_member_state(
    plan_path: str, plan_digest: str, base_commit: str
) -> dict[str, Any]:
    return {
        "plan_path": plan_path,
        "plan_digest": plan_digest,
        "logical_member_id": PLAN_PATH_RE.fullmatch(plan_path).group(1),
        "baseline_generation": 0,
        "base_commit": base_commit,
        "state": "active",
        "stop_reason": "",
        "counters": {
            "initial_generations": 0,
            "corrections": 0,
            "reviews": 0,
            "parent_adjustments": 0,
        },
        "permit": {
            "permit_id": "",
            "workspace_digest": "",
            "open": False,
        },
        "consumed_permit_ids": [],
        "reviewer_registry_proof": {
            "registry_path_digest": "",
            "event_count": 0,
            "event_chain_digest": "",
        },
        "parent_adjustment": {
            "state": "none",
            "permit_id": "",
            "incoming_candidate_digest": "",
            "base_digest": "",
            "patch_digest": "",
        },
        "publication": {"published": False, "commit": ""},
    }


def append_event(state: dict[str, Any], event_type: str, detail: dict[str, Any]) -> None:
    # Terminal transitions keep reserved headroom: recording a stop must never
    # become impossible because ordinary operations filled the bounded chain.
    limit = (
        MAX_GROUP_EVENTS
        if event_type in TERMINAL_EVENT_TYPES
        else MAX_GROUP_EVENTS - TERMINAL_EVENT_RESERVE
    )
    if len(state["events"]) >= limit:
        raise GroupError("group authority event budget is exhausted")
    previous = state["events"][-1]["event_chain_digest"] if state["events"] else digest(b"")
    event = {
        "sequence": len(state["events"]) + 1,
        "event_type": event_type,
        "detail": detail,
        "event_chain_digest": "",
    }
    event["event_chain_digest"] = canonical_digest(
        {"previous": previous, "event": {k: v for k, v in event.items() if k != "event_chain_digest"}}
    )
    state["events"].append(event)


def read_state(path: Path) -> dict[str, Any]:
    require_outside_repository(path, "group execution state")
    reject_symlink_ancestors(path, include_target=True)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise GroupError("group execution state must be a regular file")
        if metadata.st_mode & 0o777 != 0o600:
            raise GroupError("group execution state must be mode 0600")
        if metadata.st_nlink != 1:
            raise GroupError("group execution state must not be hard linked")
        data = os.read(descriptor, GROUP_STATE_MAX_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(data) > GROUP_STATE_MAX_BYTES:
        raise GroupError("group execution state exceeds size limit")
    try:
        state = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GroupError("group execution state is invalid JSON") from exc
    if not isinstance(state, dict) or state.get("schema_version") != GROUP_STATE_SCHEMA_VERSION:
        raise GroupError("group execution state must declare schema_version 1")
    require_event_chain(state)
    return state


def require_event_chain(state: dict[str, Any]) -> None:
    """Recompute the bounded hash chain so tampered history fails closed."""

    events = state.get("events")
    if not isinstance(events, list) or len(events) > MAX_GROUP_EVENTS:
        raise GroupError("group execution state event chain is malformed")
    previous = digest(b"")
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict) or set(event) != {
            "sequence",
            "event_type",
            "detail",
            "event_chain_digest",
        }:
            raise GroupError("group execution state event chain is malformed")
        if event["sequence"] != index:
            raise GroupError("group execution state event chain is malformed")
        expected = canonical_digest(
            {
                "previous": previous,
                "event": {
                    key: value
                    for key, value in event.items()
                    if key != "event_chain_digest"
                },
            }
        )
        if expected != event["event_chain_digest"]:
            raise GroupError("group execution state event chain verification failed")
        previous = expected


def require_live_group(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    """Recheck that the committed group still matches the admitted record."""

    groups = load_group_descriptions(root)
    label = state["group_description_path"]
    group = groups.get(label)
    if group is None:
        raise GroupError("the admitted group description no longer exists")
    if group["description_digest"] != state["group_description_digest"]:
        raise GroupError("the committed group description changed after admission")
    if group["description"]["group_id"] != state["group_id"]:
        raise GroupError("the committed group identity changed after admission")
    if repository_identity(root) != state["repository_identity"]:
        raise GroupError("group execution state belongs to a different repository")
    for plan_path, member in state["members"].items():
        if plan_path not in group["members"]:
            raise GroupError("group membership changed after admission")
        live = group["members"][plan_path]["member"]
        if live["plan_digest"] != member["plan_digest"]:
            raise GroupError(
                f"member plan bytes changed after admission: {plan_path}"
            )
    return group


def require_member(state: dict[str, Any], plan_path: str) -> dict[str, Any]:
    member = state["members"].get(plan_path)
    if member is None:
        raise GroupError(f"{plan_path} is not a member of this execution group")
    return member


def require_active_member(member: dict[str, Any]) -> None:
    if member["state"] != "active":
        raise GroupError(
            f"member {member['plan_path']} is stopped for {member['stop_reason']}; "
            "the stop is terminal for this member execution"
        )


def group_init(args: argparse.Namespace) -> None:
    path = Path(args.state)
    require_outside_repository(path, "group execution state")
    if path.exists() or path.is_symlink():
        raise GroupError("group execution state already exists")
    root = repository_root()
    require_clean_repository(root)
    head = current_head(root)
    require_commit(args.start_commit, "start_commit")
    if head != args.start_commit:
        raise GroupError("declared start commit is not the current HEAD")
    groups = load_group_descriptions(root)
    label = args.group_description
    group = groups.get(label)
    if group is None:
        raise GroupError(f"no validated execution group description at {label}")
    if group["description"]["target_ref"] != args.target_ref:
        raise GroupError("declared target ref does not match the committed group")
    require_committed_bytes(root, head, label, group["description_digest"])
    for plan_path, resolved in group["members"].items():
        require_committed_bytes(
            root, head, plan_path, resolved["member"]["plan_digest"]
        )
    state = {
        "schema_version": GROUP_STATE_SCHEMA_VERSION,
        "group_id": group["description"]["group_id"],
        "group_description_path": label,
        "group_description_digest": group["description_digest"],
        "repository_identity": repository_identity(root),
        "target_ref": args.target_ref,
        "common_start_commit": head,
        "upstream_claim": {"leaf_digest": "", "claimed": False},
        "publication_lease": {"owner": "", "plan_path": ""},
        "final_successor_claim": {"claim_id": "", "claimed": False},
        "members": {
            plan_path: empty_member_state(
                plan_path, resolved["member"]["plan_digest"], head
            )
            for plan_path, resolved in group["members"].items()
        },
        "events": [],
    }
    append_event(
        state,
        "group_admitted",
        {
            "group_description_digest": group["description_digest"],
            "common_start_commit": head,
        },
    )
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if path.exists() or path.is_symlink():
            raise GroupError("group execution state already exists")
        atomic_write(path, state)
    print(state["group_id"])


def claim_upstream(args: argparse.Namespace) -> None:
    path = Path(args.state)
    leaf = require_digest(args.leaf_digest, "leaf_digest")
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        require_live_group(repository_root(), state)
        if state["upstream_claim"]["claimed"]:
            raise GroupError(
                "the group already consumed its upstream accepted chain leaf"
            )
        state["upstream_claim"] = {"leaf_digest": leaf, "claimed": True}
        append_event(state, "upstream_claimed", {"leaf_digest": leaf})
        atomic_write(path, state)
    print(leaf)


def permit_issue(args: argparse.Namespace) -> None:
    path = Path(args.state)
    permit_id = require_identifier(args.permit_id, "permit_id")
    workspace = require_digest(args.workspace_digest, "workspace_digest")
    output = Path(args.output)
    require_outside_repository(output, "group member permit")
    if output.exists() or output.is_symlink():
        raise GroupError("group member permit already exists")
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        root = repository_root()
        require_live_group(root, state)
        member = require_member(state, args.member)
        require_active_member(member)
        if member["permit"]["open"]:
            raise GroupError(
                f"member {args.member} already holds an exclusive candidate permit"
            )
        if permit_id in member["consumed_permit_ids"]:
            raise GroupError("group member permit identifier replay is not allowed")
        for other_path, other in state["members"].items():
            if other_path != args.member and other["permit"]["permit_id"] == permit_id:
                raise GroupError("group member permit identifier replay is not allowed")
        if member["counters"]["initial_generations"] >= MEMBER_INITIAL_GENERATION_LIMIT:
            raise GroupError(
                f"member {args.member} already spent its single initial generation"
            )
        member["counters"]["initial_generations"] += 1
        member["permit"] = {
            "permit_id": permit_id,
            "workspace_digest": workspace,
            "open": True,
        }
        member["consumed_permit_ids"].append(permit_id)
        append_event(
            state,
            "member_permit_issued",
            {"plan_path": args.member, "permit_id": permit_id},
        )
        atomic_write(path, state)
        permit = {
            "schema_version": GROUP_PERMIT_SCHEMA_VERSION,
            "group_id": state["group_id"],
            "group_description_digest": state["group_description_digest"],
            "plan_path": args.member,
            "permit_id": permit_id,
            "baseline_generation": member["baseline_generation"],
            "base_commit": member["base_commit"],
            "repository_identity": state["repository_identity"],
            "state_digest": canonical_digest(state),
        }
        atomic_write(output, permit)
    print(permit_id)


def permit_release(args: argparse.Namespace) -> None:
    path = Path(args.state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        require_live_group(repository_root(), state)
        member = require_member(state, args.member)
        if not member["permit"]["open"] or member["permit"]["permit_id"] != args.permit_id:
            raise GroupError("the named permit is not the open member permit")
        member["permit"]["open"] = False
        append_event(
            state,
            "member_permit_released",
            {"plan_path": args.member, "permit_id": args.permit_id},
        )
        atomic_write(path, state)
    print(args.permit_id)


def lease_acquire(args: argparse.Namespace) -> None:
    path = Path(args.state)
    owner = require_identifier(args.owner, "owner")
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        root = repository_root()
        require_live_group(root, state)
        member = require_member(state, args.member)
        require_active_member(member)
        current = state["publication_lease"]
        if current["owner"] and current["owner"] != owner:
            raise GroupError(
                "another parent workspace already holds the publication lease"
            )
        if current["owner"] == owner:
            raise GroupError("this parent workspace already holds the publication lease")
        state["publication_lease"] = {"owner": owner, "plan_path": args.member}
        append_event(
            state,
            "publication_lease_acquired",
            {"owner": owner, "plan_path": args.member},
        )
        atomic_write(path, state)
    print(owner)


def lease_release(args: argparse.Namespace) -> None:
    path = Path(args.state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        if state["publication_lease"]["owner"] != args.owner:
            raise GroupError("only the recorded lease owner may release the lease")
        state["publication_lease"] = {"owner": "", "plan_path": ""}
        append_event(state, "publication_lease_released", {"owner": args.owner})
        atomic_write(path, state)
    print(args.owner)


def record_review(args: argparse.Namespace) -> None:
    path = Path(args.state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        require_live_group(repository_root(), state)
        member = require_member(state, args.member)
        require_active_member(member)
        if member["counters"]["reviews"] >= MEMBER_REVIEW_LIMIT:
            raise GroupError(
                f"member {args.member} exhausted its independent review budget"
            )
        registry_path_digest = require_digest(
            args.registry_path_digest, "registry_path_digest"
        )
        registry_chain_digest = require_digest(
            args.registry_event_chain_digest, "registry_event_chain_digest"
        )
        if not isinstance(args.registry_event_count, int) or args.registry_event_count < 1:
            raise GroupError("registry_event_count must be a positive integer")
        prior = member["reviewer_registry_proof"]
        if prior["registry_path_digest"]:
            # Both reviews of one member must come from the same canonical
            # reviewer registry, advancing along its own append-only chain.
            if prior["registry_path_digest"] != registry_path_digest:
                raise GroupError(
                    f"member {args.member} reviews must use one canonical reviewer registry"
                )
            if args.registry_event_count <= prior["event_count"]:
                raise GroupError(
                    "reviewer registry event count must advance for each recorded review"
                )
            if registry_chain_digest == prior["event_chain_digest"]:
                raise GroupError(
                    "reviewer registry event chain must advance for each recorded review"
                )
        member["counters"]["reviews"] += 1
        member["reviewer_registry_proof"] = {
            "registry_path_digest": registry_path_digest,
            "event_count": args.registry_event_count,
            "event_chain_digest": registry_chain_digest,
        }
        append_event(
            state,
            "member_review_recorded",
            {"plan_path": args.member, "reviews": member["counters"]["reviews"]},
        )
        atomic_write(path, state)
    print(member["counters"]["reviews"])


def adjust_reserve(args: argparse.Namespace) -> None:
    path = Path(args.state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        require_live_group(repository_root(), state)
        member = require_member(state, args.member)
        require_active_member(member)
        if member["permit"]["permit_id"] != args.permit_id or not member["permit"]["open"]:
            raise GroupError(
                "parent adjustment requires the exact open member permit"
            )
        adjustment = member["parent_adjustment"]
        if adjustment["state"] == "reserved":
            raise GroupError(
                "a parent adjustment is already reserved and unresolved for this member"
            )
        if member["counters"]["corrections"] >= MEMBER_CORRECTION_LIMIT:
            raise GroupError(
                f"member {args.member} already spent its single correction slot"
            )
        member["counters"]["corrections"] += 1
        member["parent_adjustment"] = {
            "state": "reserved",
            "permit_id": args.permit_id,
            "incoming_candidate_digest": require_digest(
                args.incoming_candidate_digest, "incoming_candidate_digest"
            ),
            "base_digest": require_digest(args.base_digest, "base_digest"),
            "patch_digest": "",
        }
        append_event(
            state,
            "parent_adjustment_reserved",
            {"plan_path": args.member, "permit_id": args.permit_id},
        )
        atomic_write(path, state)
    print("reserved")


def adjust_close(args: argparse.Namespace) -> None:
    path = Path(args.state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        require_live_group(repository_root(), state)
        member = require_member(state, args.member)
        require_active_member(member)
        adjustment = member["parent_adjustment"]
        if adjustment["state"] != "reserved":
            raise GroupError("no parent adjustment is reserved for this member")
        if adjustment["permit_id"] != args.permit_id:
            raise GroupError(
                "parent adjustment close must name the reserving member permit"
            )
        if adjustment["incoming_candidate_digest"] != args.incoming_candidate_digest:
            raise GroupError(
                "parent adjustment close must bind the reserved candidate identity"
            )
        adjustment["state"] = "closed"
        adjustment["patch_digest"] = require_digest(
            args.patch_digest, "patch_digest"
        )
        append_event(
            state,
            "parent_adjustment_closed",
            {"plan_path": args.member, "patch_digest": adjustment["patch_digest"]},
        )
        atomic_write(path, state)
    print("closed")


def member_stop(args: argparse.Namespace) -> None:
    """Record a terminal member stop; this must work even after authority drift."""

    path = Path(args.state)
    if args.reason not in MEMBER_STOP_REASONS:
        raise GroupError(f"unknown member stop reason: {args.reason}")
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        member = require_member(state, args.member)
        if member["state"] != "active":
            raise GroupError(
                f"member {args.member} is already stopped for {member['stop_reason']}"
            )
        member["state"] = "stopped"
        member["stop_reason"] = args.reason
        member["permit"]["open"] = False
        append_event(
            state, "member_stopped", {"plan_path": args.member, "reason": args.reason}
        )
        atomic_write(path, state)
    print(args.reason)


def require_descendant_baseline(
    root: Path, state: dict[str, Any], member: dict[str, Any], base_commit: str
) -> None:
    """Prove the new baseline exists and advances the member on the target ref."""

    for label, commit in (("new_base_commit", base_commit), ("prior baseline", member["base_commit"])):
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=sanitized_git_environment(),
        )
        if completed.returncode != 0:
            raise GroupError(f"{label} does not name a commit in this repository")
    ancestor = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", member["base_commit"], base_commit],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=sanitized_git_environment(),
    )
    if ancestor.returncode != 0:
        raise GroupError(
            "new_base_commit must be a descendant of the recorded member baseline"
        )
    reachable = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", base_commit, state["target_ref"]],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=sanitized_git_environment(),
    )
    if reachable.returncode != 0:
        raise GroupError(
            "new_base_commit must be reachable from the admitted group target ref"
        )


def transfer_baseline(args: argparse.Namespace) -> None:
    path = Path(args.state)
    permit_id = require_identifier(args.new_permit_id, "new_permit_id")
    base_commit = require_commit(args.new_base_commit, "new_base_commit")
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        root = repository_root()
        require_live_group(root, state)
        member = require_member(state, args.member)
        require_active_member(member)
        if (
            member["permit"]["permit_id"] != args.prior_permit_id
            or not member["permit"]["open"]
        ):
            raise GroupError(
                "a baseline transfer must consume the exact open prior member permit"
            )
        if base_commit == member["base_commit"]:
            raise GroupError(
                "a baseline transfer must advance the recorded member baseline"
            )
        require_descendant_baseline(root, state, member, base_commit)
        if member["parent_adjustment"]["state"] == "reserved":
            raise GroupError(
                "a reserved parent adjustment must resolve before a baseline transfer"
            )
        if permit_id in member["consumed_permit_ids"]:
            raise GroupError("group member permit identifier replay is not allowed")
        counters = dict(member["counters"])
        proof = dict(member["reviewer_registry_proof"])
        member["baseline_generation"] += 1
        member["base_commit"] = base_commit
        member["permit"] = {
            "permit_id": permit_id,
            "workspace_digest": require_digest(
                args.workspace_digest, "workspace_digest"
            ),
            "open": True,
        }
        member["consumed_permit_ids"].append(permit_id)
        member["counters"] = counters
        member["reviewer_registry_proof"] = proof
        append_event(
            state,
            "member_baseline_transferred",
            {
                "plan_path": args.member,
                "baseline_generation": member["baseline_generation"],
                "prior_permit_id": args.prior_permit_id,
                "new_permit_id": permit_id,
            },
        )
        atomic_write(path, state)
    print(member["baseline_generation"])


def check_enrollment(args: argparse.Namespace) -> None:
    root = repository_root(Path(args.repository) if args.repository else None)
    require_group_permit(
        root,
        args.plan,
        args.operation,
        permit=args.group_permit,
        state=args.group_state,
    )
    print("ungrouped" if enrolled_member(root, args.plan) is None else "permitted")


def show_state(args: argparse.Namespace) -> None:
    state = read_state(Path(args.state))
    print(json.dumps(state, sort_keys=True, indent=2))


def validate_descriptions(args: argparse.Namespace) -> None:
    root = repository_root(Path(args.repository) if args.repository else None)
    groups = load_group_descriptions(root)
    for label in sorted(groups):
        print(label)
    if not groups:
        print("no execution group descriptions")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-descriptions")
    validate.add_argument("--repository")
    validate.set_defaults(handler=validate_descriptions)

    init = sub.add_parser("group-init")
    init.add_argument("state")
    init.add_argument("--group-description", required=True)
    init.add_argument("--target-ref", required=True)
    init.add_argument("--start-commit", required=True)
    init.set_defaults(handler=group_init)

    upstream = sub.add_parser("claim-upstream")
    upstream.add_argument("state")
    upstream.add_argument("--leaf-digest", required=True)
    upstream.set_defaults(handler=claim_upstream)

    issue = sub.add_parser("permit-issue")
    issue.add_argument("state")
    issue.add_argument("--member", required=True)
    issue.add_argument("--permit-id", required=True)
    issue.add_argument("--workspace-digest", required=True)
    issue.add_argument("--output", required=True)
    issue.set_defaults(handler=permit_issue)

    release = sub.add_parser("permit-release")
    release.add_argument("state")
    release.add_argument("--member", required=True)
    release.add_argument("--permit-id", required=True)
    release.set_defaults(handler=permit_release)

    acquire = sub.add_parser("lease-acquire")
    acquire.add_argument("state")
    acquire.add_argument("--member", required=True)
    acquire.add_argument("--owner", required=True)
    acquire.set_defaults(handler=lease_acquire)

    lease_free = sub.add_parser("lease-release")
    lease_free.add_argument("state")
    lease_free.add_argument("--owner", required=True)
    lease_free.set_defaults(handler=lease_release)

    review = sub.add_parser("record-review")
    review.add_argument("state")
    review.add_argument("--member", required=True)
    review.add_argument("--registry-path-digest", required=True)
    review.add_argument("--registry-event-count", type=int, required=True)
    review.add_argument("--registry-event-chain-digest", required=True)
    review.set_defaults(handler=record_review)

    reserve = sub.add_parser("adjust-reserve")
    reserve.add_argument("state")
    reserve.add_argument("--member", required=True)
    reserve.add_argument("--permit-id", required=True)
    reserve.add_argument("--incoming-candidate-digest", required=True)
    reserve.add_argument("--base-digest", required=True)
    reserve.set_defaults(handler=adjust_reserve)

    close = sub.add_parser("adjust-close")
    close.add_argument("state")
    close.add_argument("--member", required=True)
    close.add_argument("--permit-id", required=True)
    close.add_argument("--incoming-candidate-digest", required=True)
    close.add_argument("--patch-digest", required=True)
    close.set_defaults(handler=adjust_close)

    stop = sub.add_parser("member-stop")
    stop.add_argument("state")
    stop.add_argument("--member", required=True)
    stop.add_argument("--reason", required=True)
    stop.set_defaults(handler=member_stop)

    transfer = sub.add_parser("transfer-baseline")
    transfer.add_argument("state")
    transfer.add_argument("--member", required=True)
    transfer.add_argument("--prior-permit-id", required=True)
    transfer.add_argument("--new-permit-id", required=True)
    transfer.add_argument("--new-base-commit", required=True)
    transfer.add_argument("--workspace-digest", required=True)
    transfer.set_defaults(handler=transfer_baseline)

    gate = sub.add_parser("check-enrollment")
    gate.add_argument("--repository")
    gate.add_argument("--plan", required=True)
    gate.add_argument("--operation", choices=GATED_OPERATIONS, required=True)
    gate.add_argument("--group-permit")
    gate.add_argument("--group-state")
    gate.set_defaults(handler=check_enrollment)

    show = sub.add_parser("show")
    show.add_argument("state")
    show.set_defaults(handler=show_state)

    return root


def main() -> int:
    args = parser().parse_args()
    try:
        args.handler(args)
    except (OSError, UnicodeError, GroupError) as exc:
        print(f"parallel plan state failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
