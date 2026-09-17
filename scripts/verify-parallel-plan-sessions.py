#!/usr/bin/env python3
"""Bounded verification of a real two-session parallel plan demonstration.

A plan that changes how two independent agent sessions implement, publish and
retire their own work cannot be accepted by fixtures alone. Mock manifests
prove the mechanics; they never prove that two operator-started sessions really
overlapped, that both results survived ordered publication, or that each task
checkout was retired afterwards.

This module owns two private structured artifacts that live outside the
repository.

``requirement record``
    One record per plan, at a fixed account-owned path derived from the
    repository identity and the plan path. It is created before implementation
    begins and binds the plan digest, the exact live acceptance digest, the
    execution genesis of the parent run and the reserved demonstration group
    identity. The exact group description digest and the report digest are
    appended once the demonstration has actually run.

``live report``
    The bounded description of one finished demonstration: installed revision,
    plans and group, distinct sessions, worktrees, diffs, review and validation
    evidence, publication order and retirement. Every Git fact it claims is
    re-derived here from the demonstration repository, and every session claim
    is re-derived from runtime-provided transcript bytes.

The environment variable named below only locates report bytes for the root
lifecycle test. Completion resolves the requirement record from the fixed path
instead, so unsetting or redirecting the variable cannot waive the obligation.
Every command except ``init`` and ``bind`` is read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

import pwd


REQUIREMENT_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1
REQUIREMENT_RECORD_TYPE = "parallel_live_evidence_requirement"
REPORT_RECORD_TYPE = "parallel_live_session_report"

# The contract is a committed plan manifest field. Prose, an environment flag
# or the presence of a record never creates or removes the obligation.
LIVE_EVIDENCE_CONTRACTS = frozenset({"parallel_sessions_v1"})
CONTRACT_FIELD = "live_evidence_contract"
ACCEPTANCE_FIELD = "live_evidence_acceptance_sha256"

REPORT_ENVIRONMENT_VARIABLE = "PROJECT_AGENT_WORKFLOW_PARALLEL_LIVE_REPORT"
STATE_RELATIVE_DIRECTORY = ".local/state/project-agent-workflow/required-evidence"

MAX_RECORD_BYTES = 65_536
MAX_REPORT_BYTES = 1_048_576
MAX_TRANSCRIPT_BYTES = 8 * 1024 * 1024
MEMBER_COUNT = 2
MINIMUM_INTERVAL_TOOL_RECORDS = 1

DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
GROUP_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
PLAN_PATH_RE = re.compile(r"docs/plan/(active|checked/[^/]+/[^/]+/[^/]+)/[0-9]{3}-[a-z0-9-]+\.md\Z")
MEMBER_PLAN_RE = re.compile(r"docs/plan/[a-z/0-9-]*[0-9]{3}-[a-z0-9-]+\.md\Z")
BRANCH_REF_RE = re.compile(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]*\Z")

REQUIREMENT_KEYS = (
    "schema_version",
    "record_type",
    "repository_identity",
    "plan_path",
    "plan_digest",
    "execution_plan_digest",
    "live_evidence_contract",
    "live_acceptance_digest",
    "execution_genesis_digest",
    "run_id",
    "reserved_group_id",
    "state",
    "group_description_digest",
    "report_path",
    "report_digest",
    "record_digest",
)

REPORT_KEYS = (
    "schema_version",
    "record_type",
    "plan_path",
    "plan_digest",
    "live_acceptance_digest",
    "execution_genesis_digest",
    "template_revision",
    "demonstration_repository",
    "demonstration_target_ref",
    "group_id",
    "group_description_path",
    "group_description_digest",
    "members",
    "publication_order",
    "validation_evidence",
    "transcript_sources",
    "hook_sources",
    "missing_sources",
    "record_digest",
)

MEMBER_KEYS = (
    "plan_path",
    "logical_member_id",
    "session_digest",
    "worktree_path",
    "branch_ref",
    "base_commit",
    "task_tip",
    "published_commit",
    "changed_paths",
    "patch_digest",
    "review_receipt_digests",
    "implementation_started_at",
    "implementation_ended_at",
)

TRANSCRIPT_KEYS = (
    "session_digest",
    "transcript_path",
    "transcript_digest",
    "tool_record_count",
)


class EvidenceError(Exception):
    """One bounded refusal. Every refusal preserves the inspected bytes."""


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def digest_text(value: str) -> str:
    return digest_bytes(value.encode("utf-8"))


def canonical_digest(value: Any) -> str:
    return digest_text(json.dumps(value, sort_keys=True, separators=(",", ":")))


def account_home() -> Path:
    """Return the account home, never a caller-controlled HOME."""

    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def required_evidence_directory() -> Path:
    return account_home() / STATE_RELATIVE_DIRECTORY


def git_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_") and key not in {"HOME", "XDG_CONFIG_HOME"}
    }
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["HOME"] = str(account_home())
    return environment


def git_run(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", "-C", str(repository), *arguments),
        capture_output=True,
        text=True,
        check=False,
        env=git_environment(),
    )


def git_text(repository: Path, *arguments: str) -> str:
    completed = git_run(repository, *arguments)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise EvidenceError(f"git {' '.join(arguments)} failed: {detail}")
    return completed.stdout.strip()


def git_succeeds(repository: Path, *arguments: str) -> bool:
    return git_run(repository, *arguments).returncode == 0


def repository_root(start: Path | None = None) -> Path:
    base = start or Path.cwd()
    return Path(git_text(base, "rev-parse", "--show-toplevel")).resolve()


def canonical_origin(repository: Path) -> str:
    completed = git_run(repository, "config", "--get", "remote.origin.url")
    if completed.returncode != 0:
        raise EvidenceError("repository has no canonical remote.origin.url")
    value = completed.stdout.strip()
    if not value:
        raise EvidenceError("repository has no canonical remote.origin.url")
    return value


def repository_identity(repository: Path) -> str:
    return digest_text(canonical_origin(repository))


def has_symlink_component(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def require_outside_repository(path: Path, label: str, root: Path) -> None:
    resolved = Path(os.path.realpath(path))
    anchor = Path(os.path.realpath(root))
    for candidate in (resolved, Path(os.path.realpath(path.parent)) / path.name):
        try:
            candidate.relative_to(anchor)
        except ValueError:
            continue
        raise EvidenceError(f"{label} must live outside the repository")


def read_private_bytes(path: Path, label: str, maximum: int) -> bytes:
    if has_symlink_component(path):
        raise EvidenceError(f"{label} path contains a symlink component")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError as error:
        raise EvidenceError(f"{label} is missing: {path}") from error
    except OSError as error:
        raise EvidenceError(f"{label} cannot be read: {error}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise EvidenceError(f"{label} must be a regular file")
        if metadata.st_nlink != 1:
            raise EvidenceError(f"{label} must not be hard linked")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise EvidenceError(f"{label} must be private with mode 0600")
        data = os.read(descriptor, maximum + 1)
    finally:
        os.close(descriptor)
    if len(data) > maximum:
        raise EvidenceError(f"{label} exceeds {maximum} bytes")
    if not data:
        raise EvidenceError(f"{label} is empty")
    return data


def read_private_json(path: Path, label: str, maximum: int) -> tuple[dict[str, Any], str]:
    data = read_private_bytes(path, label, maximum)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceError(f"{label} is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} must be a JSON object")
    return value, digest_bytes(data)


def write_private_json(path: Path, value: dict[str, Any]) -> str:
    directory = path.parent
    if has_symlink_component(directory):
        raise EvidenceError("required-evidence directory contains a symlink component")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    payload = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    data = payload.encode("utf-8")
    if len(data) > MAX_RECORD_BYTES:
        raise EvidenceError("required-evidence record exceeds its bounded size")
    temporary = directory / f".{path.name}.tmp"
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    os.chmod(path, 0o600)
    return digest_bytes(data)


def require_exact_keys(value: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
    actual = set(value)
    expected = set(keys)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise EvidenceError(
            f"{label} must declare exactly its known fields; "
            f"missing={missing} unknown={unknown}"
        )


def require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or DIGEST_RE.fullmatch(value) is None:
        raise EvidenceError(f"{label} must be one sha256 digest")
    return value


def require_commit(value: Any, label: str) -> str:
    if not isinstance(value, str) or COMMIT_RE.fullmatch(value) is None:
        raise EvidenceError(f"{label} must be one full commit id")
    return value


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError(f"{label} must be a non-empty string")
    return value


def self_digest(value: dict[str, Any]) -> str:
    return canonical_digest({key: value[key] for key in value if key != "record_digest"})


# ---------------------------------------------------------------------------
# committed plan manifest
# ---------------------------------------------------------------------------


def plan_manifest(text: str) -> dict[str, Any]:
    """Parse the bounded manifest grammar the plan documents already use."""

    manifest: dict[str, Any] = {}
    key: str | None = None
    for raw in text.splitlines():
        if raw.startswith("## "):
            break
        if raw.startswith("  - ") and key is not None:
            manifest.setdefault(key, [])
            if isinstance(manifest[key], list):
                manifest[key].append(raw[4:])
            continue
        match = re.fullmatch(r"([a-z0-9_]+):(?: (.*))?", raw)
        if match is None:
            key = None
            continue
        key = match.group(1)
        value = match.group(2)
        if value is None:
            manifest[key] = []
        else:
            manifest[key] = value
            key = None
    return manifest


def committed_plan_bytes(repository: Path, revision: str, plan_path: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(repository), "show", f"{revision}:{plan_path}"),
        capture_output=True,
        check=False,
        env=git_environment(),
    )
    if completed.returncode != 0:
        raise EvidenceError(f"plan {plan_path} is not committed at {revision}")
    return completed.stdout


def plan_contract(repository: Path, plan_path: str) -> dict[str, Any] | None:
    """Return the live-evidence contract this plan declares, or None."""

    absolute = repository / plan_path
    if not absolute.is_file():
        raise EvidenceError(f"plan file is missing: {plan_path}")
    text = absolute.read_text(encoding="utf-8")
    manifest = plan_manifest(text)
    contract = manifest.get(CONTRACT_FIELD)
    acceptance_digest = manifest.get(ACCEPTANCE_FIELD)
    if contract is None and acceptance_digest is None:
        return None
    if not isinstance(contract, str) or contract not in LIVE_EVIDENCE_CONTRACTS:
        raise EvidenceError(
            f"{CONTRACT_FIELD} must name one known live-evidence contract"
        )
    if not isinstance(acceptance_digest, str):
        raise EvidenceError(f"{CONTRACT_FIELD} requires {ACCEPTANCE_FIELD}")
    require_digest(acceptance_digest, ACCEPTANCE_FIELD)
    acceptance = manifest.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        raise EvidenceError("a live-evidence plan must declare acceptance items")
    matches = [item for item in acceptance if digest_text(item) == acceptance_digest]
    if len(matches) != 1:
        raise EvidenceError(
            f"{ACCEPTANCE_FIELD} must name exactly one acceptance item of this plan"
        )
    return {
        "contract": contract,
        "live_acceptance_digest": acceptance_digest,
        "acceptance_item": matches[0],
        "plan_digest": digest_bytes(absolute.read_bytes()),
        "status": manifest.get("status"),
    }


# ---------------------------------------------------------------------------
# requirement record
# ---------------------------------------------------------------------------


def requirement_path(repository: Path, plan_path: str) -> Path:
    key = hashlib.sha256(
        json.dumps(
            {
                "repository_identity": repository_identity(repository),
                "plan_path": plan_path,
                "record_type": REQUIREMENT_RECORD_TYPE,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return required_evidence_directory() / f"{key}.json"


def load_requirement(repository: Path, plan_path: str) -> dict[str, Any]:
    path = requirement_path(repository, plan_path)
    record, _ = read_private_json(path, "required-evidence record", MAX_RECORD_BYTES)
    require_exact_keys(record, REQUIREMENT_KEYS, "required-evidence record")
    if record["schema_version"] != REQUIREMENT_SCHEMA_VERSION:
        raise EvidenceError("required-evidence record must declare schema_version 1")
    if record["record_type"] != REQUIREMENT_RECORD_TYPE:
        raise EvidenceError("required-evidence record names another record type")
    if self_digest(record) != record["record_digest"]:
        raise EvidenceError("required-evidence record digest verification failed")
    if record["repository_identity"] != repository_identity(repository):
        raise EvidenceError("required-evidence record names another repository")
    if record["plan_path"] != plan_path:
        raise EvidenceError("required-evidence record names another plan")
    if record["state"] not in {"reserved", "bound"}:
        raise EvidenceError("required-evidence record carries an unknown state")
    return record


def ledger_identity(state_path: Path, repository: Path) -> dict[str, str]:
    require_outside_repository(state_path, "execution ledger", repository)
    ledger, _ = read_private_json(state_path, "execution ledger", 1_048_576)
    for field in ("run_id", "plan_path", "plan_digest", "genesis_digest"):
        if field not in ledger:
            raise EvidenceError(f"execution ledger is missing {field}")
    return {
        "run_id": require_text(ledger["run_id"], "ledger run_id"),
        "plan_path": require_text(ledger["plan_path"], "ledger plan_path"),
        "plan_digest": require_digest(ledger["plan_digest"], "ledger plan_digest"),
        "genesis_digest": require_digest(
            ledger["genesis_digest"], "ledger genesis_digest"
        ),
    }


def command_init(args: argparse.Namespace) -> None:
    repository = repository_root()
    plan_path = args.plan
    contract = plan_contract(repository, plan_path)
    if contract is None:
        raise EvidenceError("this plan declares no live-evidence contract")
    if GROUP_ID_RE.fullmatch(args.group_id) is None:
        raise EvidenceError("reserved group id must be a bounded lowercase identifier")
    ledger = ledger_identity(Path(args.execution_state), repository)
    if ledger["plan_path"] != plan_path:
        raise EvidenceError("the execution ledger was created for another plan")
    path = requirement_path(repository, plan_path)
    if path.exists() or path.is_symlink():
        raise EvidenceError(
            "a required-evidence record already exists for this plan; "
            "a replaced record is refused instead of overwritten"
        )
    record = {
        "schema_version": REQUIREMENT_SCHEMA_VERSION,
        "record_type": REQUIREMENT_RECORD_TYPE,
        "repository_identity": repository_identity(repository),
        "plan_path": plan_path,
        "plan_digest": contract["plan_digest"],
        "execution_plan_digest": ledger["plan_digest"],
        "live_evidence_contract": contract["contract"],
        "live_acceptance_digest": contract["live_acceptance_digest"],
        "execution_genesis_digest": ledger["genesis_digest"],
        "run_id": ledger["run_id"],
        "reserved_group_id": args.group_id,
        "state": "reserved",
        "group_description_digest": "",
        "report_path": "",
        "report_digest": "",
        "record_digest": "",
    }
    record["record_digest"] = self_digest(record)
    write_private_json(path, record)
    emit(
        {
            "operation": "init",
            "record_path": str(path),
            "record_digest": record["record_digest"],
            "plan_path": plan_path,
            "live_acceptance_digest": record["live_acceptance_digest"],
            "execution_genesis_digest": record["execution_genesis_digest"],
            "reserved_group_id": args.group_id,
            "state": "reserved",
        }
    )


def command_bind(args: argparse.Namespace) -> None:
    repository = repository_root()
    record = load_requirement(repository, args.plan)
    if record["state"] != "reserved":
        raise EvidenceError(
            "this required-evidence record already names a verified report"
        )
    report_path = Path(args.report).absolute()
    summary = verify_report(repository, record, report_path)
    updated = dict(record)
    updated["state"] = "bound"
    updated["group_description_digest"] = summary["group_description_digest"]
    updated["report_path"] = str(report_path)
    updated["report_digest"] = summary["report_digest"]
    updated["record_digest"] = ""
    updated["record_digest"] = self_digest(updated)
    write_private_json(requirement_path(repository, args.plan), updated)
    emit(
        {
            "operation": "bind",
            "plan_path": args.plan,
            "record_digest": updated["record_digest"],
            "report_digest": updated["report_digest"],
            "group_description_digest": updated["group_description_digest"],
            "state": "bound",
        }
    )


def command_show(args: argparse.Namespace) -> None:
    repository = repository_root()
    record = load_requirement(repository, args.plan)
    emit(
        {
            "operation": "show",
            "record_path": str(requirement_path(repository, args.plan)),
            "plan_path": record["plan_path"],
            "state": record["state"],
            "reserved_group_id": record["reserved_group_id"],
            "report_digest": record["report_digest"],
        }
    )


def command_require(args: argparse.Namespace) -> None:
    repository = repository_root()
    contract = plan_contract(repository, args.plan)
    if contract is None:
        emit({"operation": "require", "plan_path": args.plan, "obligation": "none"})
        return
    record = load_requirement(repository, args.plan)
    if record["live_evidence_contract"] != contract["contract"]:
        raise EvidenceError(
            "the plan now declares a different live-evidence contract than its record"
        )
    if record["live_acceptance_digest"] != contract["live_acceptance_digest"]:
        raise EvidenceError(
            "the plan acceptance item bound by the required-evidence record changed"
        )
    if record["state"] != "bound":
        raise EvidenceError(
            "this plan requires verified two-session live evidence; "
            "its required-evidence record still reserves the demonstration"
        )
    report_path = Path(record["report_path"])
    summary = verify_report(repository, record, report_path)
    if summary["report_digest"] != record["report_digest"]:
        raise EvidenceError("the bound live report bytes changed after binding")
    emit(
        {
            "operation": "require",
            "plan_path": args.plan,
            "obligation": record["live_evidence_contract"],
            "report_digest": summary["report_digest"],
            "satisfied": True,
        }
    )


def command_verify(args: argparse.Namespace) -> None:
    repository = repository_root()
    located = args.report or os.environ.get(REPORT_ENVIRONMENT_VARIABLE)
    if not located:
        raise EvidenceError(
            "no live report was located; pass --report or set "
            f"{REPORT_ENVIRONMENT_VARIABLE}"
        )
    record = None
    if args.plan:
        record = load_requirement(repository, args.plan)
    summary = verify_report(repository, record, Path(located).absolute())
    summary["operation"] = "verify"
    emit(summary)


# ---------------------------------------------------------------------------
# live report verification
# ---------------------------------------------------------------------------


def parse_timestamp(value: Any, label: str) -> datetime:
    text = require_text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceError(f"{label} must be one ISO-8601 instant") from error
    if parsed.tzinfo is None:
        raise EvidenceError(f"{label} must carry an explicit time zone")
    return parsed


def demonstration_repository(path_text: str, template_root: Path) -> Path:
    candidate = Path(path_text)
    if not candidate.is_absolute():
        raise EvidenceError("demonstration_repository must be an absolute path")
    if has_symlink_component(candidate):
        raise EvidenceError("demonstration_repository contains a symlink component")
    if not candidate.is_dir():
        raise EvidenceError(f"demonstration repository is missing: {candidate}")
    resolved = Path(os.path.realpath(candidate))
    if resolved == Path(os.path.realpath(template_root)):
        raise EvidenceError(
            "the demonstration must run in an isolated generated project, "
            "not in this repository"
        )
    if not git_succeeds(resolved, "rev-parse", "--git-dir"):
        raise EvidenceError("demonstration repository is not a Git repository")
    return resolved


def installed_revision(project: Path) -> str:
    answers = project / ".copier-answers.yml"
    if not answers.is_file():
        raise EvidenceError(
            "the demonstration project carries no .copier-answers.yml, so no "
            "installed revision can be derived"
        )
    for line in answers.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"_commit: (.+)", line.strip())
        if match is not None:
            return match.group(1).strip().strip("'\"")
    raise EvidenceError(".copier-answers.yml declares no _commit revision")


def verify_member_shape(member: Any, index: int) -> dict[str, Any]:
    if not isinstance(member, dict):
        raise EvidenceError("each live report member must be a JSON object")
    require_exact_keys(member, MEMBER_KEYS, f"live report member {index}")
    if MEMBER_PLAN_RE.fullmatch(str(member["plan_path"])) is None:
        raise EvidenceError("each member must name one numbered plan document")
    require_text(member["logical_member_id"], "logical_member_id")
    require_digest(member["session_digest"], "member session_digest")
    require_text(member["worktree_path"], "member worktree_path")
    if BRANCH_REF_RE.fullmatch(str(member["branch_ref"])) is None:
        raise EvidenceError("each member must name one full local branch ref")
    require_commit(member["base_commit"], "member base_commit")
    require_commit(member["task_tip"], "member task_tip")
    require_commit(member["published_commit"], "member published_commit")
    require_digest(member["patch_digest"], "member patch_digest")
    changed = member["changed_paths"]
    if not isinstance(changed, list) or not changed:
        raise EvidenceError("each member must record the paths it changed")
    for path_text in changed:
        value = PurePosixPath(str(path_text))
        if value.is_absolute() or any(part in {"", ".", ".."} for part in value.parts):
            raise EvidenceError("member changed paths must be normalized relative paths")
    receipts = member["review_receipt_digests"]
    if not isinstance(receipts, list) or not receipts:
        raise EvidenceError("each member must record at least one review receipt")
    for receipt in receipts:
        require_digest(receipt, "member review receipt digest")
    return member


def verify_publication_order(
    project: Path, report: dict[str, Any], members: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    order = report["publication_order"]
    if not isinstance(order, list) or len(order) != MEMBER_COUNT:
        raise EvidenceError("publication_order must list exactly both member plans")
    by_plan = {member["plan_path"]: member for member in members}
    if sorted(order) != sorted(by_plan):
        raise EvidenceError("publication_order must name exactly the reported members")
    ordered = [by_plan[plan] for plan in order]
    first, second = ordered
    if first["published_commit"] == second["published_commit"]:
        raise EvidenceError("both members claim the same published commit")
    if not git_succeeds(
        project,
        "merge-base",
        "--is-ancestor",
        first["published_commit"],
        second["published_commit"],
    ):
        raise EvidenceError(
            "the first published member must be an ancestor of the second; "
            "publication was not serialized"
        )
    return ordered


def verify_retirement(project: Path, member: dict[str, Any], final_tip: str) -> None:
    if git_succeeds(project, "show-ref", "--verify", "--quiet", member["branch_ref"]):
        raise EvidenceError(
            f"member branch {member['branch_ref']} still exists; the task was not retired"
        )
    registered = git_text(project, "worktree", "list", "--porcelain")
    for line in registered.splitlines():
        if line.startswith("worktree ") and line[len("worktree ") :] == member["worktree_path"]:
            raise EvidenceError(
                f"member worktree {member['worktree_path']} is still registered"
            )
    if Path(member["worktree_path"]).exists():
        raise EvidenceError(
            f"member worktree {member['worktree_path']} still exists on disk"
        )
    if not git_succeeds(
        project, "merge-base", "--is-ancestor", member["task_tip"], final_tip
    ):
        raise EvidenceError(
            "a retired member task tip must be contained in the published history; "
            "unaccounted member work was discarded"
        )


def verify_changes_retained(
    project: Path, member: dict[str, Any], final_tip: str
) -> None:
    changed = set(
        git_text(
            project,
            "diff",
            "--name-only",
            f"{member['base_commit']}..{final_tip}",
        ).splitlines()
    )
    missing = [path for path in member["changed_paths"] if path not in changed]
    if missing:
        raise EvidenceError(
            "the published history no longer carries every member change: "
            f"{sorted(missing)}"
        )


def verify_transcripts(
    report: dict[str, Any], members: list[dict[str, Any]], project: Path
) -> list[dict[str, Any]]:
    missing = report["missing_sources"]
    if not isinstance(missing, list):
        raise EvidenceError("missing_sources must be a list")
    if missing:
        raise EvidenceError(
            "primary transcript evidence is unavailable for "
            f"{sorted(str(item) for item in missing)}; this plan stays incomplete"
        )
    sources = report["transcript_sources"]
    if not isinstance(sources, list) or len(sources) != MEMBER_COUNT:
        raise EvidenceError("transcript_sources must describe exactly both sessions")
    expected = {member["session_digest"] for member in members}
    seen: set[str] = set()
    verified: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise EvidenceError("each transcript source must be a JSON object")
        require_exact_keys(source, TRANSCRIPT_KEYS, f"transcript source {index}")
        session = require_digest(source["session_digest"], "transcript session_digest")
        if session in seen:
            raise EvidenceError("two transcript sources name one session")
        seen.add(session)
        path = Path(require_text(source["transcript_path"], "transcript_path"))
        if not path.is_absolute():
            raise EvidenceError("transcript_path must be absolute")
        require_outside_repository(path, "session transcript", project)
        data = read_private_bytes(path, "session transcript", MAX_TRANSCRIPT_BYTES)
        if digest_bytes(data) != require_digest(
            source["transcript_digest"], "transcript_digest"
        ):
            raise EvidenceError(
                "a session transcript no longer matches its recorded digest; "
                "altered or replayed evidence is refused"
            )
        member = next(
            item for item in members if item["session_digest"] == session
        ) if session in expected else None
        if member is None:
            raise EvidenceError("a transcript source names no reported member session")
        counted = count_tool_records(data, member)
        if counted != source["tool_record_count"]:
            raise EvidenceError(
                "the recorded tool-record count disagrees with the transcript bytes"
            )
        if counted < MINIMUM_INTERVAL_TOOL_RECORDS:
            raise EvidenceError(
                "a session transcript proves no implementation tool event inside "
                "its reported interval; terminal lifetime is not implementation"
            )
        verified.append({"session_digest": session, "tool_record_count": counted})
    if seen != expected:
        raise EvidenceError("transcript sources do not cover both member sessions")
    return verified


def count_tool_records(data: bytes, member: dict[str, Any]) -> int:
    start = parse_timestamp(
        member["implementation_started_at"], "implementation_started_at"
    )
    end = parse_timestamp(member["implementation_ended_at"], "implementation_ended_at")
    counted = 0
    for line in data.decode("utf-8", errors="strict").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise EvidenceError(f"session transcript holds invalid JSON: {error}") from error
        if not isinstance(record, dict):
            continue
        if record.get("role") != "tool":
            continue
        if record.get("session_digest") != member["session_digest"]:
            continue
        created = record.get("created_at")
        if created is None:
            continue
        moment = parse_timestamp(created, "transcript created_at")
        if start <= moment <= end:
            counted += 1
    return counted


def verify_overlap(members: list[dict[str, Any]]) -> dict[str, str]:
    intervals = []
    for member in members:
        start = parse_timestamp(
            member["implementation_started_at"], "implementation_started_at"
        )
        end = parse_timestamp(
            member["implementation_ended_at"], "implementation_ended_at"
        )
        if end <= start:
            raise EvidenceError("an implementation interval must advance in time")
        intervals.append((start, end))
    latest_start = max(start for start, _ in intervals)
    earliest_end = min(end for _, end in intervals)
    if latest_start >= earliest_end:
        raise EvidenceError(
            "the reported implementation intervals do not overlap; separate "
            "sessions alone do not prove concurrent implementation"
        )
    return {
        "overlap_started_at": latest_start.isoformat(),
        "overlap_ended_at": earliest_end.isoformat(),
    }


def verify_report(
    repository: Path, record: dict[str, Any] | None, report_path: Path
) -> dict[str, Any]:
    require_outside_repository(report_path, "live report", repository)
    report, report_digest = read_private_json(
        report_path, "live report", MAX_REPORT_BYTES
    )
    require_exact_keys(report, REPORT_KEYS, "live report")
    if report["schema_version"] != REPORT_SCHEMA_VERSION:
        raise EvidenceError("live report must declare schema_version 1")
    if report["record_type"] != REPORT_RECORD_TYPE:
        raise EvidenceError("live report names another record type")
    if self_digest(report) != report["record_digest"]:
        raise EvidenceError("live report digest verification failed")

    plan_path = require_text(report["plan_path"], "live report plan_path")
    if PLAN_PATH_RE.fullmatch(plan_path) is None:
        raise EvidenceError("live report must name one numbered plan document")
    require_digest(report["plan_digest"], "live report plan_digest")
    require_digest(report["live_acceptance_digest"], "live_acceptance_digest")
    require_digest(report["execution_genesis_digest"], "execution_genesis_digest")

    if record is not None:
        if report["plan_path"] != record["plan_path"]:
            raise EvidenceError("live report names another plan than its record")
        if report["live_acceptance_digest"] != record["live_acceptance_digest"]:
            raise EvidenceError("live report names another live acceptance item")
        if report["execution_genesis_digest"] != record["execution_genesis_digest"]:
            raise EvidenceError("live report names another execution genesis")
        if report["group_id"] != record["reserved_group_id"]:
            raise EvidenceError(
                "live report names a group that was not reserved before implementation"
            )

    revision = require_commit(report["template_revision"], "template_revision")
    if not git_succeeds(repository, "cat-file", "-e", f"{revision}^{{commit}}"):
        raise EvidenceError("template_revision names no commit of this repository")
    head = git_text(repository, "rev-parse", "HEAD")
    if not git_succeeds(repository, "merge-base", "--is-ancestor", revision, head):
        raise EvidenceError(
            "the demonstrated revision is not contained in the current history; "
            "the evidence describes a stale installation"
        )

    project = demonstration_repository(
        require_text(report["demonstration_repository"], "demonstration_repository"),
        repository,
    )
    if installed_revision(project) != revision:
        raise EvidenceError(
            "the demonstration project installs another template revision than "
            "the live report claims"
        )

    if GROUP_ID_RE.fullmatch(str(report["group_id"])) is None:
        raise EvidenceError("group_id must be a bounded lowercase identifier")
    target_ref = require_text(report["demonstration_target_ref"], "demonstration_target_ref")
    if BRANCH_REF_RE.fullmatch(target_ref) is None:
        raise EvidenceError("demonstration_target_ref must be one full local branch ref")
    final_tip = git_text(project, "rev-parse", target_ref)

    members = report["members"]
    if not isinstance(members, list) or len(members) != MEMBER_COUNT:
        raise EvidenceError("a live report describes exactly two member sessions")
    shaped = [verify_member_shape(member, index) for index, member in enumerate(members)]
    for field in (
        "plan_path",
        "logical_member_id",
        "session_digest",
        "worktree_path",
        "branch_ref",
        "task_tip",
    ):
        values = [member[field] for member in shaped]
        if len(set(values)) != MEMBER_COUNT:
            raise EvidenceError(f"both members share one {field}; sessions are not distinct")

    description_path = require_text(
        report["group_description_path"], "group_description_path"
    )
    description = committed_plan_bytes(project, final_tip, description_path)
    if digest_bytes(description) != require_digest(
        report["group_description_digest"], "group_description_digest"
    ):
        raise EvidenceError("the committed group description digest does not match")

    ordered = verify_publication_order(project, report, shaped)
    for member in shaped:
        if not git_succeeds(
            project, "cat-file", "-e", f"{member['published_commit']}^{{commit}}"
        ):
            raise EvidenceError("a member published commit is absent from the project")
        if not git_succeeds(
            project,
            "merge-base",
            "--is-ancestor",
            member["published_commit"],
            final_tip,
        ):
            raise EvidenceError(
                "a member published commit is not contained in the target ref"
            )
        verify_changes_retained(project, member, final_tip)
        verify_retirement(project, member, final_tip)

    validation = report["validation_evidence"]
    if not isinstance(validation, list) or not validation:
        raise EvidenceError("a live report records the integration validation evidence")
    for entry in validation:
        require_digest(entry, "validation evidence digest")
    hooks = report["hook_sources"]
    if not isinstance(hooks, list):
        raise EvidenceError("hook_sources must be a list of corroborating sources")

    transcripts = verify_transcripts(report, shaped, project)
    overlap = verify_overlap(shaped)

    return {
        "report_path": str(report_path),
        "report_digest": report_digest,
        "plan_path": plan_path,
        "group_id": report["group_id"],
        "group_description_digest": report["group_description_digest"],
        "template_revision": revision,
        "demonstration_repository": str(project),
        "publication_order": [member["plan_path"] for member in ordered],
        "transcripts": transcripts,
        **overlap,
        "verified": True,
    }


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)

    init = sub.add_parser(
        "init", help="reserve the required-evidence record before implementation"
    )
    init.add_argument("--plan", required=True)
    init.add_argument("--execution-state", required=True)
    init.add_argument("--group-id", required=True)
    init.set_defaults(handler=command_init)

    bind = sub.add_parser("bind", help="bind one verified live report to the record")
    bind.add_argument("--plan", required=True)
    bind.add_argument("--report", required=True)
    bind.set_defaults(handler=command_bind)

    verify = sub.add_parser("verify", help="verify one live report without writing")
    verify.add_argument("--plan")
    verify.add_argument("--report")
    verify.set_defaults(handler=command_verify)

    require = sub.add_parser(
        "require", help="refuse completion until this plan holds verified live evidence"
    )
    require.add_argument("--plan", required=True)
    require.set_defaults(handler=command_require)

    show = sub.add_parser("show", help="print the bounded record state")
    show.add_argument("--plan", required=True)
    show.set_defaults(handler=command_show)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        args.handler(args)
    except EvidenceError as error:
        print(f"parallel live evidence refused: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"parallel live evidence refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
