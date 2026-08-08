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
[ "$status" = "ready_to_archive" ] || {
  echo "cannot finalize $src: status is $status, expected ready_to_archive" >&2
  exit 1
}
python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-manifest "$src"
grep -q '^checked_summary_ja: .\+' "$src" || {
  echo "cannot finalize $src: missing non-empty checked_summary_ja" >&2
  exit 1
}
awk '/^## Validation Notes$/{in_notes=1; next} /^## /{in_notes=0} in_notes && NF {found=1} END{exit(found ? 0 : 1)}' "$src" || {
  echo "cannot finalize $src: Validation Notes are empty" >&2
  exit 1
}

base=$(basename "$src")
id=${base%%-*}
python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-active-mapping "$id" "$src" ready_to_archive

year=$(date +%Y); month=$(date +%m); day=$(date +%d)
case "$day" in 0[1-9]|1[0-5]) half=01-15 ;; *) half=16-31 ;; esac
dst_dir="docs/plan/checked/$year/$month/$half"
dst="$dst_dir/$base"
python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-archive-target "$id" "$dst"
mkdir -p "$dst_dir"
python3 .project-agent-workflow/scripts/lint-plan-docs.py --copy-status-exclusive "$src" "$dst" checked
rm "$src"
python3 .project-agent-workflow/scripts/lint-plan-docs.py --remove-active "$id"
python3 .project-agent-workflow/scripts/lint-plan-docs.py --append-checked "$id" "$dst"
echo "$dst"
