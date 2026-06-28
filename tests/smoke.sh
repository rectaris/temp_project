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
  git -C "$out" check-ignore .agent-logs/sample/manifest.json >/dev/null
  git -C "$out" check-ignore .agent-artifacts/sample/output.txt >/dev/null
  (cd "$out" && python3 scripts/lint-plan-docs.py)
  (cd "$out" && python3 scripts/format-plan-docs.py --check)
  (cd "$out" && python3 scripts/structure-map.py --check >/dev/null)
done

run_plan_lifecycle_smoke "$tmp/typescript"

good_plan=$(cd "$tmp/typescript" && scripts/create-plan.sh active final-decisions --summary "Final decision plan." --summary-ja "最終決定を記録する。" )
(cd "$tmp/typescript" && python3 scripts/lint-plan-docs.py)
(cd "$tmp/typescript" && scripts/complete-plan.sh "$good_plan" >/dev/null)

bad_plan=$(cd "$tmp/typescript" && scripts/create-plan.sh active recommendation-matrix --summary "Recommendation matrix." --summary-ja "推奨案を比較する。" )
cat >>"$tmp/typescript/$bad_plan" <<'EOF_BAD_PLAN'
## Decision Audit

1. Storage location
   Compare possible storage locations.

   A: Store the full audit in the active plan.
   B: Store the full audit in a separate artifact.

   推奨: B
   理由: Active plans should keep only final decisions.
EOF_BAD_PLAN
if (cd "$tmp/typescript" && python3 scripts/lint-plan-docs.py >/dev/null 2>&1); then
  echo "lint-plan-docs.py accepted an active-plan recommendation matrix" >&2
  exit 1
fi
bad_base=$(basename "$bad_plan")
bad_id=${bad_base%%-*}
(cd "$tmp/typescript" && python3 scripts/lint-plan-docs.py --remove-active "$bad_id")
rm "$tmp/typescript/$bad_plan"
(cd "$tmp/typescript" && python3 scripts/lint-plan-docs.py)

test -f "$tmp/typescript/.codex/agents/repo_explorer.toml"
test -f "$tmp/typescript/.codex/hooks/pre_tool_hardening_gate.py"
test -f "$tmp/python/.codex/agents/repo_explorer.toml"
test -f "$tmp/python/.codex/hooks/pre_tool_hardening_gate.py"
test -f "$tmp/docs/.codex/agents/repo_explorer.toml"
grep -q 'エージェントワークフロー' "$tmp/typescript/README.md"
grep -q '外部サービス連携' "$tmp/typescript/README.md"
grep -q 'Codex hooks: `false`' "$tmp/python/AGENTS.md"
grep -q 'SkillSpector scan: `true`' "$tmp/typescript/AGENTS.md"
grep -q 'SkillSpector scan: `false`' "$tmp/python/AGENTS.md"
grep -q 'Optional SkillSpector scan: `true`' "$tmp/typescript/docs/agent/SPEC_VALIDATION.md"
grep -q 'SkillSpector is not required' "$tmp/python/docs/agent/SPEC_VALIDATION.md"
test -f "$tmp/typescript/scripts/skillspector-scan.sh"
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
grep -q 'Agent Logging' "$tmp/typescript/docs/agent/SPEC_AGENT_LOGGING.md"
grep -q 'Headroom is an optional backend' "$tmp/typescript/docs/agent/SPEC_CONTEXT_COMPRESSION.md"
grep -q 'agent_logging:' "$tmp/typescript/docs/agent/spec-index.yaml"
grep -q 'Context compression helper: optional' "$tmp/typescript/AGENTS.md"
grep -q 'scripts/context-compress.sh' "$tmp/typescript/docs/agent/SPEC_CONTEXT_COMPRESSION.md"
test -f "$tmp/typescript/.codex/skills/decision-audit/SKILL.md"
test -f "$tmp/typescript/.codex/skills/decision-audit/agents/openai.yaml"
grep -q 'name: decision-audit' "$tmp/typescript/.codex/skills/decision-audit/SKILL.md"
grep -q 'decision_audit:' "$tmp/typescript/docs/agent/spec-index.yaml"
grep -q 'SPEC_DECISION_AUDIT.md' "$tmp/typescript/docs/agent/spec-index.yaml"
grep -q 'Decision Audit Preflight' "$tmp/typescript/docs/agent/SPEC_PLAN_WORKFLOW.md"
grep -q 'Run decision audit before creating or materially updating active plans' "$tmp/typescript/AGENTS.md"
grep -q 'Full decision-audit output does not belong in `docs/plan/active`' "$tmp/typescript/docs/agent/SPEC_DECISION_AUDIT.md"

mkdir -p "$tmp/typescript/.agent-logs/sample/raw"
printf 'line 1\nline 2\n' >"$tmp/typescript/.agent-logs/sample/raw/session.log"
(cd "$tmp/typescript" && HEADROOM_DISABLED=1 scripts/context-compress.sh .agent-logs/sample/raw/session.log sample >/dev/null)
test -f "$tmp/typescript/.agent-logs/sample/compressed/session.log.compressed.md"
test -f "$tmp/typescript/.agent-logs/sample/manifest.json"
if (cd "$tmp/typescript" && scripts/context-compress.sh AGENTS.md >/dev/null 2>&1); then
  echo "context-compress.sh accepted AGENTS.md" >&2
  exit 1
fi
if (cd "$tmp/typescript" && scripts/context-compress.sh docs/agent/SPEC_VALIDATION.md >/dev/null 2>&1); then
  echo "context-compress.sh accepted validation policy" >&2
  exit 1
fi

echo "smoke test passed"
