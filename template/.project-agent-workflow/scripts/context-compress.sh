#!/bin/sh
set -eu

usage() {
  echo "Usage: $0 <input-file> [run-id]" >&2
}

fail() {
  echo "context-compress: $1" >&2
  exit 1
}

refuse_if_normative() {
  path=$1
  rel=${path#./}
  base=$(basename -- "$rel")

  case "$rel" in
    AGENTS.md|*/AGENTS.md|docs/agent|docs/agent/*|.project-agent-workflow/docs/agent|.project-agent-workflow/docs/agent/*|docs/plan/active|docs/plan/active/*)
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
    echo "- source: $source_rel"
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

case "$run_id" in
  *[!A-Za-z0-9_-]*|"") fail "run-id must use only letters, numbers, underscores, or hyphens" ;;
esac

[ -f "$input" ] || fail "missing input file: $input"
repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || fail "must run inside a Git repository"
repo_root=$(python3 - "$repo_root" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
)
input_abs=$(python3 - "$input" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve(strict=True))
PY
) || fail "missing input file: $input"

case "$input_abs" in
  "$repo_root"/*) source_rel=${input_abs#"$repo_root"/} ;;
  *) fail "input must resolve inside the repository: $input" ;;
esac

refuse_if_normative "$source_rel"
cd "$repo_root"

safe_name=$(printf '%s' "$(basename -- "$source_rel")" | tr -c 'A-Za-z0-9._-' '_')
source_hash=$(python3 - "$source_rel" <<'PY'
import hashlib
import sys
print(hashlib.sha256(sys.argv[1].encode("utf-8")).hexdigest()[:12])
PY
)
run_dir=".agent-logs/$run_id"
out_dir="$run_dir/compressed"
output="$out_dir/${safe_name}.${source_hash}.compressed.md"
tmp="$output.$$.tmp"
err="$output.$$.headroom.err"
backend=fallback

mkdir -p "$out_dir"

if [ "${HEADROOM_DISABLED:-0}" != "1" ] && command -v headroom >/dev/null 2>&1; then
  if headroom "$input_abs" >"$tmp" 2>"$err" && [ -s "$tmp" ]; then
    mv "$tmp" "$output"
    rm -f "$err"
    backend=headroom
  else
    rm -f "$tmp" "$err"
    fallback_compress "$input_abs" "$output"
  fi
else
  fallback_compress "$input_abs" "$output"
fi

python3 .project-agent-workflow/scripts/agent_log_manifest.py record-compression \
  --run-dir "$run_dir" \
  --run-id "$run_id" \
  --source "$source_rel" \
  --output "$output"

echo "$output"
echo "backend=$backend" >&2
