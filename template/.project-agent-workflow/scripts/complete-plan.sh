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
id=$(basename "$src"); id=${id%%-*}
case "$status" in
  in_progress)
    python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-manifest "$src"
    python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-active-mapping "$id" "$src" "$status"
    if grep -Eq '^[[:space:]]*[-*+][[:space:]]+\[ \]' "$src"; then
      echo "cannot mark plan ready: unchecked tasks remain in $src" >&2
      exit 1
    fi
    awk '
      /^## Validation Notes$/ { in_notes=1; next }
      /^## / { in_notes=0 }
      in_notes {
        line=$0
        sub(/^[[:space:]]*([-*+]|[0-9]+[.)])[[:space:]]+/, "", line)
        sub(/^[[:space:]]+/, "", line)
        if (line != "" && tolower(line) !~ /^pending([ .:]|$)/) found=1
      }
      END { exit(found ? 0 : 1) }
    ' "$src" || {
      echo "cannot mark plan ready: Validation Notes are empty or pending in $src" >&2
      exit 1
    }
    python3 .project-agent-workflow/scripts/lint-plan-docs.py --complete-transition "$id" "$src" "$status"
    echo "$src"
    ;;
  deferred)
    echo "cannot mark deferred plan ready; return it to in_progress after its deferral condition is resolved: $src" >&2
    exit 1
    ;;
  ready_to_archive)
    python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-active-mapping "$id" "$src" ready_to_archive
    echo "plan is already ready_to_archive: $src" >&2
    exit 0
    ;;
  *)
    echo "cannot mark plan ready from status: $status" >&2
    exit 1
    ;;
esac
