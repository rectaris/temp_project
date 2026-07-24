#!/usr/bin/env python3
"""Parse repository or generated YAML files with a pinned YAML implementation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml


EXCLUDED_DIRECTORIES = {
    ".agent-artifacts",
    ".agent-logs",
    ".git",
    ".uv-cache",
    ".venv",
    "__pycache__",
    "node_modules",
}


def yaml_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in {".yml", ".yaml"}
        and not (set(path.relative_to(root).parts) & EXCLUDED_DIRECTORIES)
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    root = args.root.resolve()
    paths = yaml_files(root)
    if not paths:
        raise SystemExit(f"no YAML files found under {root}")
    for path in paths:
        try:
            with path.open(encoding="utf-8") as handle:
                yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            print(f"invalid YAML: {path}: {exc}", file=sys.stderr)
            return 1
    print(f"YAML parse passed: {len(paths)} files under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
