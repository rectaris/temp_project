#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/project-agent-workflow-minimum.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

if ! command -v uvx >/dev/null 2>&1; then
  if [ "${REQUIRE_MINIMUM_COMPAT:-0}" = "1" ]; then
    echo "uvx is required for the minimum compatibility test" >&2
    exit 127
  fi
  echo "uvx not found; skipped minimum compatibility test"
  exit 0
fi

if [ "${REQUIRE_MINIMUM_COMPAT:-0}" = "1" ]; then
  actual_python=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  expected_python=${MINIMUM_PYTHON_VERSION:-3.11}
  if [ "$actual_python" != "$expected_python" ]; then
    echo "minimum compatibility requires Python $expected_python, found $actual_python" >&2
    exit 1
  fi
fi

# Copier 9.6.0 is the first tested 9.x release that evaluates this template's dynamic exclusions.
copier_version=${MINIMUM_COPIER_VERSION:-9.6.0}
python_path=$(command -v python3)
UV_CACHE_DIR="$root/.uv-cache" UV_TOOL_DIR="$tmp/uv-tools" uvx --python "$python_path" --from "copier==$copier_version" copier copy -q -f --vcs-ref HEAD --data-file "$root/tests/fixtures/docs.answers.yml" "$root" "$tmp/generated"
python3 "$root/scripts/check-copier-template.py" --print-expected-generated "$root/tests/fixtures/docs.answers.yml" >"$tmp/expected"
find "$tmp/generated" -type f -printf '%P\n' | LC_ALL=C sort >"$tmp/actual"
diff -u "$tmp/expected" "$tmp/actual"
test ! -f "$tmp/generated/.github/workflows/codex-ci-autofix.yml"

echo "minimum Copier/Python compatibility test passed"
