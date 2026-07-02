#!/usr/bin/env python3
"""Check root-level agent workflow policy for this template repository."""

from __future__ import annotations

import argparse
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
    ".codex/hooks/agent_log_event.py",
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
    "docs/agent/spec-index.yaml",
    "docs/agent/SPEC_AGENT_LOGGING.md",
    "docs/agent/SPEC_CONTEXT_COMPRESSION.md",
    "docs/agent/SPEC_DECISION_AUDIT.md",
    "docs/agent/SPEC_PLAN_WORKFLOW.md",
    "scripts/agent-log-event.py",
    "scripts/check-agent-log-manifest.py",
    "scripts/context-compress.sh",
]

REQUIRED_AGENT_RULES = [
    "docs/agent/spec-index.yaml",
    ".agent-logs/",
    ".agent-artifacts/",
    ".codex/hooks/agent_log_event.py",
    ".codex/skills/decision-audit",
    ".codex/skills/implementation-guidelines",
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
    check_active_plans()
    print("root agent policy check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
