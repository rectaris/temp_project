#!/usr/bin/env python3
"""Static checks for the Copier template without requiring Copier."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED = [
    ".github/workflows/ci.yml",
    "copier.yml",
    "template/AGENTS.md.jinja",
    "template/README.md.jinja",
    "template/.gitignore.jinja",
    "template/[[ _copier_conf.answers_file ]].jinja",
    "template/docs/agent/spec-index.yaml.jinja",
    "template/docs/agent/SPEC_VALIDATION.md.jinja",
    "template/docs/agent/SPEC_GIT_WORKFLOW.md",
    "template/docs/agent/SPEC_FILE_MANAGEMENT.md",
    "template/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja",
    "template/scripts/create-plan.sh",
    "template/scripts/next-plan-id.sh",
    "template/scripts/promote-plan.sh",
    "template/scripts/complete-plan.sh",
    "template/scripts/finalize-active-plan.sh",
    "template/scripts/check-agent-completion.sh",
    "template/scripts/lint-plan-docs.py",
    "template/scripts/format-plan-docs.py",
    "template/scripts/search-plan-archive.py",
    "template/scripts/validate-changes.py",
    "template/scripts/security-static-check.py",
    "template/scripts/structure-map.py",
    "references/template-development.md",
    "tests/fixtures/typescript.answers.yml",
    "tests/fixtures/python.answers.yml",
    "tests/fixtures/docs.answers.yml",
    "tests/copier-update.sh",
    "tests/smoke.sh",
    "tests/test-hooks.py",
]


QUESTIONS = {
    "project_name",
    "project_slug",
    "project_purpose",
    "primary_language",
    "planning_style",
    "use_codex_agents",
    "use_hooks",
    "max_agent_threads",
    "use_plan_lifecycle",
    "use_change_validation",
    "use_security_static",
    "use_structure_scanner",
    "use_mcp_policy",
    "use_linear_sync",
    "use_graph_memory",
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


def main() -> int:
    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            fail(f"missing required file: {rel}")

    copier_yml = read("copier.yml")
    for key in ("_subdirectory: template", "_templates_suffix: .jinja", "_answers_file: .copier-answers.yml"):
        if key not in copier_yml:
            fail(f"copier.yml missing {key}")
    for question in QUESTIONS:
        if not re.search(rf"^{re.escape(question)}:", copier_yml, re.MULTILINE):
            fail(f"copier.yml missing question: {question}")

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

    print("copier template static check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
