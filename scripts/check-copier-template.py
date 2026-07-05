#!/usr/bin/env python3
"""Static checks for the Copier template without requiring Copier."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


SOURCE_REQUIRED = [
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
    "docs/agent/SPEC_SKILL_AUTHORING.md",
    "scripts/agent-log-event.py",
    "scripts/check-agent-log-manifest.py",
    "scripts/check-codex-toml.py",
    "scripts/check-root-agent-policy.py",
    "scripts/context-compress.sh",
    "scripts/import-codex-transcript.py",
    "scripts/plan_validation_commands.py",
    "scripts/sync-plan-to-linear.sh",
    "scripts/validate-changes.py",
    "template/AGENTS.md.jinja",
    "template/README.md.jinja",
    "template/.github/workflows/ci.yml",
    "template/.github/workflows/codex-ci-autofix.yml",
    "template/.github/codex/prompts/ci-autofix.md",
    "template/.gitignore.jinja",
    "template/.codex/config.toml.jinja",
    "template/.codex/hooks.json.jinja",
    "template/.codex/agents/change_reviewer.toml",
    "template/.codex/agents/docs_researcher.toml",
    "template/.codex/agents/repo_explorer.toml",
    "template/.codex/agents/scoped_worker.toml",
    "template/.codex/hooks/agent_log_event.py",
    "template/.codex/hooks/pre_tool_hardening_gate.py",
    "template/.codex/hooks/stop_review_gate.py",
    "template/.codex/skills/decision-audit/SKILL.md",
    "template/.codex/skills/decision-audit/agents/openai.yaml",
    "template/.codex/skills/graph-memory/SKILL.md",
    "template/.codex/skills/graph-memory/agents/openai.yaml",
    "template/.codex/skills/implementation-guidelines/SKILL.md",
    "template/.codex/skills/implementation-guidelines/agents/openai.yaml",
    "template/.codex/skills/linear-ops/SKILL.md",
    "template/.codex/skills/linear-ops/agents/openai.yaml",
    "template/.codex/skills/mcp-ops/SKILL.md",
    "template/.codex/skills/mcp-ops/agents/openai.yaml",
    "template/.codex/skills/plan-archive/SKILL.md",
    "template/.codex/skills/plan-archive/agents/openai.yaml",
    "template/[[ _copier_conf.answers_file ]].jinja",
    "template/docs/agent/spec-index.yaml.jinja",
    "template/docs/agent/CODEX_CI_AUTOFIX.md",
    "template/docs/agent/SPEC_DEVELOPMENT_FLOW.md.jinja",
    "template/docs/agent/SPEC_ENVIRONMENT.md",
    "template/docs/agent/SPEC_AGENT_LOGGING.md",
    "template/docs/agent/SPEC_COPIER_ADOPTION.md",
    "template/docs/agent/SPEC_CONTEXT_COMPRESSION.md",
    "template/docs/agent/SPEC_DECISION_AUDIT.md",
    "template/docs/agent/SPEC_ORCHESTRATION.md",
    "template/docs/agent/SPEC_VALIDATION.md.jinja",
    "template/docs/agent/SPEC_GIT_WORKFLOW.md",
    "template/docs/agent/SPEC_FILE_MANAGEMENT.md",
    "template/docs/agent/SPEC_JAPANESE_TECH_WRITING.md",
    "template/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja",
    "template/docs/agent/external-services.yaml.jinja",
    "template/docs/agent/SPEC_PLAN_WORKFLOW.md",
    "template/docs/agent/SPEC_SKILL_AUTHORING.md",
    "template/docs/agent/SPEC_UI_DESIGN.md",
    "template/docs/plan/README.md",
    "template/docs/plan/checked.md",
    "template/docs/plan/plan.md",
    "template/docs/plan/backlog/README.md",
    "template/docs/plan/handoffs/README.md",
    "template/docs/plan/sub-agents/custom-agents.md",
    "template/docs/plan/sub-agents/helper-prompts.md",
    "template/scripts/create-plan.sh",
    "template/scripts/next-plan-id.sh",
    "template/scripts/promote-plan.sh",
    "template/scripts/complete-plan.sh",
    "template/scripts/finalize-active-plan.sh",
    "template/scripts/check-agent-completion.sh",
    "template/scripts/check-agent-log-manifest.py",
    "template/scripts/check-codex-toml.py",
    "template/scripts/context-compress.sh",
    "template/scripts/import-codex-transcript.py",
    "template/scripts/lint-plan-docs.sh",
    "template/scripts/format-plan-docs.sh",
    "template/scripts/select-task-context.sh",
    "template/scripts/clean-handoffs.sh",
    "template/scripts/lint-plan-docs.py",
    "template/scripts/planlib.py",
    "template/scripts/plan_validation_commands.py",
    "template/scripts/format-plan-docs.py",
    "template/scripts/search-plan-archive.py",
    "template/scripts/validate-changes.py",
    "template/scripts/security_rules.py",
    "template/scripts/security-static-check.py",
    "template/scripts/skillspector-scan.sh",
    "template/scripts/structure-map.py",
    "template/scripts/sync-plan-to-linear.sh",
    "references/template-development.md",
    "tests/fixtures/typescript.answers.yml",
    "tests/fixtures/python.answers.yml",
    "tests/fixtures/docs.answers.yml",
    "tests/copier-update.sh",
    "tests/lib-copier.sh",
    "tests/smoke.sh",
    "tests/test-hooks.py",
    "scripts/init-project-workflow.sh",
]

GENERATED_REQUIRED = [
    ".copier-answers.yml",
    ".gitignore",
    ".codex/config.toml",
    ".codex/agents/change_reviewer.toml",
    ".codex/agents/docs_researcher.toml",
    ".codex/agents/repo_explorer.toml",
    ".codex/agents/scoped_worker.toml",
    ".codex/hooks/agent_log_event.py",
    ".codex/hooks/pre_tool_hardening_gate.py",
    ".codex/hooks/stop_review_gate.py",
    ".codex/skills/decision-audit/SKILL.md",
    ".codex/skills/decision-audit/agents/openai.yaml",
    ".codex/skills/graph-memory/SKILL.md",
    ".codex/skills/graph-memory/agents/openai.yaml",
    ".codex/skills/implementation-guidelines/SKILL.md",
    ".codex/skills/implementation-guidelines/agents/openai.yaml",
    ".codex/skills/linear-ops/SKILL.md",
    ".codex/skills/linear-ops/agents/openai.yaml",
    ".codex/skills/mcp-ops/SKILL.md",
    ".codex/skills/mcp-ops/agents/openai.yaml",
    ".codex/skills/plan-archive/SKILL.md",
    ".codex/skills/plan-archive/agents/openai.yaml",
    "AGENTS.md",
    "README.md",
    ".github/workflows/ci.yml",
    ".github/workflows/codex-ci-autofix.yml",
    ".github/codex/prompts/ci-autofix.md",
    "docs/agent/spec-index.yaml",
    "docs/agent/CODEX_CI_AUTOFIX.md",
    "docs/agent/SPEC_DEVELOPMENT_FLOW.md",
    "docs/agent/SPEC_ENVIRONMENT.md",
    "docs/agent/SPEC_AGENT_LOGGING.md",
    "docs/agent/SPEC_COPIER_ADOPTION.md",
    "docs/agent/SPEC_CONTEXT_COMPRESSION.md",
    "docs/agent/SPEC_DECISION_AUDIT.md",
    "docs/agent/SPEC_FILE_MANAGEMENT.md",
    "docs/agent/SPEC_EXTERNAL_SERVICES.md",
    "docs/agent/external-services.yaml",
    "docs/agent/SPEC_GIT_WORKFLOW.md",
    "docs/agent/SPEC_ORCHESTRATION.md",
    "docs/agent/SPEC_JAPANESE_TECH_WRITING.md",
    "docs/agent/SPEC_PLAN_WORKFLOW.md",
    "docs/agent/SPEC_SKILL_AUTHORING.md",
    "docs/agent/SPEC_UI_DESIGN.md",
    "docs/agent/SPEC_VALIDATION.md",
    "docs/plan/README.md",
    "docs/plan/backlog/README.md",
    "docs/plan/checked.md",
    "docs/plan/handoffs/README.md",
    "docs/plan/sub-agents/custom-agents.md",
    "docs/plan/sub-agents/helper-prompts.md",
    "docs/plan/plan.md",
    "scripts/check-agent-completion.sh",
    "scripts/check-agent-log-manifest.py",
    "scripts/check-codex-toml.py",
    "scripts/context-compress.sh",
    "scripts/import-codex-transcript.py",
    "scripts/complete-plan.sh",
    "scripts/workflow-status.sh",
    "scripts/create-plan.sh",
    "scripts/finalize-active-plan.sh",
    "scripts/format-plan-docs.py",
    "scripts/select-task-context.sh",
    "scripts/clean-handoffs.sh",
    "scripts/lint-plan-docs.sh",
    "scripts/format-plan-docs.sh",
    "scripts/lint-plan-docs.py",
    "scripts/next-plan-id.sh",
    "scripts/planlib.py",
    "scripts/plan_validation_commands.py",
    "scripts/promote-plan.sh",
    "scripts/search-plan-archive.py",
    "scripts/security_rules.py",
    "scripts/structure-map.py",
    "scripts/validate-changes.py",
    "scripts/security-static-check.py",
    "scripts/sync-plan-to-linear.sh",
]

SOURCE_SHELL_LINT = [path for path in SOURCE_REQUIRED if path.endswith(".sh")]
SOURCE_PYTHON_COMPILE = [path for path in SOURCE_REQUIRED if path.endswith(".py")]


QUESTIONS = {
    "project_name",
    "project_slug",
    "project_purpose",
    "primary_language",
    "codex_hooks_mode",
    "skillspector_mode",
    "mcp_policy_mode",
    "linear_sync_mode",
    "graph_memory_mode",
}

EXPECTED_CHOICE_VALUES = {
    "primary_language": {"typescript", "python", "mixed", "docs"},
    "codex_hooks_mode": {"disabled", "install_templates", "enable_local_logging"},
    "skillspector_mode": {"disabled", "document_optional"},
    "mcp_policy_mode": {"disabled", "document_optional"},
    "linear_sync_mode": {"disabled", "document_optional"},
    "graph_memory_mode": {"disabled", "document_optional"},
}

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


def parse_fixture(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            fail(f"fixture line is not key/value: {path}: {raw_line}")
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


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

    for fixture in sorted((ROOT / "tests/fixtures").glob("*.answers.yml")):
        answers = parse_fixture(fixture)
        missing = QUESTIONS - set(answers)
        if missing:
            fail(f"{fixture} missing answers: {sorted(missing)}")
        obsolete = REMOVED_LOCAL_WORKFLOW_QUESTIONS & set(answers)
        if obsolete:
            fail(f"{fixture} still contains removed local workflow answers: {sorted(obsolete)}")
        obsolete_activation = REMOVED_ACTIVATION_QUESTIONS & set(answers)
        if obsolete_activation:
            fail(f"{fixture} still contains removed activation answers: {sorted(obsolete_activation)}")

    print("copier template static check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
