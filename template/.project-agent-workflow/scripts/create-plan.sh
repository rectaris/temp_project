#!/bin/sh
set -eu

usage() {
  echo "Usage: $0 <active|backlog> <slug> --purpose implementation" >&2
  echo "          --write-scope <path> [--write-scope <path>]..." >&2
  echo "          --feasibility <kind>:<evidence> [--feasibility ...]..." >&2
  echo "          --completion <text> --witness <command> [--completion ... --witness ...]..." >&2
  echo "          [--summary <text>] [--summary-ja <text>]" >&2
  echo "A numbered plan authorizes bounded implementation, so feasibility evidence" >&2
  echo "and plan-local completion witnesses are creation inputs, not later edits." >&2
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
purpose=""
write_scope_items=""
feasibility_items=""
completion_items=""
witness_items=""

append_item() {
  case "$2" in
    *"
"*) echo "$1 must be a single line" >&2; exit 2 ;;
    "") echo "$1 must not be empty" >&2; exit 2 ;;
  esac
}

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
    --purpose)
      shift
      [ "$#" -gt 0 ] || { usage; exit 2; }
      purpose=$1
      ;;
    --write-scope)
      shift
      [ "$#" -gt 0 ] || { usage; exit 2; }
      append_item "--write-scope" "$1"
      write_scope_items="$write_scope_items$1
"
      ;;
    --feasibility)
      shift
      [ "$#" -gt 0 ] || { usage; exit 2; }
      append_item "--feasibility" "$1"
      feasibility_items="$feasibility_items$1
"
      ;;
    --completion)
      shift
      [ "$#" -gt 0 ] || { usage; exit 2; }
      append_item "--completion" "$1"
      completion_items="$completion_items$1
"
      ;;
    --witness)
      shift
      [ "$#" -gt 0 ] || { usage; exit 2; }
      append_item "--witness" "$1"
      witness_items="$witness_items$1
"
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

if [ -z "$purpose" ] || [ -z "$write_scope_items" ] || [ -z "$feasibility_items" ] \
  || [ -z "$completion_items" ] || [ -z "$witness_items" ]; then
  usage
  exit 2
fi

admission=$(
  PLAN_ADMISSION_PURPOSE="$purpose" \
  PLAN_ADMISSION_WRITE_SCOPE="$write_scope_items" \
  PLAN_ADMISSION_FEASIBILITY="$feasibility_items" \
  PLAN_ADMISSION_COMPLETIONS="$completion_items" \
  PLAN_ADMISSION_WITNESSES="$witness_items" \
  python3 .project-agent-workflow/scripts/lint-plan-docs.py --render-admission
)

id=$(python3 .project-agent-workflow/scripts/lint-plan-docs.py --next-id)
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
task_types:
  - environment_data_flow
review_class: B
human_design_required: no
human_approval_status: not_required
$admission
context_files:
  - none
target_json:
  - none
required_specs:
  - docs/agent/PROJECT_POLICY.md
  - .project-agent-workflow/docs/agent/SPEC_VALIDATION.md
  - .project-agent-workflow/docs/agent/SPEC_GIT_WORKFLOW.md
  - .project-agent-workflow/docs/agent/SPEC_FILE_MANAGEMENT.md
  - .project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md
  - .project-agent-workflow/docs/agent/SPEC_HUMAN_REPORTING.md
  - .project-agent-workflow/docs/agent/SPEC_DEVELOPMENT_FLOW.md
  - .project-agent-workflow/docs/agent/SPEC_ENVIRONMENT.md
  - docs/agent/PROJECT_ENVIRONMENT.md
validation:
  - git diff --check
acceptance:
  - TBD
acceptance_focus:
  - TBD
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

if ! python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-admission "$path"; then
  rm -f "$path"
  exit 1
fi

if [ "$kind" = "active" ]; then
  python3 .project-agent-workflow/scripts/lint-plan-docs.py --add-active "$id" "$path"
fi

echo "$path"
