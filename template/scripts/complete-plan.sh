#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 docs/plan/active/NNN-slug.md" >&2
  exit 2
fi

src=$1
case "$src" in
  docs/plan/active/[0-9][0-9][0-9]-*.md) ;;
  *) echo "expected active plan path" >&2; exit 2 ;;
esac
[ -f "$src" ] || { echo "missing plan: $src" >&2; exit 1; }

status=$(awk -F': ' '$1 == "status" { print $2; exit }' "$src")
case "$status" in
  in_progress|deferred)
    sed "s/^status: .*/status: ready_to_archive/" "$src" >"$src.tmp"
    mv "$src.tmp" "$src"
    id=$(basename "$src"); id=${id%%-*}
    python3 scripts/lint-plan-docs.py --add-active "$id" "$src"
    awk -F"	" -v id="$id" 'BEGIN{OFS="	"} $1 == id {$3="ready_to_archive"} {print}' docs/plan/plan.md >docs/plan/plan.md.tmp
    mv docs/plan/plan.md.tmp docs/plan/plan.md
    echo "$src"
    ;;
  ready_to_archive)
    echo "plan is already ready_to_archive: $src" >&2
    exit 0
    ;;
  *)
    echo "cannot mark plan ready from status: $status" >&2
    exit 1
    ;;
esac
