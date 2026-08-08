#!/usr/bin/env python3
"""Generic repository structure scanner."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path.cwd()
REQUIRED = ["AGENTS.md", ".project-agent-workflow/docs/agent/spec-index.yaml", "docs/plan/plan.md"]


def policy_errors() -> list[str]:
    errors: list[str] = []
    index = ROOT / ".project-agent-workflow/docs/agent/spec-index.yaml"
    if not index.is_file():
        return errors
    text = index.read_text(encoding="utf-8")
    if not text.startswith("version: 1\n"):
        errors.append(".project-agent-workflow/docs/agent/spec-index.yaml must start with version: 1")
    for key in ("name", "slug"):
        match = re.search(rf"^  {key}:\s*(.+)$", text, re.MULTILINE)
        if not match:
            errors.append(f".project-agent-workflow/docs/agent/spec-index.yaml missing project.{key}")
            continue
        try:
            value = json.loads(match.group(1))
        except json.JSONDecodeError:
            errors.append(f".project-agent-workflow/docs/agent/spec-index.yaml project.{key} must be a JSON-compatible quoted scalar")
            continue
        if not isinstance(value, str) or not value:
            errors.append(f".project-agent-workflow/docs/agent/spec-index.yaml project.{key} must be a non-empty string")
    referenced = sorted(
        set(re.findall(r"(?:\.project-agent-workflow/)?docs/agent/[A-Za-z0-9_.-]+", text))
    )
    for rel in referenced:
        if not (ROOT / rel).is_file():
            errors.append(f"spec-index references missing file: {rel}")
    hooks = ROOT / ".codex/hooks.json"
    if hooks.is_file():
        try:
            json.loads(hooks.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f".codex/hooks.json is invalid JSON: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts]
    report = {
        "files": len(files),
        "agent_specs": len(list((ROOT / ".project-agent-workflow/docs/agent").glob("SPEC_*.md"))),
        "plan_files": len(list((ROOT / "docs/plan").rglob("*.md"))) if (ROOT / "docs/plan").exists() else 0,
        "missing": [path for path in REQUIRED if not (ROOT / path).is_file()],
        "policy_errors": policy_errors(),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.check and (report["missing"] or report["policy_errors"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
