#!/bin/sh
set -eu

group_state=
if [ "${1:-}" = "--group-state" ]; then
  [ "$#" -ge 2 ] || { echo "--group-state requires a path" >&2; exit 2; }
  group_state=$2
  shift 2
fi

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 [--group-state PATH] docs/plan/active/NNN-slug.md" >&2
  exit 2
fi

src=$1
case "$src" in
  docs/plan/active/[0-9][0-9][0-9]-*.md) ;;
  *) echo "expected active plan path" >&2; exit 2 ;;
esac
[ -f "$src" ] || { echo "missing plan: $src" >&2; exit 1; }

# An enrolled parallel execution group member is finalized through the grouped
# adapter, never through this legacy serial entrypoint.
[ -f .project-agent-workflow/scripts/parallel-plan-state.py ] || {
  echo "missing parallel plan group authority: .project-agent-workflow/scripts/parallel-plan-state.py" >&2
  exit 1
}
if [ -n "$group_state" ]; then
  python3 .project-agent-workflow/scripts/parallel-plan-state.py check-enrollment \
    --plan "$src" --operation finalization --group-state "$group_state" >/dev/null || exit 1
else
  python3 .project-agent-workflow/scripts/parallel-plan-state.py check-enrollment \
    --plan "$src" --operation finalization >/dev/null || exit 1
fi

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

# Local semantic records are advisory and remain parent-owned.
if [ -f .project-agent-workflow/scripts/referent-contract.py ]; then
  python3 .project-agent-workflow/scripts/referent-contract.py pending --target "$src" >&2 || :
fi

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
python3 - "$src" "$dst" <<'PY'
from pathlib import Path
import os
import sys
import tempfile

source, destination = sys.argv[1], sys.argv[2]
new_entry = f"- {destination}"


def rebind(text: str) -> str | None:
    lines = text.splitlines(keepends=True)
    field = None
    changed = False
    for index, raw in enumerate(lines):
        line = raw.rstrip()
        if line.startswith("## "):
            break
        if ":" in line and not line.startswith(" "):
            field = line.split(":", 1)[0].strip()
            continue
        stripped = raw.strip()
        if field != "context_files" or not stripped.startswith("- "):
            continue
        if stripped[2:].strip() != source:
            continue
        indent = raw[: len(raw) - len(raw.lstrip())]
        ending = raw[len(raw.rstrip("\r\n")):]
        lines[index] = f"{indent}{new_entry}{ending}"
        changed = True
    return "".join(lines) if changed else None


def live_plans() -> list[Path]:
    # Finalization already parsed the whole active index before its first
    # mutation, so these rows come from a validated document.
    plans = []
    index = Path("docs/plan/plan.md")
    if index.is_file():
        for row in index.read_text(encoding="utf-8").splitlines():
            columns = row.split("\t")
            if len(columns) == 3 and columns[1].startswith("docs/plan/active/"):
                plans.append(Path(columns[1]))
    backlog = Path("docs/plan/backlog")
    if backlog.is_dir():
        plans.extend(sorted(backlog.glob("**/[0-9][0-9][0-9]-*.md")))
    return plans


rewritten: list[tuple[Path, str]] = []
try:
    for plan in live_plans():
        if str(plan) == source or not plan.is_file():
            continue
        original = plan.read_text(encoding="utf-8")
        updated = rebind(original)
        if updated is None:
            continue
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{plan.name}.", suffix=".tmp", dir=plan.parent
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(updated)
        os.replace(temporary, plan)
        rewritten.append((plan, original))
except BaseException:
    for plan, original in rewritten:
        plan.write_text(original, encoding="utf-8")
    Path(destination).unlink(missing_ok=True)
    raise
PY
rm "$src"
python3 .project-agent-workflow/scripts/lint-plan-docs.py --remove-active "$id"
python3 .project-agent-workflow/scripts/lint-plan-docs.py --append-checked "$id" "$dst"
echo "$dst"
