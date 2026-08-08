#!/usr/bin/env python3
"""Adopt the namespaced workflow without applying Copier's historical diff."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


BACKUP_RELATIVE = Path(".project-agent-workflow-migration/v1-pre-namespace")
MIGRATION_ROOT = Path(".project-agent-workflow-migration")
MANIFEST_NAME = "manifest.json"

LEGACY_FILES = (
    "AGENTS.md",
    ".codex/hooks.json",
    ".codex/agents/change_reviewer.toml",
    ".codex/agents/docs_researcher.toml",
    ".codex/agents/repo_explorer.toml",
    ".codex/agents/scoped_worker.toml",
    ".codex/hooks/agent_log_event.py",
    ".codex/hooks/pre_tool_hardening_gate.py",
    ".codex/hooks/semantic_guard_advisory.py",
    ".codex/hooks/stop_review_gate.py",
    ".github/codex/prompts/ci-autofix.md",
    ".github/workflows/codex-ci-autofix.yml",
    ".github/workflows/ci.yml",
    "docs/agent/CODEX_CI_AUTOFIX.md",
    "docs/agent/SPEC_AGENT_LOGGING.md",
    "docs/agent/SPEC_CONTEXT_COMPRESSION.md",
    "docs/agent/SPEC_COPIER_ADOPTION.md",
    "docs/agent/SPEC_DECISION_AUDIT.md",
    "docs/agent/SPEC_DEVELOPMENT_FLOW.md",
    "docs/agent/SPEC_ENVIRONMENT.md",
    "docs/agent/SPEC_EXTERNAL_SERVICES.md",
    "docs/agent/SPEC_FILE_MANAGEMENT.md",
    "docs/agent/SPEC_GIT_WORKFLOW.md",
    "docs/agent/SPEC_JAPANESE_TECH_WRITING.md",
    "docs/agent/SPEC_ORCHESTRATION.md",
    "docs/agent/SPEC_PLAN_WORKFLOW.md",
    "docs/agent/SPEC_REFERENT_FIRST.md",
    "docs/agent/SPEC_SECURITY.md",
    "docs/agent/SPEC_SKILL_AUTHORING.md",
    "docs/agent/SPEC_UI_DESIGN.md",
    "docs/agent/SPEC_USER_COMMUNICATION.md",
    "docs/agent/SPEC_VALIDATION.md",
    "docs/agent/external-services.yaml",
    "docs/agent/spec-index.yaml",
    "scripts/agent_log_manifest.py",
    "scripts/check-agent-completion.sh",
    "scripts/check-agent-log-manifest.py",
    "scripts/check-codex-toml.py",
    "scripts/check-external-service-policy.py",
    "scripts/clean-handoffs.sh",
    "scripts/complete-plan.sh",
    "scripts/context-compress.sh",
    "scripts/create-plan.sh",
    "scripts/finalize-active-plan.sh",
    "scripts/format-plan-docs.py",
    "scripts/format-plan-docs.sh",
    "scripts/import-codex-transcript.py",
    "scripts/lint-plan-docs.py",
    "scripts/lint-plan-docs.sh",
    "scripts/migrate-legacy-template-files.py",
    "scripts/next-plan-id.sh",
    "scripts/plan_validation_commands.py",
    "scripts/planlib.py",
    "scripts/promote-plan.sh",
    "scripts/referent-contract.py",
    "scripts/search-plan-archive.py",
    "scripts/security-static-check.py",
    "scripts/security_rules.py",
    "scripts/select-task-context.sh",
    "scripts/skillspector-scan.sh",
    "scripts/structure-map.py",
    "scripts/sync-plan-to-linear.sh",
    "scripts/validate-changes.py",
    "scripts/workflow-status.sh",
)

LEGACY_SKILLS = (
    "decision-audit",
    "define-referents-first",
    "graph-memory",
    "implementation-guidelines",
    "linear-ops",
    "mcp-ops",
    "plan-archive",
    "sequential-plan-orchestrator",
    "write-for-reader",
)

PROJECT_AGENT_FILES = (
    ".codex/agents/change_reviewer.toml",
    ".codex/agents/docs_researcher.toml",
    ".codex/agents/repo_explorer.toml",
    ".codex/agents/scoped_worker.toml",
)

LEGACY_OPTIONAL_DIGESTS = {
    ".github/workflows/codex-ci-autofix.yml": "04ac61e8f4ba19cfb6dfb694fcc5b36ab7b55339abeca6364d96a31d0ab2d561",
    "scripts/skillspector-scan.sh": "a11271499deae5818c755bb7a88d20eb9d7e8883ecbb34e8fb5a4a327516f38b",
}

MANAGED_SECTION = """
<!-- project-agent-workflow:managed-core:start -->
## Managed project-agent-workflow

- Read `.project-agent-workflow/AGENTS.md` for generic workflow policy.
- Keep the repository-specific rules in this root file authoritative when they are more specific.
- Store new project facts outside `.project-agent-workflow/`.
<!-- project-agent-workflow:managed-core:end -->
""".strip()

PRESERVED_SECTION_START = "<!-- project-agent-workflow:pre-v1-rules:start -->"
PRESERVED_SECTION_END = "<!-- project-agent-workflow:pre-v1-rules:end -->"
SKILLSPECTOR_BRIDGE = """#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$script_dir/../.project-agent-workflow/scripts/skillspector-scan.sh" "$@"
"""


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def require_repository_root(destination: Path) -> None:
    result = git(destination, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        raise SystemExit(f"not a Git repository: {destination}")
    if Path(result.stdout.strip()).resolve() != destination:
        raise SystemExit(f"destination must be the Git repository root: {destination}")
    status = git(destination, "status", "--porcelain=v1").stdout
    if status:
        raise SystemExit("destination repository is dirty; commit or stash changes before adoption")


def require_safe_target_ref(target_ref: str) -> None:
    if target_ref == "v1.0.0":
        raise SystemExit("v1.0.0 contains the unsafe smart-diff migration; use v1.1.1 or newer")
    if target_ref == "v1.1.0":
        raise SystemExit("v1.1.0 contains incomplete adoption validation; use v1.1.1 or newer")
    match = re.fullmatch(r"v([0-9]+)\.([0-9]+)\.([0-9]+)", target_ref)
    if not match or tuple(int(value) for value in match.groups()) < (1, 1, 1):
        raise SystemExit("adoption requires a stable release tag at v1.1.1 or newer")


def read_previous_ref(destination: Path) -> str:
    answers = destination / ".copier-answers.yml"
    if not answers.is_file():
        raise SystemExit(f"missing Copier answers file: {answers}")
    match = re.search(r"(?m)^_commit:\s*['\"]?([^'\"\s]+)", answers.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"missing _commit in Copier answers file: {answers}")
    value = match.group(1)
    if not (value.startswith("v0.") or value == "v1.0.0"):
        raise SystemExit(
            f"adoption is only for pre-v1 or v1.0.0 repair projects; found _commit: {value}"
        )
    return value


def read_answer(destination: Path, name: str) -> str | None:
    answers = destination / ".copier-answers.yml"
    match = re.search(
        rf"(?m)^{re.escape(name)}:\s*['\"]?([^'\"\s#]+)",
        answers.read_text(encoding="utf-8"),
    )
    return match.group(1) if match else None


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 2}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"invalid migration manifest: {path}")
    value["schema_version"] = 2
    return value


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def same_entry(first: Path, second: Path) -> bool:
    if first.is_symlink() or second.is_symlink():
        return first.is_symlink() and second.is_symlink() and first.readlink() == second.readlink()
    if first.is_file() and second.is_file():
        return digest(first) == digest(second)
    return first.is_dir() and second.is_dir()


def copy_entry(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        destination.symlink_to(source.readlink(), target_is_directory=source.is_dir())
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)


def backup_file(
    destination: Path,
    backup_root: Path,
    relative: Path,
    recorded: list[str],
) -> None:
    source = destination / relative
    if not source.exists() and not source.is_symlink():
        return
    if source.is_dir() and not source.is_symlink():
        for child in sorted(source.rglob("*")):
            if child.is_dir() and not child.is_symlink():
                continue
            backup_file(destination, backup_root, child.relative_to(destination), recorded)
        return
    primary = backup_root / relative
    if not primary.exists() and not primary.is_symlink():
        copy_entry(source, primary)
        recorded.append(relative.as_posix())
        return
    if same_entry(source, primary):
        return
    alternate = backup_root / "current-before-recopy" / relative
    if alternate.exists() or alternate.is_symlink():
        if not same_entry(source, alternate):
            raise SystemExit(f"migration backups differ for current file: {relative}")
        return
    copy_entry(source, alternate)
    recorded.append((Path("current-before-recopy") / relative).as_posix())


def backup_legacy_paths(destination: Path, backup_root: Path, manifest: dict[str, Any]) -> None:
    copied = [str(item) for item in manifest.get("adoption_copied", [])]
    for relative in LEGACY_FILES:
        backup_file(destination, backup_root, Path(relative), copied)
    for skill in LEGACY_SKILLS:
        backup_file(destination, backup_root, Path(f".codex/skills/{skill}"), copied)
    manifest["adoption_copied"] = sorted(set(copied))


def restore_missing_legacy_paths(
    destination: Path,
    backup_root: Path,
    manifest: dict[str, Any],
) -> None:
    restored = [str(item) for item in manifest.get("adoption_restored", [])]
    hook_paths = {
        ".codex/hooks/agent_log_event.py",
        ".codex/hooks/pre_tool_hardening_gate.py",
        ".codex/hooks/semantic_guard_advisory.py",
        ".codex/hooks/stop_review_gate.py",
    }
    candidates = [*LEGACY_FILES, *(f".codex/skills/{skill}" for skill in LEGACY_SKILLS)]
    for value in candidates:
        if value == "AGENTS.md" or value == ".codex/hooks.json" or value in hook_paths:
            continue
        source = backup_root / value
        target = destination / value
        should_restore_agent = value in PROJECT_AGENT_FILES and source.exists()
        if not source.exists() or (target.exists() and not should_restore_agent):
            continue
        if target.exists() or target.is_symlink():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
        copy_entry(source, target)
        restored.append(value)
    manifest["adoption_restored"] = sorted(set(restored))


def reconcile_unchanged_optional_paths(
    destination: Path,
    manifest: dict[str, Any],
) -> tuple[list[str], list[str]]:
    retired = [str(item) for item in manifest.get("retired_legacy_optional_paths", [])]
    bridged = [str(item) for item in manifest.get("bridged_legacy_optional_paths", [])]
    review = [str(item) for item in manifest.get("modified_legacy_optional_paths", [])]
    for value, expected_digest in LEGACY_OPTIONAL_DIGESTS.items():
        path = destination / value
        if not path.is_file():
            continue
        if value == ".github/workflows/codex-ci-autofix.yml" and read_answer(
            destination, "ci_autofix_mode"
        ) != "disabled":
            continue
        if digest(path) != expected_digest:
            review.append(value)
            continue
        if value == "scripts/skillspector-scan.sh" and read_answer(
            destination, "skillspector_mode"
        ) == "document_optional":
            path.write_text(SKILLSPECTOR_BRIDGE, encoding="utf-8")
            path.chmod(0o755)
            bridged.append(value)
        else:
            path.unlink()
            retired.append(value)
    retired = sorted(set(retired))
    bridged = sorted(set(bridged) - set(retired))
    review = sorted(set(review) - set(retired) - set(bridged))
    manifest["retired_legacy_optional_paths"] = retired
    manifest["bridged_legacy_optional_paths"] = bridged
    manifest["modified_legacy_optional_paths"] = review
    return retired, review


def copier_command(
    copier_executable: str | None,
    target_ref: str,
    data: Iterable[str] = (),
) -> list[str]:
    prefix = [copier_executable] if copier_executable else [sys.executable, "-m", "copier"]
    command = [
        *prefix,
        "recopy",
        "--defaults",
        "--trust",
        "--vcs-ref",
        target_ref,
        "--force",
        "--quiet",
    ]
    for item in data:
        command.extend(("--data", item))
    return command


def run_recopy(
    destination: Path,
    copier_executable: str | None,
    target_ref: str,
    data: Iterable[str] = (),
) -> None:
    result = subprocess.run(copier_command(copier_executable, target_ref, data), cwd=destination)
    if result.returncode:
        raise SystemExit(
            f"Copier recopy failed with exit code {result.returncode}; "
            f"review the preserved files under {BACKUP_RELATIVE}"
        )


def update_hook_wiring(destination: Path, check_only: bool = False) -> str:
    helper = Path(__file__).resolve().with_name("update_hook_wiring.py")
    command = [sys.executable, str(helper), "--destination", str(destination)]
    if check_only:
        command.append("--check")
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"Hook configuration update failed: {message}")
    try:
        payload = json.loads(result.stdout)
        status = payload["status"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SystemExit("Hook configuration update returned an invalid result") from exc
    if not isinstance(status, str):
        raise SystemExit("Hook configuration update returned an invalid status")
    return status


def append_managed_instructions(destination: Path, previous_ref: str, backup_root: Path) -> None:
    agents = destination / "AGENTS.md"
    if not agents.is_file():
        raise SystemExit("Copier recopy did not leave AGENTS.md")
    text = agents.read_text(encoding="utf-8").rstrip()
    if "project-agent-workflow:managed-core:start" not in text:
        text = f"{text}\n\n{MANAGED_SECTION}"
    previous_agents = backup_root / "AGENTS.md"
    if previous_ref == "v1.0.0" and previous_agents.is_file() and PRESERVED_SECTION_START not in text:
        previous = previous_agents.read_text(encoding="utf-8").strip()
        if previous and previous not in text:
            text = (
                f"{text}\n\n{PRESERVED_SECTION_START}\n"
                "## Preserved pre-v1 project instructions\n\n"
                f"{previous}\n{PRESERVED_SECTION_END}"
            )
    agents.write_text(text + "\n", encoding="utf-8")


def conflict_paths(destination: Path) -> list[str]:
    conflicts = git(destination, "ls-files", "-u").stdout.splitlines()
    if conflicts:
        return sorted({line.split("\t", 1)[1] for line in conflicts if "\t" in line})
    candidates = git(
        destination,
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    ).stdout.split("\0")
    found: list[str] = []
    for value in candidates:
        if not value:
            continue
        relative_path = Path(value)
        if relative_path == MIGRATION_ROOT or MIGRATION_ROOT in relative_path.parents:
            continue
        path = destination / relative_path
        if path.is_symlink() or not path.is_file():
            continue
        relative = relative_path.as_posix()
        if path.name.endswith(".rej"):
            found.append(relative)
            continue
        try:
            if path.stat().st_size > 2 * 1024 * 1024:
                continue
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if re.search(r"(?m)^(<<<<<<<|=======|>>>>>>>)", content):
            found.append(relative)
    return sorted(set(found))


def stale_ref_paths(destination: Path, previous_ref: str) -> list[str]:
    result = git(
        destination,
        "grep",
        "-l",
        "-F",
        previous_ref,
        "--",
        ".",
        ":!.copier-answers.yml",
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise SystemExit(f"could not search for project-owned references to {previous_ref}")
    return sorted(line for line in result.stdout.splitlines() if line)


def legacy_schema_review_paths(destination: Path) -> list[str]:
    relative = Path("docs/agent/external-services.yaml")
    path = destination / relative
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return [relative.as_posix()] if "credential_env:" in text else []


def validate_result(destination: Path, allowed_deletions: Iterable[str] = ()) -> None:
    required = (
        ".copier-answers.yml",
        ".project-agent-workflow/AGENTS.md",
        ".project-agent-workflow/ownership.yaml",
        ".codex/hooks/stop_review_gate.py",
        "AGENTS.md",
    )
    missing = [path for path in required if not (destination / path).is_file()]
    if missing:
        raise SystemExit(f"adoption is missing required files: {', '.join(missing)}")
    conflicts = conflict_paths(destination)
    if conflicts:
        raise SystemExit(f"adoption left unresolved conflicts: {', '.join(conflicts)}")
    deleted = set(git(destination, "diff", "--diff-filter=D", "--name-only").stdout.splitlines())
    unexpected = sorted(deleted - set(allowed_deletions))
    if unexpected:
        raise SystemExit(f"adoption deleted project-owned or unclassified files: {', '.join(unexpected)}")


def adopt(
    destination: Path,
    target_ref: str,
    copier_executable: str | None,
    data: Iterable[str] = (),
) -> None:
    destination = destination.resolve()
    require_safe_target_ref(target_ref)
    require_repository_root(destination)
    previous_ref = read_previous_ref(destination)
    update_hook_wiring(destination, check_only=True)
    backup_root = destination / BACKUP_RELATIVE
    manifest_path = backup_root / MANIFEST_NAME
    manifest = load_manifest(manifest_path)
    manifest.update(
        {
            "operation": "recopy_adoption",
            "previous_ref": previous_ref,
            "target_ref": target_ref,
        }
    )
    backup_legacy_paths(destination, backup_root, manifest)
    restore_missing_legacy_paths(destination, backup_root, manifest)
    write_manifest(manifest_path, manifest)
    run_recopy(destination, copier_executable, target_ref, data)
    append_managed_instructions(destination, previous_ref, backup_root)
    retired, modified_optional = reconcile_unchanged_optional_paths(destination, manifest)
    manifest["hook_configuration"] = update_hook_wiring(destination)
    validate_result(destination, retired)
    manifest["project_review_paths"] = stale_ref_paths(destination, previous_ref)
    manifest["legacy_schema_review_paths"] = legacy_schema_review_paths(destination)
    write_manifest(manifest_path, manifest)
    print(f"completed non-destructive namespaced-layout adoption from {previous_ref} to {target_ref}")
    print(f"review backup manifest: {manifest_path.relative_to(destination)}")
    if manifest["project_review_paths"]:
        print("review project-owned references to the previous Copier version:")
        for path in manifest["project_review_paths"]:
            print(f"- {path}")
    if manifest["legacy_schema_review_paths"]:
        print("review project-owned external-service policy before enabling the managed validator:")
        for path in manifest["legacy_schema_review_paths"]:
            print(f"- {path}")
    if modified_optional:
        print("review modified legacy optional files preserved in place:")
        for path in modified_optional:
            print(f"- {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=Path.cwd())
    parser.add_argument("--vcs-ref", default="v1.1.1")
    parser.add_argument("--copier-executable")
    parser.add_argument("--data", action="append", default=[])
    args = parser.parse_args()
    adopt(args.destination, args.vcs_ref, args.copier_executable, args.data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
