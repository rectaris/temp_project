#!/usr/bin/env python3
"""Generic repository structure scanner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path.cwd()
REQUIRED = ["AGENTS.md", "docs/agent/spec-index.yaml", "docs/plan/plan.md"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts]
    report = {
        "files": len(files),
        "agent_specs": len(list((ROOT / "docs/agent").glob("SPEC_*.md"))) if (ROOT / "docs/agent").exists() else 0,
        "plan_files": len(list((ROOT / "docs/plan").rglob("*.md"))) if (ROOT / "docs/plan").exists() else 0,
        "missing": [path for path in REQUIRED if not (ROOT / path).is_file()],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.check and report["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
