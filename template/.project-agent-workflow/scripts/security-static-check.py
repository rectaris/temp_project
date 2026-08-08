#!/usr/bin/env python3
"""Lightweight static security checks for generated repositories."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import security_rules


ROOT = Path.cwd()
SKIP_DIRS = {
    ".git",
    ".project-agent-workflow-migration",
    "node_modules",
    "dist",
    "coverage",
    ".venv",
    ".uv-cache",
    ".uv-tools",
    ".uv-home",
}
SKIP_FILES = {
    Path("scripts/security-static-check.py"),
    Path("scripts/security_rules.py"),
    Path(".project-agent-workflow/scripts/security-static-check.py"),
    Path(".project-agent-workflow/scripts/security_rules.py"),
}
TEXT_SUFFIXES = {".sh", ".py", ".js", ".mjs", ".ts", ".tsx", ".yml", ".yaml", ".toml", ".md", ".json"}
MANAGED_FILES = {
    Path(".agents/skills/decision-audit/SKILL.md"),
    Path(".agents/skills/define-referents-first/SKILL.md"),
    Path(".agents/skills/graph-memory/SKILL.md"),
    Path(".agents/skills/implementation-guidelines/SKILL.md"),
    Path(".agents/skills/linear-ops/SKILL.md"),
    Path(".agents/skills/mcp-ops/SKILL.md"),
    Path(".agents/skills/plan-archive/SKILL.md"),
    Path(".agents/skills/sequential-plan-orchestrator/SKILL.md"),
    Path(".agents/skills/write-for-reader/SKILL.md"),
    Path(".codex/hooks/agent_log_event.py"),
    Path(".codex/hooks/pre_tool_hardening_gate.py"),
    Path(".codex/hooks/semantic_guard_advisory.py"),
    Path(".codex/hooks/stop_review_gate.py"),
    Path(".github/codex/prompts/ci-autofix.md"),
    Path(".github/workflows/project-agent-workflow.yml"),
    Path(".github/workflows/codex-ci-autofix.yml"),
}
RULES = [
    (security_rules.PRIVATE_KEY_MATERIAL, "private key material"),
    (security_rules.REMOTE_SCRIPT_PIPE, "remote script piped to shell"),
    (security_rules.SUDO_COMMAND, "sudo command in repository script"),
    (re.compile(r"\bpull_request_target\b"), "pull_request_target workflow requires careful review"),
]


def git_paths(args: list[str]) -> list[Path]:
    result = subprocess.run(
        ["git", *args, "-z"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [Path(os.fsdecode(value)) for value in result.stdout.split(b"\0") if value]


def changed_paths() -> set[Path]:
    paths = set(git_paths(["diff", "--cached", "--name-only"]))
    paths.update(git_paths(["diff", "--name-only"]))
    paths.update(git_paths(["ls-files", "--others", "--exclude-standard"]))
    return paths


def is_managed(relative: Path) -> bool:
    return relative in MANAGED_FILES or relative.parts[:1] == (".project-agent-workflow",)


def iter_files(scope: str = "repository") -> list[Path]:
    out: list[Path] = []
    candidates = (ROOT / path for path in changed_paths()) if scope == "changed" else ROOT.rglob("*")
    for path in candidates:
        try:
            relative = path.relative_to(ROOT)
        except ValueError:
            continue
        if relative.is_absolute() or ".." in relative.parts:
            continue
        if not path.is_file() or path.is_symlink():
            continue
        if path.resolve() == Path(__file__).resolve() or relative in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if scope == "managed" and not is_managed(relative):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {"Dockerfile", "Makefile"}:
            out.append(path)
    return sorted(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--managed", action="store_true", help="scan Copier-managed workflow files")
    scope.add_argument("--changed", action="store_true", help="scan Git-visible changed files")
    args = parser.parse_args(argv)
    selected_scope = "managed" if args.managed else "changed" if args.changed else "repository"
    findings: list[str] = []
    for path in iter_files(selected_scope):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern, message in RULES:
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}: {message}")
    if findings:
        print("static security check failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1
    print("static security check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
