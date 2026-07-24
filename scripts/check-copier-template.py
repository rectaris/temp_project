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
    "template/.github/workflows/ci.yml",
    "template/.github/workflows/codex-ci-autofix.yml.jinja",
    "template/.github/codex/prompts/ci-autofix.md",
    "template/.gitignore.jinja",
    "template/.codex/config.toml.jinja",
    "template/.codex/hooks.json.jinja",
    "template/.codex/agents/change_reviewer.toml",
    "template/.codex/agents/docs_researcher.toml",
    "template/.codex/agents/repo_explorer.toml",
    "template/.codex/agents/scoped_worker.toml",
    "template/.codex/agents/sequential_plan_worker.toml",
    "template/.codex/hooks/agent_log_event.py",
    "template/.codex/hooks/pre_tool_hardening_gate.py",
    "template/.codex/hooks/semantic_guard_advisory.py",
    "template/.codex/hooks/stop_review_gate.py",
    "template/.codex/skills/define-referents-first/SKILL.md",
    "template/.codex/skills/define-referents-first/agents/openai.yaml",
    "template/.codex/skills/define-referents-first/references/workflow.md",
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
    "template/.codex/skills/sequential-plan-orchestrator/SKILL.md",
    "template/.codex/skills/sequential-plan-orchestrator/agents/openai.yaml",
    "template/.codex/skills/write-for-reader/SKILL.md",
    "template/.codex/skills/write-for-reader/agents/openai.yaml",
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
    "template/docs/agent/SPEC_REFERENT_FIRST.md",
    "template/docs/agent/SPEC_SECURITY.md",
    "template/docs/agent/SPEC_SKILL_AUTHORING.md",
    "template/docs/agent/SPEC_UI_DESIGN.md",
    "template/docs/agent/SPEC_USER_COMMUNICATION.md",
    "template/docs/agent/PROJECT_ENVIRONMENT.md",
    "template/docs/agent/PROJECT_UI_DESIGN.md",
    "template/docs/plan/README.md",
    "template/docs/plan/checked.md",
    "template/docs/plan/plan.md",
    "template/docs/plan/backlog/README.md",
    "template/docs/plan/handoffs/README.md",
    "template/docs/plan/sub-agents/custom-agents.md",
    "template/docs/plan/sub-agents/helper-prompts.md",
    "template/docs/plan/active/.gitkeep",
    "template/docs/plan/backlog/.gitkeep",
    "template/docs/plan/checked/.gitkeep",
    "template/docs/plan/handoffs/.gitkeep",
    "template/scripts/create-plan.sh",
    "template/scripts/next-plan-id.sh",
    "template/scripts/promote-plan.sh",
    "template/scripts/complete-plan.sh",
    "template/scripts/check-agent-completion.sh",
    "template/scripts/finalize-active-plan.sh",
    "template/scripts/check-agent-log-manifest.py",
    "template/scripts/agent_log_manifest.py",
    "template/scripts/check-codex-toml.py",
    "template/scripts/check-external-service-policy.py",
    "template/scripts/context-compress.sh",
    "template/scripts/import-codex-transcript.py",
    "template/scripts/lint-plan-docs.sh",
    "template/scripts/format-plan-docs.sh",
    "template/scripts/select-task-context.sh",
    "template/scripts/clean-handoffs.sh",
    "template/scripts/lint-plan-docs.py",
    "template/scripts/migrate-legacy-template-files.py",
    "template/scripts/planlib.py",
    "template/scripts/plan_validation_commands.py",
    "template/scripts/referent-contract.py",
    "template/scripts/format-plan-docs.py",
    "template/scripts/search-plan-archive.py",
    "template/scripts/validate-changes.py",
    "template/scripts/security_rules.py",
    "template/scripts/security-static-check.py",
    "template/scripts/skillspector-scan.sh",
    "template/scripts/structure-map.py",
    "template/scripts/sync-plan-to-linear.sh",
    "template/scripts/workflow-status.sh",
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
    "tests/test-hooks.py",
    "tests/test-referent-contract.py",
    "tests/test-validation-tools.py",
    "tests/fixtures/referent-contract/scenarios.json",
    "tests/fixtures/referent-contract/evaluation-protocol.md",
    "tests/fixtures/write-for-reader/scenarios.json",
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
    ".codex/agents/sequential_plan_worker.toml",
    ".codex/hooks/agent_log_event.py",
    ".codex/hooks/pre_tool_hardening_gate.py",
    ".codex/hooks/semantic_guard_advisory.py",
    ".codex/hooks/stop_review_gate.py",
    ".codex/skills/define-referents-first/SKILL.md",
    ".codex/skills/define-referents-first/agents/openai.yaml",
    ".codex/skills/define-referents-first/references/workflow.md",
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
    ".codex/skills/sequential-plan-orchestrator/SKILL.md",
    ".codex/skills/sequential-plan-orchestrator/agents/openai.yaml",
    ".codex/skills/write-for-reader/SKILL.md",
    ".codex/skills/write-for-reader/agents/openai.yaml",
    "AGENTS.md",
    "README.md",
    ".github/workflows/ci.yml",
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
    "docs/agent/SPEC_REFERENT_FIRST.md",
    "docs/agent/SPEC_SECURITY.md",
    "docs/agent/SPEC_SKILL_AUTHORING.md",
    "docs/agent/SPEC_UI_DESIGN.md",
    "docs/agent/SPEC_USER_COMMUNICATION.md",
    "docs/agent/PROJECT_ENVIRONMENT.md",
    "docs/agent/PROJECT_UI_DESIGN.md",
    "docs/agent/SPEC_VALIDATION.md",
    "docs/plan/README.md",
    "docs/plan/backlog/README.md",
    "docs/plan/checked.md",
    "docs/plan/handoffs/README.md",
    "docs/plan/sub-agents/custom-agents.md",
    "docs/plan/sub-agents/helper-prompts.md",
    "docs/plan/plan.md",
    "docs/plan/active/.gitkeep",
    "docs/plan/backlog/.gitkeep",
    "docs/plan/checked/.gitkeep",
    "docs/plan/handoffs/.gitkeep",
    "scripts/check-agent-completion.sh",
    "scripts/finalize-active-plan.sh",
    "scripts/check-agent-log-manifest.py",
    "scripts/agent_log_manifest.py",
    "scripts/check-codex-toml.py",
    "scripts/check-external-service-policy.py",
    "scripts/context-compress.sh",
    "scripts/import-codex-transcript.py",
    "scripts/complete-plan.sh",
    "scripts/workflow-status.sh",
    "scripts/create-plan.sh",
    "scripts/format-plan-docs.py",
    "scripts/select-task-context.sh",
    "scripts/clean-handoffs.sh",
    "scripts/lint-plan-docs.sh",
    "scripts/format-plan-docs.sh",
    "scripts/lint-plan-docs.py",
    "scripts/migrate-legacy-template-files.py",
    "scripts/next-plan-id.sh",
    "scripts/planlib.py",
    "scripts/plan_validation_commands.py",
    "scripts/referent-contract.py",
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
    "ci_autofix_mode",
}

EXPECTED_CHOICE_VALUES = {
    "primary_language": {"typescript", "python", "mixed", "docs"},
    "codex_hooks_mode": {"disabled", "install_templates", "enable_local_logging"},
    "skillspector_mode": {"disabled", "document_optional"},
    "mcp_policy_mode": {"disabled", "document_optional"},
    "linear_sync_mode": {"disabled", "document_optional"},
    "graph_memory_mode": {"disabled", "document_optional"},
    "ci_autofix_mode": {"disabled", "patch_only", "direct_push"},
}

EXPECTED_DEFAULT_VALUES = {
    "ci_autofix_mode": "disabled",
}

CONDITIONAL_GENERATED = {
    ".codex/hooks.json": ("codex_hooks_mode", {"enable_local_logging"}),
    "scripts/skillspector-scan.sh": ("skillspector_mode", {"document_optional"}),
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


def require_sequential_worker() -> None:
    path = ROOT / "template/.codex/agents/sequential_plan_worker.toml"
    text = path.read_text(encoding="utf-8")
    required = (
        'name = "sequential_plan_worker"',
        'sandbox_mode = "workspace-write"',
        "Do not process the next active plan",
        "Do not spawn descendant agents",
        "Do not edit the assigned plan's status",
        "Do not commit changes",
    )
    for marker in required:
        if marker not in text:
            fail(f"sequential worker missing required contract: {marker}")
    if "gpt-5.3-codex-spark" in text:
        fail("sequential worker must not require an entitlement-specific preview model")


def template_source_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "template"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def require_template_manifest_complete() -> None:
    tracked = template_source_files()
    listed = {path for path in SOURCE_REQUIRED if path.startswith("template/")}
    missing = sorted(tracked - listed)
    stale = sorted(listed - tracked)
    if missing or stale:
        fail(f"template source manifest mismatch: missing={missing}, stale={stale}")


def require_referent_first_alignment() -> None:
    pairs = (
        ("docs/agent/SPEC_REFERENT_FIRST.md", "template/docs/agent/SPEC_REFERENT_FIRST.md"),
        (".codex/skills/define-referents-first/SKILL.md", "template/.codex/skills/define-referents-first/SKILL.md"),
        (
            ".codex/skills/define-referents-first/agents/openai.yaml",
            "template/.codex/skills/define-referents-first/agents/openai.yaml",
        ),
        (
            ".codex/skills/define-referents-first/references/workflow.md",
            "template/.codex/skills/define-referents-first/references/workflow.md",
        ),
        ("scripts/referent-contract.py", "template/scripts/referent-contract.py"),
        (".codex/hooks/semantic_guard_advisory.py", "template/.codex/hooks/semantic_guard_advisory.py"),
    )
    for root_path, template_path in pairs:
        if read(root_path) != read(template_path):
            fail(f"referent-first root/template files differ: {root_path} != {template_path}")


def require_user_communication_alignment() -> None:
    pairs = (
        ("docs/agent/SPEC_USER_COMMUNICATION.md", "template/docs/agent/SPEC_USER_COMMUNICATION.md"),
        (".codex/skills/write-for-reader/SKILL.md", "template/.codex/skills/write-for-reader/SKILL.md"),
        (
            ".codex/skills/write-for-reader/agents/openai.yaml",
            "template/.codex/skills/write-for-reader/agents/openai.yaml",
        ),
        (".codex/hooks/stop_review_gate.py", "template/.codex/hooks/stop_review_gate.py"),
    )
    for root_path, template_path in pairs:
        if read(root_path) != read(template_path):
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
