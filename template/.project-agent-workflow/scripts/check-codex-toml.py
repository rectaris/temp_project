#!/usr/bin/env python3
"""Parse Codex TOML configuration files."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - compatibility for Python < 3.11.
    tomllib = None  # type: ignore[assignment]


def main() -> int:
    if tomllib is None:
        print("codex toml check skipped: Python tomllib is unavailable")
        return 0
    for path in sorted(Path(".codex").glob("**/*.toml")):
        tomllib.loads(path.read_text(encoding="utf-8"))
    print("codex toml ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
