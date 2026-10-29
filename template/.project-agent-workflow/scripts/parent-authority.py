#!/bin/sh
""":"
exec /usr/bin/python3 -I -S -B "$0" "$@"
":"""
"""Inspect or materialize accepted parent controls in either workflow layout."""

import importlib.util
from pathlib import Path
import sys


def main() -> int:
    base = Path(__file__).resolve().parent
    paths = (base / "project_workflow/parent_authority.py", base / "parent_authority.py")
    found = [path for path in paths if path.is_file() and not path.is_symlink()]
    if len(found) != 1:
        raise SystemExit("parent authority refused: missing or ambiguous distribution")
    spec = importlib.util.spec_from_file_location("parent_authority", found[0])
    if spec is None or spec.loader is None:
        raise SystemExit("parent authority refused: module loader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main()


if __name__ == "__main__":
    sys.exit(main())
