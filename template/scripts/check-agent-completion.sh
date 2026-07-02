#!/bin/sh
set -eu

if [ -f docs/plan/plan.md ] && grep -q '^[0-9][0-9][0-9]	' docs/plan/plan.md; then
  open=$(awk -F '\t' '/^[0-9][0-9][0-9]\t/ { print $2 }' docs/plan/plan.md)
  for plan in $open; do
    if [ -f "$plan" ] && grep -q '^completion_deferred_reason: .' "$plan"; then
      continue
    fi
    echo "open active plan blocks completion: $plan" >&2
    echo "Next: complete and archive the plan, or add completion_deferred_reason if work is intentionally deferred." >&2
    exit 1
  done
fi

if [ -n "$(git status --short)" ]; then
  echo "dirty worktree blocks completion report" >&2
  git status --short >&2
  echo "Next: inspect git status --short, then commit intended changes or remove unrelated generated files." >&2
  exit 1
fi

echo "agent completion gate passed"
