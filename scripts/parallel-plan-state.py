#!/usr/bin/env python3
"""Parent-owned authority for independent parallel plan execution.

The committed group description under ``docs/plan/execution-groups/`` declares an
exact finite member set. This module owns the mutable runtime authority for that
set: exclusive member permits, one upstream claim, one publication lease, the
single parent-adjustment slot, source-baseline transfers, and every member's
cumulative budgets and stop state. The runtime record lives outside the
repository; the committed description carries no runtime authority by itself.

session_binding means the private plan-bound session, process-incarnation, exact task-worktree and ownership-generation record; it grants no implementation or publication authority.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
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
# without a otherwise valid permit. Installation is proved by the adapter file
# that ships beside this authority, so an installation without the adapter keeps
# failing closed instead of silently opening the legacy serial paths.
GROUPED_ADAPTER_NAME = "run-parallel-plans.py"
GROUPED_ADAPTER_EXPECTED_VERSION = 1

EXECUTION_GROUP_DIR = "docs/plan/execution-groups"
GROUP_MEMBER_COUNT = 2
MEMBER_INITIAL_GENERATION_LIMIT = 1
MEMBER_CORRECTION_LIMIT = 1
MEMBER_REVIEW_LIMIT = 2
MEMBER_PARENT_ADJUSTMENT_LIMIT = 1
# One member may move to a newer target baseline once in this release. Another
# target movement preserves the assembled result and stops for the owner
# instead of looping through repeated assemble/review rounds.
MEMBER_BASELINE_TRANSFER_LIMIT = 1
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
SESSION_GROUP_SCHEMA_VERSION = 2
SESSION_MEMBER_KEYS = GROUP_MEMBER_KEYS | {"implementation_mode"}
SESSION_ENVIRONMENT_VARIABLE = "PROJECT_AGENT_WORKFLOW_SESSION_ID"

# Product tooling and specifications may be editable, but the controls that
# admit, review, validate and publish this group must remain serial-only.
SESSION_SERIAL_PATHS = (
    ".git", ".githooks", ".codex", ".github", "docs/plan",
    "AGENTS.md", "scripts/AGENTS.md", "tests/AGENTS.md",
    "hooks", "scripts/project_workflow/__init__.py",
    "scripts/project_workflow/worktree_guard.py",
    "scripts/project_workflow/plan_authoring.py",
)
SESSION_SERIAL_COMMANDS = (
    "parallel-plan-state.py", "plan-execution-state.py", "run-parallel-plans.py",
    "run-sandboxed-plan-worker.py", "manage-plan-worktrees.py", "worktree_guard.py",
    "plan_validation_commands.py", "complete-plan.sh", "finalize-active-plan.sh",
    "check-agent-completion.sh", "check-root-agent-policy.py", "planlib.py",
    "lint-plan-docs.py", "lint-project-workflow.sh", "check-copier-template.py",
    "restructure-plan.py", "create-root-plan.py", "create-plan.sh", "promote-plan.sh",
    "shelve-plan.sh", "plan_authoring.py",
    "security_rules.py", "tool_command_context.py", "validate-changes.py",
    "check-agent-log-manifest.py", "agent_log_manifest.py", "lint-python.py",
)
SESSION_SERIAL_SPECS = (
    "SPEC_PLAN_WORKFLOW.md", "SPEC_SECURITY.md", "SPEC_GIT_RETIREMENT.md",
    "SPEC_ORCHESTRATION.md", "SPEC_AGENT_LOGGING.md", "spec-index.yaml",
)
SESSION_BINDING_KEYS = {
    "state", "session_digest", "generation", "process_identity",
    "worktree_path", "branch_ref", "worktree_identity",
}

# handoff means the frozen parent-direct result one member submits to
# integration. It closes that member's writing claim and carries only bounded
# identity and digests; the full Git diff stays in the adapter artifact the
# record_digest binds. Submitting a handoff is not acceptance, not review, not
# validation and never authorizes publication.
PARENT_DIRECT_HANDOFF_SCHEMA_VERSION = 1
PARENT_DIRECT_HANDOFF_MODE = "parent_direct"
SESSION_HANDOFF_KEYS = {
    "schema_version", "handoff_mode", "plan_digest", "base_commit",
    "session_digest", "generation", "patch_digest", "changed_paths_digest",
    "record_digest",
}
# A member takes at most one formal review before it hands off. The remaining
# slot of MEMBER_REVIEW_LIMIT stays reserved for the integration review of the
# assembled result at the final base, so an early member review can never
# consume it and a restarted session cannot replenish it.
SESSION_MEMBER_REVIEW_LIMIT = 1

# ledger_binding means the single external execution ledger one member may ever
# own. It is claimed once under the group lock, so a retained partial setup, a
# new run name, a new session or a fresh checkout cannot obtain a second ledger
# and thereby replenish a spent member budget.
SESSION_LEDGER_KEYS = {
    "run_id", "state_path_digest", "lifecycle_path_digest", "session_digest",
    "generation",
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
    "scripts/run-parallel-plans.py",
    "tests/smoke.sh",
    ".project-agent-workflow/docs/agent/",
    ".project-agent-workflow/scripts/lint-project-workflow.sh",
    ".project-agent-workflow/scripts/plan_validation_commands.py",
    ".project-agent-workflow/scripts/plan-execution-state.py",
    ".project-agent-workflow/scripts/parallel-plan-state.py",
    ".project-agent-workflow/scripts/run-sandboxed-plan-worker.py",
    ".project-agent-workflow/scripts/run-parallel-plans.py",
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

# Lifecycle operations follow a verified publication instead of an open
# candidate permit: the member permit is consumed by then, and only the exact
# published commit may become a formally accepted and archived member result.
LIFECYCLE_OPERATIONS = frozenset({"completion", "finalization", "archive"})

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
    "required_specs",
    "validation_authority_scope",
    "focused_validation",
    "validation",
    "acceptance",
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


def read_private_bounded_bytes(path: Path, label: str, maximum: int = MAX_BYTES) -> bytes:
    """Read a bounded artifact that must still be private to its owner."""

    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode):
        raise GroupError(f"{label} must not be a symbolic link")
    if metadata.st_mode & 0o777 != 0o600:
        raise GroupError(f"{label} must be mode 0600")
    return read_bounded_bytes(path, label, maximum)


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


def session_scope_reaches_authority(entry: str) -> bool:
    entry = normalized_scope_path(entry)
    for prefix in ("template/", ".project-agent-workflow/"):
        if entry.startswith(prefix):
            entry = entry[len(prefix):]
    if entry.endswith(".jinja"):
        entry = entry[:-6]
    controls = (
        *SESSION_SERIAL_PATHS,
        *(f"scripts/{name}" for name in SESSION_SERIAL_COMMANDS),
        *(f"docs/agent/{name}" for name in SESSION_SERIAL_SPECS),
        "references/orchestration.md", "tests/smoke.sh",
    )
    return any(scopes_overlap(entry, path) for path in controls)


def member_read_inputs(manifest: dict[str, Any]) -> set[str]:
    inputs = {
        normalized_scope_path(path)
        for key in ("context_files", "required_specs", "validation_authority_scope")
        for path in manifest[key]
        if path != "none"
    }
    for command in (*manifest["focused_validation"], *manifest["validation"]):
        parser = validation_command_parser()
        try:
            arguments = parser.parse_validation_command(command).argv
        except parser.ValidationCommandError as exc:
            raise GroupError(f"member validation command is invalid: {exc}") from exc
        if parser.is_pytest_check(arguments):
            prefix = next(p for p in parser.PYTEST_PREFIXES if arguments[:len(p)] == p)
            operands = arguments[len(prefix):] or ("tests",)
            inputs.update(normalized_scope_path(p.split("::", 1)[0]) for p in operands)
            inputs.update({"pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini", "conftest.py"})
        else:
            # The authoritative grammar admits only literal path operands.
            # Include every operand, not just the invoked validation script.
            inputs.update(
                normalized_scope_path(argument)
                for argument in arguments
                if "/" in argument or Path(argument).suffix in {".py", ".sh"}
            )
        if arguments[0] == "npm":
            inputs.update({"package.json", "package-lock.json", "npm-shrinkwrap.json", ".npmrc"})
        if arguments[:2] == ("uv", "run"):
            inputs.update({"pyproject.toml", "uv.lock"})
    return inputs


def validation_command_parser():
    path = Path(__file__).with_name("plan_validation_commands.py").resolve()
    name = f"parallel_validation_commands_{digest(str(path))[7:]}"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise GroupError("validation command authority is unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def validate_group_description(
    data: Any,
    *,
    description_bytes: bytes,
    label: str,
) -> dict[str, Any]:
    """Validate the committed shape of one execution group description."""

    description = exact_object(data, GROUP_DESCRIPTION_KEYS, label)
    version = description["schema_version"]
    if type(version) is not int or version not in {1, SESSION_GROUP_SCHEMA_VERSION}:
        raise GroupError(f"{label} must declare schema_version 1 or 2")
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
        member = exact_object(
            raw, SESSION_MEMBER_KEYS if version == 2 else GROUP_MEMBER_KEYS,
            f"{label} member {index}",
        )
        if version == 2 and member["implementation_mode"] != "parent_direct":
            raise GroupError(f"{label} schema-2 members require parent_direct mode")
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


def path_exists_at_head(root: Path, path: str) -> bool:
    """Report whether one repository path exists in the HEAD commit."""

    completed = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"HEAD:{path}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=sanitized_git_environment(),
    )
    return completed.returncode == 0


def resolve_group_members(
    root: Path,
    description: dict[str, Any],
    label: str,
    published: frozenset[str] = frozenset(),
) -> dict[str, dict[str, Any]]:
    """Bind each declared member to its live plan and check independence.

    ``published`` names members whose verified result the parent already
    published to the group target. A member plan whose removal from the declared
    path is already committed is resolved the same way, because a completed
    member is archived out of ``docs/plan/active/`` by design and must not break
    every remaining plan operation in the repository. A plan still tracked at
    HEAD but missing from the working tree stays an error. Independence, write-scope, and plan-byte
    binding constrain candidate generation and serial assembly, and a published
    member has already passed all of them and consumed its permit. Its own plan
    then moves through the ordinary completion and archive transitions, so this
    binding stops pinning its bytes or location instead of misreading an
    authorized lifecycle edit as authority drift.
    """

    resolved: dict[str, dict[str, Any]] = {}
    for member in description["members"]:
        plan_path = member["plan_path"]
        plan_file = root / plan_path
        if plan_path in published:
            resolved[plan_path] = {
                "member": member,
                "manifest": None,
                "write_scope": None,
                "published": True,
            }
            continue
        if not plan_file.is_file():
            if path_exists_at_head(root, plan_path):
                raise GroupError(
                    f"{label} member plan is tracked but missing from the working "
                    f"tree: {plan_path}"
                )
            resolved[plan_path] = {
                "member": member,
                "manifest": None,
                "write_scope": None,
                "published": True,
            }
            continue
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
            session_member = description["schema_version"] == 2
            if session_member:
                if entry not in manifest["write_scope"]:
                    raise GroupError("session member write scope must use exact canonical files")
                target = root / entry
                reject_symlink_ancestors(target, include_target=True)
                if target.is_dir():
                    raise GroupError("session member write scope requires exact file paths")
            if (
                session_scope_reaches_authority(entry) if session_member
                else scope_reaches_authority(entry)
            ):
                raise GroupError(
                    f"{label} member write scope reaches validation or specification "
                    f"authority: {plan_path} -> {entry}"
                )
        resolved[plan_path] = {
            "member": member,
            "manifest": manifest,
            "write_scope": write_scope,
            "published": False,
        }
    paths = sorted(resolved)
    live = [path for path in paths if resolved[path]["write_scope"] is not None]
    if len(live) == len(paths):
        first, second = paths[0], paths[1]
        for left in resolved[first]["write_scope"]:
            for right in resolved[second]["write_scope"]:
                if scopes_overlap(left, right):
                    raise GroupError(
                        f"{label} members declare overlapping write scope: "
                        f"{left} / {right}"
                    )
    for path in live:
        manifest = resolved[path]["manifest"]
        others = [other for other in paths if other != path]
        for other in others:
            if (
                description["schema_version"] == 2
                and resolved[other]["manifest"] is not None
            ):
                for write in resolved[path]["write_scope"]:
                    for read in member_read_inputs(resolved[other]["manifest"]):
                        if scopes_overlap(write, read):
                            raise GroupError(
                                f"{label} member writes a partner input: {write} / {read}"
                            )
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


def load_group_descriptions(
    root: Path,
    published: frozenset[str] = frozenset(),
) -> dict[str, dict[str, Any]]:
    """Load and validate every committed group description in the repository.

    ``published`` is forwarded to :func:`resolve_group_members` so an already
    published member keeps resolving through its own lifecycle transitions.
    """

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
        resolved = resolve_group_members(root, description, label, published)
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


def grouped_adapter_version() -> int | None:
    """Report the installed grouped execution adapter version, or None.

    The adapter must ship as one regular non-symlink sibling command. A missing
    or replaced adapter keeps every enrolled member refused on the legacy
    serial paths.
    """

    path = Path(__file__).resolve().with_name(GROUPED_ADAPTER_NAME)
    try:
        metadata = path.lstat()
    except OSError:
        return None
    if not stat.S_ISREG(metadata.st_mode):
        return None
    return GROUPED_ADAPTER_EXPECTED_VERSION


def published_member_paths(root: Path, state: str | None) -> frozenset[str]:
    """Report members a group execution state already records as published.

    This read is advisory and only relaxes plan-byte pinning: it never un-enrols
    a member, never opens a permit, and never stands in for the locked
    publication check that :func:`require_published_member` performs.
    """

    if state is None:
        return frozenset()
    path = Path(state)
    if not path.is_file() or path.is_symlink():
        return frozenset()
    try:
        document = read_state(path)
    except GroupError:
        return frozenset()
    if document["repository_identity"] != repository_identity(root):
        return frozenset()
    return frozenset(
        plan_path
        for plan_path, member in document["members"].items()
        if member["publication"]["published"]
    )


def enrolled_member(
    root: Path,
    plan_path: str,
    published: frozenset[str] = frozenset(),
) -> dict[str, Any] | None:
    """Return the group enrolment for one plan path, or None when ungrouped."""

    normalized = plan_path.strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    for label, group in load_group_descriptions(root, published).items():
        if normalized in group["members"]:
            return {
                "group_label": label,
                "group_id": group["description"]["group_id"],
                "description_digest": group["description_digest"],
                "plan_path": normalized,
                "schema_version": group["description"]["schema_version"],
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
    enrolment = enrolled_member(root, plan_path, published_member_paths(root, state))
    if enrolment is None:
        return
    if enrolment["schema_version"] == 2:
        require_session_member_operation(root, plan_path, operation, enrolment, state)
        return
    if grouped_adapter_version() is None:
        raise GroupError(
            f"{plan_path} requires the grouped execution adapter, which is not "
            f"installed; the {operation} path stays closed"
        )
    if operation in LIFECYCLE_OPERATIONS:
        require_published_member(root, plan_path, operation, enrolment, state)
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
    if state is None:
        raise GroupError(
            "group member permits are only honoured against the live group "
            "execution state record"
        )
    require_permit_is_current(root, Path(state), verified)


def require_session_member_operation(
    root: Path,
    plan_path: str,
    operation: str,
    enrolment: dict[str, Any],
    state: str | None,
) -> None:
    """Admit one parent-direct member operation inside its own live session.

    Registration alone still grants nothing. The member passes only with the
    session adapter installed, its canonical group state, an active member whose
    writing claim is still open, and the exact live session process that owns
    its worktree. Publication stays refused in every case: a member hands its
    frozen result to integration and never publishes or accepts it.
    """

    if operation in LIFECYCLE_OPERATIONS:
        raise GroupError(
            f"{plan_path} is a parent-direct session group member; the "
            f"{operation} path is refused because members never publish or accept "
            "their own result and integration owns the published outcome"
        )
    if grouped_adapter_version() is None:
        raise GroupError(
            f"{plan_path} requires the parent-direct session adapter, which is not "
            f"installed; the {operation} path stays closed"
        )
    if state is None:
        raise GroupError(
            f"{plan_path} is enrolled in parent-direct session group "
            f"{enrolment['group_id']}; the {operation} path requires the live "
            "session group state that records its member session binding"
        )
    path = Path(state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
        document = read_state(path)
        require_session_state(root, path, document)
        if document["group_id"] != enrolment["group_id"]:
            raise GroupError("session group state names a different execution group")
        member = require_member(document, plan_path)
        require_active_member(member)
        require_open_member_writing(member, plan_path)
        binding = member["session_binding"]
        if binding is None or binding["state"] != "bound":
            raise GroupError(
                f"{plan_path} has no live member session binding; the {operation} "
                "path stays closed outside its own bound member session"
            )
        if require_session_process(binding["process_identity"]["pid"]) != binding[
            "process_identity"
        ]:
            raise GroupError("member operation belongs to a stale session process")


def require_published_member(
    root: Path,
    plan_path: str,
    operation: str,
    enrolment: dict[str, Any],
    state: str | None,
) -> None:
    """Admit a lifecycle operation only for a verified published member.

    Publication is the parent-owned proof that this member's exact reviewed and
    validated result reached the group target. Without it the member has no
    formally accepted result to complete, finalize, or archive.
    """

    if state is None:
        raise GroupError(
            f"{plan_path} is enrolled in execution group "
            f"{enrolment['group_id']}; the {operation} path requires the group "
            "execution state that records its verified publication"
        )
    state_path = Path(state)
    with with_lock(state_path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
        document = read_state(state_path)
        require_live_group(root, document, allow_lifecycle_evolution=True)
        if document["group_id"] != enrolment["group_id"]:
            raise GroupError("group execution state names a different execution group")
        member = require_member(document, plan_path)
        publication = member["publication"]
        if not publication["published"]:
            raise GroupError(
                f"{plan_path} has not published a verified result; the "
                f"{operation} path stays closed until the parent publishes its "
                "reviewed commit to the group target"
            )
        require_commit(publication["commit"], "member publication commit")
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "merge-base",
                "--is-ancestor",
                publication["commit"],
                document["target_ref"],
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=sanitized_git_environment(),
        )
        if completed.returncode != 0:
            raise GroupError(
                "the recorded member publication is not reachable from the group "
                f"target ref; the {operation} path stays closed"
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


def read_state(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    require_outside_repository(path, "group execution state", root)
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
    if (
        not isinstance(state, dict)
        or type(state.get("schema_version")) is not int
        or state["schema_version"] not in {1, SESSION_GROUP_SCHEMA_VERSION}
    ):
        raise GroupError("group execution state must declare schema_version 1 or 2")
    require_event_chain(state)
    if state["schema_version"] == 2:
        validate_session_state(state)
    return state


def validate_member_handoff(
    state: dict[str, Any], plan: str, member: dict[str, Any]
) -> None:
    """Validate one member's frozen parent-direct handoff against its history.

    The handoff is bounded identity and digests only. The full Git diff lives in
    the adapter artifact that ``record_digest`` binds, so a replaced, foreign or
    stale artifact cannot pass as this member's submitted result.
    """

    handoff = member["handoff"]
    recorded = [
        event["detail"]["handoff"]
        for event in state["events"]
        if event["event_type"] == "member_handoff_submitted"
        and event["detail"].get("plan_path") == plan
    ]
    if handoff != (recorded[-1] if recorded else None):
        raise GroupError("member handoff differs from its recorded history")
    if handoff is None:
        return
    exact_object(handoff, SESSION_HANDOFF_KEYS, "member handoff")
    if handoff["schema_version"] != PARENT_DIRECT_HANDOFF_SCHEMA_VERSION:
        raise GroupError("member handoff must declare schema_version 1")
    if handoff["handoff_mode"] != PARENT_DIRECT_HANDOFF_MODE:
        raise GroupError("member handoff must declare the parent-direct mode")
    if handoff["plan_digest"] != member["plan_digest"]:
        raise GroupError("member handoff is bound to different plan bytes")
    if handoff["base_commit"] != member["base_commit"]:
        raise GroupError("member handoff is bound to a superseded member baseline")
    require_commit(handoff["base_commit"], "member handoff base commit")
    for key in (
        "session_digest", "patch_digest", "changed_paths_digest", "record_digest",
    ):
        require_digest(handoff[key], f"member handoff {key}")
    if type(handoff["generation"]) is not int or handoff["generation"] < 0:
        raise GroupError("member handoff ownership generation is invalid")
    binding = member["session_binding"]
    if binding is None or binding["state"] != "stopped":
        raise GroupError("a submitted member handoff must close its writing claim")
    if (
        binding["session_digest"] != handoff["session_digest"]
        or binding["generation"] != handoff["generation"]
    ):
        raise GroupError("member handoff is bound to a different session owner")


def require_open_member_writing(member: dict[str, Any], plan: str) -> None:
    """Refuse a member operation once its frozen handoff closed member writing."""

    if member["handoff"] is not None:
        raise GroupError(
            f"member {plan} closed its writing claim with a submitted handoff; "
            "integration owns the result and members never publish"
        )


def validate_member_ledger(
    state: dict[str, Any], plan: str, member: dict[str, Any]
) -> None:
    """Validate one member's one-use execution ledger claim against its history."""

    ledger = member["ledger_binding"]
    recorded = [
        event["detail"]["ledger_binding"]
        for event in state["events"]
        if event["event_type"] == "member_ledger_claimed"
        and event["detail"].get("plan_path") == plan
    ]
    if ledger != (recorded[-1] if recorded else None):
        raise GroupError("member ledger claim differs from its recorded history")
    if ledger is None:
        return
    exact_object(ledger, SESSION_LEDGER_KEYS, "member ledger claim")
    if not isinstance(ledger["run_id"], str) or not IDENTIFIER_RE.fullmatch(
        ledger["run_id"]
    ):
        raise GroupError("member ledger claim names an invalid run id")
    for key in ("state_path_digest", "lifecycle_path_digest", "session_digest"):
        require_digest(ledger[key], f"member ledger {key}")
    if ledger["state_path_digest"] == ledger["lifecycle_path_digest"]:
        raise GroupError("member ledger claim reuses one path for two records")
    if type(ledger["generation"]) is not int or ledger["generation"] < 0:
        raise GroupError("member ledger ownership generation is invalid")


def validate_session_state(state: dict[str, Any]) -> None:
    exact_object(state, {
        "schema_version", "group_id", "group_description_path",
        "group_description_digest", "repository_identity", "target_ref",
        "common_start_commit", "upstream_claim", "publication_lease",
        "final_successor_claim", "members", "events", "common_git_identity",
        "integration_session_digest", "integration_process_identity",
    }, "session group state")
    require_digest(state["integration_session_digest"], "integration session digest")
    validate_process_identity(state["integration_process_identity"])
    admission = state["events"][0] if state["events"] else {}
    if admission.get("event_type") != "group_admitted" or any(
        admission.get("detail", {}).get(key) != state[key]
        for key in ("integration_session_digest", "integration_process_identity")
    ):
        raise GroupError("integration owner differs from its admitted history")
    if not isinstance(state["members"], dict) or len(state["members"]) != 2:
        raise GroupError("session group must retain exactly two members")
    seen: set[str] = {state["integration_session_digest"]}
    processes = [state["integration_process_identity"]]
    for plan, member in state["members"].items():
        if not isinstance(plan, str) or not PLAN_PATH_RE.fullmatch(plan):
            raise GroupError("session group member path is invalid")
        keys = set(empty_member_state(plan, "", "")) | {
            "session_binding", "obligations_digest", "handoff", "ledger_binding",
        }
        exact_object(member, keys, "session group member")
        require_digest(member["obligations_digest"], "member obligations digest")
        validate_member_handoff(state, plan, member)
        validate_member_ledger(state, plan, member)
        binding = member["session_binding"]
        latest = [
            event["detail"]["session_binding"]
            for event in state["events"]
            if event["event_type"] in {
                "member_session_preparing", "member_session_bound", "member_session_stopped",
            } and event["detail"].get("plan_path") == plan
        ]
        if binding != (latest[-1] if latest else None):
            raise GroupError("session binding differs from its recorded history")
        if binding is None:
            continue
        exact_object(binding, SESSION_BINDING_KEYS, "session binding")
        if binding["state"] not in {"preparing", "bound", "stopped"}:
            raise GroupError("session binding state is invalid")
        require_digest(binding["session_digest"], "member session digest")
        if binding["session_digest"] in seen:
            raise GroupError("session group reuses a member or integration session")
        seen.add(binding["session_digest"])
        if type(binding["generation"]) is not int or binding["generation"] < 0:
            raise GroupError("session ownership generation is invalid")
        process = binding["process_identity"]
        validate_process_identity(process)
        if process in processes:
            raise GroupError("session group reuses a member or integration process")
        processes.append(process)
        if not isinstance(binding["worktree_path"], str) or not Path(
            binding["worktree_path"]
        ).is_absolute():
            raise GroupError("session worktree path must be absolute")
        if not isinstance(binding["branch_ref"], str) or not TARGET_REF_RE.fullmatch(
            binding["branch_ref"]
        ):
            raise GroupError("session worktree branch is invalid")
        if binding["state"] != "preparing" and not isinstance(
            binding["worktree_identity"], dict
        ):
            raise GroupError("bound session must retain its worktree identity")


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


def worktree_manager():
    name = "parallel_session_worktree_manager"
    if name not in sys.modules:
        path = Path(__file__).with_name("manage-plan-worktrees.py")
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise GroupError("managed worktree command is unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def session_state_path(root: Path, group_id: str) -> Path:
    guard = worktree_manager().guard
    key = canonical_digest({
        "repository_identity": guard.repository_identity(root), "group_id": group_id,
    })[7:]
    return guard.account_home() / (
        ".local/state/project-agent-workflow/session-groups"
    ) / f"{key}.json"


def session_identity(explicit: str | None = None) -> str:
    value = explicit or os.environ.get(SESSION_ENVIRONMENT_VARIABLE) or os.environ.get(
        "CODEX_THREAD_ID"
    )
    return digest(require_identifier(value, "session identity"))


def process_identity(pid: int) -> dict[str, Any] | None:
    if type(pid) is not int or pid <= 1:
        raise GroupError("session process must have a positive non-system PID")
    if not Path("/proc/self/stat").is_file():
        raise GroupError("session process identity requires readable procfs evidence")
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
    except FileNotFoundError:
        return None
    fields = raw[raw.rfind(")") + 2:].split()
    if len(fields) < 20:
        raise GroupError("session process identity is malformed")
    if fields[0] == "Z":
        return None
    return {
        "pid": pid, "start_ticks": int(fields[19]),
        "boot_digest": digest(Path("/proc/sys/kernel/random/boot_id").read_bytes()),
    }


def validate_process_identity(value: Any) -> None:
    process = exact_object(
        value, {"pid", "start_ticks", "boot_digest"}, "session process identity",
    )
    if (
        type(process["pid"]) is not int or process["pid"] <= 1
        or type(process["start_ticks"]) is not int or process["start_ticks"] < 0
    ):
        raise GroupError("session process identity is invalid")
    require_digest(process["boot_digest"], "session process boot digest")


def require_session_process(pid: int) -> dict[str, Any]:
    identity = process_identity(pid)
    if identity is None:
        raise GroupError("session process has already stopped")
    current = os.getpid()
    for _ in range(128):
        if current == pid:
            return identity
        if current <= 1:
            break
        try:
            raw = Path(f"/proc/{current}/stat").read_text()
            current = int(raw[raw.rfind(")") + 2:].split()[1])
        except (FileNotFoundError, ValueError, IndexError) as exc:
            raise GroupError("session process ancestry is unavailable") from exc
    raise GroupError("session process is not an ancestor of this command")


def require_session_state(root: Path, path: Path, state: dict[str, Any]) -> None:
    if state["schema_version"] != SESSION_GROUP_SCHEMA_VERSION:
        raise GroupError("session ownership requires a schema-2 group")
    if path.absolute() != session_state_path(root, state["group_id"]):
        raise GroupError("session group state is not at its canonical private path")
    if state["common_git_identity"] != worktree_manager().guard.repository_identity(root):
        raise GroupError("session group belongs to a different common Git directory")
    require_live_group(root, state, allow_sessions=True)


def session_enrolment(root: Path, plan: str | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    enrolled = enrolled_member(root, plan)
    return enrolled if enrolled and enrolled["schema_version"] == 2 else None


def session_member_prepare(manager, args: argparse.Namespace, *, resume: bool) -> bool:
    root = manager.repository_root()
    enrolled = session_enrolment(root, args.plan)
    if enrolled is None:
        return False
    path = session_state_path(root, enrolled["group_id"])
    owner = session_identity(getattr(args, "session_id", None))
    process = require_session_process(getattr(args, "session_pid", None))
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        require_session_state(root, path, state)
        if (
            owner == state["integration_session_digest"]
            or process == state["integration_process_identity"]
        ):
            raise GroupError("integration and member sessions and processes must be distinct")
        member = require_member(state, args.plan)
        require_active_member(member)
        require_open_member_writing(member, args.plan)
        for other_path, other in state["members"].items():
            binding = other["session_binding"]
            if other_path != args.plan and binding and (
                binding["session_digest"] == owner
                or binding["process_identity"] == process
            ):
                raise GroupError("another member already binds this session or process")
        previous = member["session_binding"]
        if previous:
            recovering = (
                previous["state"] == "preparing"
                and previous["session_digest"] == owner
                and previous["process_identity"] == process
            )
            if not recovering and not resume:
                raise GroupError("member session already started; use an explicit stopped resume")
            if not recovering and previous["state"] != "stopped" and (
                process_identity(previous["process_identity"]["pid"])
                == previous["process_identity"]
            ):
                raise GroupError("prior session process is still live; lease expiry is insufficient")
        elif resume:
            raise GroupError("member has no prior session to resume")
        if manager.git_text(root, "rev-parse", "HEAD") != member["base_commit"]:
            raise GroupError("member preparation requires its exact admitted baseline")
        delegated = argparse.Namespace(**vars(args))
        if getattr(args, "source_ref", None) not in {None, state["target_ref"]}:
            raise GroupError("member preparation cannot change the admitted source ref")
        delegated.owner_id = f"group-{state['group_id']}-{member['logical_member_id']}"
        delegated.source_ref = state["target_ref"]
        delegated.worktree = getattr(args, "worktree", None)
        delegated.branch = getattr(args, "branch", None)
        delegated.purpose = None
        delegated.lease_seconds = getattr(args, "lease_seconds", 14_400)
        allowed = manager.resolve_allowed_root(root, args.allowed_root)
        task = manager.plan_task(manager.committed_plan(root, args.plan, member["base_commit"]))
        target, branch = manager.default_placement(task, allowed)
        target = manager.validate_target(
            delegated.worktree or str(target), allowed, must_exist=False, allow_existing=True,
        )
        _, branch_ref = manager.normalize_branch(delegated.branch or branch, root)
        paths = manager.metadata_paths(manager.repository_identity(root), task)
        if not previous and (paths["record"].exists() or paths["journal"].exists()):
            raise GroupError("task worktree already exists outside this session preparation")
        if previous and paths["record"].exists():
            old_record = manager.read_record(paths["record"])
            if (
                old_record["owner"]["id"] != delegated.owner_id
                or old_record["start_commit"] != member["base_commit"]
                or old_record["source_ref"] != state["target_ref"]
                or old_record["branch_ref"] != previous["branch_ref"]
                or old_record["worktree_path"] != previous["worktree_path"]
            ):
                raise GroupError("existing task record differs from this session preparation")
        if previous and (
            previous["worktree_path"] != str(target) or previous["branch_ref"] != branch_ref
        ):
            raise GroupError("resume cannot change the exact member worktree or branch")
        for other_path, other in state["members"].items():
            binding = other["session_binding"]
            if other_path != args.plan and binding and (
                binding["worktree_path"] == str(target) or binding["branch_ref"] == branch_ref
            ):
                raise GroupError("member worktrees and branches must be distinct")
        if not previous or not recovering:
            member["session_binding"] = {
                "state": "preparing", "session_digest": owner,
                "generation": previous["generation"] + 1 if previous else 0,
                "process_identity": process, "worktree_path": str(target),
                "branch_ref": branch_ref, "worktree_identity": None,
            }
            append_event(state, "member_session_preparing", {
                "plan_path": args.plan, "session_binding": member["session_binding"].copy(),
            })
            atomic_write(path, state)
        # The group lock precedes the manager's ownership lock. A partial
        # manager result remains bound to this exact preparation for recovery.
        result = manager.prepare_ungrouped(delegated, emit=False)
        record = manager.read_record(paths["record"])
        actual, _ = manager.verify_record_context(root, allowed, record)
        if (
            actual != target or record["branch_ref"] != branch_ref
            or record["source_ref"] != state["target_ref"]
            or record["start_commit"] != member["base_commit"]
            or record["owner"]["id"] != delegated.owner_id
        ):
            raise GroupError("prepared worktree differs from the session binding")
        if require_session_process(process["pid"]) != process:
            raise GroupError("session process changed during worktree preparation")
        binding = member["session_binding"]
        binding["state"] = "bound"
        binding["worktree_identity"] = record["worktree_identity"]
        append_event(state, "member_session_bound", {
            "plan_path": args.plan, "session_binding": binding.copy(),
        })
        atomic_write(path, state)
    print(json.dumps({
        **result, "session_generation": binding["generation"],
        "execution_enabled": grouped_adapter_version() is not None,
        "publication_enabled": False,
    }, sort_keys=True))
    return True


def require_session_binding(
    root: Path, binding, *, session_id: str | None = None,
) -> None:
    if binding.kind != "plan":
        return
    plan = binding.task["identity"]["path"]
    enrolled = session_enrolment(root, plan)
    if enrolled is None:
        return
    path = session_state_path(root, enrolled["group_id"])
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
        state = read_state(path, root=root)
        require_session_state(root, path, state)
        member = require_member(state, plan)
        require_active_member(member)
        require_open_member_writing(member, plan)
        owner = member["session_binding"]
        if owner is None or owner["state"] != "bound":
            raise GroupError("member session has no completed live worktree binding")
        if owner["session_digest"] != session_identity(session_id):
            raise GroupError("grouped write belongs to a different session")
        if (
            owner["worktree_path"] != str(root)
            or owner["branch_ref"] != binding.branch_ref
            or owner["worktree_identity"] != binding.record["worktree_identity"]
        ):
            raise GroupError("grouped write belongs to a different worktree")
        if require_session_process(owner["process_identity"]["pid"]) != owner["process_identity"]:
            raise GroupError("grouped write belongs to a stale session process")
    if grouped_adapter_version() is None:
        raise GroupError(
            "session binding is valid, but member execution remains closed until "
            "the parent-direct session adapter is installed"
        )


def session_stop(args: argparse.Namespace) -> None:
    root = repository_root()
    path = Path(args.state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        require_session_state(root, path, state)
        member = require_member(state, args.member)
        require_open_member_writing(member, args.member)
        binding = member["session_binding"]
        if binding is None or binding["state"] != "bound":
            raise GroupError("only a bound session can issue a stopped handoff")
        if binding["session_digest"] != session_identity(args.session_id):
            raise GroupError("only the current session can stop its writing claim")
        if require_session_process(binding["process_identity"]["pid"]) != binding["process_identity"]:
            raise GroupError("stopped handoff requires the exact live session process")
        binding["state"] = "stopped"
        append_event(state, "member_session_stopped", {
            "plan_path": args.member, "session_binding": binding.copy(),
        })
        atomic_write(path, state)
    print("member session stopped; execution budgets and worktree are retained")


def verify_handoff_artifacts(
    root: Path,
    args: argparse.Namespace,
    state: dict[str, Any],
    member: dict[str, Any],
    binding: dict[str, Any],
) -> None:
    """Refuse a handoff whose claimed digests do not describe real artifacts.

    The submitted digests are evidence only when the bounded private record and
    its patch exist, agree with each other, and agree with the member identity
    this authority already holds. Recording a digest that describes nothing
    would let a member close its writing claim without producing a result.
    """

    record_path = Path(args.record)
    require_outside_repository(record_path, "member handoff record", root)
    data = read_private_bounded_bytes(record_path, "member handoff record")
    try:
        record = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GroupError("member handoff record is invalid JSON") from exc
    if not isinstance(record, dict) or "record_digest" not in record:
        raise GroupError("member handoff record is not a handoff record")
    recomputed = canonical_digest(
        {key: value for key, value in record.items() if key != "record_digest"}
    )
    if recomputed != record["record_digest"] or recomputed != args.record_digest:
        raise GroupError("member handoff record does not match its recorded digest")
    for label, observed, expected in (
        ("group", record.get("group_id"), state["group_id"]),
        (
            "group description",
            record.get("group_description_digest"),
            state["group_description_digest"],
        ),
        ("plan path", record.get("plan_path"), args.member),
        ("plan digest", record.get("plan_digest"), member["plan_digest"]),
        ("baseline", record.get("base_commit"), member["base_commit"]),
        ("session", record.get("session_digest"), binding["session_digest"]),
        ("ownership generation", record.get("session_generation"), binding["generation"]),
        ("worktree", record.get("worktree_path"), binding["worktree_path"]),
        ("patch digest", record.get("patch_digest"), args.patch_digest),
        (
            "changed paths digest",
            record.get("changed_paths_digest"),
            args.changed_paths_digest,
        ),
    ):
        if observed != expected:
            raise GroupError(f"member handoff record names a different {label}")
    if record.get("acceptance") != "not_accepted":
        raise GroupError("member handoff record claims acceptance it cannot hold")
    changed = record.get("changed_paths")
    scope = record.get("write_scope")
    if not isinstance(changed, list) or not changed:
        raise GroupError("member handoff record describes no changed path")
    if not isinstance(scope, list) or not scope:
        raise GroupError("member handoff record declares no write scope")
    if canonical_digest(changed) != args.changed_paths_digest:
        raise GroupError("member handoff record contradicts its changed-path digest")
    outside = sorted(path for path in changed if path not in set(scope))
    if outside:
        raise GroupError(
            "member handoff record changes paths outside its declared write scope: "
            + ", ".join(outside)
        )
    patch_path = Path(str(record.get("patch_path", "")))
    if not patch_path.is_absolute():
        raise GroupError("member handoff record names no absolute patch path")
    require_outside_repository(patch_path, "member handoff patch", root)
    patch = read_private_bounded_bytes(patch_path, "member handoff patch")
    if not patch:
        raise GroupError("member handoff patch is empty")
    if digest(patch) != args.patch_digest:
        raise GroupError("member handoff patch does not match its recorded digest")


def session_handoff_record(args: argparse.Namespace) -> None:
    """Freeze one member result and close that member's writing claim.

    The adapter derives the full Git diff and writes the bounded handoff
    artifact; this authority records only its identity and digests under the
    group lock. Recording a handoff is not acceptance, not review, not
    validation and never authorizes member publication.
    """

    root = repository_root()
    path = Path(args.state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        require_session_state(root, path, state)
        member = require_member(state, args.member)
        require_active_member(member)
        require_open_member_writing(member, args.member)
        binding = member["session_binding"]
        if binding is None or binding["state"] != "bound":
            raise GroupError("only a bound member session can submit a handoff")
        if binding["session_digest"] != session_identity(args.session_id):
            raise GroupError("only the current member session can submit its handoff")
        if require_session_process(binding["process_identity"]["pid"]) != binding[
            "process_identity"
        ]:
            raise GroupError("a submitted handoff requires the exact live session process")
        if args.generation != binding["generation"]:
            raise GroupError("member handoff names a stale ownership generation")
        if args.base_commit != member["base_commit"]:
            raise GroupError("member handoff is bound to a superseded member baseline")
        if args.plan_digest != member["plan_digest"]:
            raise GroupError("member handoff is bound to different plan bytes")
        verify_handoff_artifacts(root, args, state, member, binding)
        handoff = {
            "schema_version": PARENT_DIRECT_HANDOFF_SCHEMA_VERSION,
            "handoff_mode": PARENT_DIRECT_HANDOFF_MODE,
            "plan_digest": require_digest(args.plan_digest, "plan_digest"),
            "base_commit": require_commit(args.base_commit, "base_commit"),
            "session_digest": binding["session_digest"],
            "generation": binding["generation"],
            "patch_digest": require_digest(args.patch_digest, "patch_digest"),
            "changed_paths_digest": require_digest(
                args.changed_paths_digest, "changed_paths_digest"
            ),
            "record_digest": require_digest(args.record_digest, "record_digest"),
        }
        binding["state"] = "stopped"
        append_event(state, "member_session_stopped", {
            "plan_path": args.member, "session_binding": binding.copy(),
        })
        member["handoff"] = handoff
        append_event(state, "member_handoff_submitted", {
            "plan_path": args.member, "handoff": handoff.copy(),
        })
        atomic_write(path, state)
    print(json.dumps({
        "member": args.member,
        "handoff_record_digest": handoff["record_digest"],
        "member_writing_open": False,
        "acceptance": "not_accepted",
        "publication_enabled": False,
    }, sort_keys=True))


def session_correction(args: argparse.Namespace) -> None:
    """Spend the single allowance shared by member correction and adjustment.

    A member's substantive correction and the integration parent-adjustment slot
    are one logical allowance. Spending it here leaves the later adjustment
    refused, and a new session, worktree or ownership generation never
    replenishes it.
    """

    root = repository_root()
    path = Path(args.state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        require_session_state(root, path, state)
        member = require_member(state, args.member)
        require_active_member(member)
        require_open_member_writing(member, args.member)
        binding = member["session_binding"]
        if binding is None or binding["state"] != "bound":
            raise GroupError("only a bound member session can spend its correction allowance")
        if binding["session_digest"] != session_identity(args.session_id):
            raise GroupError("only the current member session can spend its correction allowance")
        if require_session_process(binding["process_identity"]["pid"]) != binding[
            "process_identity"
        ]:
            raise GroupError("a member correction requires the exact live session process")
        if member["counters"]["corrections"] >= MEMBER_CORRECTION_LIMIT:
            raise GroupError(
                f"member {args.member} already spent its single correction slot; "
                "the member correction and the parent adjustment share one allowance"
            )
        member["counters"]["corrections"] += 1
        append_event(state, "member_correction_reserved", {
            "plan_path": args.member,
            "corrections": member["counters"]["corrections"],
            "generation": binding["generation"],
        })
        atomic_write(path, state)
    print(member["counters"]["corrections"])


def claim_member_ledger(
    root: Path,
    path: Path,
    plan: str,
    *,
    run_id: str,
    state_path: Path,
    lifecycle_path: Path,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Claim the single execution ledger this member may ever own.

    The claim is recorded before the ledger records exist, so an interrupted
    preparation retains it and a second initialization is refused. A new run
    name, a new session or a fresh checkout therefore cannot obtain a second
    ledger and replenish a spent member budget.
    """

    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        require_session_state(root, path, state)
        member = require_member(state, plan)
        require_active_member(member)
        require_open_member_writing(member, plan)
        binding = member["session_binding"]
        if binding is None or binding["state"] != "bound":
            raise GroupError(
                f"{plan} has no live member session binding; its execution ledger "
                "is claimed from inside its own bound session"
            )
        if binding["session_digest"] != session_identity(session_id):
            raise GroupError("only the current member session can claim its ledger")
        if require_session_process(binding["process_identity"]["pid"]) != binding[
            "process_identity"
        ]:
            raise GroupError("a ledger claim requires the exact live session process")
        existing = member["ledger_binding"]
        if existing is not None:
            raise GroupError(
                f"member {plan} already claimed execution ledger run "
                f"{existing['run_id']}; a second initialization is refused and a "
                "new run name, session or checkout never replenishes its budget"
            )
        ledger = {
            "run_id": run_id,
            "state_path_digest": canonical_digest(str(state_path.absolute())),
            "lifecycle_path_digest": canonical_digest(str(lifecycle_path.absolute())),
            "session_digest": binding["session_digest"],
            "generation": binding["generation"],
        }
        member["ledger_binding"] = ledger
        append_event(state, "member_ledger_claimed", {
            "plan_path": plan, "ledger_binding": ledger.copy(),
        })
        atomic_write(path, state)
    return ledger


def require_member_ledger_binding(
    root: Path,
    path: Path,
    plan: str,
    *,
    run_id: str,
    state_path: Path,
    lifecycle_path: Path,
) -> dict[str, Any]:
    """Refuse a member ledger record its one-use group claim does not name.

    The claim is what makes the ledger single-use. Without this check a member
    could initialize a fresh ledger under another run name or destination and
    obtain replenished budgets and a cleared stop state.
    """

    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
        state = read_state(path)
        require_session_state(root, path, state)
        member = require_member(state, plan)
        require_active_member(member)
        ledger = member["ledger_binding"]
    if ledger is None:
        raise GroupError(
            f"member {plan} has no execution ledger claim; claim it with "
            "plan-execution-state.py prepare-parent-direct --group-state before "
            "any ledger record exists"
        )
    if ledger["run_id"] != run_id:
        raise GroupError(
            f"member {plan} claimed execution ledger run {ledger['run_id']}; a new "
            "run name never replenishes its budget"
        )
    for label, key, observed in (
        ("execution state", "state_path_digest", state_path),
        ("candidate lifecycle state", "lifecycle_path_digest", lifecycle_path),
    ):
        if ledger[key] != canonical_digest(str(observed.absolute())):
            raise GroupError(
                f"member {plan} claimed a different {label} destination; a new "
                "ledger destination never replenishes its budget"
            )
    return ledger


def session_ledger_claim(args: argparse.Namespace) -> None:
    ledger = claim_member_ledger(
        repository_root(),
        Path(args.state),
        args.member,
        run_id=args.run_id,
        state_path=Path(args.execution_state),
        lifecycle_path=Path(args.lifecycle_state),
        session_id=args.session_id,
    )
    print(json.dumps(ledger, sort_keys=True))


def print_session_state_path(args: argparse.Namespace) -> None:
    root = repository_root()
    group = load_group_descriptions(root).get(args.group_description)
    if group is None or group["description"]["schema_version"] != 2:
        raise GroupError("expected one committed schema-2 group description")
    print(session_state_path(root, group["description"]["group_id"]))


def require_live_group(
    root: Path,
    state: dict[str, Any],
    *,
    allow_lifecycle_evolution: bool = False,
    allow_sessions: bool = False,
) -> dict[str, Any]:
    """Recheck that the committed group still matches the admitted record.

    Member plan bytes stay pinned while a member can still generate, adjust, or
    publish a candidate. After a verified publication the ordinary plan
    lifecycle rewrites that member's own status and validation notes, so those
    authorized edits must not be misread as authority drift. Every other
    member, the committed group description, the group identity, membership,
    and the repository identity stay pinned in both cases.
    """

    if state["schema_version"] == 2 and not allow_sessions:
        raise GroupError(
            "parent-direct session registration does not enable this execution operation"
        )
    published = frozenset(
        plan_path
        for plan_path, member in state["members"].items()
        if member["publication"]["published"]
    ) if allow_lifecycle_evolution else frozenset()
    groups = load_group_descriptions(root, published)
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
    if group["description"]["target_ref"] != state["target_ref"]:
        raise GroupError("the committed group target ref changed after admission")
    for plan_path, member in state["members"].items():
        if plan_path not in group["members"]:
            raise GroupError("group membership changed after admission")
        if allow_lifecycle_evolution and member["publication"]["published"]:
            continue
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
    if group["description"]["schema_version"] == 2:
        expected = session_state_path(root, state["group_id"])
        if path.absolute() != expected:
            raise GroupError(f"schema-2 group state must use its canonical private path: {expected}")
        state["schema_version"] = 2
        state["common_git_identity"] = worktree_manager().guard.repository_identity(root)
        state["integration_session_digest"] = session_identity(args.integration_session_id)
        state["integration_process_identity"] = require_session_process(args.integration_session_pid)
        for plan_path, member in state["members"].items():
            manifest = group["members"][plan_path]["manifest"]
            if manifest is None:
                raise GroupError("session group initialization requires two live plans")
            specifications = {
                relative: digest(read_bounded_bytes(root / relative, "required specification"))
                for relative in manifest["required_specs"] if relative != "none"
            }
            member["session_binding"] = None
            member["handoff"] = None
            member["ledger_binding"] = None
            member["obligations_digest"] = canonical_digest({
                "acceptance": manifest["acceptance"],
                "validation": manifest["validation"],
                "focused_validation": manifest["focused_validation"],
                "required_specifications": specifications,
            })
    admission = {
        "group_description_digest": group["description_digest"],
        "common_start_commit": head,
    }
    if state["schema_version"] == 2:
        admission.update({
            "integration_session_digest": state["integration_session_digest"],
            "integration_process_identity": state["integration_process_identity"],
        })
    append_event(state, "group_admitted", admission)
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
        if state["schema_version"] == SESSION_GROUP_SCHEMA_VERSION:
            # Integration, not the member session, holds this lease. The
            # authenticated integration session is the only caller that may
            # take it, so registration still grants a member nothing.
            require_session_state(root, path, state)
            require_integration_session(
                state, args.integration_session_id, args.integration_session_pid
            )
        else:
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


def require_integration_session(
    state: dict[str, Any], session_id: str | None, session_pid: int | None
) -> None:
    """Authenticate the integration session that admitted this schema-2 group.

    A member session can read the group state and knows its own handoff digest,
    so neither fact is publication authority. The group records the integration
    session identity and its process incarnation at admission, and the process
    check requires the caller to actually run inside that process tree, which a
    separately started member session cannot do.
    """

    if session_id is None or session_pid is None:
        raise GroupError(
            "this operation requires the integration session identity and its "
            "live process"
        )
    if session_identity(session_id) != state["integration_session_digest"]:
        raise GroupError(
            "this operation requires the integration session that admitted the group"
        )
    identity = require_session_process(session_pid)
    if identity["boot_digest"] != state["integration_process_identity"]["boot_digest"]:
        raise GroupError(
            "the integration session process evidence comes from another boot"
        )


def lease_release(args: argparse.Namespace) -> None:
    """Free the exclusive publication lease held by its recorded owner.

    Releasing must keep working after authority drift, so this path rechecks
    the live group only for a schema-2 group, whose lease belongs to the
    authenticated integration session. The owner is a bounded identifier, which
    keeps an unheld lease, whose owner is the empty string, from being
    "released" repeatedly into the bounded event chain.
    """

    path = Path(args.state)
    owner = require_identifier(args.owner, "owner")
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        if state["schema_version"] == SESSION_GROUP_SCHEMA_VERSION:
            require_integration_session(
                state, args.integration_session_id, args.integration_session_pid
            )
        if state["publication_lease"]["owner"] != owner:
            raise GroupError("only the recorded lease owner may release the lease")
        state["publication_lease"] = {"owner": "", "plan_path": ""}
        append_event(state, "publication_lease_released", {"owner": owner})
        atomic_write(path, state)
    print(owner)


def spend_member_review(
    root: Path,
    path: Path,
    plan: str,
    *,
    assembly_record_digest: str,
    registry_path_digest: str,
    registry_event_count: int,
    registry_event_chain_digest: str,
) -> int:
    """Spend one review from the budget this member owns.

    The execution ledger and this authority must describe one review history,
    so every formal review of a member reaches this budget. A member session
    reviews at most once before it hands off: the remaining slot belongs to the
    integration review of the assembled result at the final base, so neither a
    restarted session nor a second member round can consume it.
    """

    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        sessions = state["schema_version"] == SESSION_GROUP_SCHEMA_VERSION
        require_live_group(root, state, allow_sessions=sessions)
        member = require_member(state, plan)
        require_active_member(member)
        reserved = sessions and member["handoff"] is None
        limit = SESSION_MEMBER_REVIEW_LIMIT if reserved else MEMBER_REVIEW_LIMIT
        if member["counters"]["reviews"] >= limit:
            if reserved:
                raise GroupError(
                    f"member {plan} already took its single pre-handoff review; "
                    "the remaining review is reserved for integration at the final base"
                )
            raise GroupError(f"member {plan} exhausted its independent review budget")
        # A review is evidence about one exact assembled artifact. Recording the
        # artifact identity is what lets publication refuse a different result
        # that merely happens to follow a review of an earlier candidate.
        review_target = require_digest(assembly_record_digest, "assembly_record_digest")
        path_digest = require_digest(registry_path_digest, "registry_path_digest")
        chain_digest = require_digest(
            registry_event_chain_digest, "registry_event_chain_digest"
        )
        if not isinstance(registry_event_count, int) or registry_event_count < 1:
            raise GroupError("registry_event_count must be a positive integer")
        prior = member["reviewer_registry_proof"]
        if prior["registry_path_digest"]:
            # Both reviews of one member must come from the same canonical
            # reviewer registry, advancing along its own append-only chain.
            if prior["registry_path_digest"] != path_digest:
                raise GroupError(
                    f"member {plan} reviews must use one canonical reviewer registry"
                )
            if registry_event_count <= prior["event_count"]:
                raise GroupError(
                    "reviewer registry event count must advance for each recorded review"
                )
            if chain_digest == prior["event_chain_digest"]:
                raise GroupError(
                    "reviewer registry event chain must advance for each recorded review"
                )
        member["counters"]["reviews"] += 1
        member["reviewer_registry_proof"] = {
            "registry_path_digest": path_digest,
            "event_count": registry_event_count,
            "event_chain_digest": chain_digest,
        }
        append_event(
            state,
            "member_review_recorded",
            {
                "plan_path": plan,
                "reviews": member["counters"]["reviews"],
                "assembly_record_digest": review_target,
            },
        )
        atomic_write(path, state)
    return member["counters"]["reviews"]


def record_review(args: argparse.Namespace) -> None:
    print(spend_member_review(
        repository_root(),
        Path(args.state),
        args.member,
        assembly_record_digest=args.assembly_record_digest,
        registry_path_digest=args.registry_path_digest,
        registry_event_count=args.registry_event_count,
        registry_event_chain_digest=args.registry_event_chain_digest,
    ))


def adjust_reserve(args: argparse.Namespace) -> None:
    path = Path(args.state)
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        sessions = state["schema_version"] == SESSION_GROUP_SCHEMA_VERSION
        require_live_group(repository_root(), state, allow_sessions=sessions)
        member = require_member(state, args.member)
        require_active_member(member)
        if sessions:
            # A parent-direct member holds no candidate permit. Its submitted
            # handoff is the exact artifact an integration adjustment reworks.
            handoff = member["handoff"]
            if handoff is None:
                raise GroupError(
                    "a parent adjustment requires the member's submitted handoff"
                )
            if args.permit_id != handoff["record_digest"]:
                raise GroupError(
                    "parent adjustment requires the exact submitted member handoff"
                )
        elif member["permit"]["permit_id"] != args.permit_id or not member["permit"]["open"]:
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
        sessions = state["schema_version"] == SESSION_GROUP_SCHEMA_VERSION
        require_live_group(repository_root(), state, allow_sessions=sessions)
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
        if state["schema_version"] == SESSION_GROUP_SCHEMA_VERSION:
            raise GroupError(
                "legacy member-stop is closed for session groups; "
                "session-stop releases only the current owner's writing claim"
            )
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
        if member["baseline_generation"] >= MEMBER_BASELINE_TRANSFER_LIMIT:
            raise GroupError(
                f"member {args.member} already spent its single baseline transfer; "
                "the assembled result is preserved and the target movement stops "
                "for an owner decision"
            )
        if member["publication"]["published"]:
            raise GroupError(
                f"member {args.member} already published its accepted result"
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


def publication_record(args: argparse.Namespace) -> None:
    """Record one verified member publication under the publication lease.

    Acceptance follows publication, never a worker completion claim: this call
    requires the exclusive lease, the exact member permit, and a commit already
    reachable from the admitted group target ref.
    """

    path = Path(args.state)
    if bool(args.permit_id) == bool(args.handoff_digest):
        raise GroupError(
            "record one publication identity: --permit-id for a sandboxed "
            "candidate, or --handoff-digest for a parent-direct member handoff"
        )
    commit = require_commit(args.commit, "commit")
    assembly_digest = require_digest(args.assembly_digest, "assembly_digest")
    with with_lock(path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        root = repository_root()
        if args.handoff_digest:
            require_session_state(root, path, state)
            require_integration_session(
                state, args.integration_session_id, args.integration_session_pid
            )
        else:
            require_live_group(root, state)
        member = require_member(state, args.member)
        require_active_member(member)
        if state["publication_lease"]["owner"] == "":
            raise GroupError("recording a publication requires the publication lease")
        if state["publication_lease"]["plan_path"] != args.member:
            raise GroupError("the publication lease was acquired for another member")
        if member["publication"]["published"]:
            raise GroupError(
                f"member {args.member} already published its accepted result"
            )
        if args.handoff_digest:
            handoff = member["handoff"]
            if handoff is None:
                raise GroupError(
                    "a parent-direct publication requires the member's submitted "
                    "handoff record"
                )
            if handoff["record_digest"] != require_digest(
                args.handoff_digest, "handoff_digest"
            ):
                raise GroupError(
                    "a publication must consume the exact submitted member handoff"
                )
            # The adapter checks the review too, but the authority must not
            # depend on its caller for that fact: a member knows its own
            # handoff digest and could otherwise record a publication directly.
            reviewed = any(
                event["event_type"] == "member_review_recorded"
                and event["detail"].get("plan_path") == args.member
                and event["detail"].get("assembly_record_digest") == assembly_digest
                for event in state["events"]
            )
            if not reviewed:
                raise GroupError(
                    "a parent-direct publication requires one recorded independent "
                    "review of this exact assembled result"
                )
        elif (
            member["permit"]["permit_id"] != args.permit_id
            or not member["permit"]["open"]
        ):
            raise GroupError(
                "a publication must consume the exact open member permit"
            )
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "merge-base",
                "--is-ancestor",
                commit,
                state["target_ref"],
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=sanitized_git_environment(),
        )
        if completed.returncode != 0:
            raise GroupError(
                "the published commit is not reachable from the group target ref"
            )
        member["publication"] = {"published": True, "commit": commit}
        if args.handoff_digest:
            # The lease is one-use per member: leaving it held would lock the
            # partner out of its own publication.
            state["publication_lease"] = {"owner": "", "plan_path": ""}
        else:
            member["permit"]["open"] = False
        append_event(
            state,
            "member_published",
            {
                "plan_path": args.member,
                "commit": commit,
                "assembly_digest": assembly_digest,
            },
        )
        atomic_write(path, state)
    print(commit)


def group_complete(args: argparse.Namespace) -> None:
    """Report the group complete only after every member published."""

    state = read_state(Path(args.state))
    require_live_group(
        repository_root(),
        state,
        allow_lifecycle_evolution=True,
        allow_sessions=state["schema_version"] == SESSION_GROUP_SCHEMA_VERSION,
    )
    pending = sorted(
        plan
        for plan, member in state["members"].items()
        if not member["publication"]["published"]
    )
    if pending:
        raise GroupError(
            "the execution group is incomplete; these members have not published "
            f"a verified result: {', '.join(pending)}"
        )
    print("complete")


def check_enrollment(args: argparse.Namespace) -> None:
    root = repository_root(Path(args.repository) if args.repository else None)
    require_group_permit(
        root,
        args.plan,
        args.operation,
        permit=args.group_permit,
        state=args.group_state,
    )
    published = published_member_paths(root, args.group_state)
    print(
        "ungrouped"
        if enrolled_member(root, args.plan, published) is None
        else "permitted"
    )


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
    init.add_argument("--integration-session-id")
    init.add_argument("--integration-session-pid", type=int)
    init.set_defaults(handler=group_init)

    location = sub.add_parser("session-state-path")
    location.add_argument("--group-description", required=True)
    location.set_defaults(handler=print_session_state_path)

    stop_session = sub.add_parser("session-stop")
    stop_session.add_argument("state")
    stop_session.add_argument("--member", required=True)
    stop_session.add_argument("--session-id")
    stop_session.set_defaults(handler=session_stop)

    handoff = sub.add_parser("session-handoff")
    handoff.add_argument("state")
    handoff.add_argument("--member", required=True)
    handoff.add_argument("--session-id")
    handoff.add_argument("--generation", type=int, required=True)
    handoff.add_argument("--base-commit", required=True)
    handoff.add_argument("--plan-digest", required=True)
    handoff.add_argument("--patch-digest", required=True)
    handoff.add_argument("--changed-paths-digest", required=True)
    handoff.add_argument("--record-digest", required=True)
    handoff.add_argument("--record", required=True)
    handoff.set_defaults(handler=session_handoff_record)

    correction = sub.add_parser("session-correction")
    correction.add_argument("state")
    correction.add_argument("--member", required=True)
    correction.add_argument("--session-id")
    correction.set_defaults(handler=session_correction)

    ledger = sub.add_parser("session-ledger-claim")
    ledger.add_argument("state")
    ledger.add_argument("--member", required=True)
    ledger.add_argument("--session-id")
    ledger.add_argument("--run-id", required=True)
    ledger.add_argument("--execution-state", required=True)
    ledger.add_argument("--lifecycle-state", required=True)
    ledger.set_defaults(handler=session_ledger_claim)

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
    acquire.add_argument("--integration-session-id")
    acquire.add_argument("--integration-session-pid", type=int)
    acquire.set_defaults(handler=lease_acquire)

    lease_free = sub.add_parser("lease-release")
    lease_free.add_argument("state")
    lease_free.add_argument("--owner", required=True)
    lease_free.add_argument("--integration-session-id")
    lease_free.add_argument("--integration-session-pid", type=int)
    lease_free.set_defaults(handler=lease_release)

    review = sub.add_parser("record-review")
    review.add_argument("state")
    review.add_argument("--member", required=True)
    review.add_argument("--registry-path-digest", required=True)
    review.add_argument("--registry-event-count", type=int, required=True)
    review.add_argument("--registry-event-chain-digest", required=True)
    review.add_argument("--assembly-record-digest", required=True)
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

    publication = sub.add_parser("publication-record")
    publication.add_argument("state")
    publication.add_argument("--member", required=True)
    publication.add_argument("--permit-id")
    publication.add_argument("--handoff-digest")
    publication.add_argument("--integration-session-id")
    publication.add_argument("--integration-session-pid", type=int)
    publication.add_argument("--commit", required=True)
    publication.add_argument("--assembly-digest", required=True)
    publication.set_defaults(handler=publication_record)

    complete = sub.add_parser("group-complete")
    complete.add_argument("state")
    complete.set_defaults(handler=group_complete)

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
