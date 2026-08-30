"""Shared helpers for plan manifest and index handling."""

from __future__ import annotations

import json
import hashlib
import os
import re
import tempfile
import fcntl
from contextlib import contextmanager
from pathlib import Path


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
    "acceptance",
    "acceptance_focus",
    "integration_gates",
    "predecessor_plans",
    "successor_plans",
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
WITNESS_REQUIRED_STATUSES = {"in_progress"}
VALIDATION_WITNESS_STAGES = {"static", "focused", "authoritative"}
STATIC_VALIDATION_WITNESSES = {"resolved-context-files"}
VALIDATION_WITNESS_REASON_MAX_BYTES = 240
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


@contextmanager
def lifecycle_lock():
    lock_dir = ROOT / ".agent-artifacts"
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir / "plan-lifecycle.lock").open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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

    values: dict[str, str | list[str]] = {key: [] for key in LIST_KEYS}
    current: str | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
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
    contract_path = Path(contract_raw)
    if (
        not contract_raw
        or contract_raw != contract_path.as_posix()
        or contract_path.is_absolute()
        or ".." in contract_path.parts
    ):
        raise PlanError("pre-schema integration plan lacks normalized replan_contract provenance")
    try:
        contract = json.loads((root / contract_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlanError("pre-schema integration plan has unreadable replan_contract provenance") from exc
    if not isinstance(contract, dict) or contract.get("schema_version") != 1:
        raise PlanError("pre-schema integration plan has unsupported replan_contract provenance")
    if contract.get("contract_path") != contract_raw:
        raise PlanError("pre-schema integration plan contract identity differs")

    archive_raw = contract.get("archive_path")
    if not isinstance(archive_raw, str):
        raise PlanError("pre-schema integration plan contract lacks a replanned archive")
    archive_path = Path(archive_raw)
    if (
        archive_raw != archive_path.as_posix()
        or archive_path.parts[:3] != ("docs", "plan", "replanned")
        or archive_path.suffix != ".md"
    ):
        raise PlanError("pre-schema integration plan contract has invalid archive provenance")
    try:
        archive_text = (root / archive_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
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
    plan_digest = acceptance_digest(plan_path.read_text(encoding="utf-8"))
    acceptance = values.get("acceptance", [])
    if not isinstance(acceptance, list):
        raise PlanError("plan acceptance must be a list")
    if (
        record.get("content_digest") != plan_digest
        or record.get("acceptance_digests") != [acceptance_digest(item) for item in acceptance]
    ):
        raise PlanError("pre-schema integration plan bytes differ from contracted provenance")


def validate_resolved_context_files(context_files: list[str], *, root: Path = ROOT) -> None:
    if not context_files:
        raise PlanError("resolved-context-files requires context_files")
    seen: set[str] = set()
    root = root.resolve()
    for raw in context_files:
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
        try:
            resolved = target.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise PlanError(f"resolved-context-files cannot resolve: {raw}") from exc
        if target.is_symlink() or not resolved.is_file():
            raise PlanError(f"resolved-context-files requires a regular file: {raw}")
        expected_status = None
        if path.parts[:3] == ("docs", "plan", "checked"):
            expected_status = "checked"
        elif path.parts[:3] == ("docs", "plan", "replanned") and path.suffix == ".md":
            expected_status = "replanned"
        if expected_status is not None:
            match = re.search(
                r"^status:\s*(\S+)\s*$",
                resolved.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            if match is None or match.group(1) != expected_status:
                raise PlanError(
                    f"resolved-context-files expected {expected_status} status: {raw}"
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
    ids = plan_ids()
    value = 1
    while value in ids:
        value += 1
    return f"{value:03d}"


def read_active_rows() -> list[tuple[str, str, str]]:
    if not PLAN.exists():
        return []
    rows: list[tuple[str, str, str]] = []
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\d{3}\t", line):
            continue
        parts = line.split("\t")
        if len(parts) == 3:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def write_active_rows(rows: list[tuple[str, str, str]]) -> None:
    if not rows:
        PLAN.write_text("# Active Plan\n\nNo active development items.\n", encoding="utf-8")
        return
    body = "\n".join("\t".join(row) for row in rows)
    PLAN.write_text(f"# Active Plan\n\nid\tpath\tstatus\n{body}\n", encoding="utf-8")


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
        original_index = PLAN.read_text(encoding="utf-8")
        updated_plan = status_text(original_plan, "ready_to_archive")
        expected = f"{plan_id}\t{path}\t{old_status}"
        replacement = f"{plan_id}\t{path}\tready_to_archive"
        lines = original_index.splitlines()
        if lines.count(expected) != 1:
            raise PlanError(f"active index must contain exactly one row for {plan_id}")
        updated_index = "\n".join(replacement if line == expected else line for line in lines).rstrip() + "\n"
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
