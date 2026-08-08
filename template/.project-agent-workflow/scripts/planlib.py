"""Shared helpers for plan manifest and index handling."""

from __future__ import annotations

import os
import re
import tempfile
import fcntl
from contextlib import contextmanager
from pathlib import Path


ROOT = Path.cwd()
SPEC_INDEX = ROOT / ".project-agent-workflow/docs/agent/spec-index.yaml"
PLAN = ROOT / "docs/plan/plan.md"
CHECKED = ROOT / "docs/plan/checked.md"
ACTIVE_DIR = ROOT / "docs/plan/active"
BACKLOG_DIR = ROOT / "docs/plan/backlog"
CHECKED_DIR = ROOT / "docs/plan/checked"
OPEN_PLAN_DIRS = [ACTIVE_DIR, BACKLOG_DIR]
PLAN_DIRS = [*OPEN_PLAN_DIRS, CHECKED_DIR]

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
    "expected_output",
    "checked_summary_ja",
    "completion_deferred_reason",
}
LIST_KEYS = {
    "task_types",
    "target_files",
    "write_scope",
    "context_files",
    "target_json",
    "required_specs",
    "validation",
    "acceptance",
    "acceptance_focus",
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
class PlanError(ValueError):
    """Raised for invalid plan docs or indexes."""


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


def routing_contract() -> tuple[set[str], dict[str, set[str]]]:
    if not SPEC_INDEX.is_file():
        return set(), {}
    default_reads: set[str] = set()
    route_requirements: dict[str, set[str]] = {}
    section = ""
    in_task_types = False
    current_route = ""
    for line in SPEC_INDEX.read_text(encoding="utf-8").splitlines():
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


def task_type_values() -> set[str]:
    _, route_requirements = routing_contract()
    return set(route_requirements)


def required_specs_for(task_types: list[str]) -> set[str]:
    default_reads, route_requirements = routing_contract()
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


def status_text(text: str, status: str) -> str:
    updated, count = re.subn(r"^status: .*", f"status: {status}", text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise PlanError("plan must contain exactly one leading status field to update")
    return updated


def rewrite_status(path: str, status: str) -> None:
    target = ROOT / path
    if target.parent != ACTIVE_DIR or not target.is_file():
        raise PlanError(f"missing plan: {path}")
    content = status_text(target.read_text(encoding="utf-8"), status)
    atomic_write_text(target, content)


def copy_with_status_exclusive(source: str, destination: str, status: str) -> None:
    source_path = ROOT / source
    destination_path = ROOT / destination
    if source_path.parent not in {ACTIVE_DIR, BACKLOG_DIR} or not source_path.is_file():
        raise PlanError(f"missing plan: {source}")
    if destination_path.parent != ACTIVE_DIR and CHECKED_DIR not in destination_path.parents:
        raise PlanError(f"destination is outside active or checked plan directories: {destination}")
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
            if directory == CHECKED_DIR
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


def set_active_status(plan_id: str, path: str, old_status: str, new_status: str) -> None:
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
        pattern = f"**/{plan_id}-*.md" if directory == CHECKED_DIR else f"{plan_id}-*.md"
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
