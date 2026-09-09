"""Shared helpers for plan manifest and index handling."""

from __future__ import annotations

import json
import hashlib
import os
import re
import stat
import subprocess
import tempfile
import fcntl
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path.cwd()
SPEC_INDEX = ROOT / ".project-agent-workflow/docs/agent/spec-index.yaml"
LEGACY_SPEC_INDEX = ROOT / "docs/agent/spec-index.yaml"
ADOPTION_MANIFEST = ROOT / ".project-agent-workflow-migration/v1-pre-namespace/manifest.json"
PLAN = ROOT / "docs/plan/plan.md"
CHECKED = ROOT / "docs/plan/checked.md"
REPLANNED = ROOT / "docs/plan/replanned.md"
ACTIVE_DIR = ROOT / "docs/plan/active"
BACKLOG_DIR = ROOT / "docs/plan/backlog"
SHELVED_DIR = ROOT / "docs/plan/shelved"
CHECKED_DIR = ROOT / "docs/plan/checked"
REPLANNED_DIR = ROOT / "docs/plan/replanned"
OPEN_PLAN_DIRS = [ACTIVE_DIR, BACKLOG_DIR, SHELVED_DIR]
PLAN_DIRS = [*OPEN_PLAN_DIRS, CHECKED_DIR, REPLANNED_DIR]

REQUIRED_FIELDS = (
    "status",
    "task_types",
    "review_class",
    "human_design_required",
    "human_approval_status",
    "write_scope",
    "context_files",
    "required_specs",
    "validation",
    "acceptance",
    "checked_summary_ja",
)
LEGACY_REQUIRED_FIELDS = (
    "status",
    "task_type",
    "review_class",
    "human_design_required",
    "human_approval_status",
    "target_files",
    "required_specs",
    "validation",
    "acceptance",
    "expected_output",
    "checked_summary_ja",
)
SCALAR_KEYS = {
    "status",
    "task_type",
    "plan_purpose",
    "review_class",
    "human_design_required",
    "human_approval_status",
    "implementation_risk",
    "implementation_ambiguity",
    "implementation_tier",
    "expected_output",
    "checked_summary_ja",
    "completion_deferred_reason",
    "primary_invariant",
    "execution_group",
    "replan_source",
    "replan_contract",
    "validation_witness_schema",
}
IMPLEMENTATION_CLASSIFICATION_KEYS = {"implementation_risk", "implementation_ambiguity"}
LIST_KEYS = {
    "task_types",
    "target_files",
    "write_scope",
    "context_files",
    "target_json",
    "required_specs",
    "validation",
    "focused_validation",
    "validation_authority_scope",
    "validation_witness_map",
    "feasibility_evidence",
    "completion_conditions",
    "completion_witness_map",
    "acceptance",
    "acceptance_focus",
    "integration_gates",
    "predecessor_plans",
    "successor_plans",
    "replan_sources",
    "inherited_acceptance_digests",
    "replan_reason_codes",
}
CONTEXT_FIELDS = (
    "TASK_TYPES",
    "REQUIRED_SPECS",
    "WRITE_SCOPE",
    "CONTEXT_FILES",
    "TARGET_JSON",
    "VALIDATION",
)
CONTEXT_KEYS = {
    "TASK_TYPES": "task_types",
    "REQUIRED_SPECS": "required_specs",
    "WRITE_SCOPE": "write_scope",
    "CONTEXT_FILES": "context_files",
    "TARGET_JSON": "target_json",
    "VALIDATION": "validation",
}
CONTEXT_REQUIRED = ("task_types", "write_scope", "context_files", "required_specs", "validation")
ADMISSION_FIELDS = (
    "plan_purpose",
    "feasibility_evidence",
    "completion_conditions",
    "completion_witness_map",
)
PLAN_PURPOSE_VALUES = {"implementation"}
FEASIBILITY_EVIDENCE_KINDS = {
    "reproduced_defect",
    "existing_mechanism",
    "bounded_prototype",
    "mechanical_transformation",
}
MAX_FEASIBILITY_EVIDENCE = 8
MAX_COMPLETION_CONDITIONS = 8
FEASIBILITY_EVIDENCE_MAX_BYTES = 400
COMPLETION_CONDITION_MAX_BYTES = 400
ADMISSION_PLACEHOLDER_VALUES = {
    "-",
    "?",
    "n/a",
    "na",
    "none",
    "pending",
    "placeholder",
    "t.b.d.",
    "tbd",
    "todo",
    "unknown",
    "xxx",
}
ADMISSION_LIFECYCLE_PREFIXES = (
    "docs/plan/",
    ".agent-logs/",
    ".agent-artifacts/",
)
TIER_ONE_VALUE = "1"
WITNESS_REQUIRED_STATUSES = {"in_progress"}
VALIDATION_WITNESS_STAGES = {"static", "focused", "authoritative"}
STATIC_VALIDATION_WITNESSES = {"resolved-context-files"}
VALIDATION_WITNESS_REASON_MAX_BYTES = 240
MIGRATION_PROVENANCE_PATH = (
    ".project-agent-workflow-migration/validation-witness-provenance-v1.json"
)
MIGRATION_PROVENANCE_SCHEMA = 1
MIGRATION_PROVENANCE_OPERATION = "validation_witness_migration_snapshot"
MIGRATION_PROVENANCE_VERSION = "v1.4.5"
MIGRATION_BOUNDARY_POLICY_PATH = ".project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
MIGRATION_BOUNDARY_MARKER = b"validation-witness-migration-provenance-schema: 1"
COMPANION_BASELINE_PATH = (
    "docs/plan/replanned/baselines/live-validation-successors-v1.json"
)
COMPANION_FLAT_ACCEPTANCE_SCHEMAS = {1, 2}
COMPANION_LINEAGE_RESIDUE_FIELDS = (
    "replan_source",
    "replan_sources",
    "inherited_acceptance_digests",
)
COMPANION_CONTRACT_DIRECTORY = "docs/plan/replanned/contracts"
COMPANION_BASELINE_CONTRACT_SCHEMA = 1
COMPANION_PROJECTION_WITNESS_SCHEMA = 1
SELF_PROJECTING_CONTRACT_SCHEMAS = {2, 3, 4}
SELF_PROJECTING_MAPPED_ACCEPTANCE_SCHEMAS = {3, 4}
REPLANNED_INDEX_PATH = "docs/plan/replanned.md"
REPLANNED_INDEX_ROW_RE = re.compile(r"^[0-9]{3}\t")
PUBLISHED_CONTRACT_RE = re.compile(
    r"docs/plan/replanned/contracts/[0-9]{3}-[a-z0-9][a-z0-9-]*\.json"
)
PUBLISHED_ARCHIVE_RE = re.compile(
    r"docs/plan/replanned/[0-9]{4}/[0-9]{2}/(?:01-15|16-31)/"
    r"([0-9]{3})-[a-z0-9][a-z0-9-]*\.md"
)
GIT_EVIDENCE_TIMEOUT_SECONDS = 60
GIT_REGULAR_BLOB_MODES = {b"100644", b"100755"}
GIT_OBJECT_ID_RE = re.compile(rb"[0-9a-f]{40,64}")
CONTEXT_FILES_NONE = "none"
MAX_WITNESS_EVIDENCE_BYTES = 4 * 1024 * 1024
ACTIVE_PREDECESSOR_RE = re.compile(
    r"docs/plan/active/([0-9]{3})-([a-z0-9][a-z0-9-]*)\.md"
)
CHECKED_PREDECESSOR_RE = re.compile(
    r"docs/plan/checked/[0-9]{4}/[0-9]{2}/(?:01-15|16-31)/"
    r"([0-9]{3})-([a-z0-9][a-z0-9-]*)\.md"
)
class PlanError(ValueError):
    """Raised for invalid plan docs or indexes."""


def has_pre_v1_adoption_provenance() -> bool:
    try:
        manifest = json.loads(ADOPTION_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(manifest, dict):
        return False
    previous_ref = manifest.get("previous_ref")
    copied = manifest.get("adoption_copied")
    return bool(
        manifest.get("operation") == "recopy_adoption"
        and isinstance(previous_ref, str)
        and re.fullmatch(r"v0\.[0-9]+\.[0-9]+", previous_ref)
        and isinstance(copied, list)
        and "docs/agent/spec-index.yaml" in copied
    )


WORKTREE_GUARD_MODULE_NAME = "worktree_guard"


def locate_worktree_guard() -> Any:
    """Load the shared worktree guard shipped beside this module, once per process.

    The guard tracks which shared lifecycle lock this process already holds, and
    `flock` does not nest across two open file descriptions. Re-executing the
    module would therefore hand a lifecycle command a second, empty view of that
    state and let it block against its own lock, so the loaded instance is
    reused.
    """

    import importlib.util
    import sys

    cached = sys.modules.get(WORKTREE_GUARD_MODULE_NAME)
    if cached is not None:
        return cached
    candidate = Path(__file__).resolve().with_name("worktree_guard.py")
    if not candidate.is_file():
        raise PlanError("could not locate worktree_guard.py beside this module")
    spec = importlib.util.spec_from_file_location(WORKTREE_GUARD_MODULE_NAME, candidate)
    if spec is None or spec.loader is None:
        raise PlanError("could not load worktree_guard.py beside this module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def shared_lifecycle_state_available() -> bool:
    """Report whether this directory can hold state shared across linked worktrees.

    Only the absence of that possibility justifies worktree-local locking and
    scanning. A lock-wait timeout, a corrupt ledger, or a full ledger are the
    exact situations the shared mechanism exists for, so those failures must
    reach the caller instead of silently restoring the behaviour that let two
    checkouts allocate the same identifier.
    """

    try:
        guard = locate_worktree_guard()
    except PlanError:
        return False
    try:
        guard.common_git_directory(ROOT)
    except (OSError, UnicodeError, guard.WorktreeError):
        return False
    return True


@contextmanager
def lifecycle_lock():
    """Hold the exclusive plan lifecycle lock every linked worktree shares.

    A lock inside one worktree cannot serialize a second linked checkout of the
    same repository, so the lock lives under the common Git directory. A
    directory that is not a Git worktree keeps the local lock; it also has no
    second checkout to race against. Acquisition is separated from the guarded
    body so that a failure raised by the caller never re-runs that body.
    """

    shared = None
    if shared_lifecycle_state_available():
        candidate = locate_worktree_guard().plan_lifecycle_lock(ROOT)
        candidate.__enter__()
        shared = candidate
    if shared is not None:
        try:
            yield
        finally:
            shared.__exit__(None, None, None)
        return
    lock_dir = ROOT / ".agent-artifacts"
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir / "plan-lifecycle.lock").open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


# --- active plan index grammar: keep byte-identical across enforcing commands ---
ACTIVE_INDEX_TITLE = "# Active Plan"
ACTIVE_INDEX_EMPTY_BODY = "No active development items."
ACTIVE_INDEX_HEADER = "id\tpath\tstatus"
ACTIVE_INDEX_STATUSES = ("in_progress", "ready_to_archive", "deferred", "replan_required")
ACTIVE_INDEX_ID_RE = re.compile(r"[0-9]{3}")
ACTIVE_INDEX_ROW_PATH_RE = re.compile(r"docs/plan/active/([0-9]{3})-[a-z0-9][a-z0-9-]*\.md")


class ActiveIndexError(ValueError):
    """Raised when the active plan index is not one accepted representation."""


def read_active_index(path: Path) -> str:
    """Read one active plan index without newline translation."""

    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ActiveIndexError(f"active plan index is not UTF-8 text: {exc}") from exc


def parse_active_index(text: str) -> list[tuple[str, str, str]]:
    """Return the rows of one exact accepted active plan index document.

    The empty representation is the title, one blank line, and the empty
    marker. The populated representation is the title, one blank line, the
    actual-tab header, and one or more actual-tab rows. Every other nonempty
    document is rejected whole instead of being partially parsed.
    """

    if "\r" in text or not text.endswith("\n") or text.endswith("\n\n"):
        raise ActiveIndexError("active plan index must end with exactly one trailing newline")
    lines = text.split("\n")[:-1]
    if lines[:2] != [ACTIVE_INDEX_TITLE, ""]:
        raise ActiveIndexError("active plan index must start with its title and one blank line")
    body = lines[2:]
    if not body:
        raise ActiveIndexError("active plan index must hold the empty marker or the header")
    if body[0] == ACTIVE_INDEX_EMPTY_BODY:
        if len(body) > 1:
            raise ActiveIndexError("empty active plan index must hold no other content")
        return []
    if body[0] != ACTIVE_INDEX_HEADER:
        raise ActiveIndexError(f"active plan index needs the exact tab header: {body[0]!r}")
    if len(body) == 1:
        raise ActiveIndexError("active plan index header must be followed by at least one row")
    rows: list[tuple[str, str, str]] = []
    for line in body[1:]:
        columns = line.split("\t")
        if len(columns) != 3:
            raise ActiveIndexError(f"active plan index row needs three tab columns: {line!r}")
        plan_id, path, status = columns
        if ACTIVE_INDEX_ID_RE.fullmatch(plan_id) is None:
            raise ActiveIndexError(f"active plan index row needs a three-digit id: {line!r}")
        match = ACTIVE_INDEX_ROW_PATH_RE.fullmatch(path)
        if match is None:
            raise ActiveIndexError(f"active plan index row needs a normalized path: {line!r}")
        if match.group(1) != plan_id:
            raise ActiveIndexError(f"active plan index row id does not match its file: {line!r}")
        if status not in ACTIVE_INDEX_STATUSES:
            raise ActiveIndexError(f"active plan index row status is not allowed: {line!r}")
        if any(plan_id == row[0] for row in rows):
            raise ActiveIndexError(f"duplicate active plan index id: {plan_id}")
        if any(path == row[1] for row in rows):
            raise ActiveIndexError(f"duplicate active plan index path: {path}")
        rows.append((plan_id, path, status))
    return rows


def render_active_index(rows: list[tuple[str, str, str]]) -> str:
    """Serialize fully parsed rows as the single canonical representation."""

    if rows:
        body = "\n".join("\t".join(row) for row in rows)
        text = f"{ACTIVE_INDEX_TITLE}\n\n{ACTIVE_INDEX_HEADER}\n{body}\n"
    else:
        text = f"{ACTIVE_INDEX_TITLE}\n\n{ACTIVE_INDEX_EMPTY_BODY}\n"
    if parse_active_index(text) != rows:
        raise ActiveIndexError("canonical active plan index serialization failed")
    return text
# --- end active plan index grammar ---


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def routing_contract(spec_index: Path = SPEC_INDEX) -> tuple[set[str], dict[str, set[str]]]:
    if not spec_index.is_file():
        return set(), {}
    default_reads: set[str] = set()
    route_requirements: dict[str, set[str]] = {}
    section = ""
    in_task_types = False
    current_route = ""
    for line in spec_index.read_text(encoding="utf-8").splitlines():
        if line == "default_reads:":
            section = "default_reads"
            in_task_types = False
            current_route = ""
            continue
        if line == "task_types:":
            section = "task_types"
            in_task_types = True
            current_route = ""
            continue
        if in_task_types and line and not line.startswith(" "):
            break
        if section == "default_reads":
            match = re.fullmatch(r"  - (.+)", line)
            if match:
                default_reads.add(match.group(1))
            continue
        if not in_task_types:
            continue
        route_match = re.fullmatch(r"  ([a-z][a-z0-9_]*):", line)
        if route_match:
            current_route = route_match.group(1)
            route_requirements[current_route] = set()
            section = "task_types"
            continue
        if current_route and line == "    required:":
            section = "required"
            continue
        if current_route and section == "required":
            required_match = re.fullmatch(r"      - (.+)", line)
            if required_match:
                route_requirements[current_route].add(required_match.group(1))
                continue
            if line and not line.startswith("      "):
                section = "task_types"
    return default_reads, route_requirements


def task_type_values(spec_index: Path = SPEC_INDEX) -> set[str]:
    _, route_requirements = routing_contract(spec_index)
    return set(route_requirements)


def required_specs_for(task_types: list[str], spec_index: Path = SPEC_INDEX) -> set[str]:
    default_reads, route_requirements = routing_contract(spec_index)
    required = set(default_reads)
    for task_type in task_types:
        required.update(route_requirements.get(task_type, set()))
    return required


def parse_manifest(path: Path) -> dict[str, str | list[str]]:
    if not path.is_file():
        raise PlanError(f"missing plan: {path}")

    return parse_manifest_text(path.read_text(encoding="utf-8"))


def parse_manifest_text(text: str) -> dict[str, str | list[str]]:
    values: dict[str, str | list[str]] = {key: [] for key in LIST_KEYS}
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
            if key in SCALAR_KEYS:
                if key in IMPLEMENTATION_CLASSIFICATION_KEYS and not rest:
                    values[key] = []
                    current = key
                else:
                    values[key] = rest
            elif key in LIST_KEYS:
                current = key
                if rest:
                    values[key].append(rest)  # type: ignore[union-attr]
            continue
        if current and line.lstrip().startswith("- "):
            values[current].append(line.lstrip()[2:].strip())  # type: ignore[union-attr]

    return values


def require_manifest_fields(path: Path, fields: tuple[str, ...] = REQUIRED_FIELDS) -> dict[str, str | list[str]]:
    values = parse_manifest(path)
    for key in fields:
        value = values.get(key)
        if value in (None, "", []):
            raise PlanError(f"{path} missing field: {key}:")
    validate_validation_witness_map(values, plan_path=path)
    return values


def manifest_scalar(values: dict[str, str | list[str]], key: str) -> str:
    value = values.get(key, "")
    if isinstance(value, list):
        return " ".join(value)
    return value


def manifest_joined(values: dict[str, str | list[str]], key: str) -> str:
    value = values.get(key, [])
    if isinstance(value, list):
        return " ".join(item for item in value if item != "none")
    return value


def validate_predecessor_list(values: dict[str, str | list[str]], label: str) -> list[str]:
    predecessors = values.get("predecessor_plans", [])
    if not isinstance(predecessors, list):
        raise PlanError(f"{label} predecessor_plans must be a list")
    if predecessors == ["[]"]:
        return []
    if len(predecessors) != len(set(predecessors)):
        raise PlanError(f"{label} predecessor_plans must not contain duplicates")
    for predecessor in predecessors:
        path = Path(predecessor)
        if (
            not predecessor
            or predecessor != path.as_posix()
            or path.is_absolute()
            or "." in path.parts
            or ".." in path.parts
            or not (
                ACTIVE_PREDECESSOR_RE.fullmatch(predecessor)
                or CHECKED_PREDECESSOR_RE.fullmatch(predecessor)
            )
        ):
            raise PlanError(f"{label} has invalid predecessor path: {predecessor!r}")
    return predecessors


def read_checked_rows() -> list[tuple[str, str]]:
    if not CHECKED.exists():
        return []
    rows: list[tuple[str, str]] = []
    for line in CHECKED.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\d{3}\t", line):
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise PlanError(f"malformed checked index row: {line}")
        rows.append((parts[0], parts[1]))
    return rows


def _matching_checked_paths(
    plan_id: str,
    basename: str,
    checked_rows: list[tuple[str, str]],
) -> list[str]:
    related = [
        path
        for indexed_id, path in checked_rows
        if indexed_id == plan_id or Path(path).name == basename
    ]
    exact = [
        path
        for indexed_id, path in checked_rows
        if indexed_id == plan_id and Path(path).name == basename
    ]
    if related and len(exact) != len(related):
        raise PlanError(f"predecessor identity mismatch for plan {plan_id}")
    return exact


def require_predecessors_checked(path: Path) -> None:
    values = parse_manifest(path)
    predecessors = validate_predecessor_list(values, str(path))
    checked_rows = read_checked_rows()
    for predecessor in predecessors:
        match = CHECKED_PREDECESSOR_RE.fullmatch(predecessor)
        if match is None:
            raise PlanError(
                f"{path} predecessor must use its exact checked archive before activation: "
                f"{predecessor}"
            )
        plan_id = match.group(1)
        exact = _matching_checked_paths(plan_id, Path(predecessor).name, checked_rows)
        if exact != [predecessor]:
            raise PlanError(f"{path} checked predecessor is missing or stale: {predecessor}")
        target = ROOT / predecessor
        if not target.is_file():
            raise PlanError(f"{path} checked predecessor is missing: {predecessor}")
        if manifest_scalar(parse_manifest(target), "status") != "checked":
            raise PlanError(f"{path} predecessor is not checked: {predecessor}")


def validate_active_plan_predecessors() -> None:
    rows = read_active_rows()
    by_path = {path: (plan_id, status) for plan_id, path, status in rows}
    if len(by_path) != len(rows):
        raise PlanError("active index contains duplicate predecessor identities")
    checked_rows = read_checked_rows()
    graph: dict[str, list[str]] = {path: [] for path in by_path}

    for path, (plan_id, index_status) in by_path.items():
        target = ROOT / path
        if not target.is_file():
            raise PlanError(f"missing active plan: {path}")
        values = parse_manifest(target)
        status = manifest_scalar(values, "status")
        if status != index_status:
            raise PlanError(f"active predecessor status mismatch: {path}")
        unresolved: list[str] = []
        for predecessor in validate_predecessor_list(values, path):
            active_match = ACTIVE_PREDECESSOR_RE.fullmatch(predecessor)
            if active_match is not None:
                predecessor_id = active_match.group(1)
                active_record = by_path.get(predecessor)
                if active_record is not None:
                    if active_record[0] != predecessor_id:
                        raise PlanError(f"{path} predecessor identity mismatch: {predecessor}")
                    graph[path].append(predecessor)
                    unresolved.append(predecessor)
                    continue
                exact_checked = _matching_checked_paths(
                    predecessor_id, Path(predecessor).name, checked_rows
                )
                if not exact_checked:
                    raise PlanError(f"{path} predecessor is missing: {predecessor}")
                unresolved.append(predecessor)
                continue

            checked_match = CHECKED_PREDECESSOR_RE.fullmatch(predecessor)
            assert checked_match is not None
            predecessor_id = checked_match.group(1)
            exact_checked = _matching_checked_paths(
                predecessor_id, Path(predecessor).name, checked_rows
            )
            if exact_checked != [predecessor]:
                raise PlanError(f"{path} checked predecessor is missing or stale: {predecessor}")
            checked_file = ROOT / predecessor
            if not checked_file.is_file():
                raise PlanError(f"{path} checked predecessor is missing: {predecessor}")
            if manifest_scalar(parse_manifest(checked_file), "status") != "checked":
                raise PlanError(f"{path} predecessor is not checked: {predecessor}")

        if unresolved and status != "deferred":
            raise PlanError(
                f"{path} must remain deferred until active predecessors are replaced "
                "with exact checked archive paths"
            )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(path: str) -> None:
        if path in visiting:
            raise PlanError(f"active predecessor cycle detected at: {path}")
        if path in visited:
            return
        visiting.add(path)
        for predecessor in graph[path]:
            visit(predecessor)
        visiting.remove(path)
        visited.add(path)

    for path in graph:
        visit(path)


def acceptance_digest(acceptance: str) -> str:
    return "sha256:" + hashlib.sha256(acceptance.encode("utf-8")).hexdigest()


def byte_digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def compact_json_digest(value: Any) -> str:
    """Reproduce the digest the plan restructuring transaction publishes."""

    return byte_digest(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )


def indented_json_digest(value: Any) -> str:
    """Reproduce the digest the migration provenance snapshot publishes."""

    return byte_digest(
        (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        )
    )


def reject_symlink_components(root: Path, relative: str, label: str) -> None:
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise PlanError(f"{label} has a symlink path component: {relative}")


def read_repository_bytes(root: Path, relative: str, label: str) -> bytes:
    reject_symlink_components(root, relative, label)
    try:
        descriptor = os.open(root / relative, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise PlanError(f"{label} is unavailable: {relative}") from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise PlanError(f"{label} is not a regular file: {relative}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            raw = handle.read(MAX_WITNESS_EVIDENCE_BYTES + 1)
    except OSError as exc:
        raise PlanError(f"{label} is unreadable: {relative}") from exc
    finally:
        os.close(descriptor)
    if len(raw) > MAX_WITNESS_EVIDENCE_BYTES:
        raise PlanError(f"{label} exceeds its size bound: {relative}")
    return raw


def read_repository_json(root: Path, relative: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(read_repository_bytes(root, relative, label).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlanError(f"{label} is not valid JSON: {relative}") from exc
    if not isinstance(value, dict):
        raise PlanError(f"{label} is not a JSON object: {relative}")
    return value


def normalized_repository_path(raw: object, label: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise PlanError(f"{label} is missing")
    path = PurePosixPath(raw)
    if raw != path.as_posix() or path.is_absolute() or {".", ".."} & set(path.parts):
        raise PlanError(f"{label} is not a normalized repository path: {raw!r}")
    return raw


def git_evidence(root: Path, *args: str) -> bytes:
    """Read one bounded Git fact from the plan repository's own history.

    Publication evidence is only meaningful when it comes from history the
    working tree cannot rewrite, so every failure to obtain it - a missing
    Git binary, an unborn HEAD, a broken object store, or output beyond the
    evidence bound - is refused instead of downgraded to a missing record.

    Every inherited `GIT_*` variable is dropped first. `GIT_DIR` alone
    would keep the working tree at this repository while reading objects
    from another one, which would let an ambient environment answer for
    history this repository never published.
    """

    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            env=environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=GIT_EVIDENCE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PlanError(
            "published replan contract evidence requires a readable Git history"
        ) from exc
    if completed.returncode != 0:
        raise PlanError(
            "published replan contract evidence requires a readable Git history"
        )
    if len(completed.stdout) > MAX_WITNESS_EVIDENCE_BYTES:
        raise PlanError("published replan contract evidence exceeds its size bound")
    return completed.stdout


def require_repository_history(root: Path) -> None:
    """Refuse history that belongs to another repository than the plan's own.

    A plan repository nested inside an unrelated checkout would otherwise
    answer with the outer repository's commits, which say nothing about
    what this repository published.
    """

    toplevel = git_evidence(root, "rev-parse", "--show-toplevel")
    try:
        resolved = Path(toplevel.decode("utf-8").strip()).resolve()
    except (UnicodeDecodeError, OSError) as exc:
        raise PlanError(
            "published replan contract evidence requires a readable Git history"
        ) from exc
    if resolved != root.resolve():
        raise PlanError(
            "published replan contract evidence must come from the plan repository itself"
        )


def committed_blob_bytes(root: Path, relative: str, label: str) -> bytes:
    """Read the exact committed bytes one repository path holds at HEAD."""

    listing = git_evidence(root, "ls-tree", "--full-tree", "-z", "HEAD", "--", relative)
    entries = [entry for entry in listing.split(b"\0") if entry]
    if len(entries) != 1:
        raise PlanError(f"{label} is not committed history: {relative}")
    header, separator, name = entries[0].partition(b"\t")
    fields = header.split(b" ")
    if (
        not separator
        or name != relative.encode("utf-8")
        or len(fields) != 3
        or fields[0] not in GIT_REGULAR_BLOB_MODES
        or fields[1] != b"blob"
        or not GIT_OBJECT_ID_RE.fullmatch(fields[2])
    ):
        raise PlanError(f"{label} is not a committed regular file: {relative}")
    return git_evidence(root, "cat-file", "blob", fields[2].decode("ascii"))


def committed_replanned_rows(root: Path) -> list[tuple[str, str, str]]:
    """Read the committed replanned index rows the publisher appended."""

    raw = committed_blob_bytes(root, REPLANNED_INDEX_PATH, "published replanned index")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PlanError("published replanned index is not UTF-8") from exc
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        if not REPLANNED_INDEX_ROW_RE.match(line):
            continue
        fields = line.split("\t")
        if len(fields) != 3:
            raise PlanError(f"published replanned index has a malformed row: {line}")
        rows.append((fields[0], fields[1], fields[2]))
    return rows


def manifest_list(values: dict[str, str | list[str]], key: str) -> list[str]:
    value = values.get(key, [])
    if not isinstance(value, list):
        raise PlanError(f"plan {key} must be a list")
    return value


def plan_repository_root(plan_path: Path) -> tuple[Path, str]:
    if not re.fullmatch(r"[0-9]{3}-.+\.md", plan_path.name):
        raise PlanError(f"invalid active integration plan path: {plan_path}")
    if tuple(part.name for part in plan_path.parents[:3]) != ("active", "plan", "docs"):
        raise PlanError(f"integration plan is outside docs/plan/active: {plan_path}")
    root = plan_path.parents[3].resolve()
    relative = plan_path.resolve(strict=True).relative_to(root).as_posix()
    return root, relative


def validate_legacy_witness_provenance(
    plan_path: Path,
    values: dict[str, str | list[str]],
) -> None:
    root, plan_relative = plan_repository_root(plan_path)
    contract_raw = manifest_scalar(values, "replan_contract")
    if not contract_raw:
        raise PlanError("pre-schema integration plan lacks normalized replan_contract provenance")
    try:
        contract_relative = normalized_repository_path(
            contract_raw, "pre-schema integration plan replan_contract"
        )
    except PlanError as exc:
        raise PlanError(
            "pre-schema integration plan lacks normalized replan_contract provenance"
        ) from exc
    contract_bytes = read_repository_bytes(
        root, contract_relative, "pre-schema integration plan replan contract"
    )
    try:
        contract = json.loads(contract_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlanError("pre-schema integration plan has unreadable replan_contract provenance") from exc
    if not isinstance(contract, dict) or contract.get("schema_version") != 1:
        raise PlanError("pre-schema integration plan has unsupported replan_contract provenance")
    if contract.get("contract_path") != contract_relative:
        raise PlanError("pre-schema integration plan contract identity differs")

    archive_raw = contract.get("archive_path")
    if not isinstance(archive_raw, str):
        raise PlanError("pre-schema integration plan contract lacks a replanned archive")
    archive_path = PurePosixPath(archive_raw)
    if (
        archive_raw != archive_path.as_posix()
        or archive_path.parts[:3] != ("docs", "plan", "replanned")
        or archive_path.suffix != ".md"
    ):
        raise PlanError("pre-schema integration plan contract has invalid archive provenance")
    archive_relative = normalized_repository_path(
        archive_raw, "pre-schema integration plan replanned archive"
    )
    archive_bytes = read_repository_bytes(
        root, archive_relative, "pre-schema integration plan replanned archive"
    )
    try:
        archive_text = archive_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PlanError("pre-schema integration plan replanned archive is unavailable") from exc
    if not re.search(r"^status:\s*replanned\s*$", archive_text, re.MULTILINE):
        raise PlanError("pre-schema integration plan archive is not terminal replanned history")

    candidates = contract.get("successors", [])
    if not isinstance(candidates, list):
        raise PlanError("pre-schema integration plan contract has invalid successor provenance")
    matches = [
        item for item in candidates
        if isinstance(item, dict) and item.get("path") == plan_relative
    ]
    if len(matches) != 1:
        raise PlanError("pre-schema integration plan is not one exact contracted successor")
    record = matches[0]
    plan_bytes = read_repository_bytes(root, plan_relative, "pre-schema integration plan")
    plan_digest = byte_digest(plan_bytes)
    acceptance = manifest_list(values, "acceptance")
    if (
        record.get("content_digest") != plan_digest
        or record.get("acceptance_digests") != [acceptance_digest(item) for item in acceptance]
    ):
        raise PlanError("pre-schema integration plan bytes differ from contracted provenance")

    validate_migration_bound_provenance(
        root,
        plan_relative,
        values,
        plan_digest=plan_digest,
        contract_relative=contract_relative,
        contract_bytes=contract_bytes,
        archive_relative=archive_relative,
        archive_bytes=archive_bytes,
    )


def validate_migration_bound_provenance(
    root: Path,
    plan_relative: str,
    values: dict[str, str | list[str]],
    *,
    plan_digest: str,
    contract_relative: str,
    contract_bytes: bytes,
    archive_relative: str,
    archive_bytes: bytes,
) -> None:
    """Bind a pre-schema integration plan to the guardian-backed migration snapshot.

    The replan contract alone lives in the same repository the plan lives in, so
    it proves only internal consistency. The migration snapshot is captured once
    from a clean committed tree while the original guardian is live, so requiring
    an exact match makes the pre-schema exception depend on evidence a later
    in-repository edit cannot reproduce.
    """

    policy = read_repository_bytes(
        root, MIGRATION_BOUNDARY_POLICY_PATH, "validation-witness migration boundary policy"
    )
    if MIGRATION_BOUNDARY_MARKER not in policy:
        raise PlanError(
            "pre-schema integration plan requires the crossed validation-witness migration boundary"
        )

    snapshot = read_repository_json(
        root, MIGRATION_PROVENANCE_PATH, "validation-witness migration provenance"
    )
    if (
        snapshot.get("schema_version") != MIGRATION_PROVENANCE_SCHEMA
        or snapshot.get("operation") != MIGRATION_PROVENANCE_OPERATION
        or snapshot.get("migration_version") != MIGRATION_PROVENANCE_VERSION
    ):
        raise PlanError("validation-witness migration provenance is not the supported snapshot")
    captured_plans = snapshot.get("plans")
    if not isinstance(captured_plans, list):
        raise PlanError("validation-witness migration provenance has no captured plan list")
    matches = [
        item
        for item in captured_plans
        if isinstance(item, dict) and item.get("path") == plan_relative
    ]
    if len(matches) != 1:
        raise PlanError(
            "pre-schema integration plan is not one captured migration plan: " + plan_relative
        )

    validation = manifest_list(values, "validation")
    expected = {
        "acceptance": [
            {"sha256": acceptance_digest(item), "text": item}
            for item in manifest_list(values, "acceptance")
        ],
        "path": plan_relative,
        "plan_sha256": plan_digest,
        "replan_contract": {
            "path": contract_relative,
            "schema_version": 1,
            "sha256": byte_digest(contract_bytes),
        },
        "replanned_source": {
            "path": archive_relative,
            "sha256": byte_digest(archive_bytes),
        },
        "validation": validation,
        "validation_sha256": indented_json_digest(validation),
    }
    if matches[0] != expected:
        raise PlanError(
            "pre-schema integration plan differs from its captured migration provenance"
        )


def manifest_lifecycle_status(text: str) -> str | None:
    """Read the one manifest status a plan file declares.

    The lifecycle status is a manifest field, so it is only meaningful
    before the first `## ` section. Scanning the whole file would accept a
    status line written in prose, and taking one of several would accept a
    file that declares two conflicting statuses, so exactly one top-level
    field in the manifest region is required.
    """

    declared: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            break
        if ":" not in line or line.startswith(" "):
            continue
        key, rest = line.split(":", 1)
        if key.strip() == "status":
            declared.append(rest.strip())
    if len(declared) != 1:
        return None
    return declared[0]


def validate_context_file_identity(context_files: list[str], *, root: Path = ROOT) -> None:
    """Prove every declared context path resolves to the file it names.

    A plan's context inputs are read as evidence, so a path that escapes
    the repository, traverses through a symlink, or points at a plan whose
    lifecycle status has since moved is not the input the plan declared.
    The proof does not depend on which witness an acceptance item maps to,
    because the paths are read the same way either way.

    The `none` sentinel declares that no additional path is needed, so it
    is not a path to prove. A plan that resolves it as one would reject
    every project that legitimately needs no context input.
    """

    seen: set[str] = set()
    root = root.resolve()
    for raw in context_files:
        if raw == CONTEXT_FILES_NONE:
            if len(context_files) != 1:
                raise PlanError(
                    "resolved-context-files cannot mix the none sentinel with a path"
                )
            return
        path = Path(raw)
        if (
            not raw
            or raw != path.as_posix()
            or path.is_absolute()
            or "." in path.parts
            or ".." in path.parts
            or raw in seen
        ):
            raise PlanError(f"resolved-context-files has invalid path: {raw!r}")
        seen.add(raw)
        target = root / path
        reject_symlink_components(root, raw, "resolved-context-files")
        try:
            resolved = target.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise PlanError(f"resolved-context-files cannot resolve: {raw}") from exc
        if not resolved.is_file():
            raise PlanError(f"resolved-context-files requires a regular file: {raw}")
        expected_status = None
        if path.parts[:3] == ("docs", "plan", "checked"):
            expected_status = "checked"
        elif path.parts[:3] == ("docs", "plan", "replanned") and path.suffix == ".md":
            expected_status = "replanned"
        if expected_status is not None:
            declared = manifest_lifecycle_status(resolved.read_text(encoding="utf-8"))
            if declared != expected_status:
                raise PlanError(
                    f"resolved-context-files expected {expected_status} status: {raw}"
                )


def validate_resolved_context_files(context_files: list[str], *, root: Path = ROOT) -> None:
    if not context_files or context_files == [CONTEXT_FILES_NONE]:
        raise PlanError("resolved-context-files requires context_files")
    validate_context_file_identity(context_files, root=root)


def companion_baseline_records(root: Path) -> list[dict[str, Any]]:
    """Read the companion baseline and reject every malformed record.

    A lenient reader is itself a bypass: an edit that corrupts one record
    into a shape the reader skips would hide the plan that record owns and
    let the plan pass with a weakened authoritative sequence. Every record
    and successor is therefore structurally required, so corruption fails
    the check instead of silently narrowing it.
    """

    baseline = read_repository_json(
        root, COMPANION_BASELINE_PATH, "live validation successor companion baseline"
    )
    records = baseline.get("records") if isinstance(baseline, dict) else None
    if (
        not isinstance(baseline, dict)
        or baseline.get("schema_version") != 1
        or not isinstance(records, list)
    ):
        raise PlanError("live validation successor companion baseline is unsupported")
    for record in records:
        successors = record.get("successors") if isinstance(record, dict) else None
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("contract_path"), str)
            or not isinstance(record.get("contract_digest"), str)
            or not isinstance(successors, list)
        ):
            raise PlanError(
                "live validation successor companion baseline has a malformed record"
            )
        for successor in successors:
            if not isinstance(successor, dict) or not isinstance(
                successor.get("path"), str
            ):
                raise PlanError(
                    "live validation successor companion baseline has a malformed successor"
                )
    return records


def companion_successors_for(
    records: list[dict[str, Any]], plan_relative: str
) -> list[dict[str, Any]]:
    return [
        successor
        for record in records
        for successor in record["successors"]
        if successor["path"] == plan_relative
    ]


def companion_baseline_required(root: Path) -> bool:
    """Report whether published schema-1 lineage still demands a baseline.

    The baseline only exists once a schema-1 restructuring transaction has
    published successors, so a project that never restructured a plan has
    none. Any surviving schema-1 contract, however, proves the publication
    happened, which makes a missing baseline evidence of deletion rather
    than evidence of absence.
    """

    directory = root / COMPANION_CONTRACT_DIRECTORY
    try:
        entries = sorted(directory.iterdir())
    except OSError:
        return False
    for entry in entries:
        if entry.suffix != ".json":
            continue
        relative = f"{COMPANION_CONTRACT_DIRECTORY}/{entry.name}"
        try:
            contract = read_repository_json(root, relative, "replan contract")
        except PlanError:
            return True
        if (
            isinstance(contract, dict)
            and contract.get("schema_version") == COMPANION_BASELINE_CONTRACT_SCHEMA
        ):
            return True
    return False


def companion_projected_acceptance(
    successor: dict[str, Any], schema: int
) -> list[str] | None:
    """Read the flat successor acceptance projection a schema may use.

    The schema-1 companion baseline and a schema-2 contract both publish a
    successor's acceptance as one flat digest list. Reading exactly that
    field keeps a successor from presenting another schema's projection
    form as if the transaction had published it.
    """

    if schema not in COMPANION_FLAT_ACCEPTANCE_SCHEMAS:
        return None
    digests = successor.get("acceptance_digests")
    if isinstance(digests, list) and all(isinstance(item, str) for item in digests):
        return list(digests)
    return None


def contract_source_ids(contract: dict[str, Any]) -> list[str] | None:
    sources = contract.get("sources")
    if not isinstance(sources, list) or not sources:
        return None
    ids = [
        source.get("id") for source in sources if isinstance(source, dict)
    ]
    if (
        len(ids) != len(sources)
        or not all(isinstance(value, str) and value for value in ids)
        or len(set(ids)) != len(ids)
    ):
        return None
    return [str(value) for value in ids]


def contract_projected_acceptance(
    contract: dict[str, Any], successor: dict[str, Any], schema: int
) -> list[str] | None:
    """Read the successor acceptance projection the contract's schema publishes.

    A schema-3 transaction couples several stopped sources, so it publishes
    each successor's acceptance as per-source mappings instead of one flat
    list. The projected acceptance is the mapped digests taken in contract
    source order, each kept once, which is the order the transaction wrote
    into the successor plan. Any mapping this reader cannot resolve exactly
    projects nothing, so an unreadable projection fails the comparison
    instead of narrowing it.
    """

    if schema not in SELF_PROJECTING_MAPPED_ACCEPTANCE_SCHEMAS:
        return companion_projected_acceptance(successor, schema)
    source_ids = contract_source_ids(contract)
    mappings = successor.get("acceptance_mappings")
    if source_ids is None or not isinstance(mappings, list) or not mappings:
        return None
    mapped: dict[str, list[str]] = {}
    for mapping in mappings:
        if not isinstance(mapping, dict) or set(mapping) != {
            "source_id",
            "acceptance_digests",
        }:
            return None
        source_id = mapping["source_id"]
        digests = mapping["acceptance_digests"]
        if (
            source_id not in source_ids
            or source_id in mapped
            or not isinstance(digests, list)
            or not digests
            or not all(isinstance(item, str) for item in digests)
            or len(set(digests)) != len(digests)
        ):
            return None
        mapped[source_id] = list(digests)
    if [mapping["source_id"] for mapping in mappings] != [
        source_id for source_id in source_ids if source_id in mapped
    ]:
        return None
    projected: list[str] = []
    for source_id in source_ids:
        for digest in mapped.get(source_id, []):
            if digest not in projected:
                projected.append(digest)
    return projected


def verify_companion_projection(
    successor: dict[str, Any],
    values: dict[str, str | list[str]],
    records: list[dict[str, str]],
    plan_relative: str,
    source: str,
    projected_acceptance: list[str] | None,
) -> None:
    validation = manifest_list(values, "validation")
    expected_acceptance = [
        acceptance_digest(item) for item in manifest_list(values, "acceptance")
    ]
    if (
        successor.get("validation_witness_schema") != COMPANION_PROJECTION_WITNESS_SCHEMA
        or projected_acceptance != expected_acceptance
        or successor.get("authoritative_validation") != validation
        or successor.get("authoritative_validation_digest")
        != compact_json_digest(validation)
        or successor.get("validation_witness_map_digest") != compact_json_digest(records)
    ):
        raise PlanError(
            "in-progress integration plan validation authority differs from the "
            f"{source}: " + plan_relative
        )


def verify_published_contract_publication(
    root: Path,
    plan_relative: str,
    contract_relative: str,
    contract_bytes: bytes,
) -> None:
    """Prove a self-projecting contract is published history, not a written file.

    A schema-2 or schema-3 contract carries its own successor projection,
    so nothing inside the file distinguishes a published contract from a
    hand-written one that claims whatever authority its author wants.
    Shape conformity proves nothing here, because the same actor that
    edits the plan can write a fully shaped contract beside it.

    Committed history is the evidence that actor does not hold. The
    restructuring transaction is the publisher, its contracts and archives
    are committed and never rewritten afterwards, and plan execution has
    no commit authority of its own. This reader therefore takes the
    contract, the replanned index, and every archive that index binds to
    the contract from `HEAD` rather than from the working tree, and
    requires the live contract file to still hold those committed bytes.

    The published lineage must agree with itself across three committed
    files before the projection is read: the index registers the contract,
    each registered archive is terminal `replanned` history naming that
    same contract, and each archive lists this plan as one of the
    successors the contract created.

    The guarantee is bounded by commit authority. An actor that can commit
    a forged contract, its archives, and the index row can still publish
    it; this proof separates plan authorship from publication, not a
    repository owner from their own history.
    """

    if not PUBLISHED_CONTRACT_RE.fullmatch(contract_relative):
        raise PlanError(
            "in-progress integration plan replan contract is outside the published "
            "contract directory: " + contract_relative
        )
    require_repository_history(root)
    committed_contract = committed_blob_bytes(
        root, contract_relative, "published replan contract"
    )
    if committed_contract != contract_bytes:
        raise PlanError(
            "in-progress integration plan replan contract differs from its published "
            "bytes: " + contract_relative
        )
    rows = [row for row in committed_replanned_rows(root) if row[2] == contract_relative]
    if not rows:
        raise PlanError(
            "in-progress integration plan replan contract is not published in the "
            "replanned index: " + contract_relative
        )
    for plan_id, archive_relative, _ in rows:
        archive_match = PUBLISHED_ARCHIVE_RE.fullmatch(archive_relative)
        if archive_match is None or archive_match.group(1) != plan_id:
            raise PlanError(
                "published replanned index row has an invalid archive path: "
                + archive_relative
            )
        try:
            archive_text = committed_blob_bytes(
                root, archive_relative, "published replanned archive"
            ).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PlanError(
                "published replanned archive is not UTF-8: " + archive_relative
            ) from exc
        archive_values = parse_manifest_text(archive_text)
        if (
            manifest_lifecycle_status(archive_text) != "replanned"
            or manifest_scalar(archive_values, "replan_contract") != contract_relative
        ):
            raise PlanError(
                "published replanned archive is not terminal history for this "
                "contract: " + archive_relative
            )
        if plan_relative not in manifest_list(archive_values, "successor_plans"):
            raise PlanError(
                "published replanned archive does not create this integration plan: "
                + archive_relative
            )


def validate_self_projecting_contract_authority(
    root: Path,
    plan_relative: str,
    values: dict[str, str | list[str]],
    records: list[dict[str, str]],
    contract_relative: str,
    contract_bytes: bytes,
    contract: dict[str, Any],
    schema: int,
) -> None:
    """Compare live validation authority with a proven contract's projection."""

    if contract.get("contract_path") != contract_relative:
        raise PlanError(
            "in-progress integration plan replan contract identity differs: "
            + contract_relative
        )
    verify_published_contract_publication(
        root, plan_relative, contract_relative, contract_bytes
    )
    successors = contract.get("successors")
    if not isinstance(successors, list):
        raise PlanError(
            "published replan contract has invalid successor provenance: "
            + contract_relative
        )
    matches = [
        successor
        for successor in successors
        if isinstance(successor, dict) and successor.get("path") == plan_relative
    ]
    if len(matches) != 1:
        raise PlanError(
            "in-progress integration plan is not one published contract successor: "
            + plan_relative
        )
    verify_companion_projection(
        matches[0],
        values,
        records,
        plan_relative,
        "published replan contract",
        contract_projected_acceptance(contract, matches[0], schema),
    )


def validate_companion_validation_authority(
    plan_path: Path,
    values: dict[str, str | list[str]],
    records: list[dict[str, str]],
) -> None:
    """Compare live validation authority with its published projection.

    A restructuring transaction writes the authoritative command sequence a
    successor was accepted with exactly once and never rewrites it, so that
    projection is the only surviving record of the sequence. Comparing
    before a witness map is accepted stops a later edit from removing or
    weakening the sequence and then remapping the acceptance onto whatever
    remains.

    Schema-1 lineage is proven by the companion baseline the transaction
    publishes beside the contract. Schema-2 and schema-3 transactions
    publish the projection inside the contract instead, so there is no
    second live record to compare against; that lineage is proven from
    committed history by `verify_published_contract_publication` and stays
    refused whenever the publication cannot be shown. A contract that is
    neither a baseline record nor proven history is refused rather than
    trusted, whatever shape it has.

    Every skip is itself a proof obligation: a plan without contract
    lineage must be unknown to a present baseline and must carry no
    inherited restructuring lineage, and a missing baseline must be matched
    by an absence of schema-1 lineage that could have published one.

    Whether the obligation applies at all still follows the witness-map
    schema's own `status` and `integration_gates` gate, which this function
    does not widen. A plan that clears those fields to escape the gate is
    refused by `scripts/restructure-plan.py --verify` instead, which treats
    both as protected lifecycle state.
    """

    root, plan_relative = plan_repository_root(plan_path)
    baseline_present = True
    try:
        os.lstat(root / COMPANION_BASELINE_PATH)
    except OSError:
        baseline_present = False

    baseline_records: list[dict[str, Any]] = []
    if baseline_present:
        baseline_records = companion_baseline_records(root)
    elif companion_baseline_required(root):
        raise PlanError(
            "published schema-1 lineage has no live validation successor companion "
            "baseline: " + COMPANION_BASELINE_PATH
        )

    published = companion_successors_for(baseline_records, plan_relative)
    if len(published) > 1:
        raise PlanError(
            "live validation successor companion baseline names one plan more than "
            "once: " + plan_relative
        )

    contract_relative = manifest_scalar(values, "replan_contract")
    if not contract_relative:
        if published:
            raise PlanError(
                "in-progress integration plan drops the contract lineage the companion "
                "baseline still records: " + plan_relative
            )
        residue = [
            field
            for field in COMPANION_LINEAGE_RESIDUE_FIELDS
            if values.get(field) or manifest_scalar(values, field)
        ]
        if residue:
            raise PlanError(
                "in-progress integration plan keeps restructuring lineage without a "
                f"replan contract ({', '.join(residue)}): " + plan_relative
            )
        return

    contract_relative = normalized_repository_path(
        contract_relative, "in-progress integration plan replan_contract"
    )
    contract_bytes = read_repository_bytes(
        root, contract_relative, "in-progress integration plan replan contract"
    )
    try:
        contract = json.loads(contract_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlanError(
            "in-progress integration plan has an unreadable replan contract: " + contract_relative
        ) from exc
    if not isinstance(contract, dict):
        raise PlanError(
            "in-progress integration plan has an unreadable replan contract: " + contract_relative
        )

    owned = [
        record for record in baseline_records if record["contract_path"] == contract_relative
    ]
    if len(owned) > 1:
        raise PlanError(
            "live validation successor companion baseline names one contract more than once"
        )

    if owned:
        if owned[0]["contract_digest"] != byte_digest(contract_bytes):
            raise PlanError(
                "in-progress integration plan replan contract differs from the companion "
                "baseline: " + contract_relative
            )
        matches = [
            successor
            for successor in owned[0]["successors"]
            if successor["path"] == plan_relative
        ]
        if len(matches) != 1 or len(published) != 1:
            raise PlanError(
                "in-progress integration plan is not one companion baseline successor: "
                + plan_relative
            )
        verify_companion_projection(
            matches[0],
            values,
            records,
            plan_relative,
            "companion baseline",
            companion_projected_acceptance(
                matches[0], COMPANION_BASELINE_CONTRACT_SCHEMA
            ),
        )
        return

    schema = contract.get("schema_version")
    if schema in SELF_PROJECTING_CONTRACT_SCHEMAS:
        validate_self_projecting_contract_authority(
            root,
            plan_relative,
            values,
            records,
            contract_relative,
            contract_bytes,
            contract,
            schema,
        )
        return

    raise PlanError(
        "in-progress integration plan has no published companion validation authority: "
        + plan_relative
    )


def validate_validation_witness_map(
    values: dict[str, str | list[str]],
    *,
    plan_path: Path | None = None,
) -> list[dict[str, str]]:
    acceptance = values.get("acceptance", [])
    focused = values.get("focused_validation", [])
    authoritative = values.get("validation", [])
    raw_map = values.get("validation_witness_map", [])
    integration_gates = values.get("integration_gates", [])
    status = manifest_scalar(values, "status")
    schema = manifest_scalar(values, "validation_witness_schema")
    for key, value in (
        ("acceptance", acceptance),
        ("focused_validation", focused),
        ("validation", authoritative),
        ("validation_witness_map", raw_map),
        ("integration_gates", integration_gates),
    ):
        if not isinstance(value, list):
            raise PlanError(f"plan {key} must be a list")

    required = status in WITNESS_REQUIRED_STATUSES and bool(integration_gates)
    if required and plan_path is not None:
        declared_context = values.get("context_files", [])
        if not isinstance(declared_context, list):
            raise PlanError("plan context_files must be a list")
        validate_context_file_identity(
            declared_context, root=plan_repository_root(plan_path)[0]
        )
    if not schema:
        if raw_map:
            raise PlanError("validation_witness_map requires validation_witness_schema: 1")
        if required:
            if plan_path is None:
                raise PlanError("pre-schema integration plan requires provenance validation")
            validate_legacy_witness_provenance(plan_path, values)
        return []
    if schema != "1":
        raise PlanError(f"unsupported validation_witness_schema: {schema!r}")

    if not raw_map:
        if required:
            raise PlanError("in-progress integration plan missing validation_witness_map")
        return []
    if not acceptance:
        raise PlanError("validation_witness_map requires at least one acceptance item")

    acceptance_digests = [acceptance_digest(item) for item in acceptance]
    if len(acceptance_digests) != len(set(acceptance_digests)):
        raise PlanError("acceptance items must be unique before witness mapping")

    records: list[dict[str, str]] = []
    for index, raw in enumerate(raw_map, start=1):
        try:
            record = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise PlanError(f"validation_witness_map entry {index} is not valid JSON") from exc
        if not isinstance(record, dict):
            raise PlanError(f"validation_witness_map entry {index} must be an object")
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in record.items()):
            raise PlanError(f"validation_witness_map entry {index} values must be text")

        stage = record.get("stage", "")
        expected_keys = {"acceptance_sha256", "stage", "witness"}
        if stage == "authoritative":
            expected_keys.add("authoritative_only_reason")
        if set(record) != expected_keys:
            raise PlanError(
                f"validation_witness_map entry {index} has invalid fields for stage {stage!r}"
            )
        if stage not in VALIDATION_WITNESS_STAGES:
            raise PlanError(f"validation_witness_map entry {index} has invalid stage: {stage!r}")

        witness = record["witness"]
        if not witness or witness != witness.strip():
            raise PlanError(f"validation_witness_map entry {index} has invalid witness")
        if stage == "static":
            if witness not in STATIC_VALIDATION_WITNESSES:
                raise PlanError(f"validation_witness_map entry {index} has unknown static witness")
            if witness == "resolved-context-files":
                context_files = values.get("context_files", [])
                if not isinstance(context_files, list):
                    raise PlanError("plan context_files must be a list")
                root = plan_repository_root(plan_path)[0] if plan_path is not None else ROOT
                validate_resolved_context_files(context_files, root=root)
        elif stage == "focused":
            if witness not in focused:
                raise PlanError(
                    f"validation_witness_map entry {index} focused witness is not declared"
                )
        else:
            if witness not in authoritative:
                raise PlanError(
                    f"validation_witness_map entry {index} authoritative witness is not declared"
                )
            if witness in focused:
                raise PlanError(
                    f"validation_witness_map entry {index} skips an available focused witness"
                )
            reason = record["authoritative_only_reason"]
            if (
                not reason
                or reason != reason.strip()
                or len(reason.encode("utf-8")) > VALIDATION_WITNESS_REASON_MAX_BYTES
                or any(ord(char) < 0x20 for char in reason)
            ):
                raise PlanError(
                    f"validation_witness_map entry {index} has invalid authoritative-only reason"
                )
        records.append(record)

    mapped_digests = [record["acceptance_sha256"] for record in records]
    if mapped_digests != acceptance_digests:
        raise PlanError(
            "validation_witness_map must cover acceptance items exactly once and in source order"
        )
    if required and plan_path is not None:
        validate_companion_validation_authority(plan_path, values, records)
    return records


def is_admission_placeholder(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return stripped.lower().strip(" .") in ADMISSION_PLACEHOLDER_VALUES


def bounded_admission_text(value: object, label: str, maximum_bytes: int) -> str:
    if not isinstance(value, str):
        raise PlanError(f"{label} must be text")
    if (
        value != value.strip()
        or is_admission_placeholder(value)
        or len(value.encode("utf-8")) > maximum_bytes
        or any(ord(char) < 0x20 for char in value)
    ):
        raise PlanError(f"{label} must be bounded non-placeholder text")
    return value


def has_admission_record(values: dict[str, str | list[str]]) -> bool:
    return any(values.get(field) not in (None, "", []) for field in ADMISSION_FIELDS)


def product_changing_write_scope(write_scope: list[str]) -> list[str]:
    """Return the declared write paths that leave plan-lifecycle records."""

    return [
        path
        for path in write_scope
        if not is_admission_placeholder(path)
        and path != CONTEXT_FILES_NONE
        and not path.startswith(ADMISSION_LIFECYCLE_PREFIXES)
    ]


def validate_admission_record(
    values: dict[str, str | list[str]],
) -> list[dict[str, str]]:
    """Validate the executable admission contract of one numbered plan."""

    purpose = manifest_scalar(values, "plan_purpose").strip()
    if purpose not in PLAN_PURPOSE_VALUES:
        raise PlanError("plan_purpose must be implementation")

    for key in ("feasibility_evidence", "completion_conditions", "completion_witness_map",
                "focused_validation", "write_scope"):
        if not isinstance(values.get(key, []), list):
            raise PlanError(f"plan {key} must be a list")
    evidence_items = values.get("feasibility_evidence", [])
    conditions = values.get("completion_conditions", [])
    raw_map = values.get("completion_witness_map", [])
    focused = values.get("focused_validation", [])
    write_scope = values.get("write_scope", [])
    assert isinstance(evidence_items, list)
    assert isinstance(conditions, list)
    assert isinstance(raw_map, list)
    assert isinstance(focused, list)
    assert isinstance(write_scope, list)

    if not evidence_items or len(evidence_items) > MAX_FEASIBILITY_EVIDENCE:
        raise PlanError(
            "feasibility_evidence must declare between one and "
            f"{MAX_FEASIBILITY_EVIDENCE} bounded records"
        )
    if len(evidence_items) != len(set(evidence_items)):
        raise PlanError("feasibility_evidence must not repeat a record")
    for index, raw in enumerate(evidence_items, start=1):
        try:
            record = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise PlanError(f"feasibility_evidence entry {index} is not valid JSON") from exc
        if not isinstance(record, dict) or set(record) != {"kind", "evidence"}:
            raise PlanError(
                f"feasibility_evidence entry {index} must declare exactly kind and evidence"
            )
        if record["kind"] not in FEASIBILITY_EVIDENCE_KINDS:
            raise PlanError(
                f"feasibility_evidence entry {index} has an unsupported kind: {record['kind']!r}"
            )
        bounded_admission_text(
            record["evidence"],
            f"feasibility_evidence entry {index} evidence",
            FEASIBILITY_EVIDENCE_MAX_BYTES,
        )

    if not conditions or len(conditions) > MAX_COMPLETION_CONDITIONS:
        raise PlanError(
            "completion_conditions must declare between one and "
            f"{MAX_COMPLETION_CONDITIONS} plan-local predicates"
        )
    if len(conditions) != len(set(conditions)):
        raise PlanError("completion_conditions must be unique")
    for index, condition in enumerate(conditions, start=1):
        bounded_admission_text(
            condition, f"completion_conditions entry {index}", COMPLETION_CONDITION_MAX_BYTES
        )

    records: list[dict[str, str]] = []
    for index, raw in enumerate(raw_map, start=1):
        try:
            record = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise PlanError(f"completion_witness_map entry {index} is not valid JSON") from exc
        if not isinstance(record, dict) or set(record) != {"condition_sha256", "witness"}:
            raise PlanError(
                f"completion_witness_map entry {index} must declare exactly "
                "condition_sha256 and witness"
            )
        if not all(isinstance(value, str) for value in record.values()):
            raise PlanError(f"completion_witness_map entry {index} values must be text")
        witness = record["witness"]
        if not witness or witness != witness.strip():
            raise PlanError(f"completion_witness_map entry {index} has an invalid witness")
        if witness not in focused:
            raise PlanError(
                f"completion_witness_map entry {index} witness is not a declared "
                "focused_validation command"
            )
        records.append(record)

    condition_digests = [acceptance_digest(item) for item in conditions]
    if [record["condition_sha256"] for record in records] != condition_digests:
        raise PlanError(
            "completion_witness_map must cover completion_conditions exactly once "
            "and in source order"
        )

    if not product_changing_write_scope(write_scope):
        raise PlanError(
            "plan_purpose: implementation requires a write_scope path outside "
            "plan-lifecycle records"
        )

    # A Tier 1 plan carries one acceptance item, so it can never partition that
    # item into the nonempty retained and deferred sides a bounded descope needs.
    # Checking the count at admission keeps that stop honest instead of pushing
    # the impossible partition onto the stopped run.
    if manifest_scalar(values, "implementation_tier").strip() == TIER_ONE_VALUE:
        acceptance = values.get("acceptance", [])
        if not isinstance(acceptance, list):
            raise PlanError("plan acceptance must be a list")
        if len(acceptance) != 1:
            raise PlanError(
                "implementation_tier: 1 requires exactly one acceptance item, not "
                f"{len(acceptance)}; a plan that needs several acceptance items is Tier 2"
            )
    return records


def status_text(text: str, status: str) -> str:
    updated, count = re.subn(r"^status: .*", f"status: {status}", text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise PlanError("plan must contain exactly one leading status field to update")
    if status != "shelved":
        updated = re.sub(
            r"^(shelved_reason|shelved_at): .*\n", "", updated, flags=re.MULTILINE
        )
    return updated


def rewrite_status(path: str, status: str) -> None:
    target = ROOT / path
    if target.parent != ACTIVE_DIR or not target.is_file():
        raise PlanError(f"missing plan: {path}")
    if status == "in_progress":
        require_predecessors_checked(target)
    content = status_text(target.read_text(encoding="utf-8"), status)
    atomic_write_text(target, content)


def copy_with_status_exclusive(source: str, destination: str, status: str) -> None:
    source_path = ROOT / source
    destination_path = ROOT / destination
    if source_path.parent not in {ACTIVE_DIR, BACKLOG_DIR, SHELVED_DIR} or not source_path.is_file():
        raise PlanError(f"missing plan: {source}")
    if destination_path.parent != ACTIVE_DIR and CHECKED_DIR not in destination_path.parents:
        raise PlanError(f"destination is outside active or checked plan directories: {destination}")
    if status == "in_progress":
        require_predecessors_checked(source_path)
    content = status_text(source_path.read_text(encoding="utf-8"), status)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(destination_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise PlanError(f"destination already exists: {destination}") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
    except BaseException:
        destination_path.unlink(missing_ok=True)
        raise


def context_lines(path: Path) -> list[str]:
    values = require_manifest_fields(path, CONTEXT_REQUIRED)
    return [f"{field}={manifest_joined(values, CONTEXT_KEYS[field])}" for field in CONTEXT_FIELDS]


def plan_ids() -> set[int]:
    ids: set[int] = set()
    for directory in PLAN_DIRS:
        if not directory.exists():
            continue
        pattern = (
            "**/[0-9][0-9][0-9]-*.md"
            if directory in {CHECKED_DIR, REPLANNED_DIR}
            else "[0-9][0-9][0-9]-*.md"
        )
        for path in directory.glob(pattern):
            ids.add(int(path.name[:3]))
    if CHECKED.exists():
        for line in CHECKED.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^(\d{3})\s+", line)
            if match:
                ids.add(int(match.group(1)))
    return ids


def next_id() -> str:
    """Report the smallest identifier no local file and no live reservation holds.

    This is a report, not an allocation. It still consults the shared reservation
    ledger so that it does not name an identifier another linked worktree has
    already reserved and not yet published.
    """

    ids = plan_ids()
    if shared_lifecycle_state_available():
        ids |= locate_worktree_guard().reserved_plan_ids(ROOT)
    value = 1
    while value in ids:
        value += 1
    return f"{value:03d}"


def read_active_rows() -> list[tuple[str, str, str]]:
    if not PLAN.exists():
        return []
    try:
        return parse_active_index(read_active_index(PLAN))
    except ActiveIndexError as exc:
        raise PlanError(str(exc)) from exc


def write_active_rows(rows: list[tuple[str, str, str]]) -> None:
    try:
        content = render_active_index(rows)
    except ActiveIndexError as exc:
        raise PlanError(str(exc)) from exc
    atomic_write_text(PLAN, content)


def add_active(plan_id: str, path: str, status: str = "in_progress") -> None:
    with lifecycle_lock():
        rows = [row for row in read_active_rows() if row[0] != plan_id]
        rows.append((plan_id, path, status))
        write_active_rows(rows)


def check_active_mapping(plan_id: str, path: str, status: str) -> None:
    matches = [row for row in read_active_rows() if row[0] == plan_id]
    if len(matches) != 1:
        raise PlanError(f"active index must contain exactly one row for {plan_id}")
    if matches[0] != (plan_id, path, status):
        raise PlanError(
            f"active index mapping mismatch for {plan_id}: expected {path} with status {status}"
        )
    if status == "in_progress":
        require_predecessors_checked(ROOT / path)


def set_active_status(plan_id: str, path: str, old_status: str, new_status: str) -> None:
    if new_status == "in_progress":
        require_predecessors_checked(ROOT / path)
    with lifecycle_lock():
        check_active_mapping(plan_id, path, old_status)
        rows = [
            (row_id, row_path, new_status) if row_id == plan_id else (row_id, row_path, row_status)
            for row_id, row_path, row_status in read_active_rows()
        ]
        write_active_rows(rows)


def complete_transition(plan_id: str, path: str, old_status: str) -> None:
    if old_status != "in_progress":
        raise PlanError(f"completion transition requires in_progress status, got: {old_status}")
    target = ROOT / path
    if target.parent != ACTIVE_DIR:
        raise PlanError(f"active plan path is outside active directory: {path}")
    with lifecycle_lock():
        check_active_mapping(plan_id, path, old_status)
        original_plan = target.read_text(encoding="utf-8")
        rows = read_active_rows()
        updated_plan = status_text(original_plan, "ready_to_archive")
        if [row for row in rows if row[0] == plan_id] != [(plan_id, path, old_status)]:
            raise PlanError(f"active index must contain exactly one row for {plan_id}")
        try:
            updated_index = render_active_index(
                [
                    (row[0], row[1], "ready_to_archive") if row[0] == plan_id else row
                    for row in rows
                ]
            )
        except ActiveIndexError as exc:
            raise PlanError(str(exc)) from exc
        atomic_write_text(target, updated_plan)
        try:
            atomic_write_text(PLAN, updated_index)
        except BaseException:
            atomic_write_text(target, original_plan)
            raise


def remove_active(plan_id: str) -> None:
    with lifecycle_lock():
        rows = [row for row in read_active_rows() if row[0] != plan_id]
        write_active_rows(rows)


def append_checked(plan_id: str, path: str) -> None:
    with lifecycle_lock():
        lines = CHECKED.read_text(encoding="utf-8").splitlines() if CHECKED.exists() else ["# Checked Plan Index", "", "id\tpath"]
        if any(line.startswith(f"{plan_id}\t") for line in lines):
            raise PlanError(f"checked index already contains plan id {plan_id}")
        if any(line.endswith(f"\t{path}") for line in lines):
            raise PlanError(f"checked index already contains path {path}")
        lines.append(f"{plan_id}\t{path}")
        atomic_write_text(CHECKED, "\n".join(lines).rstrip() + "\n")


def _plan_paths_for_id(plan_id: str) -> list[Path]:
    paths: list[Path] = []
    for directory in PLAN_DIRS:
        if not directory.exists():
            continue
        pattern = (
            f"**/{plan_id}-*.md"
            if directory in {CHECKED_DIR, REPLANNED_DIR}
            else f"{plan_id}-*.md"
        )
        paths.extend(directory.glob(pattern))
    return paths


def check_promotion(plan_id: str, source: str, destination: str) -> None:
    source_path = ROOT / source
    destination_path = ROOT / destination
    if not source_path.is_file():
        raise PlanError(f"missing promotion source: {source}")
    if destination_path.exists():
        raise PlanError(f"promotion destination already exists: {destination}")
    collisions = [path for path in _plan_paths_for_id(plan_id) if path != source_path]
    if collisions:
        raise PlanError(f"plan id {plan_id} already exists at {collisions[0].relative_to(ROOT)}")
    if any(row[0] == plan_id or row[1] == destination for row in read_active_rows()):
        raise PlanError(f"active index conflicts with promotion of plan id {plan_id}")
    if CHECKED.exists():
        for line in CHECKED.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{plan_id}\t"):
                raise PlanError(f"checked index already contains plan id {plan_id}")


def check_archive_target(plan_id: str, destination: str) -> None:
    destination_path = ROOT / destination
    if destination_path.exists():
        raise PlanError(f"archive already exists: {destination}")
    collisions = _plan_paths_for_id(plan_id)
    checked_collisions = [path for path in collisions if CHECKED_DIR in path.parents]
    if checked_collisions:
        raise PlanError(
            f"checked archive already contains plan id {plan_id}: {checked_collisions[0].relative_to(ROOT)}"
        )
    if CHECKED.exists():
        for line in CHECKED.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{plan_id}\t") or line.endswith(f"\t{destination}"):
                raise PlanError(f"checked index conflicts with archive target {destination}")
