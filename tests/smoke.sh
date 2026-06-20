#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=${TMPDIR:-/tmp}/project-agent-workflow-smoke-$$
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
. "$root/tests/lib-copier.sh"

python3 "$root/scripts/check-copier-template.py" >/dev/null

if ! copier_available; then
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
  run_copier "$@" >/dev/null
}

assert_generated_required_files() {
  out=$1
  python3 "$root/scripts/check-copier-template.py" --print-generated-required | while IFS= read -r path; do
    [ -n "$path" ] || continue
    test -f "$out/$path"
  done
}

run_plan_lifecycle_smoke() {
  out=$1
  (cd "$out" && scripts/create-plan.sh active sample --summary "Sample work." --summary-ja "サンプル作業を行う。" >/dev/null)
  (cd "$out" && test -f docs/plan/active/001-sample.md)
  (cd "$out" && python3 scripts/lint-plan-docs.py)
  (cd "$out" && scripts/select-task-context.sh docs/plan/active/001-sample.md | grep -q '^TASK_TYPE=tooling$')
  (cd "$out" && scripts/clean-handoffs.sh --dry-run >/dev/null)
  (cd "$out" && scripts/complete-plan.sh docs/plan/active/001-sample.md >/dev/null)
  (cd "$out" && test -f docs/plan/checked/001-sample.md)
  (cd "$out" && python3 scripts/lint-plan-docs.py)
}

for fixture in "$root"/tests/fixtures/*.answers.yml; do
  name=$(basename "$fixture" .answers.yml)
  out="$tmp/$name"
  render_fixture "$fixture" "$out"
  assert_generated_required_files "$out"
  git -C "$out" init -b main >/dev/null
  git -C "$out" diff --check
  (cd "$out" && python3 scripts/lint-plan-docs.py)
  (cd "$out" && python3 scripts/format-plan-docs.py --check)
  (cd "$out" && python3 scripts/structure-map.py --check >/dev/null)
done

run_plan_lifecycle_smoke "$tmp/typescript"

test -f "$tmp/typescript/.codex/agents/repo_explorer.toml"
test -f "$tmp/typescript/.codex/hooks/pre_tool_hardening_gate.py"
test -f "$tmp/python/.codex/agents/repo_explorer.toml"
test -f "$tmp/python/.codex/hooks/pre_tool_hardening_gate.py"
test -f "$tmp/docs/.codex/agents/repo_explorer.toml"
grep -q 'エージェントワークフロー' "$tmp/typescript/README.md"
grep -q '外部サービス連携' "$tmp/typescript/README.md"
grep -q 'Codex hooks: `false`' "$tmp/python/AGENTS.md"
grep -q 'External service policies: MCP=`true`' "$tmp/python/AGENTS.md"
grep -q 'Codex helper agents: `false`' "$tmp/docs/AGENTS.md"
grep -q 'Use tmux for long-running, shared, or interactive commands' "$tmp/typescript/AGENTS.md"
grep -q 'Command Sessions' "$tmp/typescript/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'Name tmux sessions descriptively' "$tmp/typescript/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'MCP Setup' "$tmp/typescript/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'LINEAR_ACCESS_TOKEN' "$tmp/typescript/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Graph Memory Setup' "$tmp/typescript/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear sync policy: `true`' "$tmp/typescript/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear sync is disabled' "$tmp/python/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'To add Linear later' "$tmp/python/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'To add MCP later' "$tmp/docs/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'To add graph memory later' "$tmp/docs/docs/agent/SPEC_EXTERNAL_SERVICES.md"

echo "smoke test passed"
