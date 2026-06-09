#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 docs/plan/active/NNN-slug.md" >&2
  exit 2
fi

python3 - "$1" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path


path = Path(sys.argv[1])
if not path.is_file():
    print(f"missing plan: {path}", file=sys.stderr)
    raise SystemExit(1)

scalar_keys = {"task_type", "expected_output"}
list_keys = {"target_files", "target_json", "required_specs", "validation"}
values: dict[str, str | list[str]] = {key: [] for key in list_keys}
current: str | None = None

for raw in path.read_text(encoding="utf-8").splitlines():
    line = raw.rstrip()
    if line.startswith("## "):
        break
    if not line.strip():
        continue
    if ":" in line and not line.startswith(" "):
        key, rest = line.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        current = None
        if key in scalar_keys:
            values[key] = rest
        elif key in list_keys:
            current = key
            if rest:
                values[key].append(rest)  # type: ignore[union-attr]
        continue
    if current and line.lstrip().startswith("- "):
        values[current].append(line.lstrip()[2:].strip())  # type: ignore[union-attr]

required = ("task_type", "target_files", "required_specs", "validation", "expected_output")
for key in required:
    value = values.get(key)
    if value in (None, "", []):
        print(f"missing required manifest field: {key}", file=sys.stderr)
        raise SystemExit(1)

def joined(key: str) -> str:
    value = values.get(key, [])
    if isinstance(value, list):
        return " ".join(item for item in value if item != "none")
    return value

print(f"TASK_TYPE={joined('task_type')}")
print(f"REQUIRED_SPECS={joined('required_specs')}")
print(f"TARGET_FILES={joined('target_files')}")
print(f"TARGET_JSON={joined('target_json')}")
print(f"VALIDATION={joined('validation')}")
print(f"EXPECTED_OUTPUT={joined('expected_output')}")
PY
