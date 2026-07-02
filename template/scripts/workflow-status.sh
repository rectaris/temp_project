#!/bin/sh
set -eu

if [ "${1:-}" = "--json" ]; then
  python3 - <<'PY'
from __future__ import annotations

import json
from pathlib import Path
import subprocess


def run(args: list[str]) -> list[str]:
    result = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


plan = Path("docs/plan/plan.md")
print(
    json.dumps(
        {
            "active_plan": plan.read_text(encoding="utf-8").splitlines() if plan.is_file() else None,
            "git_status": run(["git", "status", "--short"]),
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
)
PY
  exit 0
fi

echo "== Git =="
git status --short || true

echo
echo "== Active Plan =="
if [ -f docs/plan/plan.md ]; then
  sed -n '1,120p' docs/plan/plan.md
else
  echo "docs/plan/plan.md not found"
fi
