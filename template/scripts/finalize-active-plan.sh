#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 docs/plan/active/NNN-slug.md" >&2
  exit 2
fi

checked=$(scripts/complete-plan.sh "$1")
python3 scripts/lint-plan-docs.py
scripts/check-agent-completion.sh || {
  echo "Plan archived to $checked. Commit archive changes, then rerun completion gate." >&2
  exit 1
}
echo "$checked"
