#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/project-agent-workflow-update.XXXXXX")
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

mkdir -p "$tmp"
oldest_ref=${COPIER_UPDATE_OLDEST_REF:-v0.4.1}
latest_ref=${COPIER_UPDATE_LATEST_REF:-v0.4.6}
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

prepare_lane() {
  lane=$1
  base_ref=$2
  answers=$3
  out="$tmp/$lane"
  run_copier copy -q -f --vcs-ref "$base_ref" --data-file "$answers" "$root" "$out" >/dev/null
  git -C "$out" init -b main >/dev/null
  git -C "$out" config user.email "ci@example.invalid"
  git -C "$out" config user.name "CI"
  git -C "$out" add -A
  git -C "$out" commit -m "Initial generated workflow" >/dev/null

  cat >"$out/docs/agent/SPEC_PRODUCT.md" <<'EOF'
# Product Notes

Local project-owned agent notes.
EOF
  cat >"$out/docs/agent/PROJECT_ENVIRONMENT.md" <<'EOF'
# Project Environment

Preserve this project-owned environment policy.
EOF
  cat >"$out/docs/agent/PROJECT_UI_DESIGN.md" <<'EOF'
# Project UI Design

Preserve this project-owned UI policy.
EOF
  git -C "$out" add docs/agent/SPEC_PRODUCT.md docs/agent/PROJECT_ENVIRONMENT.md docs/agent/PROJECT_UI_DESIGN.md
  git -C "$out" commit -m "Add local project notes" >/dev/null
  run_copier update -q -f --vcs-ref HEAD "$out" >/dev/null
  printf '%s\n' "$out"
}

validate_common_lane() {
  out=$1
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
  test -f "$out/docs/agent/SPEC_SECURITY.md"
  test -f "$out/docs/agent/PROJECT_ENVIRONMENT.md"
  test -f "$out/docs/agent/PROJECT_UI_DESIGN.md"
  test -f "$out/scripts/workflow-status.sh"
  test -f "$out/scripts/create-plan.sh"
  test -f "$out/scripts/select-task-context.sh"
  test -f "$out/scripts/clean-handoffs.sh"
  test -f "$out/scripts/lint-plan-docs.sh"
  test -f "$out/scripts/format-plan-docs.sh"
  test -f "$out/scripts/validate-changes.py"
  test -f "$out/scripts/security-static-check.py"
  grep -q 'Local project-owned agent notes.' "$out/docs/agent/SPEC_PRODUCT.md"
  grep -q 'Preserve this project-owned environment policy.' "$out/docs/agent/PROJECT_ENVIRONMENT.md"
  grep -q 'Preserve this project-owned UI policy.' "$out/docs/agent/PROJECT_UI_DESIGN.md"
  grep -q 'Integration Checklist' "$out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
  grep -q 'ci_autofix_mode: disabled' "$out/.copier-answers.yml"
  grep -q 'CI autofix mode: `disabled`' "$out/AGENTS.md"
  test ! -f "$out/.github/workflows/codex-ci-autofix.yml"
  test ! -f "$out/.codex/hooks.json"
  test -f "$out/.codex/hooks/agent_log_event.py"

  if find "$out" -name '*.rej' -print -quit | grep -q .; then
    echo "copier update produced rejection files: $out" >&2
    exit 1
  fi
  git -C "$out" diff --check
  (cd "$out" && python3 scripts/lint-plan-docs.py)
  (cd "$out" && python3 scripts/format-plan-docs.py --check)
  (cd "$out" && python3 scripts/check-codex-toml.py >/dev/null)
  (cd "$out" && python3 scripts/structure-map.py --check >/dev/null)
  (cd "$out" && python3 scripts/security-static-check.py >/dev/null)
  python3 "$root/scripts/check-copier-template.py" --print-generated-required | while IFS= read -r path; do
    [ -n "$path" ] || continue
    test -f "$out/$path"
  done
}

oldest_out=$(prepare_lane oldest-supported "$oldest_ref" "$legacy_answers")
validate_common_lane "$oldest_out"
grep -q 'Codex hooks mode: `install_templates`' "$oldest_out/AGENTS.md"
grep -q 'SkillSpector mode: `document_optional`' "$oldest_out/AGENTS.md"
grep -q 'MCP: `documented`' "$oldest_out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear sync: `documented`' "$oldest_out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Graph memory: `documented`' "$oldest_out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
test -f "$oldest_out/scripts/skillspector-scan.sh"
if grep -q 'use_hooks\|use_skillspector\|use_mcp_policy\|use_linear_sync\|use_graph_memory' "$oldest_out/.copier-answers.yml" "$oldest_out/AGENTS.md" "$oldest_out/docs/agent/SPEC_EXTERNAL_SERVICES.md"; then
  echo "old activation booleans leaked into generated policy" >&2
  exit 1
fi
if grep -q 'state: configured' "$oldest_out/docs/agent/external-services.yaml"; then
  echo "legacy activation booleans configured external services" >&2
  exit 1
fi

latest_out=$(prepare_lane latest-stable "$latest_ref" "$root/tests/fixtures/python.answers.yml")
validate_common_lane "$latest_out"
grep -q 'Codex hooks mode: `install_templates`' "$latest_out/AGENTS.md"
grep -q 'SkillSpector mode: `disabled`' "$latest_out/AGENTS.md"
grep -q 'MCP: `disabled`' "$latest_out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
test ! -f "$latest_out/scripts/skillspector-scan.sh"

echo "copier update test passed"
