#!/usr/bin/env python3
"""Render plan files and lifecycle index updates from one checked authoring input.

The authoring input is a bounded local source, not a repository authority. It
is checked once with no repository write, and the write operation reproduces
the same digest before it renders anything, so the plan that lands is the plan
that was reviewed. Correspondence from an accepted requirement through its
write paths and completion predicates to a claimed witness behaviour and its
command is declared explicitly and covered exactly once; every manifest digest
is derived here instead of being accepted from the caller.

Deterministic checking proves references, bounds, derived digests, rendering
stability, and atomic write behaviour. It never infers that a command
semantically establishes a condition. Claimed witness behaviour is reported
verbatim so that a human reviewer judges it.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


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

SCHEMA_VERSION = 1
MAX_INPUT_BYTES = 256 * 1024
PROFILE_ROOT = "root"
PROFILE_GENERATED = "generated"
PROFILES = (PROFILE_ROOT, PROFILE_GENERATED)
STRUCTURED_INTERFACE = "structured_input"
LEGACY_INTERFACE = "legacy_arguments"
AUTHORING_INTERFACES = (STRUCTURED_INTERFACE, LEGACY_INTERFACE)
LIFECYCLE_VALUES = {"active": "in_progress", "backlog": "backlog"}
REVIEW_CLASS_VALUES = {"A", "B", "C"}
HUMAN_DESIGN_VALUES = {"yes", "no"}
HUMAN_APPROVAL_VALUES = {"not_required", "pending", "approved"}
IMPLEMENTATION_TIER_VALUES = {"0", "1", "2"}
IMPLEMENTATION_CLASSIFICATION_VALUES = {"low", "ordinary", "high"}
IDENTIFIER_RE = re.compile(r"[a-z][a-z0-9-]{0,39}")
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
PLAN_ID_RE = re.compile(r"[0-9]{3}")
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
MAX_REQUIREMENTS = 8
MAX_WRITE_PATHS = 64
MAX_WITNESSES = 8
MAX_ACCEPTANCE_ITEMS = 8
MAX_LIST_ENTRIES = 32
MAX_TEXT_BYTES = 400
MAX_SUMMARY_BYTES = 200
# The argument interface never bounded its title, so the conversion keeps a wider
# bound for it rather than rejecting an invocation that used to be accepted.
MAX_LEGACY_SUMMARY_BYTES = 400
MAX_PATH_BYTES = 200
MAX_COMMAND_BYTES = 200
MAX_SECTION_ENTRIES = 32
MAX_SECTION_BYTES = 800

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
VALIDATION_WITNESS_STAGES = ("static", "focused", "authoritative")
STATIC_VALIDATION_WITNESSES = {"resolved-context-files"}
VALIDATION_WITNESS_REASON_MAX_BYTES = 240
CONTEXT_FILES_NONE = "none"

COMMON_REQUIRED_KEYS = (
    "schema_version",
    "profile",
    "lifecycle",
    "slug",
    "summary",
    "summary_ja",
    "plan_purpose",
    "task_types",
    "review_class",
    "human_design_required",
    "human_approval_status",
    "feasibility_evidence",
    "witnesses",
    "write_paths",
    "completion_conditions",
    "acceptance_items",
    "requirements",
    "context_files",
    "required_specs",
    "validation",
    "decisions",
    "tasks",
)
COMMON_OPTIONAL_KEYS = (
    "integration_gates",
    "validation_notes",
)
PROFILE_REQUIRED_KEYS = {
    PROFILE_ROOT: ("primary_invariant", "implementation_tier"),
    PROFILE_GENERATED: ("target_json", "acceptance_focus", "problem", "goal",
                        "implementation_instructions"),
}
PROFILE_OPTIONAL_KEYS = {
    PROFILE_ROOT: ("implementation_risk", "implementation_ambiguity", "preservation_scope"),
    PROFILE_GENERATED: (),
}
LEGACY_PLACEHOLDER_KEYS = frozenset(
    {
        "acceptance_items",
        "acceptance_focus",
        "decisions",
        "tasks",
        "problem",
        "goal",
    }
)


class AuthoringError(ValueError):
    """Raised when a bounded authoring input or its target cannot be accepted."""


def locate_worktree_guard() -> Any:
    """Load the shared worktree guard shipped beside this module."""

    candidate = Path(__file__).resolve().with_name("worktree_guard.py")
    if not candidate.is_file():
        raise AuthoringError("could not locate worktree_guard.py beside this module")
    spec = importlib.util.spec_from_file_location("plan_authoring_worktree_guard", candidate)
    if spec is None or spec.loader is None:
        raise AuthoringError("could not load worktree_guard.py beside this module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def lifecycle_lock(root: Path):
    """Hold the exclusive plan lifecycle lock every linked worktree shares.

    A lock inside one worktree cannot serialize a second linked checkout of the
    same repository, so the lock lives under the common Git directory. A
    directory that is not a Git worktree at all, such as a rendered fixture,
    has no shared directory to bind to and keeps the local lock; it also has no
    second checkout to race against. Acquisition is separated from the guarded
    body so that a failure raised by the caller never re-runs that body.
    """

    shared = None
    try:
        candidate = locate_worktree_guard().plan_lifecycle_lock(root)
        candidate.__enter__()
        shared = candidate
    except Exception:  # noqa: BLE001 - any guard failure falls back to the local lock
        shared = None
    if shared is not None:
        try:
            yield
        finally:
            shared.__exit__(None, None, None)
        return
    lock_dir = root / ".agent-artifacts"
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir / "plan-lifecycle.lock").open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def text_digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def byte_digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def is_placeholder(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return stripped.lower().strip(" .") in ADMISSION_PLACEHOLDER_VALUES


def bounded_text(value: object, label: str, maximum_bytes: int, *, allow_placeholder: bool = False) -> str:
    """Return one bounded single-line manifest value or refuse it."""

    if not isinstance(value, str):
        raise AuthoringError(f"{label} must be text")
    if value != value.strip():
        raise AuthoringError(f"{label} must not carry leading or trailing whitespace")
    if not value:
        raise AuthoringError(f"{label} must not be empty")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise AuthoringError(f"{label} must be encodable as UTF-8") from exc
    if len(encoded) > maximum_bytes:
        raise AuthoringError(f"{label} must be at most {maximum_bytes} bytes")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        raise AuthoringError(f"{label} must not contain control characters")
    if not allow_placeholder and is_placeholder(value):
        raise AuthoringError(f"{label} must not be a placeholder value")
    return value


def bounded_identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or IDENTIFIER_RE.fullmatch(value) is None:
        raise AuthoringError(f"{label} must be a lowercase hyphenated identifier")
    return value


def bounded_list(value: object, label: str, maximum: int) -> list[Any]:
    if not isinstance(value, list):
        raise AuthoringError(f"{label} must be a list")
    if not value:
        raise AuthoringError(f"{label} must declare at least one entry")
    if len(value) > maximum:
        raise AuthoringError(f"{label} must declare at most {maximum} entries")
    return value


def exact_object(value: object, label: str, required: set[str], optional: set[str] = frozenset()) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuthoringError(f"{label} must be an object")
    keys = set(value)
    missing = sorted(required - keys)
    if missing:
        raise AuthoringError(f"{label} is missing required keys: {', '.join(missing)}")
    unknown = sorted(keys - required - set(optional))
    if unknown:
        raise AuthoringError(f"{label} declares unknown keys: {', '.join(unknown)}")
    return value


def normalized_repository_path(value: object, label: str) -> str:
    """Return one repository-relative path with no traversal or absolute prefix."""

    path = bounded_text(value, label, MAX_PATH_BYTES, allow_placeholder=True)
    if is_placeholder(path):
        raise AuthoringError(f"{label} must not be a placeholder value")
    if path.startswith("/") or "\\" in path or ":" in path:
        raise AuthoringError(f"{label} must be a repository-relative path: {path!r}")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise AuthoringError(f"{label} must not contain empty or traversing segments: {path!r}")
    return path


def reject_symlinked_components(root: Path, relative: str, label: str) -> None:
    """Refuse a path whose existing components include a symlink."""

    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink():
            raise AuthoringError(f"{label} resolves through a symlink: {relative}")


def reject_control_characters(value: Any, label: str) -> None:
    if isinstance(value, str):
        for char in value:
            if ord(char) < 0x20 or ord(char) == 0x7F:
                raise AuthoringError(f"{label} contains a control character")
        return
    if isinstance(value, list):
        for index, item in enumerate(value, start=1):
            reject_control_characters(item, f"{label} entry {index}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            reject_control_characters(key, f"{label} key")
            reject_control_characters(item, f"{label}.{key}")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuthoringError(f"authoring input repeats the key {key!r}")
        result[key] = value
    return result


def read_input_bytes(path: Path) -> bytes:
    """Read the exact bounded authoring input bytes."""

    if path.is_symlink():
        raise AuthoringError(f"authoring input must not be a symlink: {path}")
    if not path.is_file():
        raise AuthoringError(f"missing authoring input: {path}")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise AuthoringError(f"authoring input exceeds {MAX_INPUT_BYTES} bytes: {path}")
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise AuthoringError(f"authoring input exceeds {MAX_INPUT_BYTES} bytes: {path}")
    return raw


def parse_input(raw: bytes) -> dict[str, Any]:
    """Return one UTF-8 JSON object with no duplicate keys or control characters."""

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuthoringError(f"authoring input is not UTF-8 text: {exc}") from exc
    try:
        document = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise AuthoringError(f"authoring input is not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise AuthoringError("authoring input must be one JSON object")
    reject_control_characters(document, "authoring input")
    return document


def build_document(
    data: dict[str, Any], *, profile: str, interface: str = STRUCTURED_INTERFACE
) -> dict[str, Any]:
    """Return the checked correspondence and every derived manifest value."""

    if profile not in PROFILES:
        raise AuthoringError(f"unsupported authoring profile: {profile!r}")
    required = set(COMMON_REQUIRED_KEYS) | set(PROFILE_REQUIRED_KEYS[profile])
    optional = set(COMMON_OPTIONAL_KEYS) | set(PROFILE_OPTIONAL_KEYS[profile])
    exact_object(data, "authoring input", required, optional)

    if data["schema_version"] != SCHEMA_VERSION:
        raise AuthoringError(f"authoring input schema_version must be {SCHEMA_VERSION}")
    if data["profile"] != profile:
        raise AuthoringError(
            f"authoring input profile {data['profile']!r} does not match the requested {profile!r}"
        )
    if interface not in AUTHORING_INTERFACES:
        raise AuthoringError(f"unsupported authoring interface: {interface!r}")
    if interface == LEGACY_INTERFACE and profile != PROFILE_GENERATED:
        raise AuthoringError("the legacy argument interface renders generated plans only")
    placeholder_keys = LEGACY_PLACEHOLDER_KEYS if interface == LEGACY_INTERFACE else frozenset()

    lifecycle = data["lifecycle"]
    if lifecycle not in LIFECYCLE_VALUES:
        raise AuthoringError("lifecycle must be active or backlog")
    slug = bounded_text(data["slug"], "slug", MAX_SUMMARY_BYTES)
    if SLUG_RE.fullmatch(slug) is None:
        raise AuthoringError("slug must use lowercase letters, numbers, and hyphens")
    legacy = interface == LEGACY_INTERFACE

    def title(field: str) -> str:
        value = data[field]
        if legacy and isinstance(value, str):
            # The argument interface bounded neither title and rendered a padded
            # value verbatim, which produced a trailing-whitespace line. Strip it
            # instead of rejecting an invocation that used to be accepted.
            value = value.strip()
        return bounded_text(
            value,
            field,
            MAX_LEGACY_SUMMARY_BYTES if legacy else MAX_SUMMARY_BYTES,
            allow_placeholder=legacy,
        )

    summary = title("summary")
    summary_ja = title("summary_ja")
    if data["plan_purpose"] not in PLAN_PURPOSE_VALUES:
        raise AuthoringError("plan_purpose must be implementation")
    review_class = data["review_class"]
    if review_class not in REVIEW_CLASS_VALUES:
        raise AuthoringError("review_class must be A, B, or C")
    human_design = data["human_design_required"]
    if human_design not in HUMAN_DESIGN_VALUES:
        raise AuthoringError("human_design_required must be yes or no")
    approval = data["human_approval_status"]
    if approval not in HUMAN_APPROVAL_VALUES:
        raise AuthoringError("human_approval_status must be not_required, pending, or approved")
    if human_design == "yes" and review_class != "C":
        raise AuthoringError("human_design_required: yes requires review_class: C")
    if review_class == "C" and approval not in {"pending", "approved"}:
        raise AuthoringError("review_class C requires human_approval_status pending or approved")
    if review_class == "C" and lifecycle == "active" and approval != "approved":
        raise AuthoringError("an active class C plan requires human_approval_status: approved")

    task_types = unique_texts(data["task_types"], "task_types", MAX_LIST_ENTRIES, MAX_TEXT_BYTES)
    required_specs = unique_paths(data["required_specs"], "required_specs", MAX_LIST_ENTRIES)
    context_files = unique_paths(
        data["context_files"], "context_files", MAX_LIST_ENTRIES, allow_placeholder=True
    )
    validation = unique_commands(data["validation"], "validation", MAX_LIST_ENTRIES)
    integration_gates = optional_texts(
        data.get("integration_gates", []), "integration_gates", MAX_LIST_ENTRIES, MAX_SECTION_BYTES
    )

    feasibility = build_feasibility(data["feasibility_evidence"])
    witnesses = build_witnesses(data["witnesses"])
    write_paths = build_write_paths(data["write_paths"])
    conditions = build_conditions(data["completion_conditions"], witnesses)
    acceptance_items = build_acceptance_items(
        data["acceptance_items"],
        witnesses,
        allow_placeholder="acceptance_items" in placeholder_keys,
    )
    requirements = build_requirements(
        data["requirements"], write_paths, conditions, acceptance_items
    )

    write_scope = [write_paths[item]["path"] for item in ordered_ids(requirements, "write_paths")]
    overlap = sorted(
        (set(write_scope) - {CONTEXT_FILES_NONE}) & (set(context_files) - {CONTEXT_FILES_NONE})
    )
    if overlap:
        raise AuthoringError(f"write_scope and context_files overlap: {', '.join(overlap)}")
    if not [
        path
        for path in write_scope
        if not is_placeholder(path) and not path.startswith(ADMISSION_LIFECYCLE_PREFIXES)
    ]:
        raise AuthoringError(
            "plan_purpose: implementation requires a write_scope path outside plan-lifecycle records"
        )

    condition_ids = ordered_ids(requirements, "completion_conditions")
    acceptance_ids = ordered_ids(requirements, "acceptance_items")
    focused: list[str] = []
    for identifier in condition_ids:
        command = witnesses[conditions[identifier]["witness"]]["command"]
        if command not in focused:
            focused.append(command)
    for identifier in acceptance_ids:
        item = acceptance_items[identifier]
        if item["stage"] != "focused":
            continue
        command = witnesses[item["witness"]]["command"]
        if command not in focused:
            focused.append(command)
    if not focused:
        raise AuthoringError("completion witnesses must declare at least one focused command")

    condition_texts = [conditions[identifier]["text"] for identifier in condition_ids]
    completion_witness_map = [
        {
            "condition_sha256": text_digest(text),
            "witness": witnesses[conditions[identifier]["witness"]]["command"],
        }
        for identifier, text in zip(condition_ids, condition_texts)
    ]
    acceptance_texts = [acceptance_items[identifier]["text"] for identifier in acceptance_ids]
    validation_witness_map = build_validation_witness_map(
        acceptance_ids, acceptance_items, witnesses, focused, validation
    )
    if validation_witness_map and len(set(acceptance_texts)) != len(acceptance_texts):
        raise AuthoringError("acceptance items must be unique before witness mapping")

    document: dict[str, Any] = {
        "profile": profile,
        "authoring_interface": interface,
        "lifecycle": lifecycle,
        "status": LIFECYCLE_VALUES[lifecycle],
        "slug": slug,
        "summary": summary,
        "summary_ja": summary_ja,
        "plan_purpose": data["plan_purpose"],
        "task_types": task_types,
        "review_class": review_class,
        "human_design_required": human_design,
        "human_approval_status": approval,
        "feasibility_evidence": feasibility,
        "witnesses": witnesses,
        "write_paths": write_paths,
        "completion_conditions": conditions,
        "acceptance_items": acceptance_items,
        "requirements": requirements,
        "condition_order": condition_ids,
        "acceptance_order": acceptance_ids,
        "write_scope": write_scope,
        "focused_validation": focused,
        "completion_witness_map": completion_witness_map,
        "validation_witness_map": validation_witness_map,
        "acceptance": acceptance_texts,
        "context_files": context_files,
        "required_specs": required_specs,
        "validation": validation,
        "integration_gates": integration_gates,
        "decisions": section_entries(
            data["decisions"], "decisions", allow_placeholder="decisions" in placeholder_keys
        ),
        "tasks": section_entries(
            data["tasks"], "tasks", allow_placeholder="tasks" in placeholder_keys
        ),
        "validation_notes": optional_texts(
            data.get("validation_notes", []), "validation_notes", MAX_SECTION_ENTRIES, MAX_SECTION_BYTES
        ),
    }
    if profile == PROFILE_ROOT:
        document["primary_invariant"] = bounded_text(
            data["primary_invariant"], "primary_invariant", MAX_TEXT_BYTES
        )
        tier = data["implementation_tier"]
        if tier not in IMPLEMENTATION_TIER_VALUES:
            raise AuthoringError("implementation_tier must be 0, 1, or 2")
        document["implementation_tier"] = tier
        for key in ("implementation_risk", "implementation_ambiguity"):
            value = data.get(key)
            if value is None:
                continue
            if value not in IMPLEMENTATION_CLASSIFICATION_VALUES:
                raise AuthoringError(f"{key} must be low, ordinary, or high")
            document[key] = value
        preservation = data.get("preservation_scope", [CONTEXT_FILES_NONE])
        document["preservation_scope"] = unique_paths(
            preservation, "preservation_scope", MAX_LIST_ENTRIES, allow_placeholder=True
        )
        conflict = sorted(set(document["preservation_scope"]) & set(write_scope))
        if conflict:
            raise AuthoringError(
                f"preservation_scope must stay disjoint from write_scope: {', '.join(conflict)}"
            )
    else:
        document["target_json"] = unique_paths(
            data["target_json"], "target_json", MAX_LIST_ENTRIES, allow_placeholder=True
        )
        document["acceptance_focus"] = optional_texts(
            data["acceptance_focus"],
            "acceptance_focus",
            MAX_LIST_ENTRIES,
            MAX_TEXT_BYTES,
            allow_placeholder="acceptance_focus" in placeholder_keys,
        )
        for key in ("problem", "goal", "implementation_instructions"):
            document[key] = section_paragraphs(
                data[key], key, allow_placeholder=key in placeholder_keys
            )
    # Only the declared authoritative suite is checked against the runner's
    # command grammar. Witness commands stay caller text, so a witness that this
    # repository's runner cannot execute is still rejected when it is declared as
    # an authoritative command and still unproven when it is not.
    validate_command_syntax(validation)
    return document


def unique_texts(value: object, label: str, maximum: int, maximum_bytes: int) -> list[str]:
    items = [
        bounded_text(item, f"{label} entry {index}", maximum_bytes)
        for index, item in enumerate(bounded_list(value, label, maximum), start=1)
    ]
    if len(set(items)) != len(items):
        raise AuthoringError(f"{label} must not repeat an entry")
    return items


def optional_texts(
    value: object,
    label: str,
    maximum: int,
    maximum_bytes: int,
    *,
    allow_placeholder: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        raise AuthoringError(f"{label} must be a list")
    if len(value) > maximum:
        raise AuthoringError(f"{label} must declare at most {maximum} entries")
    items = [
        bounded_text(item, f"{label} entry {index}", maximum_bytes, allow_placeholder=allow_placeholder)
        for index, item in enumerate(value, start=1)
    ]
    if len(set(items)) != len(items):
        raise AuthoringError(f"{label} must not repeat an entry")
    return items


def unique_paths(value: object, label: str, maximum: int, *, allow_placeholder: bool = False) -> list[str]:
    entries = bounded_list(value, label, maximum)
    items: list[str] = []
    for index, item in enumerate(entries, start=1):
        entry_label = f"{label} entry {index}"
        if allow_placeholder and isinstance(item, str) and item == CONTEXT_FILES_NONE:
            items.append(CONTEXT_FILES_NONE)
            continue
        items.append(normalized_repository_path(item, entry_label))
    if len(set(items)) != len(items):
        raise AuthoringError(f"{label} must not repeat an entry")
    if CONTEXT_FILES_NONE in items and len(items) != 1:
        raise AuthoringError(f"{label} must not mix the none sentinel with real paths")
    return items


def unique_commands(value: object, label: str, maximum: int) -> list[str]:
    items = [
        bounded_text(item, f"{label} entry {index}", MAX_COMMAND_BYTES)
        for index, item in enumerate(bounded_list(value, label, maximum), start=1)
    ]
    if len(set(items)) != len(items):
        raise AuthoringError(f"{label} must not repeat a command")
    return items


def section_entries(value: object, label: str, *, allow_placeholder: bool = False) -> list[str]:
    return [
        bounded_text(
            item, f"{label} entry {index}", MAX_SECTION_BYTES, allow_placeholder=allow_placeholder
        )
        for index, item in enumerate(
            bounded_list(value, label, MAX_SECTION_ENTRIES), start=1
        )
    ]


def section_paragraphs(value: object, label: str, *, allow_placeholder: bool = False) -> list[str]:
    return section_entries(value, label, allow_placeholder=allow_placeholder)


def build_feasibility(value: object) -> list[dict[str, str]]:
    entries = bounded_list(value, "feasibility_evidence", MAX_FEASIBILITY_EVIDENCE)
    records: list[dict[str, str]] = []
    for index, item in enumerate(entries, start=1):
        label = f"feasibility_evidence entry {index}"
        record = exact_object(item, label, {"kind", "evidence"})
        if record["kind"] not in FEASIBILITY_EVIDENCE_KINDS:
            raise AuthoringError(f"{label} has an unsupported kind: {record['kind']!r}")
        records.append(
            {
                "kind": record["kind"],
                "evidence": bounded_text(
                    record["evidence"], f"{label} evidence", FEASIBILITY_EVIDENCE_MAX_BYTES
                ),
            }
        )
    serialized = [compact_json(record) for record in records]
    if len(set(serialized)) != len(serialized):
        raise AuthoringError("feasibility_evidence must not repeat a record")
    return records


def build_witnesses(value: object) -> dict[str, dict[str, str]]:
    entries = bounded_list(value, "witnesses", MAX_WITNESSES)
    witnesses: dict[str, dict[str, str]] = {}
    for index, item in enumerate(entries, start=1):
        label = f"witnesses entry {index}"
        record = exact_object(item, label, {"id", "command", "claim"})
        identifier = bounded_identifier(record["id"], f"{label} id")
        if identifier in witnesses:
            raise AuthoringError(f"witnesses repeats the identifier {identifier!r}")
        witnesses[identifier] = {
            "id": identifier,
            "command": bounded_text(record["command"], f"{label} command", MAX_COMMAND_BYTES),
            "claim": bounded_text(record["claim"], f"{label} claim", MAX_TEXT_BYTES),
        }
    commands = [record["command"] for record in witnesses.values()]
    if len(set(commands)) != len(commands):
        raise AuthoringError("witnesses must not declare the same command twice")
    return witnesses


def build_write_paths(value: object) -> dict[str, dict[str, str]]:
    entries = bounded_list(value, "write_paths", MAX_WRITE_PATHS)
    paths: dict[str, dict[str, str]] = {}
    seen: set[str] = set()
    for index, item in enumerate(entries, start=1):
        label = f"write_paths entry {index}"
        record = exact_object(item, label, {"id", "path"})
        identifier = bounded_identifier(record["id"], f"{label} id")
        if identifier in paths:
            raise AuthoringError(f"write_paths repeats the identifier {identifier!r}")
        path = normalized_repository_path(record["path"], f"{label} path")
        if path == CONTEXT_FILES_NONE:
            raise AuthoringError(f"{label} path must name a real repository path")
        if path in seen:
            raise AuthoringError(f"write_paths repeats the path {path!r}")
        seen.add(path)
        paths[identifier] = {"id": identifier, "path": path}
    return paths


def build_conditions(value: object, witnesses: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    entries = bounded_list(value, "completion_conditions", MAX_COMPLETION_CONDITIONS)
    conditions: dict[str, dict[str, str]] = {}
    texts: set[str] = set()
    for index, item in enumerate(entries, start=1):
        label = f"completion_conditions entry {index}"
        record = exact_object(item, label, {"id", "text", "witness"})
        identifier = bounded_identifier(record["id"], f"{label} id")
        if identifier in conditions:
            raise AuthoringError(f"completion_conditions repeats the identifier {identifier!r}")
        text = bounded_text(record["text"], f"{label} text", COMPLETION_CONDITION_MAX_BYTES)
        if text in texts:
            raise AuthoringError("completion_conditions must be unique")
        texts.add(text)
        witness = bounded_identifier(record["witness"], f"{label} witness")
        if witness not in witnesses:
            raise AuthoringError(f"{label} names an undeclared witness: {witness!r}")
        conditions[identifier] = {"id": identifier, "text": text, "witness": witness}
    return conditions


def build_acceptance_items(
    value: object,
    witnesses: dict[str, dict[str, str]],
    *,
    allow_placeholder: bool,
) -> dict[str, dict[str, str]]:
    entries = bounded_list(value, "acceptance_items", MAX_ACCEPTANCE_ITEMS)
    items: dict[str, dict[str, str]] = {}
    mapped: set[bool] = set()
    for index, item in enumerate(entries, start=1):
        label = f"acceptance_items entry {index}"
        record = exact_object(
            item, label, {"id", "text"}, {"witness", "stage", "authoritative_only_reason"}
        )
        identifier = bounded_identifier(record["id"], f"{label} id")
        if identifier in items:
            raise AuthoringError(f"acceptance_items repeats the identifier {identifier!r}")
        text = bounded_text(
            record["text"], f"{label} text", MAX_TEXT_BYTES, allow_placeholder=allow_placeholder
        )
        entry: dict[str, str] = {"id": identifier, "text": text, "witness": "", "stage": ""}
        if "witness" in record or "stage" in record:
            witness = bounded_identifier(record.get("witness"), f"{label} witness")
            if witness not in witnesses:
                raise AuthoringError(f"{label} names an undeclared witness: {witness!r}")
            stage = record.get("stage")
            if stage not in VALIDATION_WITNESS_STAGES:
                raise AuthoringError(
                    f"{label} stage must be static, focused, or authoritative"
                )
            entry["witness"] = witness
            entry["stage"] = stage
            if stage == "authoritative":
                entry["authoritative_only_reason"] = bounded_text(
                    record.get("authoritative_only_reason"),
                    f"{label} authoritative_only_reason",
                    VALIDATION_WITNESS_REASON_MAX_BYTES,
                )
            elif "authoritative_only_reason" in record:
                raise AuthoringError(
                    f"{label} may declare authoritative_only_reason only for an authoritative stage"
                )
            mapped.add(True)
        else:
            if not allow_placeholder:
                raise AuthoringError(f"{label} must declare its witness and stage")
            if "authoritative_only_reason" in record:
                raise AuthoringError(f"{label} declares a reason without a witness")
            mapped.add(False)
        items[identifier] = entry
    if len(mapped) != 1:
        raise AuthoringError("acceptance_items must either all declare witnesses or none of them")
    return items


def build_requirements(
    value: object,
    write_paths: dict[str, dict[str, str]],
    conditions: dict[str, dict[str, str]],
    acceptance_items: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    entries = bounded_list(value, "requirements", MAX_REQUIREMENTS)
    requirements: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(entries, start=1):
        label = f"requirements entry {index}"
        record = exact_object(
            item, label, {"id", "text", "write_paths", "completion_conditions", "acceptance_items"}
        )
        identifier = bounded_identifier(record["id"], f"{label} id")
        if identifier in seen_ids:
            raise AuthoringError(f"requirements repeats the identifier {identifier!r}")
        seen_ids.add(identifier)
        requirements.append(
            {
                "id": identifier,
                "text": bounded_text(record["text"], f"{label} text", MAX_TEXT_BYTES),
                "write_paths": reference_list(record["write_paths"], f"{label} write_paths"),
                "completion_conditions": reference_list(
                    record["completion_conditions"], f"{label} completion_conditions"
                ),
                "acceptance_items": reference_list(
                    record["acceptance_items"], f"{label} acceptance_items"
                ),
            }
        )
    require_exact_coverage(requirements, "write_paths", write_paths)
    require_exact_coverage(requirements, "completion_conditions", conditions)
    require_exact_coverage(requirements, "acceptance_items", acceptance_items)
    return requirements


def reference_list(value: object, label: str) -> list[str]:
    entries = bounded_list(value, label, MAX_LIST_ENTRIES)
    items = [
        bounded_identifier(item, f"{label} entry {index}")
        for index, item in enumerate(entries, start=1)
    ]
    if len(set(items)) != len(items):
        raise AuthoringError(f"{label} must not repeat a reference")
    return items


def require_exact_coverage(
    requirements: list[dict[str, Any]], field: str, declared: dict[str, Any]
) -> None:
    """Require every declared entry to be claimed by exactly one requirement."""

    counts: dict[str, int] = {}
    for requirement in requirements:
        for identifier in requirement[field]:
            if identifier not in declared:
                raise AuthoringError(
                    f"requirement {requirement['id']!r} references an undeclared {field} entry: "
                    f"{identifier!r}"
                )
            counts[identifier] = counts.get(identifier, 0) + 1
    duplicated = sorted(key for key, count in counts.items() if count > 1)
    if duplicated:
        raise AuthoringError(
            f"{field} entries are claimed by more than one requirement: {', '.join(duplicated)}"
        )
    uncovered = sorted(set(declared) - set(counts))
    if uncovered:
        raise AuthoringError(f"{field} entries are claimed by no requirement: {', '.join(uncovered)}")


def ordered_ids(requirements: list[dict[str, Any]], field: str) -> list[str]:
    return [identifier for requirement in requirements for identifier in requirement[field]]


def build_validation_witness_map(
    acceptance_ids: list[str],
    acceptance_items: dict[str, dict[str, str]],
    witnesses: dict[str, dict[str, str]],
    focused: list[str],
    validation: list[str],
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for identifier in acceptance_ids:
        item = acceptance_items[identifier]
        if not item["stage"]:
            return []
        command = witnesses[item["witness"]]["command"]
        stage = item["stage"]
        record = {"acceptance_sha256": text_digest(item["text"]), "stage": stage, "witness": command}
        if stage == "static":
            if command not in STATIC_VALIDATION_WITNESSES:
                raise AuthoringError(
                    f"acceptance item {identifier!r} names an unknown static witness: {command!r}"
                )
        elif stage == "focused":
            if command not in focused:
                raise AuthoringError(
                    f"acceptance item {identifier!r} focused witness is not a derived focused command"
                )
        else:
            if command not in validation:
                raise AuthoringError(
                    f"acceptance item {identifier!r} authoritative witness is not a declared "
                    "validation command"
                )
            if command in focused:
                raise AuthoringError(
                    f"acceptance item {identifier!r} skips an available focused witness"
                )
            record["authoritative_only_reason"] = item["authoritative_only_reason"]
        records.append(record)
    return records


def locate_validation_commands() -> Any:
    """Load the shared validation-command parser shipped beside this module."""

    candidates = (
        Path(__file__).resolve().with_name("plan_validation_commands.py"),
        Path(__file__).resolve().parents[1] / "plan_validation_commands.py",
    )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location(
            "plan_authoring_validation_commands", candidate
        )
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    raise AuthoringError("could not locate plan_validation_commands.py beside this command")


def validate_command_syntax(commands: list[str]) -> None:
    module = locate_validation_commands()
    try:
        module.parse_validation_commands(list(dict.fromkeys(commands)))
    except module.ValidationCommandError as exc:
        raise AuthoringError(f"declared validation command is invalid: {exc}") from exc


def manifest_list(field: str, items: list[str]) -> list[str]:
    lines = [f"{field}:"]
    lines.extend(f"  - {item}" for item in items)
    return lines


def render_plan(document: dict[str, Any], plan_id: str) -> str:
    """Render the complete plan file for one profile from the checked document."""

    if PLAN_ID_RE.fullmatch(plan_id) is None:
        raise AuthoringError(f"plan id must be three digits: {plan_id!r}")
    if document["profile"] == PROFILE_ROOT:
        return render_root_plan(document)
    return render_generated_plan(document)


def render_root_plan(document: dict[str, Any]) -> str:
    lines = [f"# {document['summary']}", ""]
    lines.append(f"status: {document['status']}")
    lines.append(f"primary_invariant: {document['primary_invariant']}")
    lines.extend(manifest_list("task_types", document["task_types"]))
    lines.append(f"review_class: {document['review_class']}")
    lines.append(f"human_design_required: {document['human_design_required']}")
    lines.append(f"human_approval_status: {document['human_approval_status']}")
    lines.append(f"implementation_tier: {document['implementation_tier']}")
    for key in ("implementation_risk", "implementation_ambiguity"):
        if key in document:
            lines.append(f"{key}: {document[key]}")
    lines.append(f"plan_purpose: {document['plan_purpose']}")
    lines.extend(
        manifest_list(
            "feasibility_evidence", [compact_json(record) for record in document["feasibility_evidence"]]
        )
    )
    lines.extend(
        manifest_list(
            "completion_conditions",
            [document["completion_conditions"][item]["text"] for item in document["condition_order"]],
        )
    )
    lines.extend(
        manifest_list(
            "completion_witness_map",
            [compact_json(record) for record in document["completion_witness_map"]],
        )
    )
    lines.extend(manifest_list("write_scope", document["write_scope"]))
    lines.extend(manifest_list("preservation_scope", document["preservation_scope"]))
    lines.extend(manifest_list("context_files", document["context_files"]))
    lines.extend(manifest_list("required_specs", document["required_specs"]))
    lines.extend(manifest_list("focused_validation", document["focused_validation"]))
    lines.extend(manifest_list("validation", document["validation"]))
    lines.extend(manifest_list("acceptance", document["acceptance"]))
    if document["validation_witness_map"]:
        lines.append("validation_witness_schema: 1")
        lines.extend(
            manifest_list(
                "validation_witness_map",
                [compact_json(record) for record in document["validation_witness_map"]],
            )
        )
    if document["integration_gates"]:
        lines.extend(manifest_list("integration_gates", document["integration_gates"]))
    lines.append(f"checked_summary_ja: {document['summary_ja']}")
    lines.append("")
    lines.extend(bullet_section("Decisions", document["decisions"]))
    lines.extend(task_section(document["tasks"]))
    lines.extend(bullet_section("Validation Notes", document["validation_notes"]))
    return "\n".join(lines).rstrip("\n") + "\n"


def render_generated_plan(document: dict[str, Any]) -> str:
    lines = [f"# {document['summary']}", ""]
    lines.append(f"status: {document['status']}")
    lines.extend(manifest_list("task_types", document["task_types"]))
    lines.append(f"review_class: {document['review_class']}")
    lines.append(f"human_design_required: {document['human_design_required']}")
    lines.append(f"human_approval_status: {document['human_approval_status']}")
    lines.append(f"plan_purpose: {document['plan_purpose']}")
    lines.extend(manifest_list("write_scope", document["write_scope"]))
    lines.extend(manifest_list("focused_validation", document["focused_validation"]))
    lines.extend(
        manifest_list(
            "feasibility_evidence", [compact_json(record) for record in document["feasibility_evidence"]]
        )
    )
    lines.extend(
        manifest_list(
            "completion_conditions",
            [document["completion_conditions"][item]["text"] for item in document["condition_order"]],
        )
    )
    lines.extend(
        manifest_list(
            "completion_witness_map",
            [compact_json(record) for record in document["completion_witness_map"]],
        )
    )
    lines.extend(manifest_list("context_files", document["context_files"]))
    lines.extend(manifest_list("target_json", document["target_json"]))
    lines.extend(manifest_list("required_specs", document["required_specs"]))
    lines.extend(manifest_list("validation", document["validation"]))
    lines.extend(manifest_list("acceptance", document["acceptance"]))
    lines.extend(manifest_list("acceptance_focus", document["acceptance_focus"]))
    if document["validation_witness_map"]:
        lines.append("validation_witness_schema: 1")
        lines.extend(
            manifest_list(
                "validation_witness_map",
                [compact_json(record) for record in document["validation_witness_map"]],
            )
        )
    if document["integration_gates"]:
        lines.extend(manifest_list("integration_gates", document["integration_gates"]))
    lines.append(f"checked_summary_ja: {document['summary_ja']}")
    lines.append("")
    lines.extend(paragraph_section("Problem", document["problem"]))
    lines.extend(paragraph_section("Goal", document["goal"]))
    lines.extend(paragraph_section("Implementation Instructions", document["implementation_instructions"]))
    lines.extend(bullet_section("Decisions", document["decisions"]))
    lines.extend(task_section(document["tasks"]))
    lines.append("## Validation Notes")
    lines.append("")
    lines.extend(f"- {note}" for note in document["validation_notes"])
    lines.append("")
    return "\n".join(lines)


def bullet_section(heading: str, items: list[str]) -> list[str]:
    lines = [f"## {heading}", ""]
    lines.extend(f"- {item}" for item in items)
    lines.append("")
    return lines


def task_section(items: list[str]) -> list[str]:
    lines = ["## Tasks", ""]
    lines.extend(f"- [ ] {item}" for item in items)
    lines.append("")
    return lines


def paragraph_section(heading: str, items: list[str]) -> list[str]:
    lines = [f"## {heading}", ""]
    for item in items:
        lines.append(item)
        lines.append("")
    return lines


def render_report(document: dict[str, Any], digest: str, *, next_plan_id: str, plan_path: str) -> str:
    """Report the complete correspondence without claiming semantic coverage."""

    lines = [
        "plan-authoring-check: 1",
        f"authoring-input-sha256: {digest}",
        f"profile: {document['profile']}",
        f"authoring-interface: {document['authoring_interface']}",
        f"lifecycle: {document['lifecycle']}",
        f"status: {document['status']}",
        f"slug: {document['slug']}",
        f"summary: {document['summary']}",
        f"next-plan-id: {next_plan_id}",
        f"target-path: {plan_path}",
    ]
    for index, requirement in enumerate(document["requirements"], start=1):
        lines.append(f"requirement {index} [{requirement['id']}]: {requirement['text']}")
        for position, identifier in enumerate(requirement["write_paths"], start=1):
            path = document["write_paths"][identifier]["path"]
            lines.append(f"  write-path {position} [{identifier}]: {path}")
        for position, identifier in enumerate(requirement["completion_conditions"], start=1):
            condition = document["completion_conditions"][identifier]
            witness = document["witnesses"][condition["witness"]]
            lines.append(f"  completion-condition {position} [{identifier}]: {condition['text']}")
            lines.append(f"    condition-sha256: {text_digest(condition['text'])}")
            lines.append(f"    witness-command [{witness['id']}]: {witness['command']}")
            lines.append(f"    claimed-witness-behavior: {witness['claim']}")
        for position, identifier in enumerate(requirement["acceptance_items"], start=1):
            item = document["acceptance_items"][identifier]
            lines.append(f"  acceptance-item {position} [{identifier}]: {item['text']}")
            lines.append(f"    acceptance-sha256: {text_digest(item['text'])}")
            if not item["stage"]:
                lines.append("    witness-command: none (legacy authoring placeholder)")
                continue
            witness = document["witnesses"][item["witness"]]
            lines.append(f"    stage: {item['stage']}")
            lines.append(f"    witness-command [{witness['id']}]: {witness['command']}")
            lines.append(f"    claimed-witness-behavior: {witness['claim']}")
            if item["stage"] == "authoritative":
                lines.append(
                    f"    authoritative-only-reason: {item['authoritative_only_reason']}"
                )
    lines.extend(f"derived write_scope: {path}" for path in document["write_scope"])
    lines.extend(f"derived focused_validation: {command}" for command in document["focused_validation"])
    lines.extend(f"declared validation: {command}" for command in document["validation"])
    lines.append(
        "semantic-review-required: claimed-witness-behavior is caller text; this check proves "
        "references, bounds, and derived digests only and never that a command establishes its "
        "condition."
    )
    lines.append("repository-writes-performed: 0")
    return "\n".join(lines) + "\n"


def plan_ids(root: Path) -> set[int]:
    ids: set[int] = set()
    plan_root = root / "docs/plan"
    for name in ("active", "backlog", "shelved"):
        directory = plan_root / name
        if directory.is_dir():
            for path in directory.glob("[0-9][0-9][0-9]-*.md"):
                ids.add(int(path.name[:3]))
    for name in ("checked", "replanned"):
        directory = plan_root / name
        if directory.is_dir():
            for path in directory.glob("**/[0-9][0-9][0-9]-*.md"):
                ids.add(int(path.name[:3]))
    checked_index = plan_root / "checked.md"
    if checked_index.is_file():
        for line in checked_index.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^(\d{3})\s+", line)
            if match:
                ids.add(int(match.group(1)))
    return ids


def next_plan_id(root: Path) -> str:
    ids = plan_ids(root)
    value = 1
    while value in ids:
        value += 1
    if value > 999:
        raise AuthoringError("no plan identifier remains available")
    return f"{value:03d}"


def reserve_plan_identifier(root: Path, document: dict[str, Any], digest: str) -> str:
    """Reserve the smallest identifier free in the published state for these bytes.

    Allocation reads the exact published source state and the live cross-worktree
    reservations rather than this checkout's files, so a stale or ahead working
    tree cannot hand the same identifier to two linked worktrees. The reservation
    is keyed by the checked input digest, so the identifier a check reports is the
    identifier its own write consumes, and publication is what releases it.
    """

    try:
        guard = locate_worktree_guard()
        reservation = guard.reserve_plan_id(
            root,
            input_digest=digest,
            lifecycle=document["lifecycle"],
            slug=document["slug"],
        )
    except AuthoringError:
        raise
    except Exception:  # noqa: BLE001 - a directory outside a repository keeps local scanning
        return next_plan_id(root)
    plan_id = reservation["plan_id"]
    if PLAN_ID_RE.fullmatch(plan_id) is None:
        raise AuthoringError(f"reserved plan identifier is malformed: {plan_id!r}")
    return plan_id


def plan_relative_path(document: dict[str, Any], plan_id: str) -> str:
    return f"docs/plan/{document['lifecycle']}/{plan_id}-{document['slug']}.md"


def read_index_rows(root: Path) -> list[tuple[str, str, str]]:
    index_path = root / "docs/plan/plan.md"
    if not index_path.is_file():
        raise AuthoringError("missing docs/plan/plan.md")
    try:
        return parse_active_index(read_active_index(index_path))
    except ActiveIndexError as exc:
        raise AuthoringError(f"active plan index is invalid: {exc}") from exc


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


def create_exclusive_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise AuthoringError(f"plan target is already occupied: {path}") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def reject_symlinked_declared_paths(root: Path, document: dict[str, Any]) -> None:
    """Refuse a declared path whose existing components include a symlink.

    A symlinked component makes the declared path and the path actually written
    two different locations, so a checked write scope would not bound the write.
    """

    for label in ("write_scope", "context_files", "target_json"):
        for relative in document.get(label, ()):  # target_json is generated-only
            reject_symlinked_components(root, relative, label)


def check_authoring_input(
    root: Path, input_path: Path, *, profile: str, interface: str = STRUCTURED_INTERFACE
) -> tuple[str, str]:
    """Report the checked correspondence and derived digest without writing."""

    raw = read_input_bytes(input_path)
    digest = byte_digest(raw)
    document = build_document(parse_input(raw), profile=profile, interface=interface)
    reject_symlinked_declared_paths(root, document)
    read_index_rows(root)
    plan_id = reserve_plan_identifier(root, document, digest)
    relative = plan_relative_path(document, plan_id)
    if (root / relative).exists():
        raise AuthoringError(f"plan target is already occupied: {relative}")
    render_plan(document, plan_id)
    return digest, render_report(document, digest, next_plan_id=plan_id, plan_path=relative)


def write_authoring_input(
    root: Path,
    input_path: Path,
    expected_digest: str,
    *,
    profile: str,
    interface: str = STRUCTURED_INTERFACE,
) -> str:
    """Render the plan and its canonical index update from the exact checked bytes."""

    if DIGEST_RE.fullmatch(expected_digest) is None:
        raise AuthoringError("expected input digest must be sha256:<64 lowercase hex>")
    raw = read_input_bytes(input_path)
    digest = byte_digest(raw)
    if digest != expected_digest:
        raise AuthoringError(
            f"authoring input changed since it was checked: {digest} != {expected_digest}"
        )
    document = build_document(parse_input(raw), profile=profile, interface=interface)
    with lifecycle_lock(root):
        reject_symlinked_declared_paths(root, document)
        rows = read_index_rows(root)
        plan_id = reserve_plan_identifier(root, document, digest)
        relative = plan_relative_path(document, plan_id)
        reject_symlinked_components(root, relative, "plan target")
        target = root / relative
        if target.exists() or target.is_symlink():
            raise AuthoringError(f"plan target is already occupied: {relative}")
        content = render_plan(document, plan_id)
        index_text: str | None = None
        if document["lifecycle"] == "active":
            if any(row[0] == plan_id for row in rows):
                raise AuthoringError(f"active plan index already holds id {plan_id}")
            try:
                index_text = render_active_index([*rows, (plan_id, relative, document["status"])])
            except ActiveIndexError as exc:
                raise AuthoringError(f"canonical active plan index update failed: {exc}") from exc
        create_exclusive_text(target, content)
        if index_text is not None:
            try:
                atomic_write_text(root / "docs/plan/plan.md", index_text)
            except OSError as exc:
                target.unlink(missing_ok=True)
                raise AuthoringError(f"active plan index write failed: {exc}") from exc
    return relative


def legacy_input_document(environ: dict[str, str]) -> dict[str, Any]:
    """Convert the legacy create-plan.sh arguments into the same checked shape."""

    def entries(name: str) -> list[str]:
        raw = environ.get(name, "")
        return [line for line in raw.split("\n") if line.strip()]

    lifecycle = environ.get("PLAN_AUTHORING_LIFECYCLE", "")
    if lifecycle not in LIFECYCLE_VALUES:
        raise AuthoringError("legacy conversion requires an active or backlog lifecycle")
    purpose = environ.get("PLAN_ADMISSION_PURPOSE", "").strip()
    if purpose not in PLAN_PURPOSE_VALUES:
        raise AuthoringError("plan creation requires --purpose implementation")
    write_scope = entries("PLAN_ADMISSION_WRITE_SCOPE")
    completions = entries("PLAN_ADMISSION_COMPLETIONS")
    witness_commands = entries("PLAN_ADMISSION_WITNESSES")
    feasibility = entries("PLAN_ADMISSION_FEASIBILITY")
    if len(completions) != len(witness_commands):
        raise AuthoringError("each --completion condition needs exactly one --witness command")

    evidence: list[dict[str, str]] = []
    for item in feasibility:
        kind, separator, text = item.partition(":")
        if not separator:
            raise AuthoringError(f"--feasibility must use <kind>:<evidence>: {item}")
        evidence.append({"kind": kind.strip(), "evidence": text.strip()})

    witnesses: list[dict[str, str]] = []
    witness_ids: dict[str, str] = {}
    for command in witness_commands:
        if command in witness_ids:
            continue
        identifier = f"w-{len(witnesses) + 1}"
        witness_ids[command] = identifier
        witnesses.append(
            {
                "id": identifier,
                "command": command,
                "claim": (
                    "Legacy argument interface: the caller declared this command as the witness "
                    "and stated no separate behaviour claim."
                ),
            }
        )
    write_path_records = [
        {"id": f"wp-{index}", "path": path} for index, path in enumerate(write_scope, start=1)
    ]
    condition_records = [
        {"id": f"cc-{index}", "text": text, "witness": witness_ids[witness_commands[index - 1]]}
        for index, text in enumerate(completions, start=1)
    ]
    acceptance_records = [{"id": "ac-1", "text": "TBD"}]
    requirement = {
        "id": "legacy-arguments",
        "text": (
            "Legacy argument interface: the caller supplied write scope, completion conditions, "
            "and witness commands without requirement-level correspondence."
        ),
        "write_paths": [record["id"] for record in write_path_records],
        "completion_conditions": [record["id"] for record in condition_records],
        "acceptance_items": ["ac-1"],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "profile": PROFILE_GENERATED,
        "lifecycle": lifecycle,
        "slug": environ.get("PLAN_AUTHORING_SLUG", ""),
        "summary": environ.get("PLAN_AUTHORING_SUMMARY", ""),
        "summary_ja": environ.get("PLAN_AUTHORING_SUMMARY_JA", ""),
        "plan_purpose": purpose,
        "task_types": ["environment_data_flow"],
        "review_class": "B",
        "human_design_required": "no",
        "human_approval_status": "not_required",
        "feasibility_evidence": evidence,
        "witnesses": witnesses,
        "write_paths": write_path_records,
        "completion_conditions": condition_records,
        "acceptance_items": acceptance_records,
        "requirements": [requirement],
        "context_files": [CONTEXT_FILES_NONE],
        "target_json": [CONTEXT_FILES_NONE],
        "required_specs": LEGACY_REQUIRED_SPECS,
        "validation": ["git diff --check"],
        "acceptance_focus": ["TBD"],
        "problem": ["TBD"],
        "goal": ["TBD"],
        "implementation_instructions": [
            "Describe the executable steps for the next agent in English by default."
        ],
        "decisions": ["TBD"],
        "tasks": ["TBD"],
        "validation_notes": [],
    }


LEGACY_REQUIRED_SPECS = [
    "docs/agent/PROJECT_POLICY.md",
    ".project-agent-workflow/docs/agent/SPEC_VALIDATION.md",
    ".project-agent-workflow/docs/agent/SPEC_GIT_WORKFLOW.md",
    ".project-agent-workflow/docs/agent/SPEC_FILE_MANAGEMENT.md",
    ".project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md",
    ".project-agent-workflow/docs/agent/SPEC_HUMAN_REPORTING.md",
    ".project-agent-workflow/docs/agent/SPEC_DEVELOPMENT_FLOW.md",
    ".project-agent-workflow/docs/agent/SPEC_ENVIRONMENT.md",
    "docs/agent/PROJECT_ENVIRONMENT.md",
]


def main(argv: list[str] | None = None, *, default_profile: str | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="repository root that owns docs/plan")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="report the checked correspondence without writing")
    check.add_argument("--input", required=True)
    check.add_argument("--print-digest", action="store_true")

    write = commands.add_parser("write", help="render the plan from the exact checked bytes")
    write.add_argument("--input", required=True)
    write.add_argument("--expect-input-sha256", required=True)

    legacy = commands.add_parser(
        "legacy-input", help="convert the legacy argument interface into one authoring input"
    )
    legacy.add_argument("--output", required=True)

    # An entrypoint that declares a profile is bound to it, so the root command
    # cannot be asked to render the generated schema or to claim the argument
    # interface it never converts from.
    if default_profile != PROFILE_ROOT:
        for sub in (check, write):
            sub.add_argument(
                "--authoring-interface",
                default=STRUCTURED_INTERFACE,
                choices=list(AUTHORING_INTERFACES),
                help="the interface that produced this input; the legacy value is set by "
                     "the argument-interface conversion and is never read from the input",
            )

    for sub in (check, write, legacy):
        if default_profile is None:
            sub.add_argument("--profile", required=True, choices=list(PROFILES))
        else:
            sub.add_argument("--profile", default=default_profile, choices=[default_profile])

    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.command == "check":
            digest, report = check_authoring_input(
                root,
                Path(args.input),
                profile=args.profile,
                interface=getattr(args, "authoring_interface", STRUCTURED_INTERFACE),
            )
            if args.print_digest:
                print(digest)
            else:
                sys.stdout.write(report)
            return 0
        if args.command == "write":
            print(
                write_authoring_input(
                    root,
                    Path(args.input),
                    args.expect_input_sha256,
                    profile=args.profile,
                    interface=getattr(args, "authoring_interface", STRUCTURED_INTERFACE),
                )
            )
            return 0
        document = legacy_input_document(dict(os.environ))
        if args.profile != PROFILE_GENERATED:
            raise AuthoringError("the legacy argument interface renders generated plans only")
        Path(args.output).write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 0
    except AuthoringError as exc:
        print(f"plan authoring failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
