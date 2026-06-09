#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=${TMPDIR:-/tmp}/project-agent-workflow-smoke-$$
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

python3 "$root/scripts/check-copier-template.py" >/dev/null

if ! command -v copier >/dev/null 2>&1; then
  if [ "${REQUIRE_COPIER:-0}" = "1" ]; then
    echo "copier CLI not found" >&2
    exit 127
  fi
  echo "copier CLI not found; skipped generated-project smoke"
  echo "smoke test passed"
  exit 0
fi

render_fixture() {
  fixture=$1
  out=$2
  set -- copy -f --vcs-ref HEAD --data-file "$fixture"
  set -- "$@" "$root" "$out"
  copier "$@" >/dev/null
}

for fixture in "$root"/tests/fixtures/*.answers.yml; do
  name=$(basename "$fixture" .answers.yml)
  out="$tmp/$name"
  render_fixture "$fixture" "$out"
  test -f "$out/.copier-answers.yml"
  test -f "$out/AGENTS.md"
  test -f "$out/README.md"
  test -f "$out/docs/agent/spec-index.yaml"
  test -f "$out/docs/agent/SPEC_FILE_MANAGEMENT.md"
  test -f "$out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
  test -f "$out/docs/plan/plan.md"
  test -f "$out/scripts/workflow-status.sh"
  test -f "$out/scripts/create-plan.sh"
  test -f "$out/scripts/validate-changes.py"
  test -f "$out/scripts/security-static-check.py"
  git -C "$out" init -b main >/dev/null
  git -C "$out" diff --check
  (cd "$out" && python3 scripts/lint-plan-docs.py)
  (cd "$out" && python3 scripts/structure-map.py --check >/dev/null)
done

(cd "$tmp/typescript" && scripts/create-plan.sh active sample --summary "Sample work." >/dev/null)
(cd "$tmp/typescript" && test -f docs/plan/active/001-sample.md)
(cd "$tmp/typescript" && python3 scripts/lint-plan-docs.py)
(cd "$tmp/typescript" && scripts/complete-plan.sh docs/plan/active/001-sample.md >/dev/null)
(cd "$tmp/typescript" && test -f docs/plan/checked/001-sample.md)
(cd "$tmp/typescript" && python3 scripts/lint-plan-docs.py)

test -f "$tmp/typescript/.codex/agents/repo_explorer.toml"
test -f "$tmp/typescript/.codex/hooks/pre_tool_hardening_gate.py"
test -f "$tmp/python/.codex/agents/repo_explorer.toml"
test -f "$tmp/python/.codex/hooks/pre_tool_hardening_gate.py"
test -f "$tmp/docs/.codex/agents/repo_explorer.toml"
grep -q 'エージェントワークフロー' "$tmp/typescript/README.md"
grep -q 'Codex hooks: `false`' "$tmp/python/AGENTS.md"
grep -q 'External service policies: MCP=`true`' "$tmp/python/AGENTS.md"
grep -q 'Codex helper agents: `false`' "$tmp/docs/AGENTS.md"
grep -q 'Linear sync policy: `true`' "$tmp/typescript/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear sync is disabled' "$tmp/python/docs/agent/SPEC_EXTERNAL_SERVICES.md"

echo "smoke test passed"
