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
base=$(basename "$src")
dst="docs/plan/active/$base"
mkdir -p docs/plan/active
mv "$src" "$dst"

id=${base%%-*}
if grep -q "No active development items." docs/plan/plan.md; then
  cat >docs/plan/plan.md <<EOF
# Active Plan

id	path	status
$id	$dst	in_progress
EOF
else
  printf "%s\t%s\t%s\n" "$id" "$dst" "in_progress" >>docs/plan/plan.md
fi

echo "$dst"
