#!/bin/sh
set -eu

# 0: completion evidence is present, 1: unchecked tasks remain,
# 2: Validation Notes are empty or pending.
completion_evidence() {
  if grep -Eq '^[[:space:]]*[-*+][[:space:]]+\[ \]' "$1"; then
    return 1
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
  ' "$1" || return 2
  return 0
}

check_only=0
group_state=
while [ "$#" -gt 0 ]; do
  case "${1:-}" in
    --check-completion-evidence) check_only=1; shift ;;
    --group-state)
      [ "$#" -ge 2 ] || { echo "--group-state requires a path" >&2; exit 2; }
      group_state=$2
      shift 2
      ;;
    *) break ;;
  esac
done

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 [--check-completion-evidence] [--group-state PATH] docs/plan/active/NNN-slug.md" >&2
  exit 2
fi

src=$1
case "$src" in
  docs/plan/active/[0-9][0-9][0-9]-*.md) ;;
  *) echo "expected active plan path" >&2; exit 2 ;;
esac
[ -f "$src" ] || { echo "missing plan: $src" >&2; exit 1; }

if [ "$check_only" -eq 1 ]; then
  completion_evidence "$src" || exit 1
  exit 0
fi

# An enrolled parallel execution group member is completed through the grouped
# adapter, never through this legacy serial entrypoint.
[ -f .project-agent-workflow/scripts/parallel-plan-state.py ] || {
  echo "missing parallel plan group authority: .project-agent-workflow/scripts/parallel-plan-state.py" >&2
  exit 1
}
if [ -n "$group_state" ]; then
  python3 .project-agent-workflow/scripts/parallel-plan-state.py check-enrollment \
    --plan "$src" --operation completion --group-state "$group_state" >/dev/null || exit 1
else
  python3 .project-agent-workflow/scripts/parallel-plan-state.py check-enrollment \
    --plan "$src" --operation completion >/dev/null || exit 1
fi

status=$(awk -F': ' '$1 == "status" { print $2; exit }' "$src")
id=$(basename "$src"); id=${id%%-*}
case "$status" in
  in_progress)
    python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-manifest "$src"
    python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-active-mapping "$id" "$src" "$status"
    evidence=0
    completion_evidence "$src" || evidence=$?
    case "$evidence" in
      0) ;;
      1)
        echo "cannot mark plan ready: unchecked tasks remain in $src" >&2
        exit 1
        ;;
      *)
        echo "cannot mark plan ready: Validation Notes are empty or pending in $src" >&2
        exit 1
        ;;
    esac
    # Local semantic records are advisory and remain parent-owned.
    if [ -f .project-agent-workflow/scripts/referent-contract.py ]; then
      python3 .project-agent-workflow/scripts/referent-contract.py pending --target "$src" >&2 || :
    fi

    python3 .project-agent-workflow/scripts/lint-plan-docs.py --complete-transition "$id" "$src" "$status"
    echo "$src"
    ;;
  deferred)
    echo "cannot mark deferred plan ready; return it to in_progress after its deferral condition is resolved: $src" >&2
    exit 1
    ;;
  replan_required)
    echo "cannot complete a plan that requires restructuring: $src" >&2
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
