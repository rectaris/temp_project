#!/usr/bin/env python3
"""Verify a private live parallel-session report against a plan's required evidence."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import pwd
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

REPORT_ENV = "PROJECT_AGENT_WORKFLOW_PARALLEL_LIVE_REPORT"
REQUIRED_EVIDENCE_ENV = "PROJECT_AGENT_WORKFLOW_REQUIRED_EVIDENCE"
REQUIREMENT_SCHEMA_VERSION = 1
REQUIREMENT_RECORD_TYPE = "parallel_live_evidence_requirement"
TRANSFER_SCHEMA_VERSION = 1
TRANSFER_RECORD_TYPE = "parallel_live_evidence_transfer"
AUTHORIZATION_RECORD_TYPE = "parallel_live_evidence_transfer_authorization"

# The contract is a committed plan manifest field. Prose, an environment flag
# or the presence of a record never creates or removes the obligation.
LIVE_EVIDENCE_CONTRACTS = frozenset({"parallel_sessions_v1"})
CONTRACT_FIELD = "live_evidence_contract"
ACCEPTANCE_FIELD = "live_evidence_acceptance_sha256"

# Both record families live under the account home, outside every repository
# worktree, so no repository checkout, branch or update can carry, rewrite or
# delete the evidence that a lifecycle gate consults.
STATE_RELATIVE_DIRECTORY = ".local/state/project-agent-workflow/required-evidence"
TRANSFER_RELATIVE_DIRECTORY = (
    ".local/state/project-agent-workflow/required-evidence-transfers"
)

MAX_RECORD_BYTES = 65_536
MAX_REPORT_BYTES = 1_048_576
MAX_LEDGER_BYTES = 4_194_304
MAX_TRANSFER_RECORDS = 4096

DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
GROUP_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
PLAN_PATH_RE = re.compile(r"docs/plan/[A-Za-z0-9._/-]*[0-9]{3}-[a-z0-9-]+\.md\Z")
PLAN_LIFECYCLE_DIRECTORIES = (
    "docs/plan/active",
    "docs/plan/backlog",
    "docs/plan/shelved",
    "docs/plan/archive",
)
PLACEHOLDER_RE = re.compile(r"\b(tbd|todo|placeholder|n/?a|pending|xxx)\b", re.IGNORECASE)

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

TRANSFER_KEYS = (
    "schema_version",
    "record_type",
    "repository_identity",
    "source_plan_path",
    "source_plan_digest",
    "destination_plan_path",
    "destination_plan_digest",
    "live_evidence_contract",
    "live_acceptance_digest",
    "source_record_digest",
    "execution_genesis_digest",
    "run_id",
    "source_head",
    "source_acceptance_digests",
    "retained_acceptance_digests",
    "deferred_acceptance_digests",
    "descope_event_digest",
    "descope_evidence_digest",
    "reservation_event_digest",
    "owner_authorization_digest",
    "state",
    "record_digest",
)

AUTHORIZATION_KEYS = (
    "schema_version",
    "record_type",
    "repository_identity",
    "source_plan_path",
    "source_plan_digest",
    "destination_plan_path",
    "destination_plan_digest",
    "live_acceptance_digest",
    "source_record_digest",
    "execution_genesis_digest",
    "run_id",
    "authorization",
    "record_digest",
)


class EvidenceError(ValueError):
    """Raised when report evidence is missing, stale, or mismatched.

    Every refusal preserves the inspected bytes. No refusal path creates,
    rewrites or removes a required-evidence or transfer record.
    """


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def digest_text(value: str) -> str:
    return digest_bytes(value.encode("utf-8"))


def canonical_digest(value: Any) -> str:
    return digest_text(json.dumps(value, sort_keys=True, separators=(",", ":")))


def file_digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def git_bytes(repo: Path, *args: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    return proc.stdout


def self_digest(value: dict[str, Any]) -> str:
    """Digest every field of a record except the field that carries it."""

    return canonical_digest({key: value[key] for key in value if key != "record_digest"})


def account_home() -> Path:
    """Return the account home, never a caller-controlled HOME.

    The record location must not follow an environment variable, so a changed
    HOME cannot point a lifecycle gate at an empty directory and turn a live
    obligation into an absent one.
    """

    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def required_evidence_directory() -> Path:
    return account_home() / STATE_RELATIVE_DIRECTORY


def transfer_directory() -> Path:
    return account_home() / TRANSFER_RELATIVE_DIRECTORY


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def canonical_origin(repo: Path) -> str:
    proc = subprocess.run([
        "git", "-C", str(repo), "config", "--get", "remote.origin.url"
    ], capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise EvidenceError(
            "repository has no canonical remote.origin.url; a live-evidence record cannot be keyed here"
        )
    return proc.stdout.strip()


def repository_identity(repo: Path) -> str:
    return digest_text(canonical_origin(repo))


def repository_root(start: Path | None = None) -> Path:
    base = start or Path.cwd()
    proc = subprocess.run([
        "git", "-C", str(base), "rev-parse", "--show-toplevel"
    ], capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise EvidenceError(f"not inside a Git repository: {base}")
    return Path(proc.stdout.strip()).resolve()


def relative_plan_path(repo: Path, plan: str | Path) -> str:
    path = Path(plan)
    if path.is_absolute():
        resolved = Path(os.path.realpath(path))
        anchor = Path(os.path.realpath(repo))
        try:
            return resolved.relative_to(anchor).as_posix()
        except ValueError as exc:
            raise EvidenceError(f"plan path lies outside the repository: {plan}") from exc
    return PurePosixPath(path.as_posix()).as_posix()


def record_key(fields: dict[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def requirement_path(repo: Path, plan: str | Path) -> Path:
    """Return the one canonical private record identity for this plan.

    The identity is the repository origin, the plan path and the record type.
    It never depends on the checkout location, so a linked worktree, a second
    clone and a task branch all resolve the same obligation.
    """

    key = record_key(
        {
            "repository_identity": repository_identity(repo),
            "plan_path": relative_plan_path(repo, plan),
            "record_type": REQUIREMENT_RECORD_TYPE,
        }
    )
    return required_evidence_directory() / f"{key}.json"


def transfer_path(repo: Path, source_plan: str | Path) -> Path:
    key = record_key(
        {
            "repository_identity": repository_identity(repo),
            "source_plan_path": relative_plan_path(repo, source_plan),
            "record_type": TRANSFER_RECORD_TYPE,
        }
    )
    return transfer_directory() / f"{key}.json"


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
    """Read a bounded private file without following any symlink."""

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


def write_private_json(path: Path, payload: dict[str, Any]) -> str:
    directory = path.parent
    if has_symlink_component(directory):
        raise EvidenceError("private record directory contains a symlink component")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    data = (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    if len(data) > MAX_RECORD_BYTES:
        raise EvidenceError("private record exceeds its bounded size")
    temporary = directory / f".{path.name}.tmp"
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
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


def require_digest_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise EvidenceError(f"{label} must be a non-empty list of sha256 digests")
    return [require_digest(item, f"{label} entry") for item in value]


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


def committed_plan_bytes(repo: Path, revision: str, plan_path: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(repo), "show", f"{revision}:{plan_path}"),
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise EvidenceError(f"plan {plan_path} is not committed at {revision}")
    return completed.stdout


def acceptance_digests(text: str, label: str) -> list[str]:
    manifest = plan_manifest(text)
    acceptance = manifest.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        raise EvidenceError(f"{label} declares no acceptance items")
    return [digest_text(item) for item in acceptance]


def plan_contract(repo: Path, plan: str | Path) -> dict[str, Any] | None:
    """Return the live-evidence contract this plan declares, or None.

    The obligation comes from the committed manifest fields and the exact
    acceptance item they name, never from prose or from the presence of a
    record.
    """

    relative = relative_plan_path(repo, plan)
    absolute = repo / relative
    if not absolute.is_file():
        raise EvidenceError(f"plan file is missing: {relative}")
    text = absolute.read_text(encoding="utf-8")
    manifest = plan_manifest(text)
    contract = manifest.get(CONTRACT_FIELD)
    acceptance_digest = manifest.get(ACCEPTANCE_FIELD)
    if contract is None and acceptance_digest is None:
        return None
    if not isinstance(contract, str) or contract not in LIVE_EVIDENCE_CONTRACTS:
        raise EvidenceError(f"{CONTRACT_FIELD} must name one known live-evidence contract")
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
        "plan_path": relative,
        "plan_digest": digest_bytes(absolute.read_bytes()),
        "contract": contract,
        "live_acceptance_digest": acceptance_digest,
        "acceptance_item": matches[0],
        "status": manifest.get("status"),
    }


def load_requirement(repo: Path, plan: str | Path) -> dict[str, Any]:
    """Read and fully verify the canonical private record for this plan."""

    relative = relative_plan_path(repo, plan)
    path = requirement_path(repo, relative)
    record, _ = read_private_json(path, "required-evidence record", MAX_RECORD_BYTES)
    require_exact_keys(record, REQUIREMENT_KEYS, "required-evidence record")
    if record["schema_version"] != REQUIREMENT_SCHEMA_VERSION:
        raise EvidenceError("required-evidence record must declare schema_version 1")
    if record["record_type"] != REQUIREMENT_RECORD_TYPE:
        raise EvidenceError("required-evidence record names another record type")
    if self_digest(record) != record["record_digest"]:
        raise EvidenceError("required-evidence record digest verification failed")
    if record["repository_identity"] != repository_identity(repo):
        raise EvidenceError("required-evidence record names another repository")
    if record["plan_path"] != relative:
        raise EvidenceError("required-evidence record names another plan")
    if record["state"] not in {"reserved", "bound"}:
        raise EvidenceError("required-evidence record carries an unknown state")
    return record


def ledger_identity(state_path: Path, repo: Path) -> dict[str, Any]:
    """Read one execution ledger through its authoritative reader.

    The ledger is the authority for the run identity, the stopped state and the
    recorded descope classification. This never edits the ledger.
    """

    require_outside_repository(state_path, "execution ledger", repo)
    ledger, ledger_digest = read_private_json(
        state_path, "execution ledger", MAX_LEDGER_BYTES
    )
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
        "state": ledger.get("state"),
        "events": ledger.get("events"),
        "source_head": ledger.get("source_head"),
        "open_attempt_id": ledger.get("open_attempt_id"),
        "ledger_digest": ledger_digest,
    }


def coerce_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def resolve_required_evidence(path: str | None) -> Path | None:
    """Resolve the record the non-gating `verify` command should read.

    Only `verify` consults this. The `require` gate resolves the canonical
    private identity instead, so no environment variable can point a lifecycle
    gate at a chosen record.
    """

    if path is not None:
        return Path(path)
    if REQUIRED_EVIDENCE_ENV in os.environ:
        return Path(os.environ[REQUIRED_EVIDENCE_ENV])
    return None


def resolve_report(path: str | None) -> Path:
    if path is not None:
        return Path(path)
    if REPORT_ENV in os.environ:
        return Path(os.environ[REPORT_ENV])
    raise ValueError(
        f"missing live report path: set {REPORT_ENV} to the report JSON file or pass --report"
    )


def require_record(
    required_record: dict[str, Any],
    repo: Path,
    plan_path: Path,
    report_path: Path,
) -> None:
    plan_digest = digest_bytes(plan_path.read_bytes())
    contract = plan_contract(repo, plan_path) or {}
    live_acceptance_digest = contract.get("live_acceptance_digest")
    if required_record.get("plan_digest") not in (None, plan_digest):
        raise ValueError(
            f"required-evidence plan digest mismatch: expected {required_record.get('plan_digest')}, found {plan_digest}"
        )
    if required_record.get("live_acceptance_digest") not in (None, live_acceptance_digest):
        raise ValueError(
            "required-evidence live acceptance digest mismatch: "
            f"expected {required_record.get('live_acceptance_digest')}, found {live_acceptance_digest}"
        )
    if required_record.get("report_digest"):
        report_digest = file_digest(report_path)
        if required_record["report_digest"] != report_digest:
            raise ValueError(
                f"required-evidence report digest mismatch: expected {required_record['report_digest']}, found {report_digest}"
            )
    if "execution_genesis_digest" not in required_record and "execution_genesis" not in required_record:
        raise ValueError("required-evidence record must declare execution_genesis")


def validate_report(report: dict[str, Any], plan_path: Path) -> None:
    text = plan_path.read_text(encoding="utf-8")
    live_acceptance = re.search(r"^live_evidence_acceptance_sha256:\s*(sha256:[0-9a-fA-F]{64})", text, flags=re.MULTILINE)
    if live_acceptance is None:
        live_acceptance = re.search(r"^live_acceptance_digest:\s*(sha256:[0-9a-fA-F]{64})", text, flags=re.MULTILINE)
    if live_acceptance is None:
        raise ValueError(f"plan does not declare a live acceptance digest: {plan_path}")
    expected = live_acceptance.group(1)
    if report.get("live_acceptance_digest") not in (None, expected):
        raise ValueError(f"report live acceptance digest mismatch: expected {expected}, found {report.get('live_acceptance_digest')}")
    if report.get("acceptance_digest") not in (None, expected):
        raise ValueError(f"report acceptance digest mismatch: expected {expected}, found {report.get('acceptance_digest')}")
    if report.get("acceptance_sha256") not in (None, expected):
        raise ValueError(f"report acceptance_sha256 mismatch: expected {expected}, found {report.get('acceptance_sha256')}")
    session_ids = coerce_strings(report.get("distinct_session_ids") or report.get("session_ids"))
    if len(set(session_ids)) < 2:
        session_count = report.get("session_count")
        if session_count is None or int(session_count) < 2:
            raise ValueError("report must contain evidence for at least two distinct sessions")
    if not report.get("distinct_session_ids") and not report.get("session_ids"):
        raise ValueError("report must identify at least two member sessions")
    intervals = report.get("implementation_intervals") or []
    if isinstance(intervals, list) and intervals:
        parsed: list[tuple[str, str]] = []
        for interval in intervals:
            if isinstance(interval, dict):
                start = interval.get("start")
                end = interval.get("end")
                if isinstance(start, str) and isinstance(end, str):
                    parsed.append((start, end))
        overlaps = False
        for i, (start_a, end_a) in enumerate(parsed):
            for start_b, end_b in parsed[i + 1 :]:
                if start_a < end_b and start_b < end_a:
                    overlaps = True
                    break
            if overlaps:
                break
        if len(parsed) >= 2 and not overlaps:
            raise ValueError("report implementation intervals do not overlap")


def verify_changes_retained(repo: Path, member: dict[str, Any], final_tip: str) -> None:
    base_commit = member.get("base_commit")
    result_tree = member.get("result_tree")
    patch_digest = member.get("patch_digest")
    reported_paths = [str(item) for item in coerce_strings(member.get("changed_paths"))]
    if not isinstance(base_commit, str) or not base_commit:
        raise EvidenceError("member record is missing base_commit")
    if not isinstance(result_tree, str) or not result_tree:
        raise EvidenceError("member result_tree must name one Git tree")
    if not isinstance(patch_digest, str) or not patch_digest:
        raise EvidenceError("member record is missing patch_digest")
    try:
        object_type = git_bytes(repo, "cat-file", "-t", result_tree).strip()
    except subprocess.CalledProcessError as exc:
        raise EvidenceError("member result_tree must name one Git tree") from exc
    if object_type != b"tree":
        raise EvidenceError("member result_tree must name one Git tree")
    patch = git_bytes(
        repo,
        "-c",
        "core.abbrev=40",
        "diff",
        "--binary",
        "--full-index",
        "--no-color",
        "--no-ext-diff",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        base_commit,
        result_tree,
    )
    if digest_bytes(patch) != patch_digest:
        raise EvidenceError("member patch digest does not reproduce the reported patch digest")
    actual_paths = git_bytes(repo, "diff", "--name-only", f"{base_commit}..{result_tree}").decode("utf-8", errors="replace").split()
    if reported_paths != actual_paths:
        raise EvidenceError("member changed_paths are not exactly the paths produced by the result tree")
    if len(reported_paths) != len(set(reported_paths)):
        raise EvidenceError("member changed_paths must not contain duplicates")
    result_identity: dict[str, str] = {}
    for path in reported_paths:
        entry = git_bytes(repo, "ls-tree", "-r", "--full-tree", result_tree, "--", path)
        if not entry:
            raise EvidenceError(f"member result tree is missing a reported path: {path}")
        parts = entry.decode("utf-8", errors="replace").strip().split()
        if len(parts) < 3:
            raise EvidenceError(f"member result tree is missing a reported path: {path}")
        result_identity[path] = f"{parts[0]}:{parts[2]}"
    for path in reported_paths:
        for rev in (member.get("published_commit", final_tip), final_tip):
            entry = b""
            try:
                entry = git_bytes(repo, "ls-tree", "-r", "--full-tree", rev, "--", path)
            except subprocess.CalledProcessError:
                entry = b""
            if not entry:
                raise EvidenceError("accepted member work was overwritten")
            parts = entry.decode("utf-8", errors="replace").strip().split()
            if len(parts) < 3:
                raise EvidenceError("accepted member work was overwritten")
            current = f"{parts[0]}:{parts[2]}"
            if current != result_identity[path]:
                raise EvidenceError("accepted member work was overwritten")


def authoritative_ledger(state_path: Path, repo: Path) -> dict[str, Any]:
    """Read one execution ledger through its own authoritative reader.

    The ledger schema, its event chain and its stopped state are owned by
    `plan-execution-state.py`. This reads through that reader rather than
    reimplementing a second, weaker authority, and never writes to the ledger.
    """

    require_outside_repository(state_path, "execution ledger", repo)
    reader = Path(__file__).resolve().parent / "plan-execution-state.py"
    if not reader.is_file():
        raise EvidenceError(
            "the authoritative execution ledger reader is missing: "
            f"{reader}"
        )
    specification = importlib.util.spec_from_file_location(
        "plan_execution_state_reader", reader
    )
    if specification is None or specification.loader is None:
        raise EvidenceError("the authoritative execution ledger reader cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    try:
        specification.loader.exec_module(module)
        return module.read_state(Path(state_path))
    except Exception as error:  # the reader raises its own bounded refusals
        raise EvidenceError(f"execution ledger refused by its authoritative reader: {error}") from error


def ledger_reservation(ledger: dict[str, Any], record_digest: str) -> str:
    """Bind the ledger's required-evidence reservation to this exact record.

    The reservation carries the record digest as its single invariant digest.
    A ledger that records one must name this record, so a replaced or forged
    record is refused rather than accepted as historical evidence. A ledger
    that records none is bound by its run identity and execution genesis
    instead, which every required-evidence record already carries.
    """

    events = ledger.get("events")
    if not isinstance(events, list):
        raise EvidenceError("execution ledger carries no events")
    matches = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("event_type") == "required_evidence_reserved"
    ]
    if not matches:
        return ""
    if len(matches) != 1:
        raise EvidenceError(
            "execution ledger records more than one required-evidence reservation"
        )
    invariants = matches[0].get("invariant_digests")
    if not isinstance(invariants, list) or invariants != [record_digest]:
        raise EvidenceError(
            "the execution ledger reservation names another required-evidence record; "
            "the original record was replaced rather than preserved"
        )
    return require_digest(matches[0].get("event_digest"), "reservation event_digest")


def ledger_descope(ledger: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    events = ledger.get("events")
    if not isinstance(events, list) or not events:
        raise EvidenceError("execution ledger carries no events")
    matches = [
        event
        for event in events
        if isinstance(event, dict) and event.get("event_type") == "descope_classification"
    ]
    if len(matches) != 1:
        raise EvidenceError(
            "execution ledger must record exactly one descope classification"
        )
    event = matches[0]
    classification = event.get("descope_classification")
    if not isinstance(classification, dict):
        raise EvidenceError("descope classification event carries no classification")
    return (
        classification,
        require_digest(event.get("event_digest"), "descope event_digest"),
        require_digest(event.get("descope_evidence_digest"), "descope evidence digest"),
    )


def load_transfer(path: Path, repo: Path) -> dict[str, Any]:
    label = "live-evidence transfer record"
    record, _ = read_private_json(path, label, MAX_RECORD_BYTES)
    require_exact_keys(record, TRANSFER_KEYS, label)
    if record["schema_version"] != TRANSFER_SCHEMA_VERSION:
        raise EvidenceError(f"{label} must declare schema_version 1")
    if record["record_type"] != TRANSFER_RECORD_TYPE:
        raise EvidenceError(f"{label} names another record type")
    if self_digest(record) != record["record_digest"]:
        raise EvidenceError(f"{label} digest verification failed")
    if record["repository_identity"] != repository_identity(repo):
        raise EvidenceError(f"{label} names another repository")
    if record["state"] != "transferred":
        raise EvidenceError(f"{label} carries an unknown state")
    return record


def outbound_transfer(repo: Path, plan: str) -> dict[str, Any] | None:
    """Return the transfer that released this plan's own obligation, if any."""

    path = transfer_path(repo, plan)
    if not path.exists() and not path.is_symlink():
        return None
    record = load_transfer(path, repo)
    if record["source_plan_path"] != plan:
        raise EvidenceError("live-evidence transfer record names another source plan")
    return record


def destination_locations(repo: Path, transfer: dict[str, Any]) -> list[str]:
    """Return every lifecycle location that holds the destination plan file.

    A deferred destination is promoted from backlog to active and later
    archived, so the recorded path alone would let an ordinary lifecycle move
    drop the obligation. The plan file name carries the plan identity and stays
    stable across those moves.
    """

    name = PurePosixPath(transfer["destination_plan_path"]).name
    return [
        f"{directory}/{name}"
        for directory in PLAN_LIFECYCLE_DIRECTORIES
        if (repo / directory / name).is_file()
    ]


def resolve_destination_plan(repo: Path, transfer: dict[str, Any]) -> str:
    """Resolve the single live location of a transferred obligation."""

    found = destination_locations(repo, transfer)
    if not found:
        raise EvidenceError(
            "the destination plan of the transferred live-evidence obligation is missing: "
            f"{transfer['destination_plan_path']}"
        )
    if len(found) > 1:
        raise EvidenceError(
            "the destination plan of the transferred live-evidence obligation resolves "
            f"to more than one lifecycle location: {', '.join(found)}"
        )
    return found[0]


def inbound_transfers(repo: Path, plan: str) -> list[dict[str, Any]]:
    """Return every transfer that made this plan the destination.

    The destination obligation is discovered from the records themselves, so a
    destination plan carries it whether or not its own manifest mentions it.
    """

    directory = transfer_directory()
    if not directory.is_dir():
        return []
    identity = repository_identity(repo)
    name = PurePosixPath(plan).name
    entries = sorted(
        entry
        for entry in directory.iterdir()
        if entry.name.endswith(".json") and not entry.name.startswith(".")
    )
    if len(entries) > MAX_TRANSFER_RECORDS:
        raise EvidenceError("the live-evidence transfer directory exceeds its bounded size")
    found: list[dict[str, Any]] = []
    for entry in entries:
        candidate, _ = read_private_json(
            entry, "live-evidence transfer record", MAX_RECORD_BYTES
        )
        if candidate.get("record_type") != TRANSFER_RECORD_TYPE:
            continue
        if candidate.get("repository_identity") != identity:
            continue
        recorded = candidate.get("destination_plan_path")
        if not isinstance(recorded, str):
            continue
        if PurePosixPath(recorded).name != name:
            continue
        found.append(load_transfer(entry, repo))
    return found


def load_authorization(path: Path, repo: Path) -> dict[str, Any]:
    label = "owner authorization"
    require_outside_repository(path, label, repo)
    record, _ = read_private_json(path, label, MAX_RECORD_BYTES)
    require_exact_keys(record, AUTHORIZATION_KEYS, label)
    if record["schema_version"] != TRANSFER_SCHEMA_VERSION:
        raise EvidenceError(f"{label} must declare schema_version 1")
    if record["record_type"] != AUTHORIZATION_RECORD_TYPE:
        raise EvidenceError(f"{label} names another record type")
    if self_digest(record) != record["record_digest"]:
        raise EvidenceError(f"{label} digest verification failed")
    text = require_text(record["authorization"], label)
    if len(text.strip()) < 24 or PLACEHOLDER_RE.search(text):
        raise EvidenceError(
            f"{label} must quote a bounded, non-placeholder owner instruction"
        )
    return record


def publish_transfer(path: Path, transfer: dict[str, Any]) -> str:
    """Publish one transfer record under a lock, exactly once.

    A concurrent attempt, a fork and a crash between the journal and the record
    all resolve to the same single record or to a refusal. No path can leave a
    released source without a bound destination, because one record carries
    both ends.
    """

    directory = path.parent
    if has_symlink_component(directory):
        raise EvidenceError("private record directory contains a symlink component")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    lock_path = directory / f".{path.name}.lock"
    descriptor = os.open(
        lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600
    )
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise EvidenceError(
                "another live-evidence transfer holds this record lock"
            ) from error
        journal_path = directory / f".{path.name}.journal"
        if path.exists() or path.is_symlink():
            existing, _ = read_private_json(
                path, "live-evidence transfer record", MAX_RECORD_BYTES
            )
            if existing != transfer:
                raise EvidenceError(
                    "a different live-evidence transfer record already exists for this "
                    "source plan; a replaced transfer is refused instead of overwritten"
                )
            journal_path.unlink(missing_ok=True)
            return "idempotent"
        if journal_path.exists() or journal_path.is_symlink():
            recorded, _ = read_private_json(
                journal_path, "live-evidence transfer journal", MAX_RECORD_BYTES
            )
            if recorded != transfer:
                raise EvidenceError(
                    "an ambiguous partial live-evidence transfer exists; it names other "
                    "identities and must be resolved before any transfer proceeds"
                )
        else:
            write_private_json(journal_path, transfer)
        write_private_json(path, transfer)
        journal_path.unlink(missing_ok=True)
        return "created"
    finally:
        os.close(descriptor)


def verify_bound_report(repo: Path, record: dict[str, Any]) -> str:
    """Verify the exact private report a record already bound."""

    report_path = Path(require_text(record["report_path"], "bound report path"))
    require_outside_repository(report_path, "bound live report", repo)
    data = read_private_bytes(report_path, "bound live report", MAX_REPORT_BYTES)
    if digest_bytes(data) != record["report_digest"]:
        raise EvidenceError("the bound live report bytes changed after binding")
    try:
        report = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceError(f"bound live report is not valid JSON: {error}") from error
    if not isinstance(report, dict):
        raise EvidenceError("bound live report must be a JSON object")
    validate_report(report, repo / record["plan_path"])
    return record["report_digest"]


def transferred_contract(
    repo: Path, plan: str, inbound: list[dict[str, Any]]
) -> dict[str, Any]:
    """Derive the contract a destination plan inherited through one transfer.

    A destination plan is usually authored before the partition, so it declares
    no contract field of its own. The transfer record is then the only
    authority, and it still binds the exact acceptance item the plan must carry.
    """

    digests = {transfer["live_acceptance_digest"] for transfer in inbound}
    contracts = {transfer["live_evidence_contract"] for transfer in inbound}
    if len(digests) != 1 or len(contracts) != 1:
        raise EvidenceError(
            "this plan received more than one distinct live-evidence obligation; "
            "each one needs its own destination"
        )
    acceptance_digest = next(iter(digests))
    absolute = repo / plan
    text = absolute.read_text(encoding="utf-8")
    carried = acceptance_digests(text, f"destination plan {plan}")
    if acceptance_digest not in carried:
        raise EvidenceError(
            "this plan received a live-evidence obligation but no longer carries its "
            "exact acceptance item; the requirement is not discharged by removing it"
        )
    return {
        "plan_path": plan,
        "plan_digest": digest_bytes(absolute.read_bytes()),
        "contract": next(iter(contracts)),
        "live_acceptance_digest": acceptance_digest,
        "status": plan_manifest(text).get("status"),
    }


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    repo = repository_root()
    plan = relative_plan_path(repo, args.plan)
    contract = plan_contract(repo, plan)
    origin = "declared"
    if contract is None:
        inbound = inbound_transfers(repo, plan)
        if not inbound:
            raise EvidenceError("this plan declares no live-evidence contract")
        contract = transferred_contract(repo, plan, inbound)
        origin = "transferred"
    if GROUP_ID_RE.fullmatch(args.group_id) is None:
        raise EvidenceError("reserved group id must be a bounded lowercase identifier")
    ledger = ledger_identity(Path(args.execution_state), repo)
    if ledger["plan_path"] != plan:
        raise EvidenceError("the execution ledger was created for another plan")
    path = requirement_path(repo, plan)
    if path.exists() or path.is_symlink():
        raise EvidenceError(
            "a required-evidence record already exists for this plan; "
            "a replaced record is refused instead of overwritten"
        )
    record = {
        "schema_version": REQUIREMENT_SCHEMA_VERSION,
        "record_type": REQUIREMENT_RECORD_TYPE,
        "repository_identity": repository_identity(repo),
        "plan_path": plan,
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
    return {
        "operation": "init",
        "record_path": str(path),
        "record_digest": record["record_digest"],
        "plan_path": plan,
        "live_acceptance_digest": record["live_acceptance_digest"],
        "execution_genesis_digest": record["execution_genesis_digest"],
        "reserved_group_id": args.group_id,
        "state": "reserved",
        "obligation_origin": origin,
    }


def command_bind(args: argparse.Namespace) -> dict[str, Any]:
    repo = repository_root()
    plan = relative_plan_path(repo, args.plan)
    record = load_requirement(repo, plan)
    if record["state"] != "reserved":
        raise EvidenceError("this required-evidence record already names a verified report")
    if outbound_transfer(repo, plan) is not None:
        raise EvidenceError(
            "this plan transferred its live-evidence obligation; bind the demonstration "
            "at the destination plan instead"
        )
    report_path = Path(args.report).absolute()
    require_outside_repository(report_path, "live report", repo)
    data = read_private_bytes(report_path, "live report", MAX_REPORT_BYTES)
    report = json.loads(data.decode("utf-8"))
    if not isinstance(report, dict):
        raise EvidenceError("live report must be a JSON object")
    validate_report(report, repo / plan)
    updated = dict(record)
    updated["state"] = "bound"
    updated["group_description_digest"] = str(report.get("group_description_digest") or "")
    updated["report_path"] = str(report_path)
    updated["report_digest"] = digest_bytes(data)
    updated["record_digest"] = ""
    updated["record_digest"] = self_digest(updated)
    write_private_json(requirement_path(repo, plan), updated)
    return {
        "operation": "bind",
        "plan_path": plan,
        "record_digest": updated["record_digest"],
        "report_digest": updated["report_digest"],
        "state": "bound",
    }


def command_show(args: argparse.Namespace) -> dict[str, Any]:
    repo = repository_root()
    plan = relative_plan_path(repo, args.plan)
    record = load_requirement(repo, plan)
    transfer = outbound_transfer(repo, plan)
    return {
        "operation": "show",
        "record_path": str(requirement_path(repo, plan)),
        "plan_path": record["plan_path"],
        "record_digest": record["record_digest"],
        "state": record["state"],
        "reserved_group_id": record["reserved_group_id"],
        "report_digest": record["report_digest"],
        "transferred_to": (transfer["destination_plan_path"] if transfer else ""),
    }


def command_transfer(args: argparse.Namespace) -> dict[str, Any]:
    """Move one reserved live-evidence obligation to the plan that now carries it.

    This records custody. It never satisfies the obligation, never edits the
    original record and never touches the stopped ledger.
    """

    repo = repository_root()
    source = relative_plan_path(repo, args.source_plan)
    destination = relative_plan_path(repo, args.destination_plan)
    if source == destination:
        raise EvidenceError("a live-evidence obligation cannot be transferred to its own plan")
    for label, value in (("source", source), ("destination", destination)):
        if PLAN_PATH_RE.fullmatch(value) is None:
            raise EvidenceError(f"{label} plan path is not one plan document: {value}")

    record = load_requirement(repo, source)
    if record["state"] != "reserved":
        raise EvidenceError(
            "this required-evidence record already names a verified report; "
            "there is no reserved obligation to transfer"
        )

    ledger = authoritative_ledger(Path(args.execution_state), repo)
    if ledger.get("run_id") != record["run_id"]:
        raise EvidenceError("the execution ledger names another run than the reserved obligation")
    if ledger.get("genesis_digest") != record["execution_genesis_digest"]:
        raise EvidenceError("the execution ledger names another execution genesis")
    if ledger.get("plan_path") != source:
        raise EvidenceError("the execution ledger was created for another plan")
    if ledger.get("state") != "descope_required":
        raise EvidenceError(
            "only a stopped descope execution may transfer a live-evidence obligation; "
            f"this ledger is {ledger.get('state')}"
        )
    if ledger.get("open_attempt_id"):
        raise EvidenceError("the source execution still holds an open writable attempt")
    reservation_event_digest = ledger_reservation(ledger, record["record_digest"])

    classification, descope_event_digest, descope_evidence_digest = ledger_descope(ledger)
    if classification.get("plan_path") != source:
        raise EvidenceError("the recorded descope classification names another plan")
    if classification.get("deferred_backlog_path") != destination:
        raise EvidenceError(
            "the recorded descope classification defers to another plan than this destination"
        )
    source_head = require_commit(classification.get("source_head"), "descope source_head")
    retained = [
        require_digest(item, "retained acceptance digest")
        for item in classification.get("retained_acceptance_digests") or []
    ]
    deferred = require_digest_list(
        classification.get("deferred_acceptance_digests"), "deferred acceptance digests"
    )
    source_digests = require_digest_list(
        classification.get("source_acceptance_digests"), "source acceptance digests"
    )
    if len(set(source_digests)) != len(source_digests):
        raise EvidenceError("the recorded source acceptance digests contain duplicates")
    if sorted(retained + deferred) != sorted(source_digests):
        raise EvidenceError(
            "the recorded descope partition does not account for every source acceptance item"
        )
    if deferred.count(record["live_acceptance_digest"]) != 1:
        raise EvidenceError(
            "the reserved live-evidence acceptance item is not the exact deferred item"
        )
    if record["live_acceptance_digest"] in retained:
        raise EvidenceError(
            "the reserved live-evidence acceptance item is recorded as retained and deferred"
        )

    committed = committed_plan_bytes(repo, source_head, source)
    if digest_bytes(committed) != classification.get("plan_digest"):
        raise EvidenceError(
            "the committed source plan at the recorded head is not the classified plan"
        )
    derived = acceptance_digests(
        committed.decode("utf-8", errors="strict"), f"committed source plan {source}"
    )
    if derived != source_digests:
        raise EvidenceError(
            "the recorded source acceptance digests are not the committed acceptance "
            "items of this plan in source order"
        )

    destination_absolute = repo / destination
    if not destination_absolute.is_file():
        raise EvidenceError(f"destination plan is missing: {destination}")
    destination_bytes = destination_absolute.read_bytes()
    destination_digests = acceptance_digests(
        destination_bytes.decode("utf-8"), f"destination plan {destination}"
    )
    if destination_digests.count(record["live_acceptance_digest"]) != 1:
        raise EvidenceError(
            "the destination plan must carry the deferred acceptance item exactly once"
        )

    source_plan_digest = digest_bytes((repo / source).read_bytes())
    destination_plan_digest = digest_bytes(destination_bytes)
    authorization = load_authorization(Path(args.owner_authorization), repo)
    expected = {
        "repository_identity": repository_identity(repo),
        "source_plan_path": source,
        "source_plan_digest": source_plan_digest,
        "destination_plan_path": destination,
        "destination_plan_digest": destination_plan_digest,
        "live_acceptance_digest": record["live_acceptance_digest"],
        "source_record_digest": record["record_digest"],
        "execution_genesis_digest": record["execution_genesis_digest"],
        "run_id": record["run_id"],
    }
    for key, value in expected.items():
        if authorization[key] != value:
            raise EvidenceError(
                f"owner authorization does not bind the exact {key} of this transfer"
            )

    transfer = {
        "schema_version": TRANSFER_SCHEMA_VERSION,
        "record_type": TRANSFER_RECORD_TYPE,
        "repository_identity": expected["repository_identity"],
        "source_plan_path": source,
        "source_plan_digest": source_plan_digest,
        "destination_plan_path": destination,
        "destination_plan_digest": destination_plan_digest,
        "live_evidence_contract": record["live_evidence_contract"],
        "live_acceptance_digest": record["live_acceptance_digest"],
        "source_record_digest": record["record_digest"],
        "execution_genesis_digest": record["execution_genesis_digest"],
        "run_id": record["run_id"],
        "source_head": source_head,
        "source_acceptance_digests": source_digests,
        "retained_acceptance_digests": retained,
        "deferred_acceptance_digests": deferred,
        "descope_event_digest": descope_event_digest,
        "descope_evidence_digest": descope_evidence_digest,
        "reservation_event_digest": reservation_event_digest,
        "owner_authorization_digest": authorization["record_digest"],
        "state": "transferred",
        "record_digest": "",
    }
    transfer["record_digest"] = self_digest(transfer)
    path = transfer_path(repo, source)
    outcome = publish_transfer(path, transfer)
    return {
        "operation": "transfer",
        "outcome": outcome,
        "record_path": str(path),
        "record_digest": transfer["record_digest"],
        "source_plan_path": source,
        "destination_plan_path": destination,
        "live_acceptance_digest": transfer["live_acceptance_digest"],
        "source_record_digest": transfer["source_record_digest"],
        "state": "transferred",
    }


def require_transferred_obligation(
    repo: Path, plan: str, inbound: list[dict[str, Any]]
) -> dict[str, Any]:
    """The destination keeps the obligation until real evidence discharges it."""

    carried = acceptance_digests(
        (repo / plan).read_text(encoding="utf-8"), f"destination plan {plan}"
    )
    for transfer in inbound:
        if transfer["live_acceptance_digest"] not in carried:
            raise EvidenceError(
                "this plan received a live-evidence obligation but no longer carries its "
                "exact acceptance item; the requirement is not discharged by removing it"
            )
    digests = {transfer["live_acceptance_digest"] for transfer in inbound}
    contracts = {transfer["live_evidence_contract"] for transfer in inbound}
    if len(digests) != 1 or len(contracts) != 1:
        raise EvidenceError(
            "this plan received more than one distinct live-evidence obligation; "
            "each one needs its own destination"
        )
    try:
        record = load_requirement(repo, plan)
    except EvidenceError as error:
        raise EvidenceError(
            "this plan received a live-evidence obligation from "
            f"{inbound[0]['source_plan_path']} and still needs its own verified "
            f"two-session demonstration: {error}"
        ) from error
    if record["live_acceptance_digest"] != next(iter(digests)):
        raise EvidenceError(
            "the required-evidence record of this plan binds another acceptance item "
            "than the transferred obligation"
        )
    if record["live_evidence_contract"] != next(iter(contracts)):
        raise EvidenceError(
            "the required-evidence record of this plan binds another live-evidence contract"
        )
    if record["state"] != "bound":
        raise EvidenceError(
            "this plan carries a transferred live-evidence obligation and requires "
            "verified two-session live evidence; its required-evidence record still "
            "reserves the demonstration"
        )
    report_digest = verify_bound_report(repo, record)
    return {
        "operation": "require",
        "plan_path": plan,
        "obligation": record["live_evidence_contract"],
        "origin": "transferred",
        "source_plan_path": inbound[0]["source_plan_path"],
        "report_digest": report_digest,
        "satisfied": True,
    }


def require_released_source(
    repo: Path,
    plan: str,
    contract: dict[str, Any] | None,
    contract_error: EvidenceError | None,
    transfer: dict[str, Any],
) -> dict[str, Any]:
    """A verified transfer releases this source gate, and nothing else."""

    record = load_requirement(repo, plan)
    if record["record_digest"] != transfer["source_record_digest"]:
        raise EvidenceError(
            "the original required-evidence record changed after its obligation was "
            "transferred; the transfer no longer names the obligation it released"
        )
    if contract_error is not None:
        # The source may still name the acceptance item it no longer carries,
        # because that exact item moved to the destination. Only the recorded
        # transfer explains that, and only for the exact transferred digest.
        declared = plan_manifest((repo / plan).read_text(encoding="utf-8")).get(
            ACCEPTANCE_FIELD
        )
        if declared != transfer["live_acceptance_digest"]:
            raise contract_error
    elif contract is not None and (
        contract["contract"] != transfer["live_evidence_contract"]
        or contract["live_acceptance_digest"] != transfer["live_acceptance_digest"]
    ):
        raise EvidenceError(
            "this plan declares a live-evidence obligation that its recorded transfer "
            "does not cover; reserve and demonstrate that obligation separately"
        )
    destination_path = resolve_destination_plan(repo, transfer)
    destination = repo / destination_path
    carried = acceptance_digests(
        destination.read_text(encoding="utf-8"),
        f"destination plan {destination_path}",
    )
    if transfer["live_acceptance_digest"] not in carried:
        raise EvidenceError(
            "the destination plan no longer carries the transferred live-evidence "
            "acceptance item; the obligation would be lost"
        )
    return {
        "operation": "require",
        "plan_path": plan,
        "obligation": "transferred",
        "destination_plan_path": destination_path,
        "live_acceptance_digest": transfer["live_acceptance_digest"],
        "transfer_record_digest": transfer["record_digest"],
        "satisfied": False,
        "released": True,
    }


def command_require(repo: Path, plan_arg: str | Path) -> dict[str, Any]:
    """Decide the live-evidence obligation of one plan from private evidence.

    The manifest, the environment and the lifecycle entrypoint never decide.
    An inbound transfer creates the obligation, the canonical record discharges
    it, and only a verified outbound transfer releases a source.
    """

    plan = relative_plan_path(repo, plan_arg)
    if not (repo / plan).is_file():
        raise EvidenceError(f"plan file is missing: {plan}")
    contract: dict[str, Any] | None = None
    contract_error: EvidenceError | None = None
    try:
        contract = plan_contract(repo, plan)
    except EvidenceError as error:
        contract_error = error
    try:
        repository_identity(repo)
    except EvidenceError as error:
        # A record is keyed by repository identity, so a repository without a
        # canonical origin can hold none. A plan that declares no contract
        # reserves nothing there and stays outside enforcement; one that still
        # declares a contract refuses, because the gate cannot key what it
        # cannot verify.
        if contract is None and contract_error is None:
            return {"operation": "require", "plan_path": plan, "obligation": "none"}
        raise EvidenceError(
            f"live-evidence rule cannot be keyed in this repository: {error}"
        ) from error

    inbound = inbound_transfers(repo, plan)
    if inbound:
        return require_transferred_obligation(repo, plan, inbound)

    transfer = outbound_transfer(repo, plan)
    if transfer is not None:
        return require_released_source(repo, plan, contract, contract_error, transfer)

    if contract_error is not None:
        raise contract_error

    if contract is None:
        # A reserved obligation is not revoked by editing the plan. Dropping
        # the contract fields must refuse, not silently clear the requirement.
        path = requirement_path(repo, plan)
        if path.exists() or path.is_symlink():
            raise EvidenceError(
                "this plan reserves a live-evidence demonstration but no longer "
                "declares its live-evidence contract"
            )
        return {"operation": "require", "plan_path": plan, "obligation": "none"}

    record = load_requirement(repo, plan)
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
    report_digest = verify_bound_report(repo, record)
    return {
        "operation": "require",
        "plan_path": plan,
        "obligation": record["live_evidence_contract"],
        "origin": "declared",
        "report_digest": report_digest,
        "satisfied": True,
    }


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False))


def resolve_plan_selector(repo: Path, selector: Path | None) -> Path:
    plan_path = selector if selector is not None else Path("docs/plan/active")
    if plan_path.is_dir():
        matches = sorted(repo.glob(str(plan_path / "[0-9][0-9][0-9]-*.md")))
        if not matches:
            raise ValueError(f"no active plan file found under {repo / 'docs/plan/active'}")
        return matches[-1]
    if not plan_path.is_absolute():
        return repo / plan_path
    return plan_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["require", "verify", "init", "bind", "show", "transfer"],
        nargs="?",
        default="verify",
    )
    parser.add_argument("--plan", type=Path, help="path to the plan being checked")
    parser.add_argument("--report", type=Path, help="path to the live-session report JSON file")
    parser.add_argument("--required-evidence", type=Path, help="path to the required-evidence JSON record")
    parser.add_argument("--execution-state", type=Path, help="path to the execution ledger")
    parser.add_argument("--group-id", help="reserved demonstration group identifier")
    parser.add_argument("--source-plan", type=Path, help="plan that reserved the obligation")
    parser.add_argument("--destination-plan", type=Path, help="plan that now carries the deferred item")
    parser.add_argument("--owner-authorization", type=Path, help="path to the owner authorization record")
    args = parser.parse_args(argv)
    try:
        repo = repository_root()
    except EvidenceError:
        repo = Path.cwd()
    try:
        if args.command in {"init", "bind", "show", "transfer"}:
            required = {
                "init": ("plan", "execution_state", "group_id"),
                "bind": ("plan", "report"),
                "show": ("plan",),
                "transfer": (
                    "source_plan",
                    "destination_plan",
                    "execution_state",
                    "owner_authorization",
                ),
            }[args.command]
            for name in required:
                if getattr(args, name) is None:
                    raise EvidenceError(
                        f"{args.command} requires --{name.replace('_', '-')}"
                    )
            handler = {
                "init": command_init,
                "bind": command_bind,
                "show": command_show,
                "transfer": command_transfer,
            }[args.command]
            emit(handler(args))
            return 0
        if args.command == "require":
            plan_obj = resolve_plan_selector(repo, args.plan)
            emit(command_require(repo, plan_obj))
            return 0
        plan_path = resolve_plan_selector(repo, args.plan)
        report_path = args.report if args.report is not None else resolve_report(None)
        required_path = resolve_required_evidence(
            str(args.required_evidence) if args.required_evidence is not None else None
        )
        if required_path is None:
            required_path = requirement_path(repo, plan_path)
        if not report_path.exists():
            raise ValueError(f"live report does not exist: {report_path}")
        if not required_path.exists():
            raise ValueError(
                f"required-evidence record does not exist: {required_path}. "
                "Create it before implementation and keep it unchanged until completion."
            )
        required_record = load_json(required_path)
        if not isinstance(required_record, dict):
            raise ValueError(f"required-evidence record must contain a JSON object: {required_path}")
        require_record(required_record, repo, plan_path, report_path)
        report = load_json(report_path)
        if not isinstance(report, dict):
            raise ValueError(f"live session report must contain a JSON object: {report_path}")
        validate_report(report, plan_path)
        print(f"parallel live-session verification passed for {plan_path}")
        return 0
    except (ValueError, EvidenceError) as exc:
        print(f"parallel live-session verification failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"parallel live-session verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
