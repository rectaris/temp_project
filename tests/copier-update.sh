#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=${TMPDIR:-/tmp}/project-agent-workflow-update-$$
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
. "$root/tests/lib-copier.sh"

if ! copier_available; then
  if [ "${REQUIRE_COPIER:-0}" = "1" ]; then
    echo "copier CLI not found" >&2
    exit 127
  fi
  echo "copier CLI not found; skipped copier update test"
  echo "copier update test passed"
  exit 0
fi

out="$tmp/generated"
base_ref=${COPIER_UPDATE_BASE_REF:-v0.4.1}
mkdir -p "$tmp"
legacy_answers="$tmp/legacy-activation.answers.yml"
cat >"$legacy_answers" <<'EOF'
project_name: typescript-app
project_slug: typescript-app
project_purpose: Build a TypeScript application.
primary_language: typescript
use_hooks: true
use_skillspector: true
use_mcp_policy: true
use_linear_sync: true
use_graph_memory: true
EOF
run_copier copy -f --vcs-ref "$base_ref" --data-file "$legacy_answers" "$root" "$out" >/dev/null

git -C "$out" init -b main >/dev/null
git -C "$out" config user.email "ci@example.invalid"
git -C "$out" config user.name "CI"
git -C "$out" add -A
git -C "$out" commit -m "Initial generated workflow" >/dev/null

cat >"$out/docs/agent/SPEC_PRODUCT.md" <<'EOF'
# Product Notes

Local project-owned agent notes.
EOF
git -C "$out" add docs/agent/SPEC_PRODUCT.md
git -C "$out" commit -m "Add local project notes" >/dev/null

run_copier update -f --vcs-ref HEAD "$out" >/dev/null

test -f "$out/.copier-answers.yml"
test -f "$out/AGENTS.md"
test -f "$out/docs/agent/spec-index.yaml"
test -f "$out/docs/agent/SPEC_FILE_MANAGEMENT.md"
test -f "$out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
test -f "$out/docs/agent/external-services.yaml"
test -f "$out/docs/plan/README.md"
test -f "$out/docs/plan/backlog/README.md"
test -f "$out/docs/plan/handoffs/README.md"
test -f "$out/docs/plan/sub-agents/custom-agents.md"
test -f "$out/docs/agent/SPEC_PRODUCT.md"
test -f "$out/scripts/workflow-status.sh"
test -f "$out/scripts/create-plan.sh"
test -f "$out/scripts/select-task-context.sh"
test -f "$out/scripts/clean-handoffs.sh"
test -f "$out/scripts/lint-plan-docs.sh"
test -f "$out/scripts/format-plan-docs.sh"
test -f "$out/scripts/validate-changes.py"
test -f "$out/scripts/security-static-check.py"
grep -q 'Local project-owned agent notes.' "$out/docs/agent/SPEC_PRODUCT.md"
grep -q 'Integration Checklist' "$out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Codex hooks mode: `install_templates`' "$out/AGENTS.md"
grep -q 'SkillSpector mode: `document_optional`' "$out/AGENTS.md"
grep -q 'MCP: `documented`' "$out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear sync: `documented`' "$out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Graph memory: `documented`' "$out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'state: documented' "$out/docs/agent/external-services.yaml"
grep -q 'allowed_reads: \[\]' "$out/docs/agent/external-services.yaml"
grep -q 'allowed_writes: \[\]' "$out/docs/agent/external-services.yaml"
test ! -f "$out/.codex/hooks.json"
test -f "$out/.codex/hooks/agent_log_event.py"
test -f "$out/scripts/skillspector-scan.sh"
grep -q 'codex_hooks_mode: install_templates' "$out/.copier-answers.yml"
grep -q 'skillspector_mode: document_optional' "$out/.copier-answers.yml"
if grep -q 'use_hooks\|use_skillspector\|use_mcp_policy\|use_linear_sync\|use_graph_memory' "$out/.copier-answers.yml" "$out/AGENTS.md" "$out/docs/agent/SPEC_EXTERNAL_SERVICES.md"; then
  echo "old activation booleans leaked into generated policy" >&2
  exit 1
fi
if grep -q 'state: configured' "$out/docs/agent/external-services.yaml"; then
  echo "legacy activation booleans configured external services" >&2
  exit 1
fi

if find "$out" -name '*.rej' -print -quit | grep -q .; then
  echo "copier update produced rejection files" >&2
  exit 1
fi

git -C "$out" diff --check
echo "copier update test passed"
