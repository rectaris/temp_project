#!/bin/sh
set -eu

[ "$#" -eq 1 ] || { echo "Usage: $0 docs/plan/active/NNN-slug.md" >&2; exit 2; }
src=$1
case "$src" in docs/plan/active/[0-9][0-9][0-9]-*.md) ;; *) echo "expected active plan path" >&2; exit 2 ;; esac
[ -f "$src" ] || { echo "missing plan: $src" >&2; exit 1; }
status=$(awk -F': ' '$1 == "status" { print $2; exit }' "$src")
[ "$status" = "ready_to_archive" ] || { echo "cannot finalize $src: status is $status, expected ready_to_archive" >&2; exit 1; }
grep -q '^checked_summary_ja: .\+' "$src" || { echo "cannot finalize $src: missing non-empty checked_summary_ja" >&2; exit 1; }
awk '/^## Validation Notes$/{in_notes=1; next} /^## /{in_notes=0} in_notes && NF {found=1} END{exit(found ? 0 : 1)}' "$src" || { echo "cannot finalize $src: Validation Notes are empty" >&2; exit 1; }
base=$(basename "$src"); id=${base%%-*}
index_row=$(awk -F"	" -v id="$id" '$1 == id {print; found=1} END{if (!found) exit 1}' docs/plan/plan.md) || { echo "cannot finalize $src: missing active-plan index entry" >&2; exit 1; }
index_path=$(printf '%s\n' "$index_row" | awk -F"	" '{print $2}')
[ "$index_path" = "$src" ] || { echo "cannot finalize $src: active index points to $index_path" >&2; exit 1; }
year=$(date +%Y); month=$(date +%m); day=$(date +%d)
case "$day" in 0[1-9]|1[0-5]) half=01-15 ;; *) half=16-31 ;; esac
dst_dir="docs/plan/checked/$year/$month/$half"; dst="$dst_dir/$base"
[ ! -e "$dst" ] || { echo "archive already exists: $dst" >&2; exit 1; }
mkdir -p "$dst_dir"
mv "$src" "$dst"
python3 - <<'PY' "$id" "$dst"
from pathlib import Path
import sys
plan = Path("docs/plan/plan.md")
rows = [line for line in plan.read_text(encoding="utf-8").splitlines() if not line.startswith(sys.argv[1] + "\t")]
plan.write_text("\n".join(rows).rstrip() + "\n", encoding="utf-8")
checked = Path("docs/plan/checked.md")
with checked.open("a", encoding="utf-8") as handle:
    handle.write(f"{sys.argv[1]}\t{sys.argv[2]}\n")
PY
echo "$dst"
