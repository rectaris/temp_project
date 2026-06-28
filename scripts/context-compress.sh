#!/bin/sh
set -eu

usage() {
  echo "Usage: $0 <input-file> [run-id]" >&2
}

fail() {
  echo "context-compress: $1" >&2
  exit 1
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

refuse_if_normative() {
  path=$1
  rel=${path#./}
  base=$(basename -- "$rel")

  case "$rel" in
    AGENTS.md|*/AGENTS.md|docs/agent|docs/agent/*|*/docs/agent|*/docs/agent/*)
      fail "refusing normative agent instruction input: $path"
      ;;
  esac

  case "$base" in
    *VALIDATION*|*SECURITY*|CODEX_CI_AUTOFIX.md|security-static-check.py|security_rules.py)
      fail "refusing validation or security policy input: $path"
      ;;
  esac
}

fallback_compress() {
  input=$1
  output=$2
  max_head=${CONTEXT_COMPRESS_HEAD_LINES:-220}
  max_tail=${CONTEXT_COMPRESS_TAIL_LINES:-120}
  line_count=$(wc -l <"$input" | tr -d ' ')

  {
    echo "# Context Compression Fallback"
    echo
    echo "- source: $input"
    echo "- backend: fallback"
    echo "- source_lines: $line_count"
    echo
    if [ "$line_count" -le $((max_head + max_tail)) ]; then
      sed -n '1,$p' "$input"
    else
      echo "## Head"
      echo
      sed -n "1,${max_head}p" "$input"
      echo
      echo "## Omitted"
      echo
      echo "$((line_count - max_head - max_tail)) lines omitted. Use search or targeted reads against the raw source for audit-critical details."
      echo
      echo "## Tail"
      echo
      start=$((line_count - max_tail + 1))
      sed -n "${start},\$p" "$input"
    fi
  } >"$output"
}

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  usage
  exit 2
fi

input=$1
run_id=${2:-${CONTEXT_COMPRESS_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}}

[ -f "$input" ] || fail "missing input file: $input"
refuse_if_normative "$input"

safe_name=$(printf '%s' "$(basename -- "$input")" | tr -c 'A-Za-z0-9._-' '_')
run_dir=".agent-logs/$run_id"
out_dir="$run_dir/compressed"
output="$out_dir/${safe_name}.compressed.md"
tmp="$output.tmp"
err="$output.headroom.err"
backend=fallback

mkdir -p "$out_dir"

if [ "${HEADROOM_DISABLED:-0}" != "1" ] && command -v headroom >/dev/null 2>&1; then
  if headroom "$input" >"$tmp" 2>"$err" && [ -s "$tmp" ]; then
    mv "$tmp" "$output"
    rm -f "$err"
    backend=headroom
  else
    rm -f "$tmp" "$err"
    fallback_compress "$input" "$output"
  fi
else
  fallback_compress "$input" "$output"
fi

if [ ! -f "$run_dir/redaction-report.md" ]; then
  {
    echo "# Redaction Report"
    echo
    echo "- created_by: scripts/context-compress.sh"
    echo "- source: $input"
    echo "- note: This wrapper does not redact source content. Review raw logs before sharing or committing summaries."
  } >"$run_dir/redaction-report.md"
fi

if [ ! -f "$run_dir/manifest.json" ]; then
  escaped_run_id=$(json_escape "$run_id")
  escaped_input=$(json_escape "$input")
  escaped_output=$(json_escape "$output")
  cat >"$run_dir/manifest.json" <<EOF
{
  "run_id": "$escaped_run_id",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "task": "context compression",
  "plans": [],
  "raw_logs": ["$escaped_input"],
  "artifacts": [],
  "compressed_outputs": ["$escaped_output"],
  "redaction_report": "redaction-report.md",
  "pinned": false
}
EOF
fi

echo "$output"
echo "backend=$backend" >&2
