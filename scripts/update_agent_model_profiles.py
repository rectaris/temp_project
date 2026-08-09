#!/usr/bin/env python3
"""Enforce fixed model fields while preserving project-owned agent instructions."""

from __future__ import annotations

import argparse
import os
import re
import stat
import tempfile
import tomllib
from pathlib import Path


PROFILES = {
    "change_reviewer": ("gpt-5.6-sol", "high"),
    "docs_researcher": ("gpt-5.6-luna", "medium"),
    "evidence_synthesizer": ("gpt-5.6-luna", "xhigh"),
    "fast_scoped_worker": ("gpt-5.3-codex-spark", "medium"),
    "repo_explorer": ("gpt-5.6-luna", "low"),
    "scoped_worker": ("gpt-5.6-terra", "medium"),
    "sequential_plan_worker": ("gpt-5.3-codex-spark", "medium"),
}

FIELD_PATTERNS = {
    "model": re.compile(r'^model\s*=.*$'),
    "model_reasoning_effort": re.compile(r'^model_reasoning_effort\s*=.*$'),
}


class ProfileError(RuntimeError):
    """Raised when an agent profile cannot be normalized safely."""


def render_profile(text: str, model: str, effort: str) -> str:
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"invalid agent TOML: {exc}") from exc

    if not isinstance(parsed.get("name"), str):
        raise ProfileError("agent TOML is missing a string name")

    lines = text.splitlines()
    expected = {"model": model, "model_reasoning_effort": effort}
    missing: list[tuple[str, str]] = []
    for field, value in expected.items():
        matches = [index for index, line in enumerate(lines) if FIELD_PATTERNS[field].fullmatch(line)]
        if len(matches) > 1:
            raise ProfileError(f"agent TOML defines {field} more than once")
        replacement = f'{field} = "{value}"'
        if matches:
            lines[matches[0]] = replacement
        else:
            missing.append((field, replacement))

    if missing:
        insert_after = next(
            (index for index, line in enumerate(lines) if line.startswith("description = ")),
            next(index for index, line in enumerate(lines) if line.startswith("name = ")),
        )
        for _, replacement in reversed(missing):
            lines.insert(insert_after + 1, replacement)

    rendered = "\n".join(lines).rstrip() + "\n"
    normalized = tomllib.loads(rendered)
    for field, value in expected.items():
        if normalized.get(field) != value:
            raise ProfileError(f"agent TOML did not normalize {field}")
    return rendered


def write_atomic(path: Path, text: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def normalize_destination(destination: Path, *, check: bool = False) -> list[Path]:
    changed: list[Path] = []
    for name, (model, effort) in PROFILES.items():
        relative = Path(".codex/agents") / f"{name}.toml"
        path = destination / relative
        if path.is_symlink():
            raise ProfileError(f"refusing to replace symlinked agent profile: {relative}")
        if not path.is_file():
            raise ProfileError(f"missing built-in agent profile: {relative}")
        original = path.read_text(encoding="utf-8")
        rendered = render_profile(original, model, effort)
        if rendered == original:
            continue
        changed.append(relative)
        if not check:
            write_atomic(path, rendered)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=Path("."))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        changed = normalize_destination(args.destination.resolve(), check=args.check)
    except (OSError, ProfileError) as exc:
        raise SystemExit(str(exc)) from exc

    if args.check and changed:
        paths = "\n".join(f"- {path}" for path in changed)
        raise SystemExit(f"agent model profiles require normalization:\n{paths}")
    if changed:
        print("normalized fixed agent model profiles:")
        for path in changed:
            print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
