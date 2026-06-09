#!/bin/sh
set -eu

usage() {
  echo "Usage: $0 <active|backlog> <slug> [--summary <text>]" >&2
}

if [ "$#" -lt 2 ]; then
  usage
  exit 2
fi

kind=$1
slug=$2
shift 2
summary="Planned work."

case "$kind" in
  active|backlog) ;;
  *) usage; exit 2 ;;
esac

case "$slug" in
  *[!a-z0-9-]*|""|-*) echo "slug must use lowercase letters, numbers, and hyphens" >&2; exit 2 ;;
esac

while [ "$#" -gt 0 ]; do
  case "$1" in
    --summary)
      shift
      [ "$#" -gt 0 ] || { usage; exit 2; }
      summary=$1
      ;;
    *) usage; exit 2 ;;
  esac
  shift
done

case "$summary" in
  *"
"*) echo "summary must be a single line" >&2; exit 2 ;;
esac

id=$(python3 scripts/lint-plan-docs.py --next-id)
dir="docs/plan/$kind"
path="$dir/$id-$slug.md"
mkdir -p "$dir"

if [ -e "$path" ]; then
  echo "plan already exists: $path" >&2
  exit 1
fi

cat >"$path" <<EOF
# $summary

status: $kind
review_class: B
target_files:
  - TBD
required_specs:
  - docs/agent/SPEC_VALIDATION.md
  - docs/agent/SPEC_GIT_WORKFLOW.md
validation:
  - git diff --check
acceptance:
  - TBD

## Notes

EOF

if [ "$kind" = "active" ]; then
  if grep -q "No active development items." docs/plan/plan.md; then
    cat >docs/plan/plan.md <<EOF
# Active Plan

id	path	status
$id	$path	in_progress
EOF
  else
    printf "%s\t%s\t%s\n" "$id" "$path" "in_progress" >>docs/plan/plan.md
  fi
fi

echo "$path"
