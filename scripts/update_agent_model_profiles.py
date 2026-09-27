#!/usr/bin/env python3
"""Enforce fixed model fields while preserving project-owned agent instructions."""

from __future__ import annotations

import argparse
import hashlib
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
    "fast_scoped_worker": ("gpt-5.6-terra", "medium"),
    "repo_explorer": ("gpt-5.6-luna", "low"),
    "scoped_worker": ("gpt-5.6-terra", "medium"),
    "sequential_plan_worker": ("gpt-5.6-terra", "medium"),
}

# A retired model is no longer a project choice: Codex no longer serves it, so a
# declared value is replaced in place by its successor. A declared reasoning
# effort stays as declared, and medium is supplied only when it is absent.
RETIRED_MODEL = "gpt-5.3-codex-spark"
RETIRED_MODEL_REPLACEMENT = ("gpt-5.6-terra", "medium")
RETIRED_MODEL_LINE = re.compile(
    r"^(?P<prefix>[ \t]*(?:model|\"model\"|'model')[ \t]*=[ \t]*)"
    r"(?P<quote>[\"'])gpt-5\.3-codex-spark(?P=quote)"
    r"(?P<suffix>[ \t]*(?:#.*)?)$"
)
# The exact v1.2.1 workspace-write sequential worker. Its v1.4.2 migration
# replaces the whole profile with the read-only contract only while these bytes
# are intact, so this task leaves that input for the migration.
LEGACY_SEQUENTIAL_WORKER_SHA256 = "744ed4f634e13ec1de27076dfa9f12411a8b01ff56ba27cfbc5151086fbe1ccb"

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
    raw_lines = text.splitlines(keepends=True)
    assignments = root_assignments(lines)
    retired = parsed.get("model") == RETIRED_MODEL
    if retired:
        effort = RETIRED_MODEL_REPLACEMENT[1]
    defaults = {"model": model, "model_reasoning_effort": effort}
    missing: list[tuple[str, str]] = []
    replaced: dict[str, str] = {}
    for field, value in defaults.items():
        matches = assignments[field]
        if len(matches) > 1:
            raise ProfileError(f"agent TOML defines {field} more than once")
        if matches:
            # The project owns a field it already declares. Filling only what is
            # absent keeps an update non-destructive; an existing value that
            # happens to equal an older seed is still the project's value. The
            # retired model below is the only declared value this task replaces.
            if not isinstance(parsed.get(field), str):
                raise ProfileError(f"agent TOML must declare {field} as a string")
        else:
            missing.append((field, value))

    if retired:
        if len(assignments["model"]) != 1:
            raise ProfileError("agent TOML declares the retired model outside a root model line")
        index = assignments["model"][0][0]
        match = RETIRED_MODEL_LINE.fullmatch(lines[index])
        if match is None:
            raise ProfileError("agent TOML declares the retired model in a form that cannot be replaced in place")
        replacement = RETIRED_MODEL_REPLACEMENT[0]
        quote = match.group("quote")
        raw_lines[index] = (
            f'{match.group("prefix")}{quote}{replacement}{quote}{match.group("suffix")}'
            f"{raw_lines[index][len(lines[index]):]}"
        )
        replaced["model"] = replacement

    if not missing and not replaced:
        return text

    if not missing:
        return verified_render(parsed, "".join(raw_lines), defaults, {}, replaced)

    description_anchor = next((index for index, _ in assignments["description"]), None)
    name_anchor = next((index for index, _ in assignments["name"]), None)
    insert_after = description_anchor if description_anchor is not None else name_anchor
    if insert_after is None:
        raise ProfileError("agent TOML is missing name or description anchor")

    anchor = "description" if description_anchor is not None else "name"
    insertion_indent = assignments[anchor][0][1]

    # Insertion works on the line list that still carries its own terminators,
    # so every byte outside the added assignments survives the render: the
    # file's newline style, its trailing whitespace, and its final blank lines.
    terminator = raw_lines[insert_after][len(lines[insert_after]):]
    if not terminator:
        terminator = "\r\n" if "\r\n" in text else "\n"
        raw_lines[insert_after] += terminator
    for field, value in reversed(missing):
        raw_lines.insert(insert_after + 1, f'{insertion_indent}{field} = "{value}"{terminator}')

    return verified_render(parsed, "".join(raw_lines), defaults, dict(missing), replaced)


def verified_render(
    parsed: dict[str, object],
    rendered: str,
    defaults: dict[str, str],
    inserted: dict[str, str],
    replaced: dict[str, str],
) -> str:
    try:
        normalized = tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"agent TOML did not remain valid TOML after normalization: {exc}") from exc
    for field in defaults:
        wanted = inserted.get(field, replaced.get(field, parsed.get(field)))
        if normalized.get(field) != wanted:
            raise ProfileError(f"agent TOML did not preserve {field}")
    remainder = {key: value for key, value in normalized.items() if key not in defaults}
    if remainder != {key: value for key, value in parsed.items() if key not in defaults}:
        raise ProfileError("agent TOML changed a field outside the fixed model fields")
    return rendered


def write_atomic(path: Path, text: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def normalize_destination(destination: Path, *, check: bool = False) -> list[Path]:
    # Every profile is rendered before any is written, so a refused profile
    # leaves the destination exactly as it was.
    pending: list[tuple[Path, Path, str]] = []
    for name, (model, effort) in PROFILES.items():
        relative = Path(".codex/agents") / f"{name}.toml"
        path = destination / relative
        # A symlinked profile is not the only way out of the destination: a
        # symlinked parent redirects every profile at once, so each component
        # between the destination and the file is checked before any read.
        for component in (*reversed(relative.parents[:-1]), relative):
            candidate = destination / component
            if candidate.is_symlink():
                raise ProfileError(f"refusing to follow symlinked agent path: {component}")
        if not path.is_file():
            raise ProfileError(f"missing built-in agent profile: {relative}")
        if path.resolve() != (destination.resolve() / relative):
            raise ProfileError(f"agent profile resolves outside the destination: {relative}")
        with path.open("r", encoding="utf-8", newline="") as handle:
            original = handle.read()
        if (
            name == "sequential_plan_worker"
            and hashlib.sha256(original.encode("utf-8")).hexdigest() == LEGACY_SEQUENTIAL_WORKER_SHA256
        ):
            continue
        try:
            rendered = render_profile(original, model, effort)
        except ProfileError as exc:
            raise ProfileError(f"{relative}: {exc}") from exc
        if rendered == original:
            continue
        pending.append((relative, path, rendered))
    if not check:
        for _relative, path, rendered in pending:
            write_atomic(path, rendered)
    return [relative for relative, _path, _rendered in pending]


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
