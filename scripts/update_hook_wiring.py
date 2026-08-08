#!/usr/bin/env python3
"""Preserve project Hook configuration while ensuring managed Stop wiring."""

from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any


HOOKS_RELATIVE = Path(".codex/hooks.json")
MANAGED_STOP_COMMAND = (
    'python3 "$(git rev-parse --show-toplevel)/'
    '.project-agent-workflow/hooks/stop_review_gate.py"'
)
MANAGED_STOP_HOOK = {
    "type": "command",
    "command": MANAGED_STOP_COMMAND,
    "timeout": 30,
    "statusMessage": "Checking completion lifecycle",
}


def load_configuration(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read Hook configuration {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Hook configuration must be a JSON object: {path}")
    hooks = value.get("hooks")
    if not isinstance(hooks, dict):
        raise ValueError(f"Hook configuration must contain a hooks object: {path}")
    stop = hooks.get("Stop", [])
    if not isinstance(stop, list):
        raise ValueError(f"Hook configuration Stop entry must be a list: {path}")
    for group in stop:
        if not isinstance(group, dict) or not isinstance(group.get("hooks", []), list):
            raise ValueError(f"Hook configuration Stop groups must contain Hook lists: {path}")
    return value


def has_stop_gate(configuration: dict[str, Any]) -> bool:
    for group in configuration["hooks"].get("Stop", []):
        for hook in group.get("hooks", []):
            if not isinstance(hook, dict):
                continue
            command = hook.get("command")
            if isinstance(command, str) and "stop_review_gate.py" in command:
                return True
    return False


def write_configuration(path: Path, configuration: dict[str, Any]) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(configuration, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(mode)
    os.replace(temporary, path)


def ensure_managed_stop(destination: Path, check_only: bool = False) -> str:
    path = destination.resolve() / HOOKS_RELATIVE
    if not path.is_file():
        return "absent"
    configuration = load_configuration(path)
    if has_stop_gate(configuration):
        return "already_present"
    if check_only:
        return "would_add"
    configuration["hooks"].setdefault("Stop", []).append({"hooks": [MANAGED_STOP_HOOK]})
    write_configuration(path, configuration)
    return "added"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        status = ensure_managed_stop(args.destination, check_only=args.check)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({"path": HOOKS_RELATIVE.as_posix(), "status": status}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
