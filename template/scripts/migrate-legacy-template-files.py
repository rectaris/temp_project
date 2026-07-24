#!/usr/bin/env python3
"""migrate-legacy-template-files means the explicit post-update command that removes only digest-matching obsolete template files and reports modified files as conflicts."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sys


ANSWERS = Path(".copier-answers.yml")
LEGACY_SKILLSPECTOR = Path("scripts/skillspector-scan.sh")
LEGACY_SKILLSPECTOR_SHA256 = "a11271499deae5818c755bb7a88d20eb9d7e8883ecbb34e8fb5a4a327516f38b"


def answer(name: str) -> str:
    try:
        text = ANSWERS.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read {ANSWERS}: {exc}") from exc
    match = re.search(rf"^{re.escape(name)}:\s*([^\s#]+)\s*$", text, re.MULTILINE)
    if match is None:
        raise ValueError(f"{ANSWERS} does not define {name}")
    return match.group(1).strip("\"'")


def migrate_skillspector() -> bool:
    if answer("skillspector_mode") != "disabled" or not LEGACY_SKILLSPECTOR.exists():
        return True
    try:
        digest = hashlib.sha256(LEGACY_SKILLSPECTOR.read_bytes()).hexdigest()
    except OSError as exc:
        print(f"legacy template migration conflict: cannot inspect {LEGACY_SKILLSPECTOR}: {exc}", file=sys.stderr)
        return False
    if digest != LEGACY_SKILLSPECTOR_SHA256:
        print(
            f"legacy template migration conflict: preserved modified {LEGACY_SKILLSPECTOR}; "
            "manual review is required",
            file=sys.stderr,
        )
        return False
    LEGACY_SKILLSPECTOR.unlink()
    print(f"removed obsolete template file: {LEGACY_SKILLSPECTOR}")
    return True


def main() -> int:
    try:
        return 0 if migrate_skillspector() else 1
    except (OSError, ValueError) as exc:
        print(f"legacy template migration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
