#!/usr/bin/env python3
"""Search checked plan index and archives."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path.cwd()
CHECKED = ROOT / "docs/plan/checked.md"
ARCHIVE = ROOT / "docs/plan/checked"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--json", action="store_true", help="print machine-readable search results")
    args = parser.parse_args()
    needle = args.text.lower()
    hits: list[dict[str, str]] = []
    if CHECKED.exists():
        for line in CHECKED.read_text(encoding="utf-8").splitlines():
            if needle in line.lower():
                hits.append({"kind": "checked_index", "path": "docs/plan/checked.md", "line": line})
    if ARCHIVE.exists():
        for path in sorted(ARCHIVE.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            if needle in text.lower():
                hits.append({"kind": "checked_archive", "path": str(path.relative_to(ROOT))})
    if args.json:
        print(
            json.dumps(
                {"count": len(hits), "hits": hits, "query": args.text},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if hits else 1
    for hit in hits:
        if hit["kind"] == "checked_index":
            print(f"{hit['path']}: {hit['line']}")
        else:
            print(hit["path"])
    return 0 if hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
