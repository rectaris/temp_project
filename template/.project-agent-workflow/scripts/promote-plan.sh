#!/bin/sh
set -eu

# Every repository-changing lifecycle command runs in its own task worktree.
# The guard reports its own enforcement scope, so a repository that cannot
# carry a binding keeps its previous behavior instead of refusing every run.
require_task_worktree() {
  _top=$(git rev-parse --show-toplevel 2>/dev/null) || return 0
  for _candidate in \
    .project-agent-workflow/scripts/worktree_guard.py \
    scripts/project_workflow/worktree_guard.py; do
    if [ -f "$_top/$_candidate" ]; then
      if ! _refusal=$(cd "$_top" && python3 "$_candidate" require --action "$1" 2>&1); then
        echo "$_refusal" >&2
        exit 1
      fi
      return 0
    fi
  done
}
require_task_worktree "promoting this plan"

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 docs/plan/backlog/NNN-slug.md" >&2
  echo "       $0 docs/plan/shelved/NNN-slug.md" >&2
  exit 2
fi

src=$1
case "$src" in
  docs/plan/backlog/[0-9][0-9][0-9]-*.md) source_kind=backlog ;;
  docs/plan/shelved/[0-9][0-9][0-9]-*.md) source_kind=shelved ;;
  *) echo "expected backlog or shelved plan path" >&2; exit 2 ;;
esac

[ -f "$src" ] || { echo "missing plan: $src" >&2; exit 1; }
review_class=$(awk -F': ' '$1 == "review_class" { print $2; exit }' "$src")
approval=$(awk -F': ' '$1 == "human_approval_status" { print $2; exit }' "$src")
if [ "$review_class" = "C" ] && [ "$approval" != "approved" ]; then
  echo "class C plan requires human_approval_status: approved before promotion" >&2
  exit 1
fi
base=$(basename "$src")
dst="docs/plan/active/$base"
id=${base%%-*}
if [ "$source_kind" = "backlog" ]; then
  python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-admission "$src"
fi
python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-promotion "$id" "$src" "$dst"
mkdir -p docs/plan/active
python3 .project-agent-workflow/scripts/lint-plan-docs.py --copy-status-exclusive "$src" "$dst" in_progress
rm "$src"

python3 .project-agent-workflow/scripts/lint-plan-docs.py --add-active "$id" "$dst"

echo "$dst"
