#!/usr/bin/env python3
"""migrate-legacy-template-files means the explicit post-update command that removes only digest-matching obsolete template files and reports modified files as conflicts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys


ANSWERS = Path(".copier-answers.yml")
LEGACY_SKILLSPECTOR = Path("scripts/skillspector-scan.sh")
LEGACY_SKILLSPECTOR_SHA256 = "a11271499deae5818c755bb7a88d20eb9d7e8883ecbb34e8fb5a4a327516f38b"
EXTERNAL_SERVICES = Path("docs/agent/external-services.yaml")


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


def migrate_external_services() -> bool:
    if not EXTERNAL_SERVICES.is_file():
        return True
    text = EXTERNAL_SERVICES.read_text(encoding="utf-8")
    if "credential_env:" not in text:
        return True

    def replace(match: re.Match[str]) -> str:
        indent, raw_value = match.groups()
        value = raw_value.strip().strip("\"'")
        authentication = "environment" if value else "none"
        reference = json.dumps(value)
        return f"{indent}authentication: {authentication}\n{indent}credential_reference: {reference}"

    migrated, count = re.subn(r'(?m)^(\s*)credential_env:\s*([^#\n]*)$', replace, text)
    if count == 0 or "credential_env:" in migrated:
        print(
            f"legacy template migration conflict: could not migrate {EXTERNAL_SERVICES}; "
            "manual review is required",
            file=sys.stderr,
        )
        return False
    EXTERNAL_SERVICES.write_text(migrated, encoding="utf-8")
    print(f"migrated legacy external-service credentials: {EXTERNAL_SERVICES}")
    return True


def main() -> int:
    try:
        success = migrate_external_services()
        success = migrate_skillspector() and success
        return 0 if success else 1
    except (OSError, ValueError) as exc:
        print(f"legacy template migration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
