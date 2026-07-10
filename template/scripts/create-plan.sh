#!/bin/sh
set -eu

usage() {
  echo "Usage: $0 <active|backlog> <slug> [--summary <text>] [--summary-ja <text>]" >&2
}

if [ "$#" -lt 2 ]; then
  usage
  exit 2
fi

kind=$1
slug=$2
shift 2
summary="Planned work."
summary_ja="作業計画を作成する。"

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
    --summary-ja)
      shift
      [ "$#" -gt 0 ] || { usage; exit 2; }
      summary_ja=$1
      ;;
    *) usage; exit 2 ;;
  esac
  shift
done

case "$summary" in
  *"
"*) echo "summary must be a single line" >&2; exit 2 ;;
esac
case "$summary_ja" in
  *"
"*) echo "summary-ja must be a single line" >&2; exit 2 ;;
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

status: $( [ "$kind" = "active" ] && echo in_progress || echo backlog )
task_type: tooling
review_class: B
human_design_required: no
human_approval_status: not_required
target_files:
  - TBD
target_json:
  - none
required_specs:
  - docs/agent/SPEC_VALIDATION.md
  - docs/agent/SPEC_GIT_WORKFLOW.md
validation:
  - git diff --check
acceptance:
  - TBD
acceptance_focus:
  - TBD
expected_output: full-implementation
checked_summary_ja: $summary_ja

## Problem

TBD

## Goal

TBD

## Implementation Instructions

Describe the executable steps for the next agent in English by default.

## Decisions

- TBD

## Tasks

- [ ] TBD

## Validation Notes

EOF

if [ "$kind" = "active" ]; then
  python3 scripts/lint-plan-docs.py --add-active "$id" "$path"
fi

echo "$path"
