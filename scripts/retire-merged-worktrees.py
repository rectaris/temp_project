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
GIT_LOCAL_ENV_VARS = frozenset(
    {
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_CONFIG",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_PARAMETERS",
        "GIT_DIR",
        "GIT_GRAFT_FILE",
        "GIT_IMPLICIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_NO_REPLACE_OBJECTS",
        "GIT_OBJECT_DIRECTORY",
        "GIT_PREFIX",
        "GIT_REPLACE_REF_BASE",
        "GIT_SHALLOW_FILE",
        "GIT_WORK_TREE",
    }
)


class RetirementError(ValueError):
    """A fail-closed local retirement error."""


def git(
    repository: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    for name in GIT_LOCAL_ENV_VARS:
        environment.pop(name, None)
    for name in tuple(environment):
        if name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            environment.pop(name, None)
    environment.update(
        {
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "LC_ALL": "C",
        }
    )
    completed = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-C", str(repository), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
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


def scan(args: argparse.Namespace) -> int:
    project_root = project_root_from_script()
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
    current = current_worktree(project_root, common_dir)
    allowed_root = validate_allowed_root(args.allowed_root, primary)
    candidates = [
        evaluate_candidate(
            project_root,
            record,
            primary=primary,
            current=current,
            allowed_root=allowed_root,
            config=config,
        )
        for record in worktrees
    ]
    candidates.sort(key=lambda item: (item["worktree_path"], item["branch_ref"] or ""))
    manifest = add_content_digest(
        {
            "schema_version": SCHEMA_VERSION,
            "repository_identity": {
                "primary_worktree": str(primary),
                "git_common_dir": str(common_dir),
            },
            "allowed_root": str(allowed_root),
            "current_worktree": str(current),
            "configuration": config,
            "candidates": candidates,
        }
    )
    output = validate_manifest_output(args.manifest, primary)
    write_manifest(output, manifest)
    result = {
        "manifest": str(output),
        "candidate_count": len(candidates),
        "eligible_count": sum(candidate["eligible"] for candidate in candidates),
        "content_digest": manifest["content_digest"],
    }
    print(json.dumps(result, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    subcommands = parser.add_subparsers(dest="command", required=True)
    scan_parser = subcommands.add_parser("scan", allow_abbrev=False)
    scan_parser.add_argument("--allowed-root", required=True)
    scan_parser.add_argument("--manifest", required=True)
    scan_parser.set_defaults(handler=scan)
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
