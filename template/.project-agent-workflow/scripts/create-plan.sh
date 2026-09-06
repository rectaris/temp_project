#!/bin/sh
set -eu

authoring=.project-agent-workflow/scripts/plan_authoring.py
lint=.project-agent-workflow/scripts/lint-plan-docs.py

usage() {
  echo "Usage: $0 --check --input <authoring-input.json>" >&2
  echo "       $0 --input <authoring-input.json>" >&2
  echo "       $0 <active|backlog> <slug> --purpose implementation" >&2
  echo "          --write-scope <path> [--write-scope <path>]..." >&2
  echo "          --feasibility <kind>:<evidence> [--feasibility ...]..." >&2
  echo "          --completion <text> --witness <command> [--completion ... --witness ...]..." >&2
  echo "          [--summary <text>] [--summary-ja <text>]" >&2
  echo "A numbered plan authorizes bounded implementation, so feasibility evidence" >&2
  echo "and plan-local completion witnesses are creation inputs, not later edits." >&2
  echo "--check reports the requirement-to-scope-to-condition-to-witness correspondence" >&2
  echo "and writes nothing; the argument interface is converted to the same input." >&2
}

# One renderer serves both interfaces: the structured input is checked and then
# written from its exact bytes, and the argument interface is converted into the
# same checked representation before anything is rendered.
render_from_input() {
  render_input=$1
  render_interface=${2:-structured_input}
  render_digest=$(python3 "$authoring" check --profile generated --input "$render_input" \
    --authoring-interface "$render_interface" --print-digest)
  render_path=$(python3 "$authoring" write --profile generated --input "$render_input" \
    --authoring-interface "$render_interface" --expect-input-sha256 "$render_digest")
  if ! python3 "$lint" --check-admission "$render_path"; then
    rm -f "$render_path"
    case "$render_path" in
      docs/plan/active/*)
        python3 "$lint" --remove-active "$(basename "$render_path" | cut -c1-3)" || true
        ;;
    esac
    exit 1
  fi
  echo "$render_path"
}

if [ "$#" -lt 2 ]; then
  usage
  exit 2
fi

case "$1" in
  --check|--input)
    mode=write
    input=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --check) mode=check ;;
        --input)
          shift
          [ "$#" -gt 0 ] || { usage; exit 2; }
          input=$1
          ;;
        *) usage; exit 2 ;;
      esac
      shift
    done
    [ -n "$input" ] || { usage; exit 2; }
    if [ "$mode" = "check" ]; then
      exec python3 "$authoring" check --profile generated --input "$input"
    fi
    render_from_input "$input"
    exit 0
    ;;
esac

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

input=$(mktemp "${TMPDIR:-/tmp}/plan-authoring-input.XXXXXX")
trap 'rm -f "$input"' EXIT HUP INT TERM

PLAN_AUTHORING_LIFECYCLE="$kind" \
PLAN_AUTHORING_SLUG="$slug" \
PLAN_AUTHORING_SUMMARY="$summary" \
PLAN_AUTHORING_SUMMARY_JA="$summary_ja" \
PLAN_ADMISSION_PURPOSE="$purpose" \
PLAN_ADMISSION_WRITE_SCOPE="$write_scope_items" \
PLAN_ADMISSION_FEASIBILITY="$feasibility_items" \
PLAN_ADMISSION_COMPLETIONS="$completion_items" \
PLAN_ADMISSION_WITNESSES="$witness_items" \
  python3 "$authoring" legacy-input --profile generated --output "$input"

render_from_input "$input" legacy_arguments
