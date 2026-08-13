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
SHA_RE = re.compile(r"sha256:[0-9a-f]{64}")


class RestructureError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


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
        prefix = entry.rstrip("/")
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


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


def render_replanned(rows: list[tuple[str, str, str]]) -> str:
    body = "\n".join("\t".join(row) for row in rows)
    return f"# Replanned Plan Index\n\nid\tpath\tcontract\n{body}\n"


def checked_paths_for_id(plan_id: str) -> list[str]:
    index = ROOT / "docs/plan/checked.md"
    if not index.is_file():
        return []
    paths: list[str] = []
    for line in index.read_text(encoding="utf-8").splitlines():
        if line.startswith(plan_id + "\t"):
            parts = line.split("\t")
            if len(parts) != 2:
                raise RestructureError(f"malformed checked index row for {plan_id}")
            path = parts[1]
            expected_name = Path(path).name
            if not re.fullmatch(r"docs/plan/checked/(?:[0-9]{4}/[0-9]{2}/(?:01-15|16-31)/)?" + re.escape(plan_id) + r"-[a-z0-9][a-z0-9-]*\.md", path):
                raise RestructureError(f"invalid checked successor path for {plan_id}: {path}")
            if not expected_name.startswith(plan_id + "-"):
                raise RestructureError(f"checked successor filename mismatch for {plan_id}")
            paths.append(path)
    return paths


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
    if scalar(manifest, "status") != "in_progress":
        raise RestructureError(f"{label} must start in status: in_progress")
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
    return {**obj, "manifest": manifest, "content_digest": sha256(content.encode("utf-8"))}


def build_archive(
    source_text: str,
    *,
    source_path: str,
    contract_path: str,
    plan_paths: list[str],
    acceptance_digests: list[str],
) -> str:
    manifest = parse_manifest(source_text)
    for forbidden in (
        "primary_invariant", "replan_source", "replan_contract", "integration_gates",
        "successor_plans", "inherited_acceptance_digests",
    ):
        if forbidden in manifest:
            raise RestructureError(f"source already contains reserved restructuring field: {forbidden}")
    updated, count = re.subn(
        r"^status: replan_required$", "status: replanned", source_text, count=1, flags=re.MULTILINE
    )
    if count != 1:
        raise RestructureError("source plan must have exactly one status: replan_required field")
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
    marker = "checked_summary_ja:"
    offset = updated.find(marker)
    if offset < 0:
        raise RestructureError("source plan lacks checked_summary_ja")
    return updated[:offset] + "\n".join(block) + "\n" + updated[offset:]


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
    for path in actual_dirty:
        if not any(scope_covers(scope, path) for scope in successor_scopes):
            raise RestructureError(f"dirty product path is outside successor write scopes: {path}")
    active_text = ACTIVE_INDEX.read_text(encoding="utf-8")
    rows = active_rows(active_text)
    if rows.count((source_id, source_path, "replan_required")) != 1:
        raise RestructureError("active index does not exactly map the stopped source plan")
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
        "schema_version": 1,
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
            }
            for index, entry in enumerate(entries)
        ],
    }
    new_rows = [row for row in rows if row[0] != source_id]
    new_rows.extend((entry["id"], entry["path"], "in_progress") for entry in entries)
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


def verify_repository_contracts() -> None:
    if not REPLANNED_INDEX.is_file():
        raise RestructureError("missing docs/plan/replanned.md")
    rows = replanned_rows(REPLANNED_INDEX.read_text(encoding="utf-8"))
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
            contract = json.loads(contract_file.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RestructureError(f"invalid durable contract for {plan_id}: {exc}") from exc
        exact_object(
            contract,
            {"schema_version", "created_at", "contract_path", "source", "reason_codes", "dirty_product_paths", "archive_path", "successors"},
            f"contract {plan_id}",
        )
        if contract["schema_version"] != 1 or contract["contract_path"] != contract_path:
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
        if not isinstance(source["content"], str) or sha256(source["content"].encode()) != source["plan_digest"]:
            raise RestructureError(f"contract source content digest mismatch for {plan_id}")
        if acceptance_records(source["content"]) != source["acceptance"]:
            raise RestructureError(f"contract source acceptance mismatch for {plan_id}")
        source_records = source["acceptance"]
        source_digests = [record["digest"] for record in source_records]
        source_text_by_digest = {record["digest"]: record["text"] for record in source_records}
        successors = contract["successors"]
        if not isinstance(successors, list) or not successors:
            raise RestructureError(f"contract has no successors for {plan_id}")
        paths: list[str] = []
        mapped: set[str] = set()
        integration_count = 0
        for index, raw_successor in enumerate(successors):
            successor = exact_object(
                raw_successor,
                {"id", "path", "content_digest", "content", "acceptance_digests", "integration"},
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
            checked_paths = checked_paths_for_id(successor["id"])
            active_exists = active_file.is_file()
            if active_exists and checked_paths:
                raise RestructureError(f"successor exists in both active and checked indexes: {path}")
            if len(checked_paths) > 1:
                raise RestructureError(f"successor has multiple checked index entries: {path}")
            if active_exists:
                live_successor_file = active_file
            elif checked_paths:
                reject_symlink_ancestors(checked_paths[0], include_target=True)
                live_successor_file = ROOT / checked_paths[0]
                if not live_successor_file.is_file():
                    raise RestructureError(f"missing checked successor plan for {plan_id}: {checked_paths[0]}")
            else:
                raise RestructureError(f"missing live successor plan for {plan_id}: {path}")
            live_successor_manifest = parse_manifest(live_successor_file.read_text(encoding="utf-8"))
            if items(live_successor_manifest, "inherited_acceptance_digests") != digests:
                raise RestructureError(f"live successor lineage mismatch for {plan_id}: {path}")
            if items(live_successor_manifest, "acceptance") != expected_successor_acceptance:
                raise RestructureError(f"live successor acceptance mismatch for {plan_id}: {path}")
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
