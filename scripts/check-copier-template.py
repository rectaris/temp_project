#!/usr/bin/env python3
"""Static checks for the Copier template without requiring Copier."""

from __future__ import annotations

import re
import subprocess
import sys
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
    "scripts/referent-contract.py",
    "scripts/sync-plan-to-linear.sh",
    "scripts/validate-changes.py",
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
    "template/.project-agent-workflow/scripts/plan_validation_commands.py",
    "template/.project-agent-workflow/scripts/referent-contract.py",
    "template/.project-agent-workflow/scripts/format-plan-docs.py",
    "template/.project-agent-workflow/scripts/search-plan-archive.py",
    "template/.project-agent-workflow/scripts/validate-changes.py",
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
    "tests/test-validation-tools.py",
    "tests/fixtures/referent-contract/scenarios.json",
    "tests/fixtures/referent-contract/evaluation-protocol.md",
    "tests/fixtures/write-for-reader/scenarios.json",
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
    ".project-agent-workflow/scripts/plan_validation_commands.py",
    ".project-agent-workflow/scripts/referent-contract.py",
    ".project-agent-workflow/scripts/promote-plan.sh",
    ".project-agent-workflow/scripts/search-plan-archive.py",
    ".project-agent-workflow/scripts/security_rules.py",
    ".project-agent-workflow/scripts/structure-map.py",
    ".project-agent-workflow/scripts/validate-changes.py",
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
    "mcp_policy_mode": {"disabled", "document_optional"},
    "linear_sync_mode": {"disabled", "document_optional"},
    "graph_memory_mode": {"disabled", "document_optional"},
    "ci_autofix_mode": {"disabled", "patch_only", "direct_push"},
}

EXPECTED_DEFAULT_VALUES = {
    "human_report_mode": "agent_select_local",
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
        'sandbox_mode = "workspace-write"',
        "Do not process the next active plan",
        "Do not spawn descendant agents",
        "Do not edit the assigned plan's status",
        "Do not commit changes",
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
    )
    for path in command_docs:
        for line in read(path).splitlines():
            command = line.strip()
            if command.startswith(("copier copy ", "copier update ")) and "--trust" not in command:
                fail(f"{path} documents an untrusted Copier command: {command}")

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
            "copier update --trust",
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


def require_ci_autofix_root_boundaries() -> None:
    text = read(".github/workflows/codex-ci-autofix.yml")
    required = (
        "ref: ${{ needs.prepare.outputs.head_sha }}",
        'cp .github/codex/prompts/ci-autofix.md "$RUNNER_TEMP/codex-ci-autofix-prompt.md"',
        'prompt-file: ${{ runner.temp }}/codex-ci-autofix-prompt.md',
        'output-file: ${{ runner.temp }}/codex-ci-autofix-output.md',
        'git diff --binary HEAD > "$RUNNER_TEMP/codex-ci-autofix.patch"',
        "git diff --check HEAD",
        "python3 template/.project-agent-workflow/scripts/security-static-check.py --changed",
        'path: ${{ runner.temp }}/codex-ci-autofix.patch',
        'path: ${{ runner.temp }}/codex-ci-autofix-output.md',
        'git apply --index "$RUNNER_TEMP/codex-ci-autofix.patch"',
        'protected=$(git diff --name-only HEAD | grep -E \'^(\\.github/workflows/|\\.github/codex/|\\.env($|\\.)|.*production.*|.*deploy.*)\' || true)',
        'deleted_tests=$(git diff --diff-filter=D --name-only HEAD -- tests || true)',
    )
    for marker in required:
        if marker not in text:
            fail(f"root CI autofix workflow must include boundary guard marker: {marker}")


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
