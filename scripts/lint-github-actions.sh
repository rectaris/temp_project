#!/bin/sh
set -eu

root=${1:-.}
if ! command -v actionlint >/dev/null 2>&1; then
  if [ "${REQUIRE_ACTIONLINT:-0}" = "1" ]; then
    echo "actionlint 1.7.12 is required" >&2
    exit 127
  fi
  echo "actionlint not found; skipped GitHub Actions lint"
  exit 0
fi

actual=$(actionlint -version | awk 'NR == 1 { print $1 }')
[ "$actual" = "1.7.12" ] || {
  echo "actionlint version mismatch: expected 1.7.12, found $actual" >&2
  exit 1
}

find "$root/.github/workflows" -type f \( -name '*.yml' -o -name '*.yaml' \) -print0 |
  xargs -0 actionlint
