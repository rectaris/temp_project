#!/usr/bin/env python3
"""Reject the unsafe pre-v1 smart-diff migration before it changes a project."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path.cwd()


def before() -> None:
    if not (ROOT / ".git").exists():
        raise SystemExit("namespaced-layout migration requires a Git repository root")
    raise SystemExit(
        "direct copier update from a pre-v1 template is not supported because "
        "Copier smart diff can replay project customizations onto new bridge files; "
        "the destination was not changed. Use a checked-out template source and run "
        "scripts/adopt-to-namespaced-layout.py instead."
    )


def after() -> None:
    # The before stage always stops a pre-v1 update. Keep the after command as a
    # compatibility no-op for already parsed v1.0 migration metadata.
    print("namespaced-layout update guard completed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("before", "after"), required=True)
    args = parser.parse_args()
    before() if args.stage == "before" else after()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
