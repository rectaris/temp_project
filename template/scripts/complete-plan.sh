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
python3 scripts/lint-plan-docs.py

base=$(basename "$src")
id=${base%%-*}
dst="docs/plan/checked/$base"
mkdir -p docs/plan/checked
mv "$src" "$dst"

tmp=$(mktemp)
awk -v id="$id" 'BEGIN { FS=OFS="\t" } $1 != id { print }' docs/plan/plan.md >"$tmp"
mv "$tmp" docs/plan/plan.md
if ! grep -q '^[0-9][0-9][0-9]	' docs/plan/plan.md; then
  cat >docs/plan/plan.md <<'EOF'
# Active Plan

No active development items.
EOF
fi

if ! grep -q "^$id	" docs/plan/checked.md; then
  printf "%s\t%s\n" "$id" "$dst" >>docs/plan/checked.md
fi

echo "$dst"
