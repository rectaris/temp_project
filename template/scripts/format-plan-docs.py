#!/usr/bin/env python3
"""Normalize whitespace for plan Markdown files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path.cwd()


def plan_files() -> list[Path]:
    base = ROOT / "docs/plan"
    if not base.exists():
        return []
    return sorted(path for path in base.rglob("*.md") if path.is_file())


def normalize(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed: list[str] = []
    for path in plan_files():
        original = path.read_text(encoding="utf-8")
        formatted = normalize(original)
        if original != formatted:
            changed.append(str(path.relative_to(ROOT)))
            if not args.check:
                path.write_text(formatted, encoding="utf-8")
    if changed and args.check:
        print("plan docs need formatting:", file=sys.stderr)
        for path in changed:
            print(f"- {path}", file=sys.stderr)
        return 1
    if changed:
        print("formatted plan docs")
    else:
        print("plan docs format passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
