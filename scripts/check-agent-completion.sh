#!/bin/sh
set -eu

plans_only=0
if [ "${1:-}" = "--plans-only" ]; then plans_only=1; fi
blocked=0
if [ -f docs/plan/plan.md ]; then
  while IFS="	" read -r id plan status; do
    case "$id" in ''|id) continue ;; esac
    [ -f "$plan" ] || continue
    lifecycle=$(awk -F': ' '$1 == "status" { print $2; exit }' "$plan")
    [ "$lifecycle" = "ready_to_archive" ] || continue
    blocked=1
    echo "ready-to-archive plan blocks completion: $plan (status: $lifecycle)" >&2
    grep -q '^checked_summary_ja: .\+' "$plan" || echo "Missing evidence: checked_summary_ja" >&2
    awk '/^## Validation Notes$/{in_notes=1; next} /^## /{in_notes=0} in_notes && NF {found=1} END{exit(found ? 0 : 1)}' "$plan" || echo "Missing evidence: non-empty Validation Notes" >&2
    echo "Next: scripts/finalize-active-plan.sh $plan" >&2
  done < docs/plan/plan.md
fi
[ "$blocked" -eq 0 ] || exit 1

if [ "$plans_only" -eq 0 ] && [ -n "$(git status --short)" ]; then
  echo "dirty worktree blocks completion report" >&2
  git status --short >&2
  echo "Next: inspect git status --short, then commit intended changes or remove unrelated generated files." >&2
  exit 1
fi
echo "agent completion gate passed"
