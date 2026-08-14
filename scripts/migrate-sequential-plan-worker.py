#!/usr/bin/env python3
"""Migrate the exact legacy sequential worker profile to the read-only contract."""

from __future__ import annotations

import argparse
import os
import stat
import sys
import tempfile
import tomllib
from pathlib import Path


LEGACY_PROFILE = '''name = "sequential_plan_worker"
description = "Bounded implementation worker for one assigned active plan with structured evidence and no descendant delegation."
model = "gpt-5.3-codex-spark"
model_reasoning_effort = "medium"
sandbox_mode = "workspace-write"

developer_instructions = """
Implement only the one active plan assigned by the parent.
Read the assigned plan and its required specs before editing.
Stay inside the explicit write scope; stop and report if the required change exceeds it.
Preserve unrelated user changes and do not weaken tests or validation.
Run every validation command required by the assigned plan.
Do not edit the assigned plan's status, ready_to_archive state, or archive location.
Do not process the next active plan.
Do not spawn descendant agents.
Do not commit changes.
Return changed paths, implementation summary, validation results, blockers, cross-plan impacts, and remaining risks.
"""
'''

READ_ONLY_PROFILE = '''name = "sequential_plan_worker"
description = "Read-only sequential plan worker contract for one assigned active plan; writable implementation must route through the sandboxed runner."
model = "gpt-5.3-codex-spark"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"

developer_instructions = """
Implement only the one active plan assigned by the parent.
Keep this profile read-only in the source repository.
For writable implementation, use `.project-agent-workflow/scripts/run-sandboxed-plan-worker.py run <plan>` to produce a candidate patch from an isolated clone, then have the parent review and apply it with `.project-agent-workflow/scripts/run-sandboxed-plan-worker.py apply <manifest>`.
Read the assigned plan and its required specs before deciding whether the runner inputs are valid.
Stay inside the explicit write scope; stop and report if the required change exceeds it.
Preserve unrelated user changes and do not weaken tests or validation.
Run every validation command required by the assigned plan after the parent applies an accepted candidate patch.
Do not edit the assigned plan's status, ready_to_archive state, or archive location.
Do not process the next active plan.
Do not spawn descendant agents.
Do not commit changes.
Return candidate patch paths, implementation summary, validation results, blockers, cross-plan impacts, and remaining risks.
"""
'''


class MigrationError(RuntimeError):
    """The existing worker profile cannot be migrated without losing project content."""


def replace_regular_file(path: Path, content: str) -> None:
    metadata = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(metadata.st_mode):
        raise MigrationError(f"sequential worker profile must be a regular file: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(stat.S_IMODE(metadata.st_mode))
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def migrate(destination: Path) -> str:
    path = destination.resolve() / ".codex/agents/sequential_plan_worker.toml"
    if path.is_symlink() or not path.is_file():
        raise MigrationError(f"missing regular sequential worker profile: {path}")
    try:
        current = path.read_text(encoding="utf-8")
        parsed = tomllib.loads(current)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise MigrationError(f"could not read a valid sequential worker profile: {exc}") from exc
    if parsed.get("name") != "sequential_plan_worker":
        raise MigrationError("sequential worker profile has an unexpected name")
    sandbox_mode = parsed.get("sandbox_mode")
    if sandbox_mode == "read-only":
        return "sequential worker profile is already read-only"
    if current != LEGACY_PROFILE:
        raise MigrationError(
            "customized workspace-write sequential worker profile requires manual review; "
            "the migration did not change it"
        )
    replace_regular_file(path, READ_ONLY_PROFILE)
    return "migrated the v1.2.1 sequential worker profile to the read-only contract"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        result = migrate(args.destination)
    except MigrationError as exc:
        print(f"sequential worker migration stopped: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
