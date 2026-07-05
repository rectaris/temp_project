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
python3 scripts/lint-plan-docs.py >/dev/null

base=$(basename "$src")
id=${base%%-*}
year=$(date +%Y)
month=$(date +%m)
day=$(date +%d)
case "$day" in
  0[1-9]|1[0-5]) half=01-15 ;;
  *) half=16-31 ;;
esac
dst_dir="docs/plan/checked/$year/$month/$half"
dst="$dst_dir/$base"
mkdir -p "$dst_dir"
mv "$src" "$dst"

python3 scripts/lint-plan-docs.py --remove-active "$id"
python3 scripts/lint-plan-docs.py --append-checked "$id" "$dst"

echo "$dst"
