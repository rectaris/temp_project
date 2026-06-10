"""Shared helpers for plan manifest and index handling."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path.cwd()
PLAN = ROOT / "docs/plan/plan.md"
CHECKED = ROOT / "docs/plan/checked.md"
PLAN_DIRS = [ROOT / "docs/plan/active", ROOT / "docs/plan/backlog", ROOT / "docs/plan/checked"]

REQUIRED_FIELDS = (
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
}
LIST_KEYS = {
    "target_files",
    "target_json",
    "required_specs",
    "validation",
    "acceptance",
    "acceptance_focus",
}
CONTEXT_FIELDS = (
    "TASK_TYPE",
    "REQUIRED_SPECS",
    "TARGET_FILES",
    "TARGET_JSON",
    "VALIDATION",
    "EXPECTED_OUTPUT",
)
CONTEXT_KEYS = {
    "TASK_TYPE": "task_type",
    "REQUIRED_SPECS": "required_specs",
    "TARGET_FILES": "target_files",
    "TARGET_JSON": "target_json",
    "VALIDATION": "validation",
    "EXPECTED_OUTPUT": "expected_output",
}
CONTEXT_REQUIRED = ("task_type", "target_files", "required_specs", "validation", "expected_output")


class PlanError(ValueError):
    """Raised for invalid plan docs or indexes."""


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


def context_lines(path: Path) -> list[str]:
    values = require_manifest_fields(path, CONTEXT_REQUIRED)
    return [f"{field}={manifest_joined(values, CONTEXT_KEYS[field])}" for field in CONTEXT_FIELDS]


def plan_ids() -> set[int]:
    ids: set[int] = set()
    for directory in PLAN_DIRS:
        if not directory.exists():
            continue
        for path in directory.glob("[0-9][0-9][0-9]-*.md"):
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
    rows = [row for row in read_active_rows() if row[0] != plan_id]
    rows.append((plan_id, path, status))
    write_active_rows(rows)


def remove_active(plan_id: str) -> None:
    rows = [row for row in read_active_rows() if row[0] != plan_id]
    write_active_rows(rows)


def append_checked(plan_id: str, path: str) -> None:
    lines = CHECKED.read_text(encoding="utf-8").splitlines() if CHECKED.exists() else ["# Checked Plan Index", "", "id\tpath"]
    if any(line.startswith(f"{plan_id}\t") for line in lines):
        return
    lines.append(f"{plan_id}\t{path}")
    CHECKED.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
