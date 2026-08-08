#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 docs/plan/backlog/NNN-slug.md" >&2
  exit 2
fi

src=$1
case "$src" in
  docs/plan/backlog/[0-9][0-9][0-9]-*.md) ;;
  *) echo "expected backlog plan path" >&2; exit 2 ;;
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
python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-promotion "$id" "$src" "$dst"
mkdir -p docs/plan/active
python3 .project-agent-workflow/scripts/lint-plan-docs.py --copy-status-exclusive "$src" "$dst" in_progress
rm "$src"

python3 .project-agent-workflow/scripts/lint-plan-docs.py --add-active "$id" "$dst"

echo "$dst"
