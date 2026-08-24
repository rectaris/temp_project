#!/usr/bin/env python3
"""Atomically replace one stopped active plan without changing its requirements."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import stat
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True


ROOT = Path.cwd()
ACTIVE_INDEX = ROOT / "docs/plan/plan.md"
REPLANNED_INDEX = ROOT / "docs/plan/replanned.md"
LOCK = ROOT / ".agent-artifacts/plan-lifecycle.lock"
MAX_SPEC_BYTES = 1_048_576
MAX_PLANS = 8
ACTIVE_PLAN_STATUSES = {"in_progress", "ready_to_archive", "deferred", "replan_required"}
REQUIRED_PLAN_FIELDS = {
    "status", "task_types", "review_class", "human_design_required", "human_approval_status",
    "write_scope", "context_files", "required_specs", "validation", "acceptance",
    "checked_summary_ja",
}
REASON_CODES = {
    "scope_drift",
    "spec_drift",
    "security_boundary_drift",
    "multiple_independent_invariants",
    "post_authoritative_design_change",
    "candidate_correction_budget_exhausted",
    "parent_remediation_budget_exhausted",
}
PLAN_PATH_RE = re.compile(r"docs/plan/active/([0-9]{3})-([a-z0-9][a-z0-9-]*)\.md")
ARCHIVE_PATH_RE = re.compile(
    r"docs/plan/replanned/[0-9]{4}/[0-9]{2}/(?:01-15|16-31)/([0-9]{3}-[a-z0-9][a-z0-9-]*\.md)"
)
CONTRACT_PATH_RE = re.compile(r"docs/plan/replanned/contracts/[0-9]{3}-[a-z0-9][a-z0-9-]*\.json")
COMPANION_PATH = "docs/plan/replanned/baselines/live-validation-successors-v1.json"
COMPANION_PLAN_PATH = "docs/plan/active/190-migrate-live-plan-contracts.md"
SHA_RE = re.compile(r"sha256:[0-9a-f]{64}")
CHECKED_PATH_RE = re.compile(
    r"docs/plan/checked/[0-9]{4}/[0-9]{2}/(?:01-15|16-31)/"
    r"([0-9]{3})-([a-z0-9][a-z0-9-]*)\.md"
)


class RestructureError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_digest(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def exact_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise RestructureError(f"{label} must contain exactly: {', '.join(sorted(keys))}")
    return value


def normalized_path(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise RestructureError(f"invalid {label}: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RestructureError(f"non-normalized {label}: {value!r}")
    return value


def reject_symlink_ancestors(relative: str, *, include_target: bool) -> None:
    current = ROOT
    parts = PurePosixPath(relative).parts
    limit = len(parts) if include_target else len(parts) - 1
    for part in parts[:limit]:
        current /= part
        if current.is_symlink():
            raise RestructureError(f"symlink path component is not allowed: {current.relative_to(ROOT)}")


def run_git(*args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if completed.returncode != 0:
        raise RestructureError(completed.stderr.decode("utf-8", "replace").strip() or "git failed")
    return completed.stdout


def current_head() -> str:
    repository_root = run_git("rev-parse", "--show-toplevel").decode().strip()
    if Path(repository_root).resolve() != ROOT.resolve():
        raise RestructureError("run plan restructuring from the repository root")
    value = run_git("rev-parse", "HEAD").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise RestructureError("git HEAD is not a full object id")
    return value


def parse_manifest(text: str) -> dict[str, str | list[str]]:
    values: dict[str, str | list[str]] = {}
    current: str | None = None
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            break
        if not line.strip():
            continue
        if ":" in line and not line.startswith(" "):
            key, rest = line.split(":", 1)
            key = key.strip()
            if key in seen:
                raise RestructureError(f"duplicate manifest field: {key}")
            seen.add(key)
            rest = rest.strip()
            values[key] = rest if rest else []
            current = None if rest else key
            continue
        if current and line.lstrip().startswith("- "):
            item = line.lstrip()[2:].strip()
            assert isinstance(values[current], list)
            values[current].append(item)
    return values


def scalar(values: dict[str, str | list[str]], key: str) -> str:
    value = values.get(key, "")
    return value if isinstance(value, str) else ""


def items(values: dict[str, str | list[str]], key: str) -> list[str]:
    value = values.get(key, [])
    return value if isinstance(value, list) else []


def acceptance_records(text: str) -> list[dict[str, str]]:
    accepted = items(parse_manifest(text), "acceptance")
    if not accepted or len(accepted) != len(set(accepted)):
        raise RestructureError("source acceptance must be non-empty and unique")
    return [{"text": item, "digest": sha256(item.encode("utf-8"))} for item in accepted]


def dirty_product_paths() -> list[str]:
    raw = run_git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    records = raw.split(b"\0")
    found: set[str] = set()
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4 or record[2:3] != b" ":
            raise RestructureError("could not parse git status")
        status = record[:2]
        paths = [record[3:]]
        if b"R" in status or b"C" in status:
            if index >= len(records) or not records[index]:
                raise RestructureError("could not parse renamed git status entry")
            paths.append(records[index])
            index += 1
        for raw_path in paths:
            path = raw_path.decode("utf-8", "strict")
            if path.startswith("docs/plan/") or path.startswith(".agent-artifacts/"):
                continue
            found.add(path)
    return sorted(found)


def scope_covers(scope: list[str], path: str) -> bool:
    for entry in scope:
        if entry.endswith("/") and path.startswith(entry):
            return True
        if path == entry:
            return True
    return False


def preservation_scope(manifest: dict[str, str | list[str]], label: str, *, required: bool) -> list[str]:
    if "preservation_scope" not in manifest:
        if required:
            raise RestructureError(f"{label} requires preservation_scope")
        return []
    scope = items(manifest, "preservation_scope")
    if scope == ["none"]:
        return []
    if not scope or "none" in scope or len(scope) != len(set(scope)):
        raise RestructureError(
            f"{label} preservation_scope must be none or unique normalized exact paths"
        )
    for entry in scope:
        path = PurePosixPath(entry)
        if (
            not entry
            or entry.startswith("/")
            or entry.endswith("/")
            or "\\" in entry
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise RestructureError(
                f"{label} preservation_scope must be none or unique normalized exact paths"
            )
    return scope


def reject_preservation_write_overlap(
    preservation_paths: list[str],
    write_scopes: list[list[str]],
    label: str,
) -> None:
    overlaps = sorted(
        path
        for path in preservation_paths
        if any(scope_covers(scope, path) for scope in write_scopes)
    )
    if overlaps:
        raise RestructureError(
            f"{label} preservation_scope overlaps write_scope: {', '.join(overlaps)}"
        )


def routing_contract(spec_index: Path) -> tuple[set[str], dict[str, set[str]]]:
    default_reads: set[str] = set()
    routes: dict[str, set[str]] = {}
    section = ""
    current = ""
    in_required = False
    for line in spec_index.read_text(encoding="utf-8").splitlines():
        if line == "default_reads:":
            section = "default"
            current = ""
            in_required = False
            continue
        if line == "task_types:":
            section = "routes"
            current = ""
            in_required = False
            continue
        if section == "default":
            match = re.fullmatch(r"  - (.+)", line)
            if match:
                default_reads.add(match.group(1))
            continue
        match = re.fullmatch(r"  ([a-z][a-z0-9_]*):", line)
        if match:
            current = match.group(1)
            routes[current] = set()
            in_required = False
            continue
        if current and line == "    required:":
            in_required = True
            continue
        if current and line.startswith("    ") and not line.startswith("      - "):
            in_required = False
        if current and in_required:
            required = re.fullmatch(r"      - (.+)", line)
            if required:
                routes[current].add(required.group(1))
    return default_reads, routes


def validate_current_plan_rules(manifest: dict[str, str | list[str]], label: str) -> None:
    task_types = items(manifest, "task_types")
    required_specs = items(manifest, "required_specs")
    context_files = items(manifest, "context_files")
    write_scope = items(manifest, "write_scope")
    preserved = preservation_scope(manifest, label, required=False)
    if len(task_types) != len(set(task_types)) or not task_types:
        raise RestructureError(f"{label} task_types must be non-empty and unique")
    spec_candidates = (
        ROOT / ".project-agent-workflow/docs/agent/spec-index.yaml",
        ROOT / "docs/agent/spec-index.yaml",
    )
    spec_index = next((path for path in spec_candidates if path.is_file()), None)
    if spec_index is None:
        raise RestructureError("missing plan routing spec index")
    default_reads, routes = routing_contract(spec_index)
    unknown = sorted(set(task_types) - set(routes))
    if unknown:
        raise RestructureError(f"{label} has unknown task_types: {', '.join(unknown)}")
    expected_specs = set(default_reads)
    for task_type in task_types:
        expected_specs.update(routes[task_type])
    missing_specs = sorted(expected_specs - set(required_specs))
    if missing_specs:
        raise RestructureError(f"{label} required_specs is missing: {', '.join(missing_specs)}")
    overlap = sorted((set(write_scope) - {"none"}) & (set(context_files) - {"none"}))
    if overlap:
        raise RestructureError(f"{label} write_scope overlaps context_files: {', '.join(overlap)}")
    reject_preservation_write_overlap(preserved, [write_scope], label)
    command_module_path = Path(__file__).with_name("plan_validation_commands.py")
    if not command_module_path.is_file():
        raise RestructureError("missing plan validation command policy")
    module_spec = importlib.util.spec_from_file_location("restructure_plan_validation", command_module_path)
    if module_spec is None or module_spec.loader is None:
        raise RestructureError("could not load plan validation command policy")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    for command in items(manifest, "validation"):
        try:
            module.parse_validation_command(command)
        except Exception as exc:
            raise RestructureError(f"{label} validation command is invalid: {exc}") from exc


def validation_projection(
    manifest: dict[str, str | list[str]],
    label: str,
    *,
    require_witness: bool,
    enforce_witness_semantics: bool = True,
) -> dict[str, Any]:
    commands = items(manifest, "validation")
    if not commands or len(commands) != len(set(commands)):
        raise RestructureError(f"{label} validation commands must be non-empty and unique")
    schema = scalar(manifest, "validation_witness_schema")
    raw_map = items(manifest, "validation_witness_map")
    if require_witness and schema != "1":
        raise RestructureError(f"{label} requires validation_witness_schema: 1")
    if require_witness and not raw_map:
        raise RestructureError(f"{label} requires validation_witness_map")
    if schema not in {"", "1"}:
        raise RestructureError(f"{label} has unsupported validation_witness_schema")
    records: list[dict[str, str]] = []
    for index, raw in enumerate(raw_map, start=1):
        try:
            record = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RestructureError(
                f"{label} validation_witness_map entry {index} is invalid"
            ) from exc
        if not isinstance(record, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in record.items()
        ):
            raise RestructureError(
                f"{label} validation_witness_map entry {index} is invalid"
            )
        stage = record.get("stage")
        expected_keys = {"acceptance_sha256", "stage", "witness"}
        if stage == "authoritative":
            expected_keys.add("authoritative_only_reason")
        if set(record) != expected_keys or stage not in {
            "static",
            "focused",
            "authoritative",
        }:
            raise RestructureError(
                f"{label} validation_witness_map entry {index} is invalid"
            )
        witness = record["witness"]
        if enforce_witness_semantics and stage == "static":
            if witness != "resolved-context-files":
                raise RestructureError(
                    f"{label} validation_witness_map entry {index} has unknown static witness"
                )
        elif enforce_witness_semantics and stage == "focused":
            if witness not in items(manifest, "focused_validation"):
                raise RestructureError(
                    f"{label} validation_witness_map entry {index} focused witness is not declared"
                )
        elif enforce_witness_semantics and stage == "authoritative":
            if witness not in commands or witness in items(manifest, "focused_validation"):
                raise RestructureError(
                    f"{label} validation_witness_map entry {index} authoritative witness is invalid"
                )
            reason = record["authoritative_only_reason"]
            if (
                not reason
                or reason != reason.strip()
                or len(reason.encode("utf-8")) > 512
                or any(ord(char) < 0x20 for char in reason)
            ):
                raise RestructureError(
                    f"{label} validation_witness_map entry {index} authoritative-only reason is invalid"
                )
        records.append(record)
    acceptance_digests = [
        sha256(value.encode("utf-8")) for value in items(manifest, "acceptance")
    ]
    if raw_map and [record["acceptance_sha256"] for record in records] != acceptance_digests:
        raise RestructureError(
            f"{label} validation_witness_map must cover acceptance in source order"
        )
    return {
        "authoritative_validation": commands,
        "authoritative_validation_digest": canonical_digest(commands),
        "validation_witness_schema": int(schema) if schema else None,
        "validation_witness_map_digest": canonical_digest(records),
    }


def validate_projection(
    projection: dict[str, Any],
    manifest: dict[str, str | list[str]],
    label: str,
) -> None:
    expected = validation_projection(
        manifest,
        label,
        require_witness=projection["validation_witness_schema"] == 1,
    )
    if projection != expected:
        raise RestructureError(f"{label} validation projection mismatch")


def active_rows(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        if re.match(r"^[0-9]{3}\t", line):
            parts = line.split("\t")
            if len(parts) != 3:
                raise RestructureError(f"malformed active index row: {line}")
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def render_active(rows: list[tuple[str, str, str]]) -> str:
    if not rows:
        return "# Active Plan\n\nNo active development items.\n"
    body = "\n".join("\t".join(row) for row in rows)
    return f"# Active Plan\n\nid\tpath\tstatus\n{body}\n"


def replanned_rows(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        if re.match(r"^[0-9]{3}\t", line):
            parts = line.split("\t")
            if len(parts) != 3:
                raise RestructureError(f"malformed replanned index row: {line}")
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def checked_rows() -> list[tuple[str, str]]:
    index = ROOT / "docs/plan/checked.md"
    if not index.is_file():
        return []
    rows: list[tuple[str, str]] = []
    for line in index.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^[0-9]{3}\t", line):
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise RestructureError(f"malformed checked index row: {line}")
        rows.append((parts[0], parts[1]))
    return rows


def predecessor_paths(manifest: dict[str, str | list[str]], label: str) -> list[str]:
    predecessors = items(manifest, "predecessor_plans")
    if predecessors == ["[]"]:
        return []
    if len(predecessors) != len(set(predecessors)):
        raise RestructureError(f"{label} predecessor_plans must not contain duplicates")
    for predecessor in predecessors:
        path = PurePosixPath(predecessor)
        if (
            not predecessor
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or not (
                PLAN_PATH_RE.fullmatch(predecessor)
                or CHECKED_PATH_RE.fullmatch(predecessor)
            )
        ):
            raise RestructureError(f"{label} has invalid predecessor path: {predecessor!r}")
    return predecessors


def matching_checked_paths(
    plan_id: str,
    basename: str,
    rows: list[tuple[str, str]],
) -> list[str]:
    related = [
        path for indexed_id, path in rows
        if indexed_id == plan_id or Path(path).name == basename
    ]
    exact = [
        path for indexed_id, path in rows
        if indexed_id == plan_id and Path(path).name == basename
    ]
    if related and len(exact) != len(related):
        raise RestructureError(f"predecessor identity mismatch for plan {plan_id}")
    return exact


def validate_active_predecessors(
    records: dict[str, tuple[str, dict[str, str | list[str]]]],
) -> None:
    checked = checked_rows()
    graph: dict[str, list[str]] = {path: [] for path in records}
    for path, (status, manifest) in records.items():
        unresolved: list[str] = []
        for predecessor in predecessor_paths(manifest, path):
            active_match = PLAN_PATH_RE.fullmatch(predecessor)
            if active_match is not None:
                if predecessor in records:
                    graph[path].append(predecessor)
                    unresolved.append(predecessor)
                    continue
                exact_checked = matching_checked_paths(
                    active_match.group(1), Path(predecessor).name, checked
                )
                if not exact_checked:
                    raise RestructureError(f"{path} predecessor is missing: {predecessor}")
                unresolved.append(predecessor)
                continue
            checked_match = CHECKED_PATH_RE.fullmatch(predecessor)
            assert checked_match is not None
            exact_checked = matching_checked_paths(
                checked_match.group(1), Path(predecessor).name, checked
            )
            if exact_checked != [predecessor]:
                raise RestructureError(
                    f"{path} checked predecessor is missing or stale: {predecessor}"
                )
            checked_file = ROOT / predecessor
            if not checked_file.is_file():
                raise RestructureError(f"{path} checked predecessor is missing: {predecessor}")
            if scalar(parse_manifest(checked_file.read_text(encoding="utf-8")), "status") != "checked":
                raise RestructureError(f"{path} predecessor is not checked: {predecessor}")
        if unresolved and status != "deferred":
            raise RestructureError(
                f"{path} must remain deferred until active predecessors are replaced "
                "with exact checked archive paths"
            )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(path: str) -> None:
        if path in visiting:
            raise RestructureError(f"active predecessor cycle detected at: {path}")
        if path in visited:
            return
        visiting.add(path)
        for predecessor in graph[path]:
            visit(predecessor)
        visiting.remove(path)
        visited.add(path)

    for path in graph:
        visit(path)


def render_replanned(rows: list[tuple[str, str, str]]) -> str:
    body = "\n".join("\t".join(row) for row in rows)
    return f"# Replanned Plan Index\n\nid\tpath\tcontract\n{body}\n"


def checked_paths_for_successor(plan_id: str, expected_path: str) -> list[str]:
    index = ROOT / "docs/plan/checked.md"
    if not index.is_file():
        return []
    paths: list[str] = []
    for line in index.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^[0-9]{3}\t", line):
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise RestructureError(f"malformed checked index row for {plan_id}")
        indexed_id, path = parts
        filename_matches = Path(path).name == Path(expected_path).name
        if indexed_id != plan_id and not filename_matches:
            continue
        if indexed_id != plan_id or not filename_matches:
            raise RestructureError(f"checked successor index identity mismatch for {plan_id}")
        if not re.fullmatch(r"docs/plan/checked/(?:[0-9]{4}/[0-9]{2}/(?:01-15|16-31)/)?" + re.escape(plan_id) + r"-[a-z0-9][a-z0-9-]*\.md", path):
            raise RestructureError(f"invalid checked successor path for {plan_id}: {path}")
        paths.append(path)
    return paths


def active_records_for_successor(plan_id: str, expected_path: str) -> list[tuple[str, str, str]]:
    if not ACTIVE_INDEX.is_file():
        return []
    related = [
        row
        for row in active_rows(ACTIVE_INDEX.read_text(encoding="utf-8"))
        if row[0] == plan_id or row[1] == expected_path
    ]
    if len(related) > 1:
        raise RestructureError(f"successor has duplicate active index records: {expected_path}")
    if related and related[0][:2] != (plan_id, expected_path):
        raise RestructureError(f"successor active index identity mismatch: {expected_path}")
    return related


def replanned_records_for_id(plan_id: str, expected_path: str) -> list[tuple[str, str]]:
    if not REPLANNED_INDEX.is_file():
        return []
    records: list[tuple[str, str]] = []
    for indexed_id, archive_path, contract_path in replanned_rows(
        REPLANNED_INDEX.read_text(encoding="utf-8")
    ):
        expected_name = Path(expected_path).name
        archive_matches = Path(archive_path).name == expected_name
        if indexed_id != plan_id and not archive_matches:
            continue
        if indexed_id != plan_id or not archive_matches:
            raise RestructureError(
                f"replanned successor index identity mismatch for {expected_path}"
            )
        normalized_path(
            archive_path,
            ARCHIVE_PATH_RE,
            f"replanned successor archive path for {plan_id}",
        )
        normalized_path(
            contract_path,
            CONTRACT_PATH_RE,
            f"replanned successor contract path for {plan_id}",
        )
        records.append((archive_path, contract_path))
    return records


def validate_replanned_successor(
    plan_id: str,
    expected_path: str,
    expected_digests: list[str],
    expected_acceptance: list[str],
    expected_preservation: list[str] | None,
    expected_projection: dict[str, Any] | None,
) -> None:
    records = replanned_records_for_id(plan_id, expected_path)
    if len(records) != 1:
        raise RestructureError(
            f"successor has missing or ambiguous replanned record: {expected_path}"
        )
    archive_path, contract_path = records[0]
    reject_symlink_ancestors(archive_path, include_target=True)
    reject_symlink_ancestors(contract_path, include_target=True)
    archive_file = ROOT / archive_path
    contract_file = ROOT / contract_path
    if not archive_file.is_file() or not contract_file.is_file():
        raise RestructureError(
            f"missing replanned successor archive or contract: {expected_path}"
        )
    try:
        contract = json.loads(contract_file.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestructureError(
            f"invalid replanned successor contract: {expected_path}"
        ) from exc
    exact_object(
        contract,
        {
            "schema_version",
            "created_at",
            "contract_path",
            "source",
            "reason_codes",
            "dirty_product_paths",
            "archive_path",
            "successors",
        },
        f"replanned successor contract {plan_id}",
    )
    if contract["schema_version"] not in {1, 2} or contract["contract_path"] != contract_path:
        raise RestructureError(
            f"replanned successor contract identity mismatch: {expected_path}"
        )
    if contract["archive_path"] != archive_path:
        raise RestructureError(
            f"replanned successor contract archive mismatch: {expected_path}"
        )
    source = exact_object(
        contract["source"],
        {"path", "head", "plan_digest", "acceptance", "content"},
        f"replanned successor source {plan_id}",
    )
    if source["path"] != expected_path:
        raise RestructureError(
            f"replanned successor source path mismatch: {expected_path}"
        )
    if (
        not isinstance(source["content"], str)
        or sha256(source["content"].encode()) != source["plan_digest"]
    ):
        raise RestructureError(
            f"replanned successor source digest mismatch: {expected_path}"
        )
    if acceptance_records(source["content"]) != source["acceptance"]:
        raise RestructureError(
            f"replanned successor source acceptance mismatch: {expected_path}"
        )
    source_manifest = parse_manifest(source["content"])
    if scalar(source_manifest, "status") != "replan_required":
        raise RestructureError(
            f"replanned successor source status mismatch: {expected_path}"
        )
    if items(source_manifest, "inherited_acceptance_digests") != expected_digests:
        raise RestructureError(
            f"replanned successor source lineage mismatch: {expected_path}"
        )
    if items(source_manifest, "acceptance") != expected_acceptance:
        raise RestructureError(
            f"replanned successor source acceptance drift: {expected_path}"
        )
    if expected_preservation is not None and preservation_scope(
        source_manifest, f"replanned successor source {plan_id}", required=True
    ) != expected_preservation:
        raise RestructureError(
            f"replanned successor source preservation_scope mismatch: {expected_path}"
        )
    if expected_projection is not None:
        validate_projection(
            expected_projection,
            source_manifest,
            f"replanned successor source {plan_id}",
        )
    archive_manifest = parse_manifest(archive_file.read_text(encoding="utf-8"))
    if scalar(archive_manifest, "status") != "replanned":
        raise RestructureError(
            f"replanned successor archive status mismatch: {expected_path}"
        )
    if scalar(archive_manifest, "replan_source") != expected_path:
        raise RestructureError(
            f"replanned successor archive lineage mismatch: {expected_path}"
        )
    if scalar(archive_manifest, "replan_contract") != contract_path:
        raise RestructureError(
            f"replanned successor archive contract mismatch: {expected_path}"
        )
    if items(archive_manifest, "inherited_acceptance_digests") != expected_digests:
        raise RestructureError(
            f"replanned successor archive digest mapping mismatch: {expected_path}"
        )
    if items(archive_manifest, "acceptance") != expected_acceptance:
        raise RestructureError(
            f"replanned successor archive acceptance mismatch: {expected_path}"
        )
    if expected_preservation is not None and preservation_scope(
        archive_manifest, f"replanned successor archive {plan_id}", required=True
    ) != expected_preservation:
        raise RestructureError(
            f"replanned successor archive preservation_scope mismatch: {expected_path}"
        )


def validate_plan_entry(
    entry: Any,
    *,
    label: str,
    source_path: str,
    contract_path: str,
    all_plan_paths: list[str],
    source_digests: set[str],
    source_ordered_digests: list[str],
    source_text_by_digest: dict[str, str],
) -> dict[str, Any]:
    obj = exact_object(entry, {"id", "path", "content", "acceptance_digests"}, label)
    plan_id = obj["id"]
    path = normalized_path(obj["path"], PLAN_PATH_RE, f"{label}.path")
    match = PLAN_PATH_RE.fullmatch(path)
    assert match
    if not isinstance(plan_id, str) or plan_id != match.group(1):
        raise RestructureError(f"{label}.id does not match its filename")
    content = obj["content"]
    digests = obj["acceptance_digests"]
    if not isinstance(content, str) or not content.endswith("\n") or len(content.encode()) > 262_144:
        raise RestructureError(f"{label}.content must be bounded UTF-8 text ending in newline")
    if not isinstance(digests, list) or not digests or len(digests) != len(set(digests)):
        raise RestructureError(f"{label}.acceptance_digests must be a non-empty unique list")
    if any(not isinstance(value, str) or value not in source_digests for value in digests):
        raise RestructureError(f"{label}.acceptance_digests contains an unknown source acceptance")
    if digests != [value for value in source_ordered_digests if value in set(digests)]:
        raise RestructureError(f"{label}.acceptance_digests must preserve source order")
    manifest = parse_manifest(content)
    missing_fields = sorted(
        key for key in REQUIRED_PLAN_FIELDS
        if key not in manifest or manifest[key] in ("", [])
    )
    if missing_fields:
        raise RestructureError(f"{label} missing required manifest fields: {', '.join(missing_fields)}")
    status = scalar(manifest, "status")
    if status not in {"in_progress", "deferred"}:
        raise RestructureError(f"{label} must start in status: in_progress or deferred")
    if status == "deferred" and not scalar(manifest, "completion_deferred_reason").strip():
        raise RestructureError(f"{label} deferred plan requires completion_deferred_reason")
    predecessor_paths(manifest, label)
    if scalar(manifest, "replan_source") != source_path:
        raise RestructureError(f"{label} replan_source mismatch")
    if scalar(manifest, "replan_contract") != contract_path:
        raise RestructureError(f"{label} replan_contract mismatch")
    if not scalar(manifest, "primary_invariant").strip():
        raise RestructureError(f"{label} requires primary_invariant")
    if items(manifest, "successor_plans") != all_plan_paths:
        raise RestructureError(f"{label} successor_plans must list every created plan in order")
    if items(manifest, "inherited_acceptance_digests") != digests:
        raise RestructureError(f"{label} inherited_acceptance_digests mismatch")
    if not items(manifest, "integration_gates"):
        raise RestructureError(f"{label} requires integration_gates")
    scope = items(manifest, "write_scope")
    if not scope:
        raise RestructureError(f"{label} requires write_scope")
    if len(scope) != len(set(scope)) or any(
        not entry or entry.startswith("/") or "\\" in entry or ".." in PurePosixPath(entry).parts
        for entry in scope
    ):
        raise RestructureError(f"{label} write_scope must contain unique normalized relative paths")
    if not items(manifest, "acceptance") or len(items(manifest, "acceptance")) != len(
        set(items(manifest, "acceptance"))
    ):
        raise RestructureError(f"{label} acceptance must be non-empty and unique")
    if scalar(manifest, "review_class") not in {"A", "B", "C"}:
        raise RestructureError(f"{label} review_class is invalid")
    if scalar(manifest, "human_design_required") not in {"yes", "no"}:
        raise RestructureError(f"{label} human_design_required is invalid")
    if scalar(manifest, "human_approval_status") not in {"not_required", "pending", "approved"}:
        raise RestructureError(f"{label} human_approval_status is invalid")
    if scalar(manifest, "review_class") == "C" and scalar(manifest, "human_approval_status") != "approved":
        raise RestructureError(f"{label} class C in-progress plan requires approval")
    if scalar(manifest, "human_design_required") == "yes" and scalar(manifest, "review_class") != "C":
        raise RestructureError(f"{label} human design work requires class C")
    expected_acceptance = [source_text_by_digest[mapped_digest] for mapped_digest in digests]
    if items(manifest, "acceptance") != expected_acceptance:
        raise RestructureError(
            f"{label} acceptance must exactly equal mapped source text in source order"
        )
    validate_current_plan_rules(manifest, label)
    projection = validation_projection(
        manifest,
        label,
        require_witness=status == "in_progress",
    )
    preserved = preservation_scope(manifest, label, required=True)
    return {
        **obj,
        "manifest": manifest,
        "preservation_scope": preserved,
        "content_digest": sha256(content.encode("utf-8")),
        "validation_projection": projection,
    }


def manifest_field_ranges(text: str) -> list[tuple[str, int, int]]:
    starts: list[tuple[str, int]] = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip()
        if line.startswith("## "):
            break
        if ":" in line and not line.startswith(" "):
            starts.append((line.split(":", 1)[0].strip(), offset))
        offset += len(raw)
    return [
        (key, start, starts[index + 1][1] if index + 1 < len(starts) else offset)
        for index, (key, start) in enumerate(starts)
    ]


def manifest_body_offset(text: str) -> int:
    offset = 0
    for raw in text.splitlines(keepends=True):
        if raw.rstrip().startswith("## "):
            return offset
        offset += len(raw)
    return len(text)


def remove_manifest_fields(prefix: str, fields: set[str]) -> str:
    ranges: list[tuple[int, int]] = []
    for key, start, end in manifest_field_ranges(prefix):
        if key in fields:
            ranges.append((start, end))
    if not ranges:
        return prefix
    chunks: list[str] = []
    cursor = 0
    for start, end in ranges:
        chunks.append(prefix[cursor:start])
        cursor = end
    chunks.append(prefix[cursor:])
    return "".join(chunks)


def build_archive(
    source_text: str,
    *,
    source_path: str,
    contract_path: str,
    plan_paths: list[str],
    acceptance_digests: list[str],
) -> str:
    body_offset = manifest_body_offset(source_text)
    manifest_prefix = source_text[:body_offset]
    body_suffix = source_text[body_offset:]
    status_ranges = [
        (start, end)
        for key, start, end in manifest_field_ranges(manifest_prefix)
        if key == "status"
    ]
    if len(status_ranges) != 1:
        raise RestructureError("source plan must have exactly one status: replan_required field")
    status_start, status_end = status_ranges[0]
    status_line = manifest_prefix[status_start:status_end].splitlines(keepends=True)[0]
    status_line_end = status_start + len(status_line)
    updated = manifest_prefix[:status_start] + "status: replanned\n" + manifest_prefix[status_line_end:]
    updated = remove_manifest_fields(
        updated,
        {
            "primary_invariant",
            "replan_source",
            "replan_contract",
            "integration_gates",
            "successor_plans",
            "inherited_acceptance_digests",
        },
    )
    summary_ranges = [
        (start, end)
        for key, start, end in manifest_field_ranges(updated)
        if key == "checked_summary_ja"
    ]
    if len(summary_ranges) != 1:
        raise RestructureError("source plan lacks checked_summary_ja")
    summary_start = summary_ranges[0][0]
    block = [
        "primary_invariant: preserve the complete source acceptance baseline",
        f"replan_source: {source_path}",
        f"replan_contract: {contract_path}",
        "integration_gates:",
        "  - combined successors must satisfy every source acceptance item",
        "successor_plans:",
        *[f"  - {path}" for path in plan_paths],
        "inherited_acceptance_digests:",
        *[f"  - {digest}" for digest in acceptance_digests],
    ]
    return (
        updated[:summary_start]
        + "\n".join(block)
        + "\n"
        + updated[summary_start:]
        + body_suffix
    )


def read_spec(path: Path) -> dict[str, Any]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RestructureError("restructure specification must be a regular file")
        data = os.read(descriptor, MAX_SPEC_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(data) > MAX_SPEC_BYTES:
        raise RestructureError("restructure specification exceeds one MiB")
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestructureError(f"invalid restructure specification: {exc}") from exc
    return exact_object(
        value,
        {"schema_version", "source", "reason_codes", "dirty_product_paths", "contract_path", "archive_path", "successors", "integration"},
        "specification",
    )


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    if spec["schema_version"] != 1 or isinstance(spec["schema_version"], bool):
        raise RestructureError("schema_version must be 1")
    source = exact_object(
        spec["source"], {"path", "head", "plan_digest", "acceptance"}, "source"
    )
    source_path = normalized_path(source["path"], PLAN_PATH_RE, "source.path")
    source_match = PLAN_PATH_RE.fullmatch(source_path)
    assert source_match
    source_id = source_match.group(1)
    source_file = ROOT / source_path
    reject_symlink_ancestors(source_path, include_target=True)
    if not source_file.is_file():
        raise RestructureError(f"missing source plan: {source_path}")
    source_bytes = source_file.read_bytes()
    source_text = source_bytes.decode("utf-8")
    manifest = parse_manifest(source_text)
    if scalar(manifest, "status") != "replan_required":
        raise RestructureError("source plan must be status: replan_required")
    if source["head"] != current_head():
        raise RestructureError("source HEAD mismatch")
    if not isinstance(source["head"], str) or not re.fullmatch(r"[0-9a-f]{40}", source["head"]):
        raise RestructureError("source HEAD must be a full object id")
    if not isinstance(source["plan_digest"], str) or not SHA_RE.fullmatch(source["plan_digest"]):
        raise RestructureError("source plan_digest must be sha256:<64 lowercase hex>")
    if source["plan_digest"] != sha256(source_bytes):
        raise RestructureError("source plan digest mismatch")
    expected_acceptance = acceptance_records(source_text)
    if source["acceptance"] != expected_acceptance:
        raise RestructureError("source acceptance text or digest mismatch")
    reason_codes = spec["reason_codes"]
    if (
        not isinstance(reason_codes, list)
        or not reason_codes
        or len(reason_codes) != len(set(reason_codes))
        or any(not isinstance(value, str) or value not in REASON_CODES for value in reason_codes)
    ):
        raise RestructureError("reason_codes must be a non-empty unique bounded list")
    if items(manifest, "replan_reason_codes") != reason_codes:
        raise RestructureError("source replan_reason_codes mismatch")
    contract_path = normalized_path(spec["contract_path"], CONTRACT_PATH_RE, "contract_path")
    archive_path = normalized_path(spec["archive_path"], ARCHIVE_PATH_RE, "archive_path")
    archive_match = ARCHIVE_PATH_RE.fullmatch(archive_path)
    assert archive_match
    if archive_match.group(1) != Path(source_path).name:
        raise RestructureError("archive filename must match the source filename")
    today = datetime.now().date()
    expected_half = "01-15" if today.day <= 15 else "16-31"
    expected_prefix = f"docs/plan/replanned/{today.year:04d}/{today.month:02d}/{expected_half}/"
    if not archive_path.startswith(expected_prefix):
        raise RestructureError("archive_path must use the current date partition")
    successors = spec["successors"]
    if not isinstance(successors, list) or not successors or len(successors) > MAX_PLANS - 1:
        raise RestructureError("successors must contain between one and seven plans")
    raw_entries = [*successors, spec["integration"]]
    raw_paths = [
        normalized_path(exact_object(entry, {"id", "path", "content", "acceptance_digests"}, "plan")["path"], PLAN_PATH_RE, "plan.path")
        for entry in raw_entries
    ]
    if len(raw_paths) != len(set(raw_paths)):
        raise RestructureError("created plan paths must be unique")
    ordered_digests = [record["digest"] for record in expected_acceptance]
    source_digests = set(ordered_digests)
    source_text_by_digest = {record["digest"]: record["text"] for record in expected_acceptance}
    entries = [
        validate_plan_entry(
            entry,
            label="integration" if index == len(raw_entries) - 1 else f"successors[{index}]",
            source_path=source_path,
            contract_path=contract_path,
            all_plan_paths=raw_paths,
            source_digests=source_digests,
            source_ordered_digests=ordered_digests,
            source_text_by_digest=source_text_by_digest,
        )
        for index, entry in enumerate(raw_entries)
    ]
    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)) or source_id in ids:
        raise RestructureError("created plan ids must be unique and differ from the source id")
    integration = entries[-1]
    if integration["acceptance_digests"] != ordered_digests:
        raise RestructureError("integration must inherit every acceptance digest in source order")
    if items(integration["manifest"], "acceptance") != [record["text"] for record in expected_acceptance]:
        raise RestructureError("integration must copy every source acceptance item exactly")
    mapped = {digest for entry in entries for digest in entry["acceptance_digests"]}
    if mapped != source_digests:
        raise RestructureError("every source acceptance digest must be mapped")
    actual_dirty = dirty_product_paths()
    declared_dirty = spec["dirty_product_paths"]
    if not isinstance(declared_dirty, list) or declared_dirty != actual_dirty:
        raise RestructureError("dirty_product_paths must exactly match current Git status")
    successor_scopes = [items(entry["manifest"], "write_scope") for entry in entries]
    preserved_paths = [
        path for entry in entries for path in entry["preservation_scope"]
    ]
    if len(preserved_paths) != len(set(preserved_paths)):
        raise RestructureError("preservation_scope paths must be assigned exactly once")
    if sorted(preserved_paths) != actual_dirty:
        raise RestructureError(
            "successor preservation_scope must exactly match dirty_product_paths"
        )
    reject_preservation_write_overlap(
        preserved_paths, successor_scopes, "successor plans"
    )
    active_text = ACTIVE_INDEX.read_text(encoding="utf-8")
    rows = active_rows(active_text)
    if rows.count((source_id, source_path, "replan_required")) != 1:
        raise RestructureError("active index does not exactly map the stopped source plan")
    active_records: dict[str, tuple[str, dict[str, str | list[str]]]] = {}
    for row_id, row_path, row_status in rows:
        if row_id == source_id:
            continue
        row_match = PLAN_PATH_RE.fullmatch(row_path)
        if row_match is None or row_match.group(1) != row_id:
            raise RestructureError(f"active plan identity mismatch: {row_path}")
        active_file = ROOT / row_path
        if not active_file.is_file():
            raise RestructureError(f"missing active plan: {row_path}")
        active_manifest = parse_manifest(active_file.read_text(encoding="utf-8"))
        if scalar(active_manifest, "status") != row_status:
            raise RestructureError(f"active plan status mismatch: {row_path}")
        active_records[row_path] = (row_status, active_manifest)
    active_records.update(
        {
            entry["path"]: (scalar(entry["manifest"], "status"), entry["manifest"])
            for entry in entries
        }
    )
    validate_active_predecessors(active_records)
    replanned_text = (
        REPLANNED_INDEX.read_text(encoding="utf-8")
        if REPLANNED_INDEX.exists()
        else "# Replanned Plan Index\n\nid\tpath\tcontract\n"
    )
    prior_replanned = replanned_rows(replanned_text)
    destinations = [contract_path, archive_path, *raw_paths]
    for destination in destinations:
        reject_symlink_ancestors(destination, include_target=False)
        if (ROOT / destination).exists() or (ROOT / destination).is_symlink():
            raise RestructureError(f"destination already exists: {destination}")
    known_ids: set[str] = set()
    for base in (ROOT / "docs/plan/active", ROOT / "docs/plan/backlog", ROOT / "docs/plan/checked", ROOT / "docs/plan/replanned"):
        if base.exists():
            for path in base.glob("**/[0-9][0-9][0-9]-*.md"):
                if path != source_file:
                    known_ids.add(path.name[:3])
    if known_ids & set(ids):
        raise RestructureError("a created plan id already exists")
    if any(row[0] in ids or row[1] in raw_paths for row in rows):
        raise RestructureError("active index conflicts with a created plan")
    if any(row[0] == source_id or row[1] == archive_path or row[2] == contract_path for row in prior_replanned):
        raise RestructureError("replanned index conflicts with the source transition")
    archive_text = build_archive(
        source_text,
        source_path=source_path,
        contract_path=contract_path,
        plan_paths=raw_paths,
        acceptance_digests=ordered_digests,
    )
    contract = {
        "schema_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "contract_path": contract_path,
        "source": {**source, "content": source_text},
        "reason_codes": reason_codes,
        "dirty_product_paths": actual_dirty,
        "archive_path": archive_path,
        "successors": [
            {
                "id": entry["id"],
                "path": entry["path"],
                "content_digest": entry["content_digest"],
                "content": entry["content"],
                "acceptance_digests": entry["acceptance_digests"],
                "integration": index == len(entries) - 1,
                **entry["validation_projection"],
            }
            for index, entry in enumerate(entries)
        ],
    }
    new_rows = [row for row in rows if row[0] != source_id]
    new_rows.extend(
        (entry["id"], entry["path"], scalar(entry["manifest"], "status"))
        for entry in entries
    )
    new_replanned = [*prior_replanned, (source_id, archive_path, contract_path)]
    return {
        "source_file": source_file,
        "source_text": source_text,
        "active_text": active_text,
        "replanned_text": replanned_text,
        "replanned_existed": REPLANNED_INDEX.exists(),
        "destinations": [
            (contract_path, json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n"),
            (archive_path, archive_text),
            *[(entry["path"], entry["content"]) for entry in entries],
        ],
        "active_new": render_active(new_rows),
        "replanned_new": render_replanned(new_replanned),
        "contract_path": contract_path,
    }


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(tmp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def exclusive_write(relative: str, text: str) -> Path:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def missing_parent_directories(relative: str) -> list[Path]:
    parents: list[Path] = []
    current = (ROOT / relative).parent
    while current != ROOT and not current.exists():
        parents.append(current)
        current = current.parent
    return parents


def execute(spec_path: Path, *, fail_after_writes: int = 0) -> str:
    reject_symlink_ancestors(".agent-artifacts/plan-lifecycle.lock", include_target=True)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    lock_descriptor = os.open(LOCK, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_descriptor, "a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = validate_spec(read_spec(spec_path))
        created: list[Path] = []
        created_directories: list[Path] = []
        index_changed = False
        try:
            for relative, content in state["destinations"]:
                created_directories.extend(missing_parent_directories(relative))
                created.append(exclusive_write(relative, content))
                if fail_after_writes and len(created) == fail_after_writes:
                    raise OSError("injected transition write failure")
            atomic_write(ACTIVE_INDEX, state["active_new"])
            index_changed = True
            atomic_write(REPLANNED_INDEX, state["replanned_new"])
            state["source_file"].unlink()
        except BaseException:
            if index_changed:
                atomic_write(ACTIVE_INDEX, state["active_text"])
                if state["replanned_existed"]:
                    atomic_write(REPLANNED_INDEX, state["replanned_text"])
                else:
                    REPLANNED_INDEX.unlink(missing_ok=True)
            for path in reversed(created):
                path.unlink(missing_ok=True)
            for path in sorted(set(created_directories), key=lambda value: len(value.parts), reverse=True):
                try:
                    path.rmdir()
                except OSError:
                    pass
            raise
    return state["contract_path"]


def validate_repository_active_predecessors() -> None:
    active_records: dict[str, tuple[str, dict[str, str | list[str]]]] = {}
    if ACTIVE_INDEX.is_file():
        for plan_id, path, status in active_rows(ACTIVE_INDEX.read_text(encoding="utf-8")):
            match = PLAN_PATH_RE.fullmatch(path)
            if match is None or match.group(1) != plan_id:
                raise RestructureError(f"active plan identity mismatch: {path}")
            target = ROOT / path
            if not target.is_file():
                raise RestructureError(f"missing active plan: {path}")
            manifest = parse_manifest(target.read_text(encoding="utf-8"))
            if scalar(manifest, "status") != status:
                raise RestructureError(f"active plan status mismatch: {path}")
            active_records[path] = (status, manifest)
    validate_active_predecessors(active_records)


def verify_repository_contracts() -> None:
    validate_repository_active_predecessors()
    if not REPLANNED_INDEX.is_file():
        raise RestructureError("missing docs/plan/replanned.md")
    rows = replanned_rows(REPLANNED_INDEX.read_text(encoding="utf-8"))
    companion_records: list[dict[str, Any]] = []
    for plan_id, archive_path, contract_path in rows:
        normalized_path(archive_path, ARCHIVE_PATH_RE, "replanned archive path")
        normalized_path(contract_path, CONTRACT_PATH_RE, "replanned contract path")
        reject_symlink_ancestors(archive_path, include_target=True)
        reject_symlink_ancestors(contract_path, include_target=True)
        archive_file = ROOT / archive_path
        contract_file = ROOT / contract_path
        if not archive_file.is_file() or not contract_file.is_file():
            raise RestructureError(f"missing replanned archive or contract for {plan_id}")
        try:
            contract_bytes = contract_file.read_bytes()
            contract = json.loads(contract_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RestructureError(f"invalid durable contract for {plan_id}: {exc}") from exc
        schema_version = contract.get("schema_version") if isinstance(contract, dict) else None
        if schema_version not in {1, 2}:
            raise RestructureError(f"contract identity mismatch for {plan_id}")
        exact_object(
            contract,
            {"schema_version", "created_at", "contract_path", "source", "reason_codes", "dirty_product_paths", "archive_path", "successors"},
            f"contract {plan_id}",
        )
        if contract["contract_path"] != contract_path:
            raise RestructureError(f"contract identity mismatch for {plan_id}")
        if contract["archive_path"] != archive_path:
            raise RestructureError(f"contract archive mismatch for {plan_id}")
        try:
            datetime.fromisoformat(contract["created_at"])
        except (TypeError, ValueError) as exc:
            raise RestructureError(f"contract timestamp is invalid for {plan_id}") from exc
        source = exact_object(
            contract["source"], {"path", "head", "plan_digest", "acceptance", "content"}, f"contract source {plan_id}"
        )
        source_path = normalized_path(source["path"], PLAN_PATH_RE, "contract source path")
        source_match = PLAN_PATH_RE.fullmatch(source_path)
        assert source_match
        if source_match.group(1) != plan_id:
            raise RestructureError(f"replanned index and source id mismatch for {plan_id}")
        if Path(archive_path).name != Path(source_path).name:
            raise RestructureError(f"replanned archive basename mismatch for {plan_id}")
        if not isinstance(source["content"], str) or sha256(source["content"].encode()) != source["plan_digest"]:
            raise RestructureError(f"contract source content digest mismatch for {plan_id}")
        if acceptance_records(source["content"]) != source["acceptance"]:
            raise RestructureError(f"contract source acceptance mismatch for {plan_id}")
        source_manifest = parse_manifest(source["content"])
        if scalar(source_manifest, "status") != "replan_required":
            raise RestructureError(f"contract source status mismatch for {plan_id}")
        source_records = source["acceptance"]
        source_digests = [record["digest"] for record in source_records]
        source_text_by_digest = {record["digest"]: record["text"] for record in source_records}
        successors = contract["successors"]
        if not isinstance(successors, list) or not successors:
            raise RestructureError(f"contract has no successors for {plan_id}")
        paths: list[str] = []
        mapped: set[str] = set()
        integration_count = 0
        contract_preservation: list[str] = []
        contract_write_scopes: list[list[str]] = []
        preservation_mode: bool | None = None
        live_companion_successors: list[dict[str, Any]] = []
        for index, raw_successor in enumerate(successors):
            successor_keys = {
                "id",
                "path",
                "content_digest",
                "content",
                "acceptance_digests",
                "integration",
            }
            if schema_version == 2:
                successor_keys.update(
                    {
                        "authoritative_validation",
                        "authoritative_validation_digest",
                        "validation_witness_schema",
                        "validation_witness_map_digest",
                    }
                )
            successor = exact_object(
                raw_successor,
                successor_keys,
                f"contract successor {plan_id}/{index}",
            )
            path = normalized_path(successor["path"], PLAN_PATH_RE, "contract successor path")
            match = PLAN_PATH_RE.fullmatch(path)
            assert match
            if successor["id"] != match.group(1):
                raise RestructureError(f"contract successor id mismatch for {plan_id}")
            if not isinstance(successor["content"], str) or sha256(successor["content"].encode()) != successor["content_digest"]:
                raise RestructureError(f"contract successor content digest mismatch for {plan_id}")
            successor_manifest = parse_manifest(successor["content"])
            projection = (
                {
                    "authoritative_validation": successor["authoritative_validation"],
                    "authoritative_validation_digest": successor[
                        "authoritative_validation_digest"
                    ],
                    "validation_witness_schema": successor[
                        "validation_witness_schema"
                    ],
                    "validation_witness_map_digest": successor[
                        "validation_witness_map_digest"
                    ],
                }
                if schema_version == 2
                else None
            )
            if projection is not None:
                validate_projection(
                    projection,
                    successor_manifest,
                    f"contract successor {plan_id}/{index}",
                )
            has_preservation = "preservation_scope" in successor_manifest
            if preservation_mode is None:
                preservation_mode = has_preservation
            elif preservation_mode != has_preservation:
                raise RestructureError(
                    f"contract successors mix preservation schemas for {plan_id}"
                )
            expected_preservation = (
                preservation_scope(
                    successor_manifest,
                    f"contract successor {plan_id}/{index}",
                    required=True,
                )
                if has_preservation
                else None
            )
            if expected_preservation is not None:
                contract_preservation.extend(expected_preservation)
                contract_write_scopes.append(items(successor_manifest, "write_scope"))
            digests = successor["acceptance_digests"]
            if not isinstance(digests, list) or not digests or len(digests) != len(set(digests)):
                raise RestructureError(f"contract successor mapping is invalid for {plan_id}")
            if any(digest not in source_text_by_digest for digest in digests):
                raise RestructureError(f"contract successor mapping is unknown for {plan_id}")
            if digests != [digest for digest in source_digests if digest in set(digests)]:
                raise RestructureError(f"contract successor mapping order mismatch for {plan_id}")
            if items(successor_manifest, "inherited_acceptance_digests") != digests:
                raise RestructureError(f"contract successor lineage mismatch for {plan_id}")
            expected_successor_acceptance = [source_text_by_digest[digest] for digest in digests]
            if items(successor_manifest, "acceptance") != expected_successor_acceptance:
                raise RestructureError(f"contract successor acceptance mismatch for {plan_id}")
            reject_symlink_ancestors(path, include_target=True)
            active_file = ROOT / path
            active_records = active_records_for_successor(successor["id"], path)
            checked_paths = checked_paths_for_successor(successor["id"], path)
            replanned_records = replanned_records_for_id(successor["id"], path)
            if sum((bool(active_records), bool(checked_paths), bool(replanned_records))) > 1:
                raise RestructureError(f"successor has ambiguous durable records: {path}")
            if len(checked_paths) > 1:
                raise RestructureError(f"successor has multiple checked index entries: {path}")
            if active_file.is_file() and not active_records:
                raise RestructureError(f"successor has an unindexed active file: {path}")
            if active_records:
                if not active_file.is_file():
                    raise RestructureError(f"missing active successor plan: {path}")
                expected_live_status = active_records[0][2]
                if expected_live_status not in ACTIVE_PLAN_STATUSES:
                    raise RestructureError(f"invalid active successor status: {path}")
                live_successor_file = active_file
            elif checked_paths:
                reject_symlink_ancestors(checked_paths[0], include_target=True)
                live_successor_file = ROOT / checked_paths[0]
                if not live_successor_file.is_file():
                    raise RestructureError(f"missing checked successor plan for {plan_id}: {checked_paths[0]}")
                expected_live_status = "checked"
            elif replanned_records:
                validate_replanned_successor(
                    successor["id"],
                    path,
                    digests,
                    expected_successor_acceptance,
                    expected_preservation,
                    projection,
                )
                live_successor_file = None
            else:
                raise RestructureError(f"missing live successor plan for {plan_id}: {path}")
            if live_successor_file is not None:
                live_successor_manifest = parse_manifest(live_successor_file.read_text(encoding="utf-8"))
                if scalar(live_successor_manifest, "status") != expected_live_status:
                    raise RestructureError(f"live successor status mismatch for {plan_id}: {path}")
                if items(live_successor_manifest, "inherited_acceptance_digests") != digests:
                    raise RestructureError(f"live successor lineage mismatch for {plan_id}: {path}")
                if items(live_successor_manifest, "acceptance") != expected_successor_acceptance:
                    raise RestructureError(f"live successor acceptance mismatch for {plan_id}: {path}")
                if expected_preservation is not None and preservation_scope(
                    live_successor_manifest,
                    f"live successor {plan_id}/{index}",
                    required=True,
                ) != expected_preservation:
                    raise RestructureError(
                        f"live successor preservation_scope mismatch for {plan_id}: {path}"
                    )
                if projection is not None:
                    validate_projection(
                        projection,
                        live_successor_manifest,
                        f"live successor {plan_id}/{index}",
                    )
                elif scalar(live_successor_manifest, "validation_witness_schema") == "1":
                    live_projection = validation_projection(
                        live_successor_manifest,
                        f"live successor {plan_id}/{index}",
                        require_witness=True,
                        enforce_witness_semantics=False,
                    )
                    live_companion_successors.append(
                        {
                            "path": path,
                            "acceptance_digests": digests,
                            **live_projection,
                        }
                    )
            mapped.update(digests)
            paths.append(path)
            if successor["integration"] is True:
                integration_count += 1
                if digests != source_digests or items(successor_manifest, "acceptance") != [record["text"] for record in source_records]:
                    raise RestructureError(f"contract integration baseline mismatch for {plan_id}")
            elif successor["integration"] is not False:
                raise RestructureError(f"contract integration flag is invalid for {plan_id}")
        if len(paths) != len(set(paths)) or mapped != set(source_digests) or integration_count != 1:
            raise RestructureError(f"contract mapping is incomplete or ambiguous for {plan_id}")
        if preservation_mode:
            dirty_paths = contract["dirty_product_paths"]
            if (
                not isinstance(dirty_paths, list)
                or len(contract_preservation) != len(set(contract_preservation))
                or sorted(contract_preservation) != dirty_paths
            ):
                raise RestructureError(
                    f"contract preservation_scope does not match dirty paths for {plan_id}"
                )
            reject_preservation_write_overlap(
                contract_preservation,
                contract_write_scopes,
                f"contract {plan_id}",
            )
        archive_text = archive_file.read_text(encoding="utf-8")
        archive_manifest = parse_manifest(archive_text)
        if scalar(archive_manifest, "status") != "replanned":
            raise RestructureError(f"archive status mismatch for {plan_id}")
        if scalar(archive_manifest, "replan_source") != source["path"]:
            raise RestructureError(f"archive source lineage mismatch for {plan_id}")
        if scalar(archive_manifest, "replan_contract") != contract_path:
            raise RestructureError(f"archive contract lineage mismatch for {plan_id}")
        if items(archive_manifest, "successor_plans") != paths:
            raise RestructureError(f"archive successor lineage mismatch for {plan_id}")
        if items(archive_manifest, "inherited_acceptance_digests") != source_digests:
            raise RestructureError(f"archive acceptance lineage mismatch for {plan_id}")
        if items(archive_manifest, "acceptance") != [record["text"] for record in source_records]:
            raise RestructureError(f"archive acceptance text mismatch for {plan_id}")
        if schema_version == 1 and live_companion_successors:
            companion_records.append(
                {
                    "contract_path": contract_path,
                    "contract_digest": sha256(contract_bytes),
                    "successors": live_companion_successors,
                }
            )
    verify_companion_baseline(companion_records)


def companion_publication_recorded() -> bool:
    return bool(
        run_git("log", "--all", "--format=%H", "--", COMPANION_PATH).strip()
    )


def companion_absence_allowed() -> bool:
    if companion_publication_recorded() or not ACTIVE_INDEX.is_file():
        return False
    publisher_records = [
        row for row in active_rows(ACTIVE_INDEX.read_text(encoding="utf-8"))
        if row[0] == "190" or row[1] == COMPANION_PLAN_PATH
    ]
    if len(publisher_records) != 1:
        return False
    plan_id, path, status = publisher_records[0]
    if (
        (plan_id, path) != ("190", COMPANION_PLAN_PATH)
        or status not in {"deferred", "in_progress"}
    ):
        return False
    publisher = ROOT / path
    if not publisher.is_file():
        return False
    publisher_manifest = parse_manifest(publisher.read_text(encoding="utf-8"))
    if (
        scalar(publisher_manifest, "status") != status
        or COMPANION_PATH not in items(publisher_manifest, "write_scope")
    ):
        return False
    for row_id, row_path, _ in active_rows(ACTIVE_INDEX.read_text(encoding="utf-8")):
        target = ROOT / row_path
        if not target.is_file():
            return False
        manifest = parse_manifest(target.read_text(encoding="utf-8"))
        if row_id != "190" and COMPANION_PATH in items(manifest, "write_scope"):
            return False
        if COMPANION_PATH in items(manifest, "context_files"):
            return False
    return True


def verify_companion_baseline(records: list[dict[str, Any]]) -> None:
    path = ROOT / COMPANION_PATH
    if not path.exists():
        if not records or companion_absence_allowed():
            return
        raise RestructureError("missing live validation successor companion baseline")
    reject_symlink_ancestors(COMPANION_PATH, include_target=True)
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestructureError("invalid live validation successor companion baseline") from exc
    exact_object(baseline, {"schema_version", "records"}, "companion baseline")
    if baseline["schema_version"] != 1 or baseline["records"] != records:
        raise RestructureError("live validation successor companion baseline mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("specification", type=Path, nargs="?")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify:
            if args.specification is not None:
                raise RestructureError("--verify does not accept a specification")
            verify_repository_contracts()
            print("replanned contracts verified")
        else:
            if args.specification is None:
                raise RestructureError("missing restructure specification")
            print(execute(args.specification))
    except (OSError, UnicodeError, RestructureError) as exc:
        print(f"plan restructuring failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
