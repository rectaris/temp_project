#!/usr/bin/env python3
"""Static checks for the Copier template without requiring Copier."""

from __future__ import annotations

import json
import tempfile
import re
import subprocess
import sys
import os
from typing import Any
from itertools import combinations, product
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


SOURCE_REQUIRED = [
    "CHANGELOG.md",
    ".github/workflows/ci.yml",
    ".github/workflows/codex-ci-autofix.yml",
    ".github/codex/prompts/ci-autofix.md",
    "copier.yml",
    "pyproject.toml",
    "uv.lock",
    "SKILL.md",
    "agents/openai.yaml",
    "references/routing.md",
    "references/planning.md",
    "references/validation.md",
    "references/file-management.md",
    "references/orchestration.md",
    "docs/agent/spec-index.yaml",
    "docs/agent/SPEC_AGENT_LOGGING.md",
    "docs/agent/SPEC_CONTEXT_COMPRESSION.md",
    "docs/agent/SPEC_DECISION_AUDIT.md",
    "docs/agent/SPEC_PLAN_WORKFLOW.md",
    "docs/agent/SPEC_REFERENT_FIRST.md",
    "docs/agent/SPEC_SKILL_AUTHORING.md",
    "docs/agent/SPEC_USER_COMMUNICATION.md",
    "scripts/agent-log-event.py",
    "scripts/check-agent-log-manifest.py",
    "scripts/check-codex-toml.py",
    "scripts/check-yaml.py",
    "scripts/check-root-agent-policy.py",
    "scripts/context-compress.sh",
    "scripts/import-codex-transcript.py",
    "scripts/install-actionlint.sh",
    "scripts/lint-github-actions.sh",
    "scripts/plan_validation_commands.py",
    "scripts/run-sandboxed-plan-worker.py",
    "scripts/restructure-plan.py",
    "scripts/plan-execution-state.py",
    "scripts/referent-contract.py",
    "scripts/sync-plan-to-linear.sh",
    "scripts/validate-changes.py",
    "scripts/validate-copier-update.py",
    "template/AGENTS.md.jinja",
    "template/README.md.jinja",
    "template/.project-agent-workflow/AGENTS.md.jinja",
    "template/.project-agent-workflow/README.md",
    "template/.project-agent-workflow/human-report.json.jinja",
    "template/.project-agent-workflow/ownership.yaml",
    "template/.github/workflows/project-agent-workflow.yml",
    "template/.github/workflows/codex-ci-autofix.yml.jinja",
    "template/.github/codex/prompts/ci-autofix.md",
    "template/.gitignore.jinja",
    "template/.codex/config.toml.jinja",
    "template/.codex/hooks.json.jinja",
    "template/.codex/agents/change_reviewer.toml",
    "template/.codex/agents/docs_researcher.toml",
    "template/.codex/agents/evidence_synthesizer.toml",
    "template/.codex/agents/fast_scoped_worker.toml",
    "template/.codex/agents/repo_explorer.toml",
    "template/.codex/agents/scoped_worker.toml",
    "template/.codex/agents/sequential_plan_worker.toml",
    "template/.codex/hooks/agent_log_event.py",
    "template/.codex/hooks/pre_tool_hardening_gate.py",
    "template/.codex/hooks/semantic_guard_advisory.py",
    "template/.codex/hooks/stop_review_gate.py",
    "template/.project-agent-workflow/hooks/agent_log_event.py",
    "template/.project-agent-workflow/hooks/pre_tool_hardening_gate.py",
    "template/.project-agent-workflow/hooks/semantic_guard_advisory.py",
    "template/.project-agent-workflow/hooks/stop_review_gate.py",
    "template/.agents/skills/define-referents-first/SKILL.md",
    "template/.agents/skills/decision-audit/SKILL.md",
    "template/.agents/skills/graph-memory/SKILL.md",
    "template/.agents/skills/implementation-guidelines/SKILL.md",
    "template/.agents/skills/linear-ops/SKILL.md",
    "template/.agents/skills/mcp-ops/SKILL.md",
    "template/.agents/skills/plan-archive/SKILL.md",
    "template/.agents/skills/sequential-plan-orchestrator/SKILL.md",
    "template/.agents/skills/write-for-reader/SKILL.md",
    "template/.agents/skills/browser-ops/SKILL.md",
    "template/.project-agent-workflow/skills/define-referents-first/SKILL.md",
    "template/.project-agent-workflow/skills/define-referents-first/agents/openai.yaml",
    "template/.project-agent-workflow/skills/define-referents-first/references/workflow.md",
    "template/.project-agent-workflow/skills/decision-audit/SKILL.md",
    "template/.project-agent-workflow/skills/decision-audit/agents/openai.yaml",
    "template/.project-agent-workflow/skills/graph-memory/SKILL.md",
    "template/.project-agent-workflow/skills/graph-memory/agents/openai.yaml",
    "template/.project-agent-workflow/skills/implementation-guidelines/SKILL.md",
    "template/.project-agent-workflow/skills/implementation-guidelines/agents/openai.yaml",
    "template/.project-agent-workflow/skills/linear-ops/SKILL.md",
    "template/.project-agent-workflow/skills/linear-ops/agents/openai.yaml",
    "template/.project-agent-workflow/skills/mcp-ops/SKILL.md",
    "template/.project-agent-workflow/skills/mcp-ops/agents/openai.yaml",
    "template/.project-agent-workflow/skills/plan-archive/SKILL.md",
    "template/.project-agent-workflow/skills/plan-archive/agents/openai.yaml",
    "template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md",
    "template/.project-agent-workflow/skills/sequential-plan-orchestrator/agents/openai.yaml",
    "template/.project-agent-workflow/skills/write-for-reader/SKILL.md",
    "template/.project-agent-workflow/skills/write-for-reader/agents/openai.yaml",
    "template/.project-agent-workflow/skills/browser-ops/SKILL.md",
    "template/.project-agent-workflow/skills/browser-ops/agents/openai.yaml",
    "template/.project-agent-workflow/skills/browser-ops/references/browser-run-policy.md",
    "template/[[ _copier_conf.answers_file ]].jinja",
    "template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja",
    "template/.project-agent-workflow/docs/agent/CODEX_CI_AUTOFIX.md",
    "template/.project-agent-workflow/docs/agent/SPEC_DEVELOPMENT_FLOW.md.jinja",
    "template/.project-agent-workflow/docs/agent/SPEC_ENVIRONMENT.md",
    "template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md",
    "template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md",
    "template/.project-agent-workflow/docs/agent/SPEC_CONTEXT_COMPRESSION.md",
    "template/.project-agent-workflow/docs/agent/SPEC_DECISION_AUDIT.md",
    "template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md",
    "template/.project-agent-workflow/docs/agent/SPEC_VALIDATION.md.jinja",
    "template/.project-agent-workflow/docs/agent/SPEC_GIT_WORKFLOW.md",
    "template/.project-agent-workflow/docs/agent/SPEC_HUMAN_REPORTING.md",
    "template/.project-agent-workflow/docs/agent/SPEC_FILE_MANAGEMENT.md",
    "template/.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md",
    "template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja",
    "template/docs/agent/external-services.yaml.jinja",
    "template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md",
    "template/.project-agent-workflow/docs/agent/SPEC_REFERENT_FIRST.md",
    "template/.project-agent-workflow/docs/agent/SPEC_SECURITY.md",
    "template/.project-agent-workflow/docs/agent/SPEC_SKILL_AUTHORING.md",
    "template/.project-agent-workflow/docs/agent/SPEC_UI_DESIGN.md",
    "template/.project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md",
    "template/docs/agent/PROJECT_ENVIRONMENT.md",
    "template/docs/agent/PROJECT_POLICY.md",
    "template/docs/agent/PROJECT_UI_DESIGN.md",
    "template/docs/plan/README.md",
    "template/docs/plan/checked.md",
    "template/docs/plan/replanned.md",
    "template/docs/plan/plan.md",
    "template/docs/plan/backlog/README.md",
    "template/docs/plan/handoffs/README.md",
    "template/docs/plan/sub-agents/custom-agents.md",
    "template/docs/plan/sub-agents/helper-prompts.md",
    "template/.project-agent-workflow/scripts/create-plan.sh",
    "template/.project-agent-workflow/scripts/next-plan-id.sh",
    "template/.project-agent-workflow/scripts/promote-plan.sh",
    "template/.project-agent-workflow/scripts/complete-plan.sh",
    "template/.project-agent-workflow/scripts/check-agent-completion.sh",
    "template/.project-agent-workflow/scripts/finalize-active-plan.sh",
    "template/.project-agent-workflow/scripts/check-agent-log-manifest.py",
    "template/.project-agent-workflow/scripts/agent_log_manifest.py",
    "template/.project-agent-workflow/scripts/check-codex-toml.py",
    "template/.project-agent-workflow/scripts/check-external-service-policy.py",
    "template/.project-agent-workflow/scripts/context-compress.sh",
    "template/.project-agent-workflow/scripts/import-codex-transcript.py",
    "template/.project-agent-workflow/scripts/human-report.py",
    "template/.project-agent-workflow/scripts/lint-plan-docs.sh",
    "template/.project-agent-workflow/scripts/format-plan-docs.sh",
    "template/.project-agent-workflow/scripts/select-task-context.sh",
    "template/.project-agent-workflow/scripts/clean-handoffs.sh",
    "template/.project-agent-workflow/scripts/lint-plan-docs.py",
    "template/.project-agent-workflow/scripts/migrate-legacy-template-files.py",
    "template/.project-agent-workflow/scripts/planlib.py",
    "template/.project-agent-workflow/scripts/restructure-plan.py",
    "template/.project-agent-workflow/scripts/plan-execution-state.py",
    "template/.project-agent-workflow/scripts/plan_validation_commands.py",
    "template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py",
    "template/.project-agent-workflow/scripts/referent-contract.py",
    "template/.project-agent-workflow/scripts/format-plan-docs.py",
    "template/.project-agent-workflow/scripts/search-plan-archive.py",
    "template/.project-agent-workflow/scripts/validate-changes.py",
    "template/.project-agent-workflow/scripts/validate-copier-update.py",
    "template/.project-agent-workflow/scripts/update-from-copier.sh",
    "template/.project-agent-workflow/scripts/security_rules.py",
    "template/.project-agent-workflow/scripts/security-static-check.py",
    "template/.project-agent-workflow/scripts/skillspector-scan.sh",
    "template/.project-agent-workflow/scripts/structure-map.py",
    "template/.project-agent-workflow/scripts/sync-plan-to-linear.sh",
    "template/.project-agent-workflow/scripts/workflow-status.sh",
    "references/template-development.md",
    "tests/fixtures/typescript.answers.yml",
    "tests/fixtures/python.answers.yml",
    "tests/fixtures/docs.answers.yml",
    "tests/fixtures/copier-pairwise.tsv",
    "tests/copier-minimum.sh",
    "tests/copier-update.sh",
    "tests/assert-generated-semantics.py",
    "tests/root-plan-lifecycle.sh",
    "tests/lib-copier.sh",
    "tests/smoke.sh",
    "tests/test-agent-model-profiles.py",
    "tests/test-human-report.py",
    "tests/test-hooks.py",
    "tests/test-copier-migration.py",
    "tests/test-copier-adoption.py",
    "tests/test-referent-contract.py",
    "tests/test-sandboxed-plan-worker.py",
    "tests/test-validation-tools.py",
    "tests/fixtures/referent-contract/scenarios.json",
    "tests/fixtures/referent-contract/evaluation-protocol.md",
    "tests/fixtures/write-for-reader/scenarios.json",
    "tests/fixtures/browser-ops/scenarios.json",
    "tests/fixtures/orchestration/staged-acceptance.json",
    "tests/fixtures/orchestration/staged-baseline-events.json",
    "tests/fixtures/orchestration/staged-holdout-events.json",
    "tests/fixtures/orchestration/staged-paired-measured-example.json",
    "scripts/init-project-workflow.sh",
    "scripts/adopt-to-namespaced-layout.py",
    "scripts/migrate-to-namespaced-layout.py",
    "scripts/update_hook_wiring.py",
    "scripts/update_agent_model_profiles.py",
]

GENERATED_REQUIRED = [
    ".copier-answers.yml",
    ".gitignore",
    ".codex/config.toml",
    ".codex/agents/change_reviewer.toml",
    ".codex/agents/docs_researcher.toml",
    ".codex/agents/evidence_synthesizer.toml",
    ".codex/agents/fast_scoped_worker.toml",
    ".codex/agents/repo_explorer.toml",
    ".codex/agents/scoped_worker.toml",
    ".codex/agents/sequential_plan_worker.toml",
    ".codex/hooks/agent_log_event.py",
    ".codex/hooks/pre_tool_hardening_gate.py",
    ".codex/hooks/semantic_guard_advisory.py",
    ".codex/hooks/stop_review_gate.py",
    ".project-agent-workflow/AGENTS.md",
    ".project-agent-workflow/README.md",
    ".project-agent-workflow/human-report.json",
    ".project-agent-workflow/ownership.yaml",
    ".project-agent-workflow/hooks/agent_log_event.py",
    ".project-agent-workflow/hooks/pre_tool_hardening_gate.py",
    ".project-agent-workflow/hooks/semantic_guard_advisory.py",
    ".project-agent-workflow/hooks/stop_review_gate.py",
    ".agents/skills/define-referents-first/SKILL.md",
    ".agents/skills/decision-audit/SKILL.md",
    ".agents/skills/graph-memory/SKILL.md",
    ".agents/skills/implementation-guidelines/SKILL.md",
    ".agents/skills/linear-ops/SKILL.md",
    ".agents/skills/mcp-ops/SKILL.md",
    ".agents/skills/plan-archive/SKILL.md",
    ".agents/skills/sequential-plan-orchestrator/SKILL.md",
    ".agents/skills/write-for-reader/SKILL.md",
    ".agents/skills/browser-ops/SKILL.md",
    ".project-agent-workflow/skills/define-referents-first/SKILL.md",
    ".project-agent-workflow/skills/define-referents-first/agents/openai.yaml",
    ".project-agent-workflow/skills/define-referents-first/references/workflow.md",
    ".project-agent-workflow/skills/decision-audit/SKILL.md",
    ".project-agent-workflow/skills/decision-audit/agents/openai.yaml",
    ".project-agent-workflow/skills/graph-memory/SKILL.md",
    ".project-agent-workflow/skills/graph-memory/agents/openai.yaml",
    ".project-agent-workflow/skills/implementation-guidelines/SKILL.md",
    ".project-agent-workflow/skills/implementation-guidelines/agents/openai.yaml",
    ".project-agent-workflow/skills/linear-ops/SKILL.md",
    ".project-agent-workflow/skills/linear-ops/agents/openai.yaml",
    ".project-agent-workflow/skills/mcp-ops/SKILL.md",
    ".project-agent-workflow/skills/mcp-ops/agents/openai.yaml",
    ".project-agent-workflow/skills/plan-archive/SKILL.md",
    ".project-agent-workflow/skills/plan-archive/agents/openai.yaml",
    ".project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md",
    ".project-agent-workflow/skills/sequential-plan-orchestrator/agents/openai.yaml",
    ".project-agent-workflow/skills/write-for-reader/SKILL.md",
    ".project-agent-workflow/skills/write-for-reader/agents/openai.yaml",
    ".project-agent-workflow/skills/browser-ops/SKILL.md",
    ".project-agent-workflow/skills/browser-ops/agents/openai.yaml",
    ".project-agent-workflow/skills/browser-ops/references/browser-run-policy.md",
    "AGENTS.md",
    "README.md",
    ".github/workflows/project-agent-workflow.yml",
    ".github/codex/prompts/ci-autofix.md",
    ".project-agent-workflow/docs/agent/spec-index.yaml",
    ".project-agent-workflow/docs/agent/CODEX_CI_AUTOFIX.md",
    ".project-agent-workflow/docs/agent/SPEC_DEVELOPMENT_FLOW.md",
    ".project-agent-workflow/docs/agent/SPEC_ENVIRONMENT.md",
    ".project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md",
    ".project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md",
    ".project-agent-workflow/docs/agent/SPEC_CONTEXT_COMPRESSION.md",
    ".project-agent-workflow/docs/agent/SPEC_DECISION_AUDIT.md",
    ".project-agent-workflow/docs/agent/SPEC_FILE_MANAGEMENT.md",
    ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md",
    "docs/agent/external-services.yaml",
    ".project-agent-workflow/docs/agent/SPEC_GIT_WORKFLOW.md",
    ".project-agent-workflow/docs/agent/SPEC_HUMAN_REPORTING.md",
    ".project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md",
    ".project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md",
    ".project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md",
    ".project-agent-workflow/docs/agent/SPEC_REFERENT_FIRST.md",
    ".project-agent-workflow/docs/agent/SPEC_SECURITY.md",
    ".project-agent-workflow/docs/agent/SPEC_SKILL_AUTHORING.md",
    ".project-agent-workflow/docs/agent/SPEC_UI_DESIGN.md",
    ".project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md",
    "docs/agent/PROJECT_ENVIRONMENT.md",
    "docs/agent/PROJECT_POLICY.md",
    "docs/agent/PROJECT_UI_DESIGN.md",
    ".project-agent-workflow/docs/agent/SPEC_VALIDATION.md",
    "docs/plan/README.md",
    "docs/plan/backlog/README.md",
    "docs/plan/checked.md",
    "docs/plan/replanned.md",
    "docs/plan/handoffs/README.md",
    "docs/plan/sub-agents/custom-agents.md",
    "docs/plan/sub-agents/helper-prompts.md",
    "docs/plan/plan.md",
    ".project-agent-workflow/scripts/check-agent-completion.sh",
    ".project-agent-workflow/scripts/finalize-active-plan.sh",
    ".project-agent-workflow/scripts/check-agent-log-manifest.py",
    ".project-agent-workflow/scripts/agent_log_manifest.py",
    ".project-agent-workflow/scripts/check-codex-toml.py",
    ".project-agent-workflow/scripts/check-external-service-policy.py",
    ".project-agent-workflow/scripts/context-compress.sh",
    ".project-agent-workflow/scripts/import-codex-transcript.py",
    ".project-agent-workflow/scripts/human-report.py",
    ".project-agent-workflow/scripts/complete-plan.sh",
    ".project-agent-workflow/scripts/workflow-status.sh",
    ".project-agent-workflow/scripts/create-plan.sh",
    ".project-agent-workflow/scripts/format-plan-docs.py",
    ".project-agent-workflow/scripts/select-task-context.sh",
    ".project-agent-workflow/scripts/clean-handoffs.sh",
    ".project-agent-workflow/scripts/lint-plan-docs.sh",
    ".project-agent-workflow/scripts/format-plan-docs.sh",
    ".project-agent-workflow/scripts/lint-plan-docs.py",
    ".project-agent-workflow/scripts/migrate-legacy-template-files.py",
    ".project-agent-workflow/scripts/next-plan-id.sh",
    ".project-agent-workflow/scripts/planlib.py",
    ".project-agent-workflow/scripts/restructure-plan.py",
    ".project-agent-workflow/scripts/plan-execution-state.py",
    ".project-agent-workflow/scripts/plan_validation_commands.py",
    ".project-agent-workflow/scripts/run-sandboxed-plan-worker.py",
    ".project-agent-workflow/scripts/referent-contract.py",
    ".project-agent-workflow/scripts/promote-plan.sh",
    ".project-agent-workflow/scripts/search-plan-archive.py",
    ".project-agent-workflow/scripts/security_rules.py",
    ".project-agent-workflow/scripts/structure-map.py",
    ".project-agent-workflow/scripts/validate-changes.py",
    ".project-agent-workflow/scripts/validate-copier-update.py",
    ".project-agent-workflow/scripts/update-from-copier.sh",
    ".project-agent-workflow/scripts/security-static-check.py",
    ".project-agent-workflow/scripts/sync-plan-to-linear.sh",
]

SOURCE_SHELL_LINT = [path for path in SOURCE_REQUIRED if path.endswith(".sh")]
SOURCE_PYTHON_COMPILE = [path for path in SOURCE_REQUIRED if path.endswith(".py")]


QUESTIONS = {
    "project_name",
    "project_slug",
    "project_purpose",
    "primary_language",
    "human_report_mode",
    "codex_hooks_mode",
    "skillspector_mode",
    "external_access_profile",
    "mcp_policy_mode",
    "linear_sync_mode",
    "graph_memory_mode",
    "ci_autofix_mode",
}

EXPECTED_CHOICE_VALUES = {
    "primary_language": {"typescript", "python", "mixed", "docs"},
    "human_report_mode": {"disabled", "agent_select_local"},
    "codex_hooks_mode": {"disabled", "install_templates", "enable_local_logging"},
    "skillspector_mode": {"disabled", "document_optional"},
    "external_access_profile": {"restricted", "task_scoped_default_allow"},
    "mcp_policy_mode": {"disabled", "document_optional"},
    "linear_sync_mode": {"disabled", "document_optional"},
    "graph_memory_mode": {"disabled", "document_optional"},
    "ci_autofix_mode": {"disabled", "patch_only", "direct_push"},
}

EXPECTED_DEFAULT_VALUES = {
    "human_report_mode": "agent_select_local",
    "external_access_profile": "restricted",
    "ci_autofix_mode": "disabled",
}

CONDITIONAL_GENERATED = {
    ".codex/hooks.json": ("codex_hooks_mode", {"enable_local_logging"}),
    ".project-agent-workflow/scripts/skillspector-scan.sh": ("skillspector_mode", {"document_optional"}),
    ".github/workflows/codex-ci-autofix.yml": ("ci_autofix_mode", {"patch_only", "direct_push"}),
}

PAIRWISE_FIXTURE = ROOT / "tests/fixtures/copier-pairwise.tsv"

JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")

REMOVED_ACTIVATION_QUESTIONS = {
    "use_hooks",
    "use_skillspector",
    "use_mcp_policy",
    "use_linear_sync",
    "use_graph_memory",
}

REMOVED_LOCAL_WORKFLOW_QUESTIONS = {
    "planning_style",
    "use_codex_agents",
    "max_agent_threads",
    "use_plan_lifecycle",
    "use_change_validation",
    "use_security_static",
    "use_structure_scanner",
}


def fail(message: str) -> None:
    print(f"template check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def normalized_template_core(path: str) -> str:
    return read(path).replace(".project-agent-workflow/", "").replace(".agents/skills/", ".codex/skills/")


def require_sequential_worker() -> None:
    path = ROOT / "template/.codex/agents/sequential_plan_worker.toml"
    text = path.read_text(encoding="utf-8")
    required = (
        'name = "sequential_plan_worker"',
        'model = "gpt-5.3-codex-spark"',
        'model_reasoning_effort = "medium"',
        'sandbox_mode = "read-only"',
        "Do not process the next active plan",
        "Do not spawn descendant agents",
        "Do not edit the assigned plan's status",
        "Do not commit changes",
        ".project-agent-workflow/scripts/run-sandboxed-plan-worker.py run <plan>",
    )
    for marker in required:
        if marker not in text:
            fail(f"sequential worker missing required contract: {marker}")


def require_agent_model_profiles() -> None:
    expected = {
        "change_reviewer": ("gpt-5.6-sol", "high"),
        "docs_researcher": ("gpt-5.6-luna", "medium"),
        "evidence_synthesizer": ("gpt-5.6-luna", "xhigh"),
        "fast_scoped_worker": ("gpt-5.3-codex-spark", "medium"),
        "repo_explorer": ("gpt-5.6-luna", "low"),
        "scoped_worker": ("gpt-5.6-terra", "medium"),
        "sequential_plan_worker": ("gpt-5.3-codex-spark", "medium"),
    }
    for name, (model, effort) in expected.items():
        text = read(f"template/.codex/agents/{name}.toml")
        for marker in (f'model = "{model}"', f'model_reasoning_effort = "{effort}"'):
            if marker not in text:
                fail(f"{name} missing fixed model profile: {marker}")


def require_fast_scoped_worker() -> None:
    path = ROOT / "template/.codex/agents/fast_scoped_worker.toml"
    text = path.read_text(encoding="utf-8")
    required = (
        'name = "fast_scoped_worker"',
        'model = "gpt-5.3-codex-spark"',
        'model_reasoning_effort = "medium"',
        'sandbox_mode = "workspace-write"',
        "Require an explicit write scope and predetermined validation",
        "Stop and report unexpected tracked-file deletion",
        "Do not spawn descendant agents",
        "Do not commit, tag, push, release",
    )
    for marker in required:
        if marker not in text:
            fail(f"fast scoped worker missing required contract: {marker}")


def require_evidence_synthesizer() -> None:
    path = ROOT / "template/.codex/agents/evidence_synthesizer.toml"
    text = path.read_text(encoding="utf-8")
    required = (
        'name = "evidence_synthesizer"',
        'model = "gpt-5.6-luna"',
        'model_reasoning_effort = "xhigh"',
        'sandbox_mode = "read-only"',
        "compares multiple repositories, logs, specifications, implementation alternatives, or cause hypotheses",
        "Do not edit files, execute external writes",
        "Do not spawn descendant agents",
        "final high-risk judgment",
    )
    for marker in required:
        if marker not in text:
            fail(f"evidence synthesizer missing required contract: {marker}")


def require_orchestration_policy_markers() -> None:
    template_spec = read("template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md").lower()
    template_agents = read("template/.project-agent-workflow/AGENTS.md.jinja").lower()
    root_orchestration = read("references/orchestration.md").lower()
    shared_markers = (
        "per-task user instruction",
        "repository-wide",
        "independent helper work",
        "main agent owns",
        "expected context reduction",
        "parallelism",
        "review value",
        "repository breadth alone",
        "proactively",
        "non-overlapping",
        "short deterministic",
        "cost",
        "write scope",
        "context files read-only",
        "advisory",
        "external writes",
        "authorization",
        "destructive",
        "secrets",
        "separate explicit policy",
        "final high-risk",
        "final report",
        "role",
        "acceptance",
        "admissible implementation slice",
        "implementation_risk",
        "implementation_ambiguity",
        "spark medium",
        "terra medium",
        "state path outside the repository",
        "orchestration run identifier",
        "symlinked targets or ancestors",
        "skipped known-unavailable starts",
        "finite and nonnegative",
        "prompts, raw output, environment values, or credentials",
        "run-sandboxed-plan-worker.py correct",
        "aggregate patch",
        "at most two correction rounds",
        "rejected patch never touches the source",
        "candidate generation and correction do not run plan validation",
        "parent diff review",
        "critical-invariant review",
        "focused_validation",
        "validation_authority_scope",
        "network-isolated review clone",
        "authoritative",
        "bounded parent implementation",
        "independent change review",
        "replan_required",
        "requirement change needs separate explicit user authorization",
        "elapsed time is telemetry",
        "plan-execution-state.py",
        "independent-review receipt",
        "--plan-execution-state",
        "at least 30 percent lower median",
        "p95 time no more than 10 percent worse",
        "run-sandboxed-plan-worker.py run",
        "read-only",
    )
    for marker in shared_markers:
        if marker not in template_spec:
            fail(f"template managed SPEC_ORCHESTRATION missing marker: {marker}")
    for marker in (
        "per-task user instruction",
        "do not delegate",
        "final ownership",
        "main session",
        "external writes",
        "secrets",
        "short deterministic",
        "authorization",
        "advisory",
        "role",
        "scope",
        "acceptance",
        "run-sandboxed-plan-worker.py",
        "read-only",
    ):
        if marker not in template_agents:
            fail(f"template managed AGENTS missing marker: {marker}")
    for marker in (
        "per-task user instruction",
        "without waiting for a per-task user instruction",
        "repository-wide",
        "proactively",
        "independent helper work",
        "short deterministic",
        "multiple independent",
        "cross-specification",
        "validation, security, or orchestration",
        "large or dense",
        "context files read-only",
        "advisory",
        "external writes",
        "authorization",
        "separate explicit policy",
        "secrets",
        "destructive",
        "final report",
        "final high-risk",
        "write scope",
        "acceptance",
        "run-sandboxed-plan-worker.py run",
        "read-only",
    ):
        if marker not in root_orchestration:
            fail(f"root orchestration policy missing marker for template parity: {marker}")

    try:
        staged = json.loads(read("tests/fixtures/orchestration/staged-acceptance.json"))
    except json.JSONDecodeError as exc:
        fail(f"invalid staged orchestration fixture: {exc}")
    if staged.get("schema_version") != 2:
        fail("staged orchestration fixture is missing the event-evidence schema")
    if staged.get("performance_claim_status") not in {"measurement_pending", "measured_pass"}:
        fail("staged orchestration performance claim status is invalid")
    if staged.get("measured_evidence_file") != "staged-paired-measured-example.json":
        fail("staged orchestration must identify its paired runner evidence")
    if staged.get("evidence_file") != "staged-baseline-events.json" or staged.get("holdout_file") != "staged-holdout-events.json":
        fail("staged orchestration evidence and holdout must remain physically separated")
    evidence = json.loads(read("tests/fixtures/orchestration/staged-baseline-events.json"))
    holdout = json.loads(read("tests/fixtures/orchestration/staged-holdout-events.json"))
    scenarios = [*evidence.get("scenarios", []), *holdout.get("scenarios", [])]
    thresholds = staged.get("thresholds", {})
    if evidence.get("schema_version") != 2 or holdout.get("schema_version") != 2:
        fail("staged orchestration evidence must use commit-backed schema")
    if evidence.get("version") != "2026-08-13-plans-062-064-070-v3":
        fail("staged orchestration fixture is missing the versioned baseline")
    if {item.get("class") for item in scenarios if isinstance(item, dict)} != {"median", "edge", "negative", "holdout"}:
        fail("staged orchestration fixture must cover median, edge, negative, and holdout")
    holdouts = [item for item in scenarios if isinstance(item, dict) and item.get("class") == "holdout"]
    if len(holdouts) != 1 or holdouts[0].get("used_for_tuning") is not False:
        fail("staged orchestration holdout must remain outside reusable tuning prompts")
    if thresholds != {
        "minimum_median_reduction_fraction": 0.3,
        "maximum_p95_regression_fraction": 0.1,
        "maximum_implementation_generations": 3,
        "maximum_known_unavailable_primary_starts": 1,
        "authoritative_full_suite_runs_per_accepted_candidate": 1,
        "maximum_unresolved_high_medium_findings": 0,
    }:
        fail("staged orchestration thresholds differ from the accepted contract")


def template_source_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "template"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return {line for line in result.stdout.splitlines() if line and (ROOT / line).is_file()}


def require_template_manifest_complete() -> None:
    tracked = template_source_files()
    listed = {path for path in SOURCE_REQUIRED if path.startswith("template/")}
    missing = sorted(tracked - listed)
    stale = sorted(listed - tracked)
    if missing or stale:
        fail(f"template source manifest mismatch: missing={missing}, stale={stale}")


def require_referent_first_alignment() -> None:
    pairs = (
        ("docs/agent/SPEC_REFERENT_FIRST.md", "template/.project-agent-workflow/docs/agent/SPEC_REFERENT_FIRST.md"),
        (".codex/skills/define-referents-first/SKILL.md", "template/.project-agent-workflow/skills/define-referents-first/SKILL.md"),
        (
            ".codex/skills/define-referents-first/agents/openai.yaml",
            "template/.project-agent-workflow/skills/define-referents-first/agents/openai.yaml",
        ),
        (
            ".codex/skills/define-referents-first/references/workflow.md",
            "template/.project-agent-workflow/skills/define-referents-first/references/workflow.md",
        ),
        ("scripts/referent-contract.py", "template/.project-agent-workflow/scripts/referent-contract.py"),
        (".codex/hooks/semantic_guard_advisory.py", "template/.codex/hooks/semantic_guard_advisory.py"),
        (
            ".project-agent-workflow/hooks/semantic_guard_advisory.py",
            "template/.project-agent-workflow/hooks/semantic_guard_advisory.py",
        ),
    )
    for root_path, template_path in pairs:
        template_text = read(template_path)
        if "/.project-agent-workflow/" in template_path and not root_path.startswith(".project-agent-workflow/"):
            template_text = normalized_template_core(template_path)
        if read(root_path) != template_text:
            fail(f"referent-first root/template files differ: {root_path} != {template_path}")


def require_user_communication_alignment() -> None:
    pairs = (
        ("docs/agent/SPEC_USER_COMMUNICATION.md", "template/.project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md"),
        (".codex/skills/write-for-reader/SKILL.md", "template/.project-agent-workflow/skills/write-for-reader/SKILL.md"),
        (
            ".codex/skills/write-for-reader/agents/openai.yaml",
            "template/.project-agent-workflow/skills/write-for-reader/agents/openai.yaml",
        ),
        (".codex/hooks/stop_review_gate.py", "template/.codex/hooks/stop_review_gate.py"),
        (
            ".project-agent-workflow/hooks/stop_review_gate.py",
            "template/.project-agent-workflow/hooks/stop_review_gate.py",
        ),
    )
    for root_path, template_path in pairs:
        template_text = read(template_path)
        if "/.project-agent-workflow/" in template_path and not root_path.startswith(".project-agent-workflow/"):
            template_text = normalized_template_core(template_path)
        if read(root_path) != template_text:
            fail(f"user-communication root/template files differ: {root_path} != {template_path}")


def require_sandboxed_plan_worker_alignment() -> None:
    root_runner = read("scripts/run-sandboxed-plan-worker.py")
    template_runner = read("template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py")
    if root_runner != template_runner:
        fail("sandboxed plan worker root/template scripts differ")
    root_mode = os.stat(ROOT / "scripts/run-sandboxed-plan-worker.py").st_mode & 0o777
    template_mode = os.stat(ROOT / "template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py").st_mode & 0o777
    if root_mode != template_mode:
        fail("sandboxed plan worker root/template script modes differ")
    if root_mode & 0o111 == 0:
        fail("sandboxed plan worker scripts must be executable")
    root_restructure = ROOT / "scripts/restructure-plan.py"
    template_restructure = ROOT / "template/.project-agent-workflow/scripts/restructure-plan.py"
    if root_restructure.read_bytes() != template_restructure.read_bytes():
        fail("plan restructuring root/template scripts differ")
    if (root_restructure.stat().st_mode & 0o777) != (template_restructure.stat().st_mode & 0o777):
        fail("plan restructuring root/template script modes differ")
    root_execution_state = ROOT / "scripts/plan-execution-state.py"
    template_execution_state = ROOT / "template/.project-agent-workflow/scripts/plan-execution-state.py"
    if root_execution_state.read_bytes() != template_execution_state.read_bytes():
        fail("plan execution state root/template scripts differ")
    if (root_execution_state.stat().st_mode & 0o777) != (template_execution_state.stat().st_mode & 0o777):
        fail("plan execution state root/template script modes differ")
    for marker in (
        'DEFAULT_CODEX_MODEL = "gpt-5.3-codex-spark"',
        'DEFAULT_CODEX_REASONING = "medium"',
        'DEFAULT_FALLBACK_CODEX_MODEL = "gpt-5.6-luna"',
        'DEFAULT_FALLBACK_CODEX_REASONING = "max"',
        "def classify_codex_unavailability",
        'label="fallback"',
        '"attempts"',
        '"selected_attempt"',
        '"fallback_reason"',
        '"--fallback-codex-model"',
        '"--fallback-codex-reasoning-effort"',
        '"--no-model-fallback"',
        "def select_plan_writable_profile",
        "implementation_risk",
        "implementation_ambiguity",
        "WRITABLE_SOL_MODEL",
        "AVAILABILITY_STATE_MAX_BYTES",
        "def open_availability_state",
        '"--availability-state"',
        '"--orchestration-run-id"',
        '"telemetry"',
        '"skipped_known_unavailable_starts"',
        "def correct_worker",
        "def verify_candidate_manifest",
        '"correct"',
        "MAX_CORRECTION_ROUNDS",
        '"correction_lineage"',
        "def validate_candidate",
        "def open_lifecycle_state",
        '"--lifecycle-state"',
        "VALIDATION_AUTHORITY_SCOPE",
        '"authoritative_passed"',
        '"apply requires exactly one successful authoritative validation"',
        "load_plan_validation_commands",
        '"focused_validation_count"',
        '"authoritative_validation_count"',
        "network_enabled=False",
    ):
        if marker not in template_runner:
            fail(f"sandboxed plan worker missing model fallback marker: {marker}")
    pairs = (
        (
            ".codex/skills/sequential-plan-orchestrator/SKILL.md",
            "template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md",
        ),
    )
    for root_path, template_path in pairs:
        template_text = normalized_template_core(template_path)
        if read(root_path) != template_text:
            fail(f"sandboxed plan worker orchestration text differs: {root_path} != {template_path}")
    for relative in (
        "template/.project-agent-workflow/AGENTS.md.jinja",
        "template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md",
        "template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md",
    ):
        text = read(relative).lower()
        for marker in ("gpt-5.3-codex-spark", "gpt-5.6-luna", "max", "usage limit", "rate limit"):
            if marker not in text:
                fail(f"{relative} missing sandboxed model fallback policy marker: {marker}")


def run_hook_payload(script_path: str, run_id: str, payload: dict[str, Any], cwd: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["CODEX_AGENT_LOG_RUN_ID"] = run_id
    result = subprocess.run(
        [sys.executable, str(ROOT / script_path), "--event", str(payload.get("hook_event_name", "UserPromptSubmit"))],
        input=json.dumps(payload),
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    if result.returncode != 0:
        fail(f"hook logger execution failed for {script_path}: {result.stderr}")
    event_path = cwd / ".agent-logs" / run_id / "raw" / "events.jsonl"
    if not event_path.is_file():
        fail(f"hook log file missing for {script_path}: {event_path}")
    lines = [line for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        fail(f"hook log file empty for {script_path}: {event_path}")
    try:
        return json.loads(lines[-1])
    except Exception as exc:
        fail(f"invalid hook log JSON for {script_path}: {event_path}: {exc}")


def require_hook_logging_parity() -> None:
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "hook-parity-session",
        "tool": "Bash",
        "tool_name": "bash",
        "prompt": "secret=should-not-log",
        "tool_input": "rm -rf /",
        "response": "tool result should not log",
        "output": "tool output should not log",
        "api_key": "sk-abcdefghijklmnopqrstuvwxyz",
    }
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        root_record = run_hook_payload(".project-agent-workflow/hooks/agent_log_event.py", "root-parity", payload, repo)
        template_record = run_hook_payload("template/.project-agent-workflow/hooks/agent_log_event.py", "template-parity", payload, repo)
    if root_record.get("event") != template_record.get("event"):
        fail("root/template hook event field diverged")
    if root_record.get("payload", {}).get("session_id") != payload["session_id"]:
        fail("root hook payload stopped logging session_id")
    if template_record.get("payload", {}).get("session_id") != payload["session_id"]:
        fail("template hook payload stopped logging session_id")
    for field in ("prompt", "tool_input", "response", "output", "api_key"):
        if field in root_record.get("payload", {}):
            fail(f"root hook payload leaked disallowed field: {field}")
        if field in template_record.get("payload", {}):
            fail(f"template hook payload leaked disallowed field: {field}")

    if root_record.get("payload", {}) != template_record.get("payload", {}):
        fail("root/template hook payload structure diverged")


def require_root_pre_tool_hardening() -> None:
    hooks = json.loads(read(".codex/hooks.json"))
    entries = hooks.get("hooks", {}).get("PreToolUse", [{}])[0].get("hooks", [])
    commands = [entry.get("command", "") for entry in entries]
    if len(commands) != 2:
        fail("root PreToolUse must contain the event logger and hardening gate")
    if "agent_log_event.py" not in commands[0]:
        fail("root PreToolUse must run event logging before the hardening gate")
    if ".project-agent-workflow/hooks/pre_tool_hardening_gate.py" not in commands[1]:
        fail("root PreToolUse must run the hardening gate")


def parse_fixture(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            fail(f"fixture line is not key/value: {path}: {raw_line}")
        key, value = line.split(":", 1)
        key = key.strip()
        if key in data:
            fail(f"fixture contains duplicate answer: {path}: {key}")
        data[key] = value.strip().strip("\"'")
    return data


def parse_pairwise_fixture(path: Path) -> list[dict[str, str]]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    if not lines:
        fail(f"pairwise fixture is empty: {path}")
    header = lines[0].split("\t")
    expected_header = ["case", *EXPECTED_CHOICE_VALUES]
    if header != expected_header:
        fail(f"pairwise fixture header mismatch: expected={expected_header}, actual={header}")
    rows: list[dict[str, str]] = []
    seen_cases: set[str] = set()
    for raw_line in lines[1:]:
        values = raw_line.split("\t")
        if len(values) != len(header):
            fail(f"pairwise fixture column mismatch: {path}: {raw_line}")
        row = dict(zip(header, values, strict=True))
        case = row.pop("case")
        if not case or case in seen_cases:
            fail(f"pairwise fixture case must be non-empty and unique: {case!r}")
        seen_cases.add(case)
        rows.append(row)
    return rows


def require_valid_answers(answers: dict[str, str], source: str, *, complete: bool) -> None:
    if complete:
        missing = QUESTIONS - set(answers)
        unknown = set(answers) - QUESTIONS
        if missing or unknown:
            fail(f"{source} answer keys mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}")
    for question, expected_values in EXPECTED_CHOICE_VALUES.items():
        value = answers.get(question)
        if value is not None and value not in expected_values:
            fail(f"{source} has invalid answer: {question}={value!r}")


def require_pairwise_coverage(answer_sets: list[dict[str, str]]) -> None:
    questions = list(EXPECTED_CHOICE_VALUES)
    missing: list[str] = []
    for first, second in combinations(questions, 2):
        observed = {(answers[first], answers[second]) for answers in answer_sets}
        expected = set(product(EXPECTED_CHOICE_VALUES[first], EXPECTED_CHOICE_VALUES[second]))
        for first_value, second_value in sorted(expected - observed):
            missing.append(f"{first}={first_value}, {second}={second_value}")
    if missing:
        fail(f"Copier fixture matrix is not pairwise complete: {missing}")


def expected_generated_paths(answers: dict[str, str]) -> list[str]:
    require_valid_answers(answers, "generated inventory input", complete=True)
    generated: set[str] = set()
    for source in template_source_files():
        relative = source.removeprefix("template/")
        if relative == "[[ _copier_conf.answers_file ]].jinja":
            output = ".copier-answers.yml"
        elif relative.endswith(".jinja"):
            output = relative.removesuffix(".jinja")
        else:
            output = relative
        condition = CONDITIONAL_GENERATED.get(output)
        if condition is not None:
            question, included_values = condition
            if answers[question] not in included_values:
                continue
        generated.add(output)
    return sorted(generated)


def copier_question_blocks(text: str) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line and not line.startswith(" ") and ":" in line:
            current = line.split(":", 1)[0]
            blocks[current] = []
            continue
        if current:
            blocks[current].append(line)
    return blocks


def require_japanese_prompts(copier_yml: str) -> None:
    blocks = copier_question_blocks(copier_yml)
    for question in QUESTIONS:
        body = blocks.get(question)
        if body is None:
            fail(f"copier.yml missing question: {question}")
        help_lines = [line for line in body if line.startswith("  help:")]
        if not help_lines:
            fail(f"copier.yml question missing help text: {question}")
        if not JAPANESE_RE.search(help_lines[0]):
            fail(f"copier.yml question help must be Japanese: {question}")

    for question, expected_values in EXPECTED_CHOICE_VALUES.items():
        body = blocks[question]
        values: set[str] = set()
        in_choices = False
        for line in body:
            if line == "  choices:":
                in_choices = True
                continue
            if in_choices and line.startswith("    ") and ":" in line:
                label, value = line.strip().split(":", 1)
                if not JAPANESE_RE.search(label):
                    fail(f"copier.yml choice label must be Japanese: {question}: {label}")
                values.add(value.strip().strip("\"'"))
                continue
            if in_choices and line and not line.startswith("    "):
                break
        if values != expected_values:
            fail(f"copier.yml choice values changed for {question}: {sorted(values)}")

    for question, expected_default in EXPECTED_DEFAULT_VALUES.items():
        if f'  default: "{expected_default}"' not in blocks[question]:
            fail(f"copier.yml default changed for {question}: expected {expected_default}")


def require_update_boundaries(copier_yml: str) -> None:
    root_owned = (
        "/AGENTS.md",
        "/README.md",
        "/.gitignore",
        "/.codex/config.toml",
        "/.codex/hooks.json",
        "/.codex/agents/*.toml",
        "/docs/agent/**",
        "/docs/plan/**",
    )
    for pattern in root_owned:
        if f'  - "{pattern}"' not in copier_yml:
            fail(f"copier.yml must root-anchor project-owned path: {pattern}")

    migration_markers = (
        "_migrations:",
        "version: v1.0.0",
        "scripts/migrate-to-namespaced-layout.py",
        "version: v1.1.1",
        "scripts/update_hook_wiring.py",
        "version: v1.2.2",
        "scripts/validate-copier-update.py",
        'when: "[[ _stage == \'before\' ]]"',
        'when: "[[ _stage == \'after\' ]]"',
    )
    for marker in migration_markers:
        if marker not in copier_yml:
            fail(f"copier.yml missing namespaced-layout migration marker: {marker}")


def require_context_compression_boundary() -> None:
    wrapper = read("template/.project-agent-workflow/scripts/context-compress.sh")
    required = (
        ".project-agent-workflow/docs/agent|",
        ".project-agent-workflow/docs/agent/*|",
    )
    for marker in required:
        if marker not in wrapper:
            fail(f"generated context compression is missing normative path refusal: {marker}")


def require_agent_profile_task() -> None:
    copier_yml = read("copier.yml")
    required = (
        "_tasks:",
        '"[[ _copier_python ]]"',
        '"[[ _copier_conf.src_path ]]/scripts/update_agent_model_profiles.py"',
    )
    for marker in required:
        if marker not in copier_yml:
            fail(f"copier.yml missing fixed agent-profile task marker: {marker}")


def require_copier_documentation_contract() -> None:
    command_docs = (
        "README.md",
        "template/README.md.jinja",
        "SKILL.md",
    )
    skill_copy_commands: list[str] = []
    for path in command_docs:
        for line in read(path).splitlines():
            command = line.strip()
            if command.startswith(("copier copy ", "copier update ")) and "--trust" not in command:
                fail(f"{path} documents an untrusted Copier command: {command}")
            if path == "SKILL.md" and command.startswith("copier copy "):
                skill_copy_commands.append(command)
                tokens = command.split()
                if "--defaults" in tokens and any(token in ("-f", "--force") for token in tokens):
                    fail(f"SKILL.md non-interactive Copier command uses overwrite forcing: {command}")

    skill_trusted_noninteractive = 0
    skill_trusted_default = 0
    for command in skill_copy_commands:
        tokens = command.split()
        if "--trust" not in tokens:
            fail(f"SKILL.md documented Copier command is untrusted: {command}")
        if "--defaults" in tokens:
            if "--trust" in tokens:
                skill_trusted_noninteractive += 1
        elif "--trust" in tokens:
            skill_trusted_default += 1

    if skill_trusted_default == 0:
        fail("SKILL.md must document a trusted Copier copy command without --defaults")
    if skill_trusted_noninteractive == 0:
        fail("SKILL.md must document a trusted Copier copy command with --defaults")

    required_markers = {
        "AGENTS.md": (
            "Treat non-destructive Copier evolution as a repository invariant",
            "unclassified tracked-file deletion",
        ),
        "CHANGELOG.md": (
            "## 未リリース",
            "## v1.1.2",
            "`model` と `model_reasoning_effort` だけを固定値へ正規化",
            "生成先が削除した `docs/plan/` の `.gitkeep` を通常の update で再生成しない",
        ),
        "template/.project-agent-workflow/AGENTS.md.jinja": (
            "project-owned product code, policy, configuration, plan history",
            "unclassified tracked-file deletion",
        ),
        "references/template-development.md": (
            "Require `--trust` for every documented copy and update command",
            "template-fixed `model` and `model_reasoning_effort` fields",
            "preserve instructions and every unrelated project-owned field",
        ),
        "template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md": (
            "## Non-Destructive Update Contract",
            "copier copy --trust",
            ".project-agent-workflow/scripts/update-from-copier.sh",
            "The `model` and `model_reasoning_effort` fields are the only exceptions.",
            "`--trust` authorizes the bundled task; it does not prove that the resulting diff is safe to commit.",
        ),
        "template/.project-agent-workflow/ownership.yaml": (
            "field_overrides:",
            "  - path: .codex/agents/*.toml",
            "    template_fixed:\n      - model\n      - model_reasoning_effort",
            "    project_owned_remainder: true",
        ),
    }
    for path, markers in required_markers.items():
        text = read(path)
        for marker in markers:
            if marker not in text:
                fail(f"{path} missing Copier documentation contract marker: {marker}")

    if "requires `--trust` only" in read("references/template-development.md"):
        fail("template development documentation still limits --trust to migrations")

    source_validator = ROOT / "scripts/validate-copier-update.py"
    generated_validator = ROOT / "template/.project-agent-workflow/scripts/validate-copier-update.py"
    if source_validator.read_bytes() != generated_validator.read_bytes():
        fail("source and generated Copier update validators must be byte-identical")

    wrapper = read("template/.project-agent-workflow/scripts/update-from-copier.sh")
    for marker in (
        '"$script_dir/../.."',
        "copier update --trust",
        "validate-copier-update.py --destination .",
        "--force|--force=*",
        "-*f*",
    ):
        if marker not in wrapper:
            fail(f"generated Copier update wrapper missing marker: {marker}")


def workflow_job(text: str, job_name: str) -> str:
    match = re.search(
        rf"^  {re.escape(job_name)}:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        fail(f"CI autofix workflow missing job: {job_name}")
    return match.group(0)


def require_markers(path: str, subject: str, text: str, markers: tuple[str, ...]) -> None:
    for marker in markers:
        if marker not in text:
            fail(f"{path} {subject} missing marker: {marker}")


def require_ci_autofix_boundaries(
    path: str,
    boundary_validation_command: str,
) -> None:
    text = read(path)
    required = (
        "ref: ${{ needs.prepare.outputs.head_sha }}",
        'git show "origin/${BASE_BRANCH}:.github/codex/prompts/ci-autofix.md" > "$RUNNER_TEMP/codex-ci-autofix-prompt.md"',
        'prompt-file: ${{ runner.temp }}/codex-ci-autofix-prompt.md',
        'output-file: ${{ runner.temp }}/codex-ci-autofix-output.md',
        'git diff --binary HEAD > "$RUNNER_TEMP/codex-ci-autofix.patch"',
        "git diff --check HEAD",
        boundary_validation_command,
        'path: ${{ runner.temp }}/codex-ci-autofix.patch',
        'path: ${{ runner.temp }}/codex-ci-autofix-output.md',
        'protected=$(git diff --name-only HEAD | grep -E \'^(\\.github/workflows/|\\.github/codex/|\\.env($|\\.)|.*production.*|.*deploy.*)\' || true)',
        'deleted_tests=$(git diff --diff-filter=D --name-only HEAD -- tests || true)',
        'git status --porcelain=v1 --untracked-files=all',
        'git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]',
        'echo "dependency setup changed tracked, staged, or non-ignored untracked paths" >&2',
        'let mode = "patch-only";',
    )
    require_markers(path, "workflow", text, required)

    prompt_guard = 'git diff --quiet "origin/${BASE_BRANCH}...HEAD" -- .github/codex/prompts/ci-autofix.md'
    require_markers(path, "workflow", text, (prompt_guard,))
    if text.index(prompt_guard) > text.index("- name: Run Codex"):
        fail(f"{path} must reject pull request prompt changes before Codex execution")

    if re.search(r"(?m)(^\s*max_attempts:\b|^\s*maxAttempts\b|max_attempts)", text):
        fail(f"{path} must not contain the obsolete commit-count max_attempts guard")
    for marker in ("direct-push", "validate-patch", "apply-patch", "patch-only-notice", "git push", "createComment", "git commit"):
        if marker in text:
            fail(f"{path} contains removed CI autofix write-path marker: {marker}")

    if re.search(r"(?m)^\s*permissions:\s+(?:write|write-all)\s*$", text):
        fail(f"{path} workflow permissions must not grant write-all or write")
    if re.search(r"(?m)^\s+[A-Za-z0-9_-]+:\s+write(?:-all)?\s*$", text):
        fail(f"{path} contains a job-level write permission")

    generate = workflow_job(text, "generate-fix")
    require_markers(
        path,
        "generate-fix job",
        generate,
        (
            "permissions:\n      actions: read\n      contents: read\n      pull-requests: read",
            prompt_guard,
        ),
    )
    if "contents: write" in generate:
        fail(f"{path} generate-fix job must not have branch write permission")


def require_ci_autofix_root_boundaries() -> None:
    require_ci_autofix_boundaries(
        ".github/workflows/codex-ci-autofix.yml",
        "python3 template/.project-agent-workflow/scripts/security-static-check.py --changed",
    )
    require_ci_autofix_boundaries(
        "template/.github/workflows/codex-ci-autofix.yml.jinja",
        "python3 .project-agent-workflow/scripts/security-static-check.py --changed",
    )


def require_generated_whitespace_range() -> None:
    path = "template/.github/workflows/project-agent-workflow.yml"
    text = read(path)
    required = (
        "BASE_SHA: ${{ github.event.pull_request.base.sha }}",
        "BEFORE_SHA: ${{ github.event.before }}",
        "EVENT_NAME: ${{ github.event_name }}",
        "HEAD_SHA: ${{ github.sha }}",
        "PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}",
        "REF_TYPE: ${{ github.ref_type }}",
        "if [ \"$EVENT_NAME\" = pull_request ]; then",
        'git diff --check "$BASE_SHA...$PR_HEAD_SHA"',
        '[ "$REF_TYPE" = tag ]',
        'git diff --check "$HEAD_SHA^..$HEAD_SHA"',
        '[ "$BEFORE_SHA" != 0000000000000000000000000000000000000000 ]',
        'git cat-file -e "$BEFORE_SHA^{commit}" 2>/dev/null',
        'git diff --check "$BEFORE_SHA..$HEAD_SHA"',
        "EMPTY_TREE=$(git hash-object -t tree /dev/null)",
        'git diff --check "$EMPTY_TREE" "$HEAD_SHA"',
    )
    require_markers(path, "whitespace range selection", text, required)
    if "run: git diff --check" in text:
        fail(f"{path} must not check only the clean worktree")


def require_namespaced_reference_paths() -> None:
    agents = read("AGENTS.md")
    japanese = read("docs/agent/SPEC_JAPANESE_TECH_WRITING.md")

    required_target = "template/.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md"
    forbidden_target = "template/docs/agent/SPEC_JAPANESE_TECH_WRITING.md"
    for path, text in (("AGENTS.md", agents), ("docs/agent/SPEC_JAPANESE_TECH_WRITING.md", japanese)):
        if required_target not in text:
            fail(f"{path} missing generated Japanese-writing sync target: {required_target}")
        if forbidden_target in text:
            fail(f"{path} still references removed generated-writing sync target: {forbidden_target}")

    skill = read("SKILL.md")
    if ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md" not in skill:
        fail("SKILL.md missing reusable external-services spec path: .project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md")
    if "`SPEC_EXTERNAL_SERVICES.md`" in skill:
        fail("SKILL.md still references stale external-services spec path: `SPEC_EXTERNAL_SERVICES.md`")

    planning = read("references/planning.md")
    planning_required = (
        "`.project-agent-workflow/scripts/create-plan.sh active <slug>`",
        "`.project-agent-workflow/scripts/create-plan.sh backlog <slug>`",
        "`.project-agent-workflow/scripts/promote-plan.sh docs/plan/backlog/NNN-slug.md`",
        "`.project-agent-workflow/scripts/complete-plan.sh docs/plan/active/NNN-slug.md`",
        "`.project-agent-workflow/scripts/finalize-active-plan.sh docs/plan/active/NNN-slug.md`",
        "`.project-agent-workflow/scripts/check-agent-completion.sh`",
        "`.project-agent-workflow/scripts/select-task-context.sh docs/plan/active/NNN-slug.md`",
        "`.project-agent-workflow/scripts/clean-handoffs.sh --dry-run`",
        "`.project-agent-workflow/scripts/lint-plan-docs.py`",
        "`.project-agent-workflow/scripts/lint-plan-docs.sh`",
        "`.project-agent-workflow/scripts/format-plan-docs.py`",
        "`.project-agent-workflow/scripts/format-plan-docs.sh --check`",
        "`.project-agent-workflow/scripts/search-plan-archive.py --text <term>`",
    )
    for marker in planning_required:
        if marker not in planning:
            fail(f"references/planning.md missing managed path marker: {marker}")

    planning_forbidden = (
        "`scripts/create-plan.sh active <slug>`",
        "`scripts/create-plan.sh backlog <slug>`",
        "`scripts/promote-plan.sh docs/plan/backlog/NNN-slug.md`",
        "`scripts/complete-plan.sh docs/plan/active/NNN-slug.md`",
        "`scripts/finalize-active-plan.sh docs/plan/active/NNN-slug.md`",
        "`scripts/check-agent-completion.sh`",
        "`scripts/select-task-context.sh docs/plan/active/NNN-slug.md`",
        "`scripts/clean-handoffs.sh --dry-run`",
        "`scripts/format-plan-docs.py --check`",
    )
    for marker in planning_forbidden:
        if marker in planning:
            fail(f"references/planning.md still contains stale managed path marker: {marker}")

    require_current_plan_manifest_reference(planning)

    validation = read("references/validation.md")
    validation_required = (
        "`.project-agent-workflow/scripts/validate-changes.py`: selects validation commands from staged or unstaged paths.",
        "`.project-agent-workflow/scripts/security-static-check.py`: scans common high-signal static risks.",
        "`.project-agent-workflow/scripts/skillspector-scan.sh`: optional NVIDIA SkillSpector wrapper for AI agent skill scans.",
        "`.project-agent-workflow/scripts/structure-map.py --check`: verifies basic agent workflow structure.",
        "`.project-agent-workflow/scripts/format-plan-docs.py --check`: verifies plan Markdown whitespace.",
    )
    for marker in validation_required:
        if marker not in validation:
            fail(f"references/validation.md missing managed path marker: {marker}")

    validation_forbidden = (
        "`scripts/validate-changes.py`: selects validation commands from staged or unstaged paths.",
        "`scripts/security-static-check.py`: scans common high-signal static risks.",
        "`scripts/skillspector-scan.sh`: optional NVIDIA SkillSpector wrapper for AI agent skill scans.",
        "`scripts/structure-map.py --check`: verifies basic agent workflow structure.",
        "`scripts/format-plan-docs.py --check`: verifies plan Markdown whitespace.",
    )
    for marker in validation_forbidden:
        if marker in validation:
            fail(f"references/validation.md still contains stale managed path marker: {marker}")


def require_current_plan_manifest_reference(planning: str) -> None:
    required_fields = (
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
    optional_fields = (
        "target_json",
        "acceptance_focus",
        "completion_deferred_reason",
        "primary_invariant",
        "integration_gates",
        "replan_source",
        "replan_contract",
        "successor_plans",
        "inherited_acceptance_digests",
        "replan_reason_codes",
    )
    legacy_fields = ("task_type", "target_files", "expected_output")
    try:
        manifest_reference, _ = planning.split("## Lifecycle Scripts", 1)
        required_section, optional_section = manifest_reference.split(
            "Optional fields for new active and backlog plans:", 1
        )
    except ValueError:
        fail("references/planning.md missing current active-plan manifest sections")
    for field in required_fields:
        if f"- `{field}`" not in required_section:
            fail(f"references/planning.md missing required active-plan field: {field}")
    for field in optional_fields:
        if f"- `{field}`" not in optional_section:
            fail(f"references/planning.md missing optional active-plan field: {field}")
    for field in legacy_fields:
        if f"- `{field}`" in manifest_reference:
            fail(f"references/planning.md recommends removed active-plan field: {field}")
        if f"`{field}`" not in optional_section:
            fail(f"references/planning.md missing legacy archive note for: {field}")


def require_browser_automation_contract() -> None:
    index = read("template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja")
    required_route = (
        "  browser_automation:",
        ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md",
        ".project-agent-workflow/docs/agent/SPEC_SECURITY.md",
        ".agents/skills/browser-ops/SKILL.md",
        ".project-agent-workflow/skills/browser-ops/references/browser-run-policy.md",
    )
    require_markers("template spec index", "browser route", index, required_route)

    bridge = read("template/.agents/skills/browser-ops/SKILL.md")
    if ".project-agent-workflow/skills/browser-ops/SKILL.md" not in bridge:
        fail("browser discovery bridge does not point at managed skill")
    skill = read("template/.project-agent-workflow/skills/browser-ops/SKILL.md")
    require_markers(
        "managed browser skill",
        "policy reads",
        skill,
        (
            "references/browser-run-policy.md",
            ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md",
            "docs/agent/external-services.yaml",
        ),
    )
    policy = read("template/.project-agent-workflow/skills/browser-ops/references/browser-run-policy.md")
    require_markers(
        "browser backend policy",
        "compatibility boundary",
        policy,
        (
            "https://blog.cloudflare.com/kitesurf/",
            "beta",
            "lower CPU and memory consumption",
            "configured_write_capable",
            "exact `write_authorization_rule` match",
            "current user authorization",
            "WebGL",
            "real TLS fingerprints",
            "ordinary HTTP retrieval",
            "Cloudflare Browser Run as one service",
            "distinct project-owned external-service record",
        ),
    )
    ownership = read("template/.project-agent-workflow/ownership.yaml")
    if "  - .agents/skills/browser-ops/SKILL.md" not in ownership:
        fail("browser discovery bridge is not reserved by Copier ownership")
    fixture = json.loads(read("tests/fixtures/browser-ops/scenarios.json"))
    requirements = fixture.get("requirements", [])
    scenarios = fixture.get("scenarios", [])
    if not any(item.get("critical") is True for item in requirements):
        fail("browser scenarios need a critical requirement")
    classes = {item.get("class") for item in scenarios}
    if not {"median", "edge", "holdout"}.issubset(classes):
        fail("browser scenarios need median, edge, and holdout cases")
    expected = {"authorized Kitesurf", "Chromium fallback", "ordinary HTTP retrieval", "documented unavailable fallback", "deny browser write"}
    if not expected.issubset({item.get("expected") for item in scenarios}):
        fail("browser scenarios do not cover backend, plain HTTP, fallback, and write denial")
    expected_conditions = {
        "kitesurf-pdf": {
            "needs_rendered_browser": True,
            "access": "read",
            "browser_run_authorized": True,
            "provider_available": True,
            "requires_chromium": False,
        },
        "chromium-webgl": {
            "needs_rendered_browser": True,
            "access": "read",
            "browser_run_authorized": True,
            "provider_available": True,
            "requires_chromium": True,
        },
        "plain-http": {"needs_rendered_browser": False},
        "provider-unavailable": {
            "needs_rendered_browser": True,
            "access": "read",
            "browser_run_authorized": True,
            "provider_available": False,
            "requires_chromium": False,
        },
        "unauthorized-submit": {
            "needs_rendered_browser": True,
            "access": "write",
            "browser_run_authorized": True,
            "provider_available": True,
            "operation_allowlisted": True,
            "exact_write_authorization_rule": True,
            "current_user_authorization": False,
            "requires_chromium": False,
        },
    }
    actual_conditions = {item.get("id"): item.get("conditions") for item in scenarios}
    if actual_conditions != expected_conditions:
        fail("browser scenarios have incorrect condition-to-route mappings")
    for scenario_id in ("kitesurf-pdf", "chromium-webgl"):
        request = next(item["request"] for item in scenarios if item.get("id") == scenario_id)
        if "configured Browser Run record" not in request:
            fail(f"{scenario_id} request lacks configured Browser Run authorization premise")


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--print-source-required":
        print("\n".join(SOURCE_REQUIRED))
        return 0
    if len(sys.argv) == 2 and sys.argv[1] == "--print-generated-required":
        print("\n".join(GENERATED_REQUIRED))
        return 0
    if len(sys.argv) == 2 and sys.argv[1] == "--print-source-shell":
        print("\n".join(SOURCE_SHELL_LINT))
        return 0
    if len(sys.argv) == 2 and sys.argv[1] == "--print-source-python":
        print("\n".join(SOURCE_PYTHON_COMPILE))
        return 0
    if len(sys.argv) == 3 and sys.argv[1] == "--print-expected-generated":
        print("\n".join(expected_generated_paths(parse_fixture(Path(sys.argv[2])))))
        return 0
    if len(sys.argv) > 1:
        fail(f"unknown arguments: {' '.join(sys.argv[1:])}")

    for rel in SOURCE_REQUIRED:
        if not (ROOT / rel).is_file():
            fail(f"missing required file: {rel}")

    copier_yml = read("copier.yml")
    for key in ("_subdirectory: template", "_templates_suffix: .jinja", "_answers_file: .copier-answers.yml"):
        if key not in copier_yml:
            fail(f"copier.yml missing {key}")
    for question in QUESTIONS:
        if not re.search(rf"^{re.escape(question)}:", copier_yml, re.MULTILINE):
            fail(f"copier.yml missing question: {question}")
    require_japanese_prompts(copier_yml)
    require_update_boundaries(copier_yml)
    require_context_compression_boundary()
    require_agent_profile_task()
    require_copier_documentation_contract()
    require_ci_autofix_root_boundaries()
    require_generated_whitespace_range()
    require_namespaced_reference_paths()
    require_browser_automation_contract()
    for question in REMOVED_LOCAL_WORKFLOW_QUESTIONS:
        if re.search(rf"^{re.escape(question)}:", copier_yml, re.MULTILINE):
            fail(f"copier.yml still prompts for local workflow question: {question}")
    for question in REMOVED_ACTIVATION_QUESTIONS:
        if re.search(rf"^{re.escape(question)}:", copier_yml, re.MULTILINE):
            fail(f"copier.yml still prompts for activation boolean: {question}")

    if (ROOT / "assets/templates").exists():
        fail("assets/templates must not exist; template/ is the source of truth")

    answers_template = read("template/[[ _copier_conf.answers_file ]].jinja")
    if "_copier_answers|to_nice_yaml" not in answers_template:
        fail("answers template must persist _copier_answers for future updates")

    require_sequential_worker()
    require_agent_model_profiles()
    require_fast_scoped_worker()
    require_evidence_synthesizer()
    require_referent_first_alignment()
    require_user_communication_alignment()
    require_sandboxed_plan_worker_alignment()
    require_hook_logging_parity()
    require_root_pre_tool_hardening()
    require_orchestration_policy_markers()
    require_template_manifest_complete()

    fixture_answers: list[dict[str, str]] = []
    for fixture in sorted((ROOT / "tests/fixtures").glob("*.answers.yml")):
        answers = parse_fixture(fixture)
        require_valid_answers(answers, str(fixture), complete=True)
        fixture_answers.append(answers)
        obsolete = REMOVED_LOCAL_WORKFLOW_QUESTIONS & set(answers)
        if obsolete:
            fail(f"{fixture} still contains removed local workflow answers: {sorted(obsolete)}")
        obsolete_activation = REMOVED_ACTIVATION_QUESTIONS & set(answers)
        if obsolete_activation:
            fail(f"{fixture} still contains removed activation answers: {sorted(obsolete_activation)}")

    pairwise_answers = parse_pairwise_fixture(PAIRWISE_FIXTURE)
    for index, answers in enumerate(pairwise_answers, start=1):
        require_valid_answers(answers, f"{PAIRWISE_FIXTURE} row {index}", complete=False)
    require_pairwise_coverage([*fixture_answers, *pairwise_answers])

    print("copier template static check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
