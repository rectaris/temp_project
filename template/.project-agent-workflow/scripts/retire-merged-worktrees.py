#!/usr/bin/env python3
"""Inventory locally merged linked worktrees without changing Git state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Sequence


SCHEMA_VERSION = 1
CONFIG_VERSION = 1
CONFIG_KEYS = {
    "version",
    "enabled",
    "merge_target_refs",
    "protected_local_branch_refs",
}
LIST_KEYS = {"merge_target_refs", "protected_local_branch_refs"}
LOCAL_BRANCH_RE = re.compile(r"^refs/heads/[^\x00-\x20~^:?*\\\[]+$")
OID_RE = re.compile(r"^[0-9a-f]{40,64}$")
MAX_CONFIG_BYTES = 65_536
MAX_MANIFEST_BYTES = 1_048_576
MANIFEST_KEYS = {
    "schema_version",
    "repository_identity",
    "allowed_root",
    "current_worktree",
    "configuration",
    "candidates",
    "content_digest",
}
CANDIDATE_KEYS = {
    "worktree_path",
    "branch_ref",
    "branch_tip_oid",
    "merge_target_ref",
    "merge_target_oid",
    "upstream_ref",
    "upstream_relation",
    "eligibility_results",
    "eligible",
}
ELIGIBILITY_KEYS = {
    "registered",
    "linked_non_primary",
    "non_current",
    "unlocked",
    "clean",
    "inside_allowed_root",
    "attached_local_branch",
    "exact_branch_tip",
    "branch_not_protected",
    "tip_is_merge_target_ancestor",
    "upstream_unambiguous",
    "upstream_configured",
    "upstream_available",
    "upstream_ahead_zero",
}
class RetirementError(ValueError):
    """A fail-closed local retirement error."""


def git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            environment.pop(name, None)
    environment.update(
        {
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "LC_ALL": "C",
        }
    )
    return environment


def git_command(
    repository: Path,
    arguments: Sequence[str],
    *,
    hooks_path: Path | None = None,
) -> list[str]:
    effective_hooks = hooks_path if hooks_path is not None else Path(os.devnull)
    return [
        "git",
        "-c",
        "core.fsmonitor=false",
        "-c",
        f"core.hooksPath={effective_hooks}",
        "-C",
        str(repository),
        *arguments,
    ]


def git(
    repository: Path,
    *arguments: str,
    check: bool = True,
    hooks_path: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        git_command(repository, arguments, hooks_path=hooks_path),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_environment(),
    )
    if check and completed.returncode != 0:
        raise RetirementError(f"Git command failed: {' '.join(arguments)}")
    return completed


def git_text(repository: Path, *arguments: str, check: bool = True) -> str:
    return git(repository, *arguments, check=check).stdout.decode("utf-8", "strict").strip()


def project_root_from_script() -> Path:
    raw_script = Path(__file__).absolute()
    if has_symlink_component(raw_script):
        raise RetirementError("command path contains a symlink component")
    script = raw_script.resolve(strict=True)
    completed = git(script.parent, "rev-parse", "--show-toplevel", check=False)
    if completed.returncode != 0:
        raise RetirementError("command path is not inside a Git worktree")
    root = canonical_directory(
        completed.stdout.decode("utf-8", "strict").strip(),
        label="Git worktree root",
    )
    if not path_is_strict_descendant(script, root):
        raise RetirementError("command path is not strictly below the Git worktree root")
    return root


def parse_config(path: Path) -> dict[str, Any]:
    if has_symlink_component(path) or path.is_symlink() or not path.is_file():
        raise RetirementError("Git-retirement configuration must be a regular non-symlink file")
    data = path.read_bytes()
    if len(data) > MAX_CONFIG_BYTES:
        raise RetirementError("Git-retirement configuration exceeds the size limit")
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise RetirementError("Git-retirement configuration must be UTF-8") from exc

    values: dict[str, Any] = {}
    active_list: str | None = None
    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  - "):
            if active_list is None:
                raise RetirementError(f"configuration list item has no key at line {line_number}")
            item = raw_line[4:].strip()
            if not item or "#" in item:
                raise RetirementError(f"configuration ref is invalid at line {line_number}")
            values[active_list].append(item)
            continue
        if raw_line[:1].isspace() or ":" not in raw_line:
            raise RetirementError(f"configuration syntax is invalid at line {line_number}")
        key, scalar = raw_line.split(":", 1)
        key = key.strip()
        scalar = scalar.strip()
        if key not in CONFIG_KEYS or key in values:
            raise RetirementError(f"configuration key is unknown or duplicated: {key}")
        active_list = None
        if key in LIST_KEYS:
            if scalar == "[]":
                values[key] = []
            elif scalar == "":
                values[key] = []
                active_list = key
            else:
                raise RetirementError(f"configuration list must use block items or []: {key}")
        elif key == "version":
            if scalar != str(CONFIG_VERSION):
                raise RetirementError(f"configuration version must be {CONFIG_VERSION}")
            values[key] = CONFIG_VERSION
        elif key == "enabled":
            if scalar not in {"true", "false"}:
                raise RetirementError("configuration enabled must be true or false")
            values[key] = scalar == "true"

    if set(values) != CONFIG_KEYS:
        missing = ", ".join(sorted(CONFIG_KEYS - set(values)))
        raise RetirementError(f"configuration is missing keys: {missing}")
    return values


def validate_local_ref(repository: Path, value: str) -> None:
    if not LOCAL_BRANCH_RE.fullmatch(value):
        raise RetirementError(f"configuration ref is not an exact local branch ref: {value}")
    short = value.removeprefix("refs/heads/")
    if git(repository, "check-ref-format", "--branch", short, check=False).returncode != 0:
        raise RetirementError(f"configuration ref is invalid: {value}")


def load_enabled_config(project_root: Path) -> dict[str, Any]:
    config = parse_config(project_root / "docs/agent/git-retirement.yaml")
    if not config["enabled"]:
        raise RetirementError("Git-retirement configuration is disabled")
    if not config["merge_target_refs"] or not config["protected_local_branch_refs"]:
        raise RetirementError("enabled configuration requires merge targets and protected branches")
    for key in LIST_KEYS:
        refs = config[key]
        if len(refs) != len(set(refs)):
            raise RetirementError(f"configuration contains duplicate refs: {key}")
        for ref in refs:
            validate_local_ref(project_root, ref)
    for ref in (*config["merge_target_refs"], *config["protected_local_branch_refs"]):
        if resolve_commit(project_root, ref) is None:
            raise RetirementError(f"configured local ref is unresolved: {ref}")
    return config


def has_symlink_component(path: Path) -> bool:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            return True
    return False


def canonical_directory(raw: str, *, label: str) -> Path:
    path = Path(raw)
    if has_symlink_component(path):
        raise RetirementError(f"{label} contains a symlink component")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RetirementError(f"{label} cannot be resolved") from exc
    if not resolved.is_dir():
        raise RetirementError(f"{label} must be a directory")
    return resolved


def validate_allowed_root(raw: str, project_root: Path) -> Path:
    allowed = canonical_directory(raw, label="allowed root")
    forbidden = {Path("/").resolve(), Path.home().resolve(), project_root.resolve(strict=True)}
    if allowed in forbidden:
        raise RetirementError("allowed root is a forbidden broad or repository path")
    return allowed


def path_is_strict_descendant(path: Path, parent: Path) -> bool:
    try:
        relative = path.relative_to(parent)
    except ValueError:
        return False
    return relative != Path(".")


def parse_worktrees(payload: bytes) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw_record in payload.split(b"\0\0"):
        if not raw_record:
            continue
        record: dict[str, Any] = {}
        for raw_field in raw_record.split(b"\0"):
            if not raw_field:
                continue
            field = raw_field.decode("utf-8", "strict")
            key, separator, value = field.partition(" ")
            if key in record:
                raise RetirementError(f"duplicate Git worktree field: {key}")
            record[key] = value if separator else True
        if "worktree" not in record or "HEAD" not in record:
            raise RetirementError("Git worktree record is incomplete")
        records.append(record)
    if not records:
        raise RetirementError("Git reported no registered worktrees")
    return records


def resolve_commit(repository: Path, ref: str) -> str | None:
    completed = git(repository, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
    if completed.returncode != 0:
        return None
    value = completed.stdout.decode("ascii", "strict").strip()
    return value if OID_RE.fullmatch(value) else None


def exact_ref_exists(repository: Path, ref: str) -> bool:
    completed = git(repository, "show-ref", "--verify", "--quiet", ref, check=False)
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise RetirementError(f"could not determine exact ref existence: {ref}")


def is_ancestor(repository: Path, ancestor: str, target: str) -> bool:
    return git(repository, "merge-base", "--is-ancestor", ancestor, target, check=False).returncode == 0


def current_worktree(project_root: Path, common_dir: Path) -> Path:
    completed = git(Path.cwd(), "rev-parse", "--path-format=absolute", "--git-common-dir", check=False)
    if completed.returncode == 0:
        candidate_common = Path(completed.stdout.decode("utf-8", "strict").strip()).resolve(strict=True)
        if candidate_common == common_dir:
            current = git_text(Path.cwd(), "rev-parse", "--show-toplevel")
            return Path(current).resolve(strict=True)
    return project_root.resolve(strict=True)


def worktree_clean(path: Path) -> bool:
    completed = git(
        path,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignore-submodules=none",
        check=False,
    )
    return completed.returncode == 0 and completed.stdout == b""


def config_values(repository: Path, key: str) -> list[str]:
    completed = git(repository, "config", "--get-all", key, check=False)
    if completed.returncode not in {0, 1}:
        return []
    return completed.stdout.decode("utf-8", "strict").splitlines()


def branch_upstream(
    repository: Path,
    branch_ref: str,
) -> tuple[str | None, int | None, int | None, bool]:
    short = branch_ref.removeprefix("refs/heads/")
    remotes = config_values(repository, f"branch.{short}.remote")
    merge_refs = config_values(repository, f"branch.{short}.merge")
    unambiguous = len(remotes) == 1 and len(merge_refs) == 1
    if not unambiguous:
        return None, None, None, False
    completed = git(
        repository,
        "for-each-ref",
        "--format=%(upstream)",
        branch_ref,
        check=False,
    )
    if completed.returncode != 0:
        return None, None, None, True
    lines = completed.stdout.decode("utf-8", "strict").splitlines()
    if len(lines) != 1 or not lines[0]:
        return None, None, None, True
    upstream = lines[0]
    if resolve_commit(repository, upstream) is None:
        return upstream, None, None, True
    comparison = git(
        repository,
        "rev-list",
        "--left-right",
        "--count",
        f"{branch_ref}...{upstream}",
        check=False,
    )
    if comparison.returncode != 0:
        return upstream, None, None, True
    fields = comparison.stdout.decode("ascii", "strict").split()
    if len(fields) != 2 or not all(field.isdigit() for field in fields):
        return upstream, None, None, True
    return upstream, int(fields[0]), int(fields[1]), True


def evaluate_candidate(
    repository: Path,
    record: dict[str, Any],
    *,
    primary: Path,
    current: Path,
    allowed_root: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    raw_path = str(record["worktree"])
    path: Path | None = None
    path_safe = False
    try:
        path = canonical_directory(raw_path, label="worktree path")
        path_safe = path_is_strict_descendant(path, allowed_root)
    except RetirementError:
        path = None

    branch_ref = record.get("branch") if isinstance(record.get("branch"), str) else None
    attached_local = branch_ref is not None and LOCAL_BRANCH_RE.fullmatch(branch_ref) is not None
    recorded_tip = str(record["HEAD"])
    branch_tip = resolve_commit(repository, branch_ref) if attached_local and branch_ref else None
    exact_tip = branch_tip == recorded_tip and branch_tip is not None

    targets = [
        (ref, resolve_commit(repository, ref))
        for ref in config["merge_target_refs"]
    ]
    selected_target = next(
        (
            (ref, oid)
            for ref, oid in targets
            if oid is not None and exact_tip and is_ancestor(repository, recorded_tip, oid)
        ),
        targets[0],
    )
    target_ref, target_oid = selected_target
    ancestor = target_oid is not None and exact_tip and is_ancestor(repository, recorded_tip, target_oid)

    upstream_ref: str | None = None
    upstream_ahead: int | None = None
    upstream_behind: int | None = None
    upstream_unambiguous = False
    if attached_local and branch_ref:
        upstream_ref, upstream_ahead, upstream_behind, upstream_unambiguous = branch_upstream(
            repository, branch_ref
        )

    results = {
        "registered": True,
        "linked_non_primary": path is not None and path != primary,
        "non_current": path is not None and path != current,
        "unlocked": "locked" not in record,
        "clean": path is not None and worktree_clean(path),
        "inside_allowed_root": path_safe,
        "attached_local_branch": attached_local,
        "exact_branch_tip": exact_tip,
        "branch_not_protected": attached_local and branch_ref not in config["protected_local_branch_refs"],
        "tip_is_merge_target_ancestor": ancestor,
        "upstream_unambiguous": upstream_unambiguous,
        "upstream_configured": upstream_ref is not None,
        "upstream_available": upstream_ref is not None and upstream_ahead is not None,
        "upstream_ahead_zero": upstream_ahead == 0,
    }
    return {
        "worktree_path": str(path) if path is not None else raw_path,
        "branch_ref": branch_ref,
        "branch_tip_oid": recorded_tip,
        "merge_target_ref": target_ref,
        "merge_target_oid": target_oid,
        "upstream_ref": upstream_ref,
        "upstream_relation": {"ahead": upstream_ahead, "behind": upstream_behind},
        "eligibility_results": results,
        "eligible": all(results.values()),
    }


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def add_content_digest(manifest: dict[str, Any]) -> dict[str, Any]:
    unsigned = dict(manifest)
    unsigned.pop("content_digest", None)
    digest = hashlib.sha256(canonical_json(unsigned)).hexdigest()
    return {**unsigned, "content_digest": f"sha256:{digest}"}


def validate_manifest_output(raw: str, project_root: Path) -> Path:
    requested = Path(raw)
    if not requested.is_absolute():
        requested = project_root / requested
    artifact_root = project_root / ".agent-artifacts/git-retirement"
    if has_symlink_component(requested) or has_symlink_component(artifact_root):
        raise RetirementError("manifest output path contains a symlink component")
    if requested.suffix != ".json" or requested.parent.absolute() != artifact_root.absolute():
        raise RetirementError("manifest output must be one JSON file directly below .agent-artifacts/git-retirement")
    if requested.exists() and (requested.is_symlink() or not requested.is_file()):
        raise RetirementError("manifest output target must be a regular non-symlink file")
    if git(project_root, "check-ignore", "-q", str(requested), check=False).returncode != 0:
        raise RetirementError("manifest output path must be ignored by repository policy")
    artifact_root.mkdir(parents=True, exist_ok=True)
    return requested


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    data = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def repository_context(project_root: Path, raw_allowed_root: str) -> dict[str, Any]:
    config = load_enabled_config(project_root)
    common_dir = Path(
        git_text(project_root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve(strict=True)
    worktrees = parse_worktrees(git(project_root, "worktree", "list", "--porcelain", "-z").stdout)
    primary = canonical_directory(str(worktrees[0]["worktree"]), label="primary worktree")
    primary_common_dir = Path(
        git_text(primary, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve(strict=True)
    if primary_common_dir != common_dir:
        raise RetirementError("primary worktree does not match the repository common directory")
    return {
        "config": config,
        "common_dir": common_dir,
        "worktrees": worktrees,
        "primary": primary,
        "current": current_worktree(project_root, common_dir),
        "allowed_root": validate_allowed_root(raw_allowed_root, primary),
    }


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RetirementError(f"manifest contains a duplicate JSON key: {key}")
        result[key] = value
    return result


def validate_manifest_input(raw: str, primary: Path) -> Path:
    requested = Path(raw)
    if not requested.is_absolute():
        raise RetirementError("apply-local manifest path must be absolute")
    artifact_root = primary / ".agent-artifacts/git-retirement"
    if has_symlink_component(requested) or has_symlink_component(artifact_root):
        raise RetirementError("manifest input path contains a symlink component")
    if requested.suffix != ".json" or requested.parent.absolute() != artifact_root.absolute():
        raise RetirementError("manifest input must be one JSON file directly below .agent-artifacts/git-retirement")
    if requested.is_symlink() or not requested.is_file():
        raise RetirementError("manifest input must be a regular non-symlink file")
    resolved = requested.resolve(strict=True)
    if resolved != requested.absolute():
        raise RetirementError("manifest input path is not exact and canonical")
    if git(primary, "check-ignore", "-q", str(requested), check=False).returncode != 0:
        raise RetirementError("manifest input path must be ignored by repository policy")
    return resolved


def read_manifest(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) > MAX_MANIFEST_BYTES:
        raise RetirementError("manifest exceeds the size limit")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=reject_duplicate_json_keys)
    except json.JSONDecodeError as exc:
        raise RetirementError("manifest is not valid JSON") from exc
    if not isinstance(value, dict) or set(value) != MANIFEST_KEYS:
        raise RetirementError("manifest top-level schema is invalid")
    if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
        raise RetirementError("manifest schema version is invalid")
    content_digest = value["content_digest"]
    if not isinstance(content_digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", content_digest):
        raise RetirementError("manifest content digest is invalid")
    unsigned = dict(value)
    unsigned.pop("content_digest")
    expected_digest = f"sha256:{hashlib.sha256(canonical_json(unsigned)).hexdigest()}"
    if content_digest != expected_digest:
        raise RetirementError("manifest content digest does not match its content")
    identity = value["repository_identity"]
    if not isinstance(identity, dict) or set(identity) != {"primary_worktree", "git_common_dir"}:
        raise RetirementError("manifest repository identity is invalid")
    if not all(isinstance(identity[key], str) for key in identity):
        raise RetirementError("manifest repository identity types are invalid")
    if not isinstance(value["allowed_root"], str) or not isinstance(value["current_worktree"], str):
        raise RetirementError("manifest path identity types are invalid")
    if not isinstance(value["configuration"], dict) or set(value["configuration"]) != CONFIG_KEYS:
        raise RetirementError("manifest configuration schema is invalid")
    candidates = value["candidates"]
    if not isinstance(candidates, list) or not candidates:
        raise RetirementError("manifest candidates must be a non-empty list")
    paths: set[str] = set()
    for candidate in candidates:
        validate_manifest_candidate(candidate)
        if candidate["worktree_path"] in paths:
            raise RetirementError("manifest contains a duplicate worktree candidate")
        paths.add(candidate["worktree_path"])
    return value


def validate_manifest_candidate(candidate: Any) -> None:
    if not isinstance(candidate, dict) or set(candidate) != CANDIDATE_KEYS:
        raise RetirementError("manifest candidate schema is invalid")
    for key in ("worktree_path", "branch_tip_oid", "merge_target_ref", "merge_target_oid"):
        if not isinstance(candidate[key], str):
            raise RetirementError(f"manifest candidate field is invalid: {key}")
    if not Path(candidate["worktree_path"]).is_absolute():
        raise RetirementError("manifest worktree path must be absolute")
    if not OID_RE.fullmatch(candidate["branch_tip_oid"]) or not OID_RE.fullmatch(
        candidate["merge_target_oid"]
    ):
        raise RetirementError("manifest candidate OID is invalid")
    if not LOCAL_BRANCH_RE.fullmatch(candidate["merge_target_ref"]):
        raise RetirementError("manifest merge target ref is invalid")
    for key in ("branch_ref", "upstream_ref"):
        if candidate[key] is not None and not isinstance(candidate[key], str):
            raise RetirementError(f"manifest candidate field is invalid: {key}")
    if candidate["branch_ref"] is not None and not LOCAL_BRANCH_RE.fullmatch(candidate["branch_ref"]):
        raise RetirementError("manifest branch ref is invalid")
    if candidate["upstream_ref"] is not None and not candidate["upstream_ref"].startswith("refs/"):
        raise RetirementError("manifest upstream ref is invalid")
    relation = candidate["upstream_relation"]
    if not isinstance(relation, dict) or set(relation) != {"ahead", "behind"}:
        raise RetirementError("manifest upstream relation is invalid")
    if any(value is not None and type(value) is not int for value in relation.values()):
        raise RetirementError("manifest upstream relation values are invalid")
    if any(value is not None and value < 0 for value in relation.values()):
        raise RetirementError("manifest upstream relation cannot be negative")
    results = candidate["eligibility_results"]
    if not isinstance(results, dict) or set(results) != ELIGIBILITY_KEYS:
        raise RetirementError("manifest eligibility result schema is invalid")
    if any(type(value) is not bool for value in results.values()) or type(candidate["eligible"]) is not bool:
        raise RetirementError("manifest eligibility values are invalid")
    if candidate["eligible"] != all(results.values()):
        raise RetirementError("manifest eligible value does not match its results")
    if candidate["eligible"] and (
        candidate["branch_ref"] is None or candidate["upstream_ref"] is None
    ):
        raise RetirementError("eligible manifest candidate requires exact branch and upstream refs")


def validate_apply_target_path(raw: str, allowed_root: Path) -> Path:
    target = Path(raw)
    if not target.is_absolute():
        raise RetirementError("apply-local worktree path must be absolute")
    if has_symlink_component(target):
        raise RetirementError("apply-local worktree path contains a symlink component")
    normalized = Path(os.path.normpath(str(target)))
    if normalized != target or not path_is_strict_descendant(normalized, allowed_root):
        raise RetirementError("apply-local worktree path is not exact or is outside the allowed root")
    if normalized.exists() and canonical_directory(str(normalized), label="apply-local worktree") != normalized:
        raise RetirementError("apply-local worktree path is not canonical")
    return normalized


def assert_manifest_context(manifest: dict[str, Any], context: dict[str, Any]) -> None:
    expected_identity = {
        "primary_worktree": str(context["primary"]),
        "git_common_dir": str(context["common_dir"]),
    }
    if manifest["repository_identity"] != expected_identity:
        raise RetirementError("manifest repository identity changed or mismatched")
    if manifest["allowed_root"] != str(context["allowed_root"]):
        raise RetirementError("manifest allowed root changed or mismatched")
    if manifest["current_worktree"] != str(context["current"]):
        raise RetirementError("manifest current worktree changed or mismatched")
    if manifest["configuration"] != context["config"]:
        raise RetirementError("manifest configuration changed or mismatched")


def find_worktree_record(records: list[dict[str, Any]], target: Path) -> dict[str, Any] | None:
    matches = [record for record in records if Path(str(record["worktree"])).absolute() == target]
    if len(matches) > 1:
        raise RetirementError("Git reported duplicate worktree registrations")
    return matches[0] if matches else None


def select_manifest_candidate(manifest: dict[str, Any], target: Path) -> dict[str, Any]:
    matches = [candidate for candidate in manifest["candidates"] if candidate["worktree_path"] == str(target)]
    if len(matches) != 1:
        raise RetirementError("manifest does not contain exactly one requested worktree candidate")
    candidate = matches[0]
    if not candidate["eligible"] or not all(candidate["eligibility_results"].values()):
        raise RetirementError("manifest candidate was not eligible at scan time")
    return candidate


def revalidate_before_worktree_removal(
    project_root: Path,
    raw_allowed_root: str,
    manifest: dict[str, Any],
    raw_target: str,
) -> tuple[dict[str, Any], dict[str, Any], Path, dict[str, Any] | None]:
    context = repository_context(project_root, raw_allowed_root)
    assert_manifest_context(manifest, context)
    target = validate_apply_target_path(raw_target, context["allowed_root"])
    candidate = select_manifest_candidate(manifest, target)
    record = find_worktree_record(context["worktrees"], target)
    if record is None:
        branch_ref = candidate["branch_ref"]
        if not isinstance(branch_ref, str):
            raise RetirementError("manifest exact branch ref is unavailable")
        branch_absent = not exact_ref_exists(project_root, branch_ref)
        if not branch_absent and resolve_commit(project_root, branch_ref) is None:
            raise RetirementError("exact branch ref exists but its commit is unavailable")
        if not target.exists() and branch_absent:
            return context, candidate, target, None
        raise RetirementError("exact worktree and branch pair changed or is only partially absent")
    observed = evaluate_candidate(
        project_root,
        record,
        primary=context["primary"],
        current=context["current"],
        allowed_root=context["allowed_root"],
        config=context["config"],
    )
    if observed != candidate:
        raise RetirementError("worktree candidate changed since the manifest scan")
    if not observed["eligible"] or not all(observed["eligibility_results"].values()):
        raise RetirementError("worktree candidate is no longer eligible")
    return context, candidate, target, record


def revalidate_before_branch_deletion(
    project_root: Path,
    raw_allowed_root: str,
    manifest: dict[str, Any],
    candidate: dict[str, Any],
    target: Path,
) -> None:
    context = repository_context(project_root, raw_allowed_root)
    assert_manifest_context(manifest, context)
    if validate_apply_target_path(str(target), context["allowed_root"]) != target:
        raise RetirementError("removed worktree path identity changed")
    if target.exists() or find_worktree_record(context["worktrees"], target) is not None:
        raise RetirementError("exact worktree path remains present or registered")
    branch_ref = candidate["branch_ref"]
    if not isinstance(branch_ref, str) or not LOCAL_BRANCH_RE.fullmatch(branch_ref):
        raise RetirementError("manifest branch ref is not an exact local branch")
    if branch_ref in context["config"]["protected_local_branch_refs"]:
        raise RetirementError("manifest branch became protected")
    branch_tip = resolve_commit(project_root, branch_ref)
    if branch_tip != candidate["branch_tip_oid"]:
        raise RetirementError("branch tip changed before branch deletion")
    target_ref = candidate["merge_target_ref"]
    target_oid = resolve_commit(project_root, target_ref)
    if target_ref not in context["config"]["merge_target_refs"] or target_oid != candidate["merge_target_oid"]:
        raise RetirementError("merge target changed before branch deletion")
    if not is_ancestor(project_root, branch_tip, target_oid):
        raise RetirementError("branch tip is no longer an ancestor of the merge target")
    upstream_ref, ahead, behind, unambiguous = branch_upstream(project_root, branch_ref)
    if (
        not unambiguous
        or upstream_ref != candidate["upstream_ref"]
        or {"ahead": ahead, "behind": behind} != candidate["upstream_relation"]
        or ahead != 0
    ):
        raise RetirementError("upstream relation changed before branch deletion")
    if any(record.get("branch") == branch_ref for record in context["worktrees"]):
        raise RetirementError("branch remains registered to a worktree")


def acquire_worktree_head_lock(target: Path, expected_branch_ref: str) -> tuple[int, Path]:
    git_dir = canonical_directory(
        git_text(target, "rev-parse", "--path-format=absolute", "--absolute-git-dir"),
        label="linked worktree Git directory",
    )
    head = git_dir / "HEAD"
    if has_symlink_component(head) or not head.is_file():
        raise RetirementError("linked worktree HEAD is not a regular symlink-safe file")
    expected = f"ref: {expected_branch_ref}\n".encode("utf-8")
    if head.read_bytes() != expected:
        raise RetirementError("linked worktree HEAD changed before lock acquisition")
    lock = git_dir / "HEAD.lock"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError as exc:
        raise RetirementError("linked worktree HEAD is already locked") from exc
    try:
        os.write(descriptor, expected)
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        lock.unlink(missing_ok=True)
        raise
    return descriptor, lock


def release_worktree_head_lock(descriptor: int, lock: Path) -> None:
    os.close(descriptor)
    lock.unlink(missing_ok=True)


def finish_branch_ref_lock(
    process: subprocess.Popen[bytes],
) -> tuple[int, str, str]:
    if process.stdin is not None and not process.stdin.closed:
        if process.poll() is None:
            try:
                process.stdin.write(b"abort\n")
                process.stdin.flush()
            except BrokenPipeError:
                pass
        process.stdin.close()
    returncode = process.wait()
    stdout = process.stdout.read().decode("utf-8", "replace") if process.stdout else ""
    stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
    return returncode, stdout.strip(), stderr.strip()


def acquire_branch_ref_lock(
    primary: Path,
    branch_ref: str,
    expected_oid: str,
) -> subprocess.Popen[bytes]:
    if not LOCAL_BRANCH_RE.fullmatch(branch_ref) or not OID_RE.fullmatch(expected_oid):
        raise RetirementError("exact branch ref lock input is invalid")
    process = subprocess.Popen(
        git_command(primary, ("update-ref", "--stdin")),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_environment(),
    )
    try:
        if process.stdin is None or process.stdout is None:
            raise RetirementError("exact branch ref transaction pipes are unavailable")
        commands = (
            b"start\n"
            + f"verify {branch_ref} {expected_oid}\n".encode("ascii")
            + b"prepare\n"
        )
        process.stdin.write(commands)
        process.stdin.flush()
        responses = [process.stdout.readline().decode("ascii", "strict").strip() for _ in range(2)]
        if responses != ["start: ok", "prepare: ok"]:
            _, _, detail = finish_branch_ref_lock(process)
            raise RetirementError(
                f"exact branch ref could not be held at the manifest OID: {detail}"
            )
    except BaseException:
        if process.poll() is None:
            finish_branch_ref_lock(process)
        raise
    return process


def release_branch_ref_lock(process: subprocess.Popen[bytes]) -> None:
    returncode, response, detail = finish_branch_ref_lock(process)
    if returncode != 0 or response != "abort: ok":
        raise RetirementError(f"exact branch ref lock release failed: {detail}")


def create_reference_delete_guard(
    primary: Path,
    branch_ref: str,
    expected_oid: str,
) -> tuple[Path, Path]:
    artifact_root = primary / ".agent-artifacts/git-retirement"
    if git(primary, "check-ignore", "-q", str(artifact_root), check=False).returncode != 0:
        raise RetirementError("reference guard directory must remain ignored")
    hook_dir = Path(tempfile.mkdtemp(prefix="apply-reference-guard-", dir=artifact_root))
    hook = hook_dir / "reference-transaction"
    zero_oid = "0" * len(expected_oid)
    peeled_ref = f"{branch_ref}^{{commit}}"
    program = (
        f"#!{sys.executable}\n"
        "import subprocess\n"
        "import sys\n"
        "if len(sys.argv) != 2:\n"
        "    raise SystemExit(1)\n"
        "if sys.argv[1] != 'prepared':\n"
        "    raise SystemExit(0)\n"
        "records = [line.split() for line in sys.stdin.read().splitlines()]\n"
        f"matched = [record for record in records if len(record) == 3 and record[2] == {branch_ref!r} and record[1] == {zero_oid!r}]\n"
        "if len(matched) != 1:\n"
        "    raise SystemExit(1)\n"
        f"resolved = subprocess.run(['git', 'rev-parse', '--verify', {peeled_ref!r}], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)\n"
        f"raise SystemExit(0 if resolved.returncode == 0 and resolved.stdout.decode('ascii', 'strict').strip() == {expected_oid!r} else 1)\n"
    )
    descriptor = os.open(hook, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o700)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(program)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        hook.unlink(missing_ok=True)
        hook_dir.rmdir()
        raise
    return hook_dir, hook


def remove_reference_delete_guard(hook_dir: Path, hook: Path) -> None:
    hook.unlink(missing_ok=True)
    hook_dir.rmdir()


def scan(args: argparse.Namespace) -> int:
    project_root = project_root_from_script()
    context = repository_context(project_root, args.allowed_root)
    candidates = [
        evaluate_candidate(
            project_root,
            record,
            primary=context["primary"],
            current=context["current"],
            allowed_root=context["allowed_root"],
            config=context["config"],
        )
        for record in context["worktrees"]
    ]
    candidates.sort(key=lambda item: (item["worktree_path"], item["branch_ref"] or ""))
    manifest = add_content_digest(
        {
            "schema_version": SCHEMA_VERSION,
            "repository_identity": {
                "primary_worktree": str(context["primary"]),
                "git_common_dir": str(context["common_dir"]),
            },
            "allowed_root": str(context["allowed_root"]),
            "current_worktree": str(context["current"]),
            "configuration": context["config"],
            "candidates": candidates,
        }
    )
    output = validate_manifest_output(args.manifest, context["primary"])
    write_manifest(output, manifest)
    result = {
        "manifest": str(output),
        "candidate_count": len(candidates),
        "eligible_count": sum(candidate["eligible"] for candidate in candidates),
        "content_digest": manifest["content_digest"],
    }
    print(json.dumps(result, sort_keys=True))
    return 0


def apply_local(args: argparse.Namespace) -> int:
    if not args.confirm_local_effects:
        raise RetirementError("apply-local requires --confirm-local-effects for this invocation")
    project_root = project_root_from_script()
    initial_context = repository_context(project_root, args.allowed_root)
    manifest_path = validate_manifest_input(args.manifest, initial_context["primary"])
    manifest = read_manifest(manifest_path)
    context, candidate, target, record = revalidate_before_worktree_removal(
        project_root,
        args.allowed_root,
        manifest,
        args.worktree,
    )
    if record is None:
        print(
            json.dumps(
                {
                    "result": "already absent exact worktree and branch pair",
                    "worktree": str(target),
                    "branch_ref": candidate["branch_ref"],
                },
                sort_keys=True,
            )
        )
        return 0
    branch_ref = candidate["branch_ref"]
    if not isinstance(branch_ref, str):
        raise RetirementError("manifest exact branch ref is unavailable")
    head_descriptor, head_lock = acquire_worktree_head_lock(target, branch_ref)
    try:
        branch_lock = acquire_branch_ref_lock(
            context["primary"],
            branch_ref,
            candidate["branch_tip_oid"],
        )
        try:
            locked_context, locked_candidate, locked_target, locked_record = (
                revalidate_before_worktree_removal(
                    project_root,
                    args.allowed_root,
                    manifest,
                    args.worktree,
                )
            )
            if locked_record is None or locked_candidate != candidate or locked_target != target:
                raise RetirementError("worktree identity changed after effect lock acquisition")
            removal = git(
                locked_context["primary"],
                "worktree",
                "remove",
                str(target),
                check=False,
            )
        finally:
            release_branch_ref_lock(branch_lock)
    finally:
        release_worktree_head_lock(head_descriptor, head_lock)
    if removal.returncode != 0:
        raise RetirementError("exact worktree removal failed; branch deletion was not attempted")
    revalidate_before_branch_deletion(
        project_root,
        args.allowed_root,
        manifest,
        candidate,
        target,
    )
    short_branch = branch_ref.removeprefix("refs/heads/")
    hook_dir, hook = create_reference_delete_guard(
        context["primary"],
        branch_ref,
        candidate["branch_tip_oid"],
    )
    try:
        deletion = git(
            context["primary"],
            "branch",
            "-d",
            "--",
            short_branch,
            check=False,
            hooks_path=hook_dir,
        )
    finally:
        remove_reference_delete_guard(hook_dir, hook)
    if deletion.returncode != 0:
        detail = deletion.stderr.decode("utf-8", "replace").strip()
        raise RetirementError(f"exact local branch deletion failed after worktree removal: {detail}")
    print(
        json.dumps(
            {
                "result": "removed exact worktree and local branch",
                "worktree": str(target),
                "branch_ref": branch_ref,
            },
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    subcommands = parser.add_subparsers(dest="command", required=True)
    scan_parser = subcommands.add_parser("scan", allow_abbrev=False)
    scan_parser.add_argument("--allowed-root", required=True)
    scan_parser.add_argument("--manifest", required=True)
    scan_parser.set_defaults(handler=scan)
    apply_parser = subcommands.add_parser("apply-local", allow_abbrev=False)
    apply_parser.add_argument("--allowed-root", required=True)
    apply_parser.add_argument("--manifest", required=True)
    apply_parser.add_argument("--worktree", required=True)
    apply_parser.add_argument("--confirm-local-effects", action="store_true")
    apply_parser.set_defaults(handler=apply_local)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return args.handler(args)
    except (OSError, UnicodeError, RetirementError) as exc:
        print(f"local Git retirement failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
