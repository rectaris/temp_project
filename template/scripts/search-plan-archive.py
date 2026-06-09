#!/usr/bin/env python3
"""Search checked plan index and archives."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path.cwd()
CHECKED = ROOT / "docs/plan/checked.md"
ARCHIVE = ROOT / "docs/plan/checked"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    args = parser.parse_args()
    needle = args.text.lower()
    hits: list[str] = []
    if CHECKED.exists():
        for line in CHECKED.read_text(encoding="utf-8").splitlines():
            if needle in line.lower():
                hits.append(f"docs/plan/checked.md: {line}")
    if ARCHIVE.exists():
        for path in sorted(ARCHIVE.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if needle in text.lower():
                hits.append(str(path.relative_to(ROOT)))
    for hit in hits:
        print(hit)
    return 0 if hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
