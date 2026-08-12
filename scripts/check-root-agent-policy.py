#!/usr/bin/env python3
"""Check root-level agent workflow policy for this template repository."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX_MARKER_RE = re.compile(r"^\s*(A|B|C|推奨|理由|Recommended|Reason)\s*[:：]")
APPROACH_MARKERS = {"A", "B", "C"}
RATIONALE_MARKERS = {"推奨", "理由", "Recommended", "Reason"}
MATRIX_WINDOW_LINES = 20

REQUIRED_ROOT_FILES = [
    ".codex/config.toml",
    ".codex/hooks.json",
    ".codex/agents/repo_explorer.toml",
    ".codex/agents/evidence_synthesizer.toml",
    ".codex/agents/fast_scoped_worker.toml",
    ".codex/hooks/agent_log_event.py",
    ".codex/hooks/semantic_guard_advisory.py",
    ".codex/hooks/stop_review_gate.py",
    ".project-agent-workflow/hooks/agent_log_event.py",
    ".project-agent-workflow/hooks/pre_tool_hardening_gate.py",
    ".project-agent-workflow/hooks/semantic_guard_advisory.py",
    ".project-agent-workflow/hooks/stop_review_gate.py",
    ".codex/skills/decision-audit/SKILL.md",
    ".codex/skills/decision-audit/agents/openai.yaml",
    ".codex/skills/graph-memory/SKILL.md",
    ".codex/skills/graph-memory/agents/openai.yaml",
    ".codex/skills/implementation-guidelines/SKILL.md",
    ".codex/skills/implementation-guidelines/agents/openai.yaml",
    ".codex/skills/define-referents-first/SKILL.md",
    ".codex/skills/define-referents-first/agents/openai.yaml",
    ".codex/skills/define-referents-first/references/workflow.md",
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
    ".codex/skills/browser-ops/SKILL.md",
    ".codex/skills/browser-ops/agents/openai.yaml",
    ".codex/skills/browser-ops/references/browser-run-policy.md",
    ".codex/agents/sequential_plan_worker.toml",
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
    "scripts/complete-plan.sh",
    "scripts/context-compress.sh",
    "scripts/plan_validation_commands.py",
    "scripts/referent-contract.py",
    "scripts/sync-plan-to-linear.sh",
    "scripts/validate-changes.py",
    "scripts/update_agent_model_profiles.py",
    "tests/root-plan-lifecycle.sh",
    "tests/test-agent-model-profiles.py",
    "tests/fixtures/write-for-reader/scenarios.json",
]

REUSABLE_SKILLS = (
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

REQUIRED_AGENT_RULES = [
    "docs/agent/spec-index.yaml",
    ".agent-logs/",
    ".agent-artifacts/",
    ".codex/hooks/agent_log_event.py",
    ".codex/skills/decision-audit",
    ".codex/skills/implementation-guidelines",
    ".codex/skills/define-referents-first",
    ".codex/skills/write-for-reader",
    "docs/agent/SPEC_REFERENT_FIRST.md",
    "docs/agent/SPEC_SKILL_AUTHORING.md",
    "docs/agent/SPEC_USER_COMMUNICATION.md",
    "*.backup",
    "decision audit",
    "docs/plan/active",
]


def fail(message: str) -> None:
    print(f"root agent policy check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def option_matrix_lines(text: str) -> list[tuple[int, str]]:
    markers: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = MATRIX_MARKER_RE.match(line)
        if match:
            markers.append((lineno, match.group(1)))
    return markers


def contains_option_matrix(text: str) -> bool:
    markers = option_matrix_lines(text)
    for index, (lineno, marker) in enumerate(markers):
        if marker not in APPROACH_MARKERS:
            continue
        window = [
            candidate
            for candidate_lineno, candidate in markers[index:]
            if candidate_lineno - lineno <= MATRIX_WINDOW_LINES
        ]
        approach_count = len({candidate for candidate in window if candidate in APPROACH_MARKERS})
        has_rationale = any(candidate in RATIONALE_MARKERS for candidate in window)
        if approach_count >= 2 and has_rationale:
            return True
    return False


def check_required_files() -> None:
    for rel in REQUIRED_ROOT_FILES:
        if not (ROOT / rel).is_file():
            fail(f"missing required root policy file: {rel}")


def check_gitignore() -> None:
    text = read(".gitignore")
    for pattern in (".agent-logs/", ".agent-artifacts/"):
        if pattern not in text:
            fail(f".gitignore missing {pattern}")


def check_agents_rules() -> None:
    text = read("AGENTS.md")
    for required in REQUIRED_AGENT_RULES:
        if required not in text:
            fail(f"AGENTS.md missing root policy reference: {required}")


def check_agent_model_profiles() -> None:
    contracts = {
        ".codex/agents/change_reviewer.toml": (
            "gpt-5.6-sol",
            "high",
            'name = "change_reviewer"',
        ),
        ".codex/agents/docs_researcher.toml": (
            "gpt-5.6-luna",
            "medium",
            'name = "docs_researcher"',
        ),
        ".codex/agents/evidence_synthesizer.toml": (
            "gpt-5.6-luna",
            "xhigh",
            'name = "evidence_synthesizer"',
            'sandbox_mode = "read-only"',
            "Do not edit files, execute external writes",
            "final high-risk judgment",
        ),
        ".codex/agents/fast_scoped_worker.toml": (
            "gpt-5.3-codex-spark",
            "medium",
            'name = "fast_scoped_worker"',
            "Require an explicit write scope and predetermined validation",
            "Do not commit, tag, push, release",
        ),
        ".codex/agents/repo_explorer.toml": (
            "gpt-5.6-luna",
            "low",
            'name = "repo_explorer"',
        ),
        ".codex/agents/scoped_worker.toml": (
            "gpt-5.6-terra",
            "medium",
            'name = "scoped_worker"',
            "Do not commit changes",
        ),
        ".codex/agents/sequential_plan_worker.toml": (
            "gpt-5.3-codex-spark",
            "medium",
            'name = "sequential_plan_worker"',
            "Do not process the next active plan",
            "Do not commit changes",
        ),
    }
    for relative, (model, effort, *role_markers) in contracts.items():
        text = read(relative)
        markers = (
            f'model = "{model}"',
            f'model_reasoning_effort = "{effort}"',
            *role_markers,
        )
        for marker in markers:
            if marker not in text:
                fail(f"{relative} missing fixed agent contract: {marker}")


def check_reusable_skill_parity() -> None:
    for skill in REUSABLE_SKILLS:
        for relative in ("SKILL.md", "agents/openai.yaml"):
            root_path = ROOT / ".codex" / "skills" / skill / relative
            template_path = ROOT / "template" / ".project-agent-workflow" / "skills" / skill / relative
            if not root_path.is_file() or not template_path.is_file():
                fail(f"missing reusable skill file for parity: {skill}/{relative}")
            template_text = (
                template_path.read_text(encoding="utf-8")
                .replace(".project-agent-workflow/", "")
                .replace(".agents/skills/", ".codex/skills/")
            )
            if root_path.read_text(encoding="utf-8") != template_text:
                fail(f"root/template reusable skill drift: {skill}/{relative}")


def check_browser_routing() -> None:
    index = read("docs/agent/spec-index.yaml")
    for marker in (
        "  browser_automation:",
        ".codex/skills/browser-ops/SKILL.md",
        ".codex/skills/browser-ops/references/browser-run-policy.md",
        "docs/agent/SPEC_SECURITY.md",
    ):
        if marker not in index:
            fail(f"root browser route missing: {marker}")
    skill = read(".codex/skills/browser-ops/SKILL.md")
    for marker in (
        "references/browser-run-policy.md",
        "template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja",
        "template/docs/agent/external-services.yaml.jinja",
    ):
        if marker not in skill:
            fail(f"root browser skill missing: {marker}")
    root_skill = skill.replace(
        "template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja",
        ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md",
    ).replace(
        "template/docs/agent/external-services.yaml.jinja",
        "docs/agent/external-services.yaml",
    )
    generated_skill = read("template/.project-agent-workflow/skills/browser-ops/SKILL.md")
    if root_skill != generated_skill:
        fail("root/template browser SKILL.md drift")

    root_reference = read(".codex/skills/browser-ops/references/browser-run-policy.md").replace(
        "template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja",
        ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md",
    ).replace(
        "template/docs/agent/external-services.yaml.jinja",
        "docs/agent/external-services.yaml",
    )
    generated_reference = read(
        "template/.project-agent-workflow/skills/browser-ops/references/browser-run-policy.md"
    )
    if root_reference != generated_reference:
        fail("root/template browser backend-reference drift")
    if read(".codex/skills/browser-ops/agents/openai.yaml") != read(
        "template/.project-agent-workflow/skills/browser-ops/agents/openai.yaml"
    ):
        fail("root/template browser agents/openai.yaml drift")

    ownership = read("template/.project-agent-workflow/ownership.yaml")
    if "  - .agents/skills/browser-ops/SKILL.md" not in ownership:
        fail("browser discovery bridge is not reserved by Copier ownership")


def check_user_communication_contract() -> None:
    root_spec = read("docs/agent/SPEC_USER_COMMUNICATION.md")
    template_spec = read("template/.project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md")
    if root_spec != template_spec:
        fail("root/template user-communication specifications differ")
    if root_spec.count("write-for-reader") != 1:
        fail("user-communication specification must name the operational skill exactly once")

    fixture_path = ROOT / "tests/fixtures/write-for-reader/scenarios.json"
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid write-for-reader scenario fixture: {exc}")
    requirements = fixture.get("requirements", [])
    scenarios = fixture.get("scenarios", [])
    if not requirements or not any(item.get("critical") is True for item in requirements):
        fail("write-for-reader scenarios need at least one critical requirement")
    classes = {item.get("class") for item in scenarios}
    if not {"median", "edge", "holdout"}.issubset(classes):
        fail("write-for-reader scenarios need median, edge, and holdout cases")
    if any(item.get("used_for_tuning") is not False for item in scenarios if item.get("class") == "holdout"):
        fail("write-for-reader holdout scenarios must remain outside tuning")


def check_namespaced_documentation_targets() -> None:
    required_target = "template/.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md"
    stale_target = "template/docs/agent/SPEC_JAPANESE_TECH_WRITING.md"
    for path in ("AGENTS.md", "docs/agent/SPEC_JAPANESE_TECH_WRITING.md"):
        text = read(path)
        if required_target not in text:
            fail(f"{path} missing generated documentation sync target: {required_target}")
        if stale_target in text:
            fail(f"{path} still references removed generated documentation sync target: {stale_target}")

    skill = read("SKILL.md")
    if ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md" not in skill:
        fail("SKILL.md missing reusable external-services spec path: .project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md")
    if "`SPEC_EXTERNAL_SERVICES.md`" in skill:
        fail("SKILL.md still references stale external-services spec path: `SPEC_EXTERNAL_SERVICES.md`")

    planning = read("references/planning.md")
    planning_required = (
        "`.project-agent-workflow/scripts/check-agent-completion.sh`",
        "`.project-agent-workflow/scripts/finalize-active-plan.sh docs/plan/active/NNN-slug.md`",
        "`.project-agent-workflow/scripts/search-plan-archive.py --text <term>`",
    )
    for marker in planning_required:
        if marker not in planning:
            fail(f"references/planning.md missing managed path marker: {marker}")

    require_current_plan_manifest_reference(planning)

    validation = read("references/validation.md")
    validation_required = (
        "`.project-agent-workflow/scripts/validate-changes.py`: selects validation commands from staged or unstaged paths.",
        "`.project-agent-workflow/scripts/security-static-check.py`: scans common high-signal static risks.",
        "`.project-agent-workflow/scripts/format-plan-docs.py --check`: verifies plan Markdown whitespace.",
    )
    for marker in validation_required:
        if marker not in validation:
            fail(f"references/validation.md missing managed path marker: {marker}")

    stale_validation = "`scripts/validate-changes.py`: selects validation commands from staged or unstaged paths."
    if stale_validation in validation:
        fail(f"references/validation.md still references stale managed path: {stale_validation}")


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
    optional_fields = ("target_json", "acceptance_focus", "completion_deferred_reason")
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


def check_orchestration_policy() -> None:
    policy = read("references/orchestration.md").lower()
    shared_markers = (
        "per-task user instruction",
        "without waiting for a per-task user instruction",
        "repository-wide",
        "independent helper work",
        "main agent owns",
        "multiple independent",
        "cross-specification",
        "validation, security, or orchestration",
        "large or dense",
        "proactively",
        "short deterministic",
        "cost",
        "external writes",
        "context files read-only",
        "advisory",
        "authorization decisions",
        "secrets",
        "destructive",
        "do not delegate",
        "separate explicit policy",
        "final high-risk",
        "final report",
        "role",
        "write scope",
    )
    for marker in shared_markers:
        if marker not in policy:
            fail(f"references/orchestration.md missing orchestration marker: {marker}")

    agents = read("AGENTS.md").lower()
    if "references/orchestration.md" not in agents:
        fail("AGENTS.md must reference references/orchestration.md")
    for marker in (
        "references/orchestration.md",
        "completion reporting",
        "final integration",
        "validation acceptance",
        "final ownership",
        "short deterministic commands",
        "external writes",
        "destructive",
        "authorization decisions",
        "per-task user instruction",
        "main session",
        "advisory",
    ):
        if marker not in agents:
            fail(f"AGENTS.md missing orchestration ownership marker: {marker}")

    try:
        fixture = json.loads((ROOT / "tests/fixtures/orchestration/proactive-bounded-subagents.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid orchestration fixture: {exc}")

    requirements = fixture.get("requirements", [])
    scenarios = fixture.get("scenarios", [])
    if not isinstance(requirements, list) or not isinstance(scenarios, list):
        fail("orchestration fixture must contain requirements and scenarios arrays")
    if not requirements or not any(item.get("critical") is True for item in requirements):
        fail("orchestration requirements need at least one critical requirement")
    for requirement in requirements:
        if not isinstance(requirement, dict) or requirement.get("id") is None:
            fail("orchestration requirements must each be an object with an id")
        if "threshold" not in requirement:
            fail(f"orchestration requirement missing threshold: {requirement.get('id')}")

    required_classes = {"median", "edge", "negative", "holdout"}
    observed = {item.get("class") for item in scenarios if isinstance(item, dict) and "class" in item}
    if not required_classes.issubset(observed):
        fail(f"orchestration fixture missing scenario classes: {sorted(required_classes - observed)}")

    for scenario in scenarios:
        if not isinstance(scenario, dict):
            fail("orchestration scenario must be an object")
        for key in ("id", "class", "task", "source", "expected"):
            if key not in scenario:
                fail(f"orchestration scenario missing {key}: {scenario}")
        if scenario.get("class") == "holdout" and scenario.get("used_for_tuning") is not False:
            fail("orchestration holdout scenario must set used_for_tuning=false")


def check_active_plans() -> None:
    active_dir = ROOT / "docs/plan/active"
    if not active_dir.exists():
        return
    for path in sorted(active_dir.glob("[0-9][0-9][0-9]-*.md")):
        if contains_option_matrix(path.read_text(encoding="utf-8")):
            fail(f"{path.relative_to(ROOT)} contains an option-analysis matrix")


def self_test() -> None:
    good = "review_class: B\n\n## Decisions\n\n1. Use final decisions only.\n"
    bad = """## Decision Audit

1. Storage location
   A: Store the full audit in the active plan.
   B: Store the full audit outside the active plan.

   推奨: B
   理由: Keep active plans executable.
"""
    if contains_option_matrix(good):
        fail("self-test rejected a compact final-decision plan")
    if not contains_option_matrix(bad):
        fail("self-test accepted an option-analysis matrix")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
    check_required_files()
    check_gitignore()
    check_agents_rules()
    check_agent_model_profiles()
    check_reusable_skill_parity()
    check_browser_routing()
    check_user_communication_contract()
    check_namespaced_documentation_targets()
    check_orchestration_policy()
    check_active_plans()
    print("root agent policy check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
