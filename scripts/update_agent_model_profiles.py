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

PROFILE_FIELDS = ("model", "model_reasoning_effort", "name", "description")
FIELD_PATTERNS = {
    field: re.compile(
        rf"^(?P<indent>[ \t]*)(?:{field}|\"{field}\"|'{field}')[ \t]*=.*$"
    )
    for field in PROFILE_FIELDS
}


class ProfileError(RuntimeError):
    """Raised when an agent profile cannot be normalized safely."""


def is_escaped(text: str, index: int) -> bool:
    """Return whether the character at index is preceded by an odd backslash run."""
    backslashes = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def scan_multiline_string(line: str, index: int, delimiter: str) -> int | None:
    """Return the position after a multiline string terminator, if present."""
    while (end := line.find(delimiter, index)) >= 0:
        if delimiter == "'''" or not is_escaped(line, end):
            return end + len(delimiter)
        index = end + 1
    return None


def multiline_delimiter(line: str) -> str | None:
    """Return an unclosed TOML multiline-string delimiter on one line, if any."""
    index = 0
    while index < len(line):
        character = line[index]
        if character == "#":
            break
        if line.startswith('\"\"\"', index) or line.startswith("'''", index):
            delimiter = line[index : index + 3]
            end = scan_multiline_string(line, index + 3, delimiter)
            if end is None:
                return delimiter
            index = end
            continue
        if character in {'\"', "'"}:
            quote = character
            index += 1
            while index < len(line):
                if line[index] == quote and (quote == "'" or not is_escaped(line, index)):
                    index += 1
                    break
                index += 1
            continue
        index += 1
    return None


def root_assignments(lines: list[str]) -> dict[str, list[tuple[int, str]]]:
    """Find root TOML assignments without interpreting strings as fields."""
    assignments = {field: [] for field in PROFILE_FIELDS}
    multiline: str | None = None
    in_root = True
    for index, line in enumerate(lines):
        if multiline is not None:
            if (end := scan_multiline_string(line, 0, multiline)) is not None:
                multiline = multiline_delimiter(line[end:])
            continue

        if line.lstrip().startswith("["):
            in_root = False
        if in_root:
            for field, pattern in FIELD_PATTERNS.items():
                if (match := pattern.fullmatch(line)) is not None:
                    assignments[field].append((index, match.group("indent")))
                    break
        multiline = multiline_delimiter(line)
    return assignments


def render_profile(text: str, model: str, effort: str) -> str:
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"invalid agent TOML: {exc}") from exc

    if not isinstance(parsed.get("name"), str):
        raise ProfileError("agent TOML is missing a string name")

    lines = text.splitlines()
    assignments = root_assignments(lines)
    expected = {"model": model, "model_reasoning_effort": effort}
    missing: list[tuple[str, str]] = []
    insertion_indent = ""
    for field, value in expected.items():
        matches = assignments[field]
        if len(matches) > 1:
            raise ProfileError(f"agent TOML defines {field} more than once")
        if matches:
            index, indent = matches[0]
            lines[index] = f'{indent}{field} = "{value}"'
            if not insertion_indent:
                insertion_indent = indent
        else:
            missing.append((field, value))

    if missing:
        description_anchor = next((index for index, _ in assignments["description"]), None)
        name_anchor = next((index for index, _ in assignments["name"]), None)
        insert_after = description_anchor if description_anchor is not None else name_anchor
        if insert_after is None:
            raise ProfileError("agent TOML is missing name or description anchor")

        anchor = "description" if description_anchor is not None else "name"
        insertion_indent = assignments[anchor][0][1]

        for field, value in reversed(missing):
            lines.insert(insert_after + 1, f'{insertion_indent}{field} = "{value}"')

    rendered = "\n".join(lines).rstrip() + "\n"
    try:
        normalized = tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"agent TOML did not remain valid TOML after normalization: {exc}") from exc
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
        try:
            rendered = render_profile(original, model, effort)
        except ProfileError as exc:
            raise ProfileError(f"{relative}: {exc}") from exc
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
