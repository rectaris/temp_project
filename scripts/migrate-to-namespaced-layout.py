#!/usr/bin/env python3
"""Preserve pre-v1 generated files before Copier replaces the legacy layout."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


ROOT = Path.cwd()
BACKUP_ROOT = ROOT / ".project-agent-workflow-migration/v1-pre-namespace"
MANIFEST = BACKUP_ROOT / "manifest.json"

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

PRESERVED_PROJECT_FILES = (".github/workflows/ci.yml",)


def load_manifest() -> dict[str, list[str]]:
    if not MANIFEST.is_file():
        return {"moved": [], "copied": [], "restored": []}
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid migration manifest: {MANIFEST}")
    return {key: [str(item) for item in value.get(key, [])] for key in ("moved", "copied", "restored")}


def write_manifest(value: dict[str, list[str]]) -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def preserve_copy(relative: str, manifest: dict[str, list[str]]) -> None:
    source = ROOT / relative
    destination = BACKUP_ROOT / relative
    if not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != source.read_bytes():
            raise ValueError(f"migration backup already differs: {destination}")
    else:
        shutil.copy2(source, destination)
    if relative not in manifest["copied"]:
        manifest["copied"].append(relative)
        write_manifest(manifest)


def preserve_move(relative: str, manifest: dict[str, list[str]]) -> None:
    source = ROOT / relative
    destination = BACKUP_ROOT / relative
    if not source.exists() and not source.is_symlink():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"migration backup already exists while source is still present: {destination}")
    shutil.move(str(source), str(destination))
    if relative not in manifest["moved"]:
        manifest["moved"].append(relative)
        write_manifest(manifest)


def migrate_external_services() -> None:
    policy = ROOT / "docs/agent/external-services.yaml"
    if not policy.is_file():
        return
    text = policy.read_text(encoding="utf-8")
    if "credential_env:" not in text:
        return

    def replace(match: re.Match[str]) -> str:
        indent, raw_value = match.groups()
        value = raw_value.strip().strip("\"'")
        authentication = "environment" if value else "none"
        return (
            f"{indent}authentication: {authentication}\n"
            f"{indent}credential_reference: {json.dumps(value)}"
        )

    migrated, count = re.subn(r'(?m)^(\s*)credential_env:\s*([^#\n]*)$', replace, text)
    if count == 0 or "credential_env:" in migrated:
        raise ValueError(f"could not migrate legacy external-service credentials: {policy}")
    policy.write_text(migrated, encoding="utf-8")


def before() -> None:
    manifest = load_manifest()
    for relative in PRESERVED_PROJECT_FILES:
        preserve_copy(relative, manifest)
    for relative in LEGACY_FILES:
        preserve_move(relative, manifest)
    for skill in LEGACY_SKILLS:
        preserve_move(f".codex/skills/{skill}", manifest)
    write_manifest(manifest)
    print(f"preserved pre-namespace template files under {BACKUP_ROOT.relative_to(ROOT)}")


def after() -> None:
    manifest = load_manifest()
    for relative in PRESERVED_PROJECT_FILES:
        backup = BACKUP_ROOT / relative
        destination = ROOT / relative
        if not backup.is_file() or destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, destination)
        if relative not in manifest["restored"]:
            manifest["restored"].append(relative)
    migrate_external_services()
    write_manifest(manifest)
    print(f"completed namespaced-layout migration; review {BACKUP_ROOT.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("before", "after"), required=True)
    args = parser.parse_args()
    if not (ROOT / ".git").exists():
        raise SystemExit("namespaced-layout migration requires a Git repository root")
    try:
        before() if args.stage == "before" else after()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"namespaced-layout migration failed: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
