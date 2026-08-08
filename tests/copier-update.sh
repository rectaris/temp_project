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
earliest_ref=${COPIER_UPDATE_EARLIEST_REF:-v0.3.1}
oldest_ref=${COPIER_UPDATE_OLDEST_REF:-v0.4.1}
latest_ref=${COPIER_UPDATE_LATEST_REF:-v0.4.6}
target_commit=${COPIER_UPDATE_TARGET_REF:-HEAD}
update_source="$tmp/update-source"
git clone -q "$root" "$update_source"
git -C "$update_source" fetch -q "$root" "$target_commit"
git -C "$update_source" switch -q -c migration-target FETCH_HEAD
git -C "$update_source" tag -f v1.1.0
target_ref=v1.1.0
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

run_adoption() {
  destination=$1
  ref=$2
  shift 2
  if command -v uv >/dev/null 2>&1 && [ -f "$root/pyproject.toml" ]; then
    (cd "$root" && UV_CACHE_DIR="$root/.uv-cache" uv run python \
      "$root/scripts/adopt-to-namespaced-layout.py" \
      --destination "$destination" --vcs-ref "$ref" "$@")
  else
    copier_executable=$(command -v copier)
    python3 "$root/scripts/adopt-to-namespaced-layout.py" \
      --destination "$destination" --vcs-ref "$ref" \
      --copier-executable "$copier_executable" "$@"
  fi
}
legacy_disabled_answers="$tmp/legacy-disabled.answers.yml"
cat >"$legacy_disabled_answers" <<'EOF'
project_name: legacy-disabled
project_slug: legacy-disabled
project_purpose: Exercise disabled legacy activation answers.
primary_language: docs
use_hooks: false
use_skillspector: false
use_mcp_policy: false
use_linear_sync: false
use_graph_memory: false
EOF

prepare_lane() {
  lane=$1
  base_ref=$2
  answers=$3
  shift 3
  out="$tmp/$lane"
  run_copier copy -q -f --vcs-ref "$base_ref" --data-file "$answers" "$update_source" "$out" >/dev/null
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
  if [ "$lane" = "earliest-supported" ]; then
    status_before=$(git -C "$out" status --porcelain=v1)
    if run_copier update -q -f --trust --vcs-ref "$target_ref" "$out" >/dev/null 2>&1; then
      echo "direct pre-v1 copier update unexpectedly succeeded" >&2
      exit 1
    fi
    status_after=$(git -C "$out" status --porcelain=v1)
    [ "$status_after" = "$status_before" ]
    test ! -e "$out/.project-agent-workflow"
    test ! -e "$out/.project-agent-workflow-migration"
  fi
  run_adoption "$out" "$target_ref" "$@" >/dev/null
  printf '%s\n' "$out"
}

validate_common_lane() {
  out=$1
  test -f "$out/.copier-answers.yml"
  test -f "$out/.project-agent-workflow/AGENTS.md"
  test -f "$out/.project-agent-workflow/docs/agent/spec-index.yaml"
  test -f "$out/.project-agent-workflow/docs/agent/SPEC_FILE_MANAGEMENT.md"
  test -f "$out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
  test -f "$out/docs/agent/external-services.yaml"
  test -f "$out/docs/plan/README.md"
  test -f "$out/docs/plan/backlog/README.md"
  test -f "$out/docs/plan/handoffs/README.md"
  test -f "$out/docs/plan/sub-agents/custom-agents.md"
  test -f "$out/docs/agent/SPEC_PRODUCT.md"
  test -f "$out/.project-agent-workflow/docs/agent/SPEC_SECURITY.md"
  test -f "$out/docs/agent/PROJECT_ENVIRONMENT.md"
  test -f "$out/docs/agent/PROJECT_UI_DESIGN.md"
  test -f "$out/.project-agent-workflow/scripts/workflow-status.sh"
  test -f "$out/.project-agent-workflow/scripts/create-plan.sh"
  test -f "$out/.project-agent-workflow/scripts/select-task-context.sh"
  test -f "$out/.project-agent-workflow/scripts/clean-handoffs.sh"
  test -f "$out/.project-agent-workflow/scripts/lint-plan-docs.sh"
  test -f "$out/.project-agent-workflow/scripts/format-plan-docs.sh"
  test -f "$out/.project-agent-workflow/scripts/validate-changes.py"
  test -f "$out/.project-agent-workflow/scripts/security-static-check.py"
  test -f "$out/.project-agent-workflow/scripts/check-external-service-policy.py"
  test -f "$out/.project-agent-workflow/scripts/migrate-legacy-template-files.py"
  test -f "$out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json"
  test -f "$out/scripts/create-plan.sh"
  grep -q 'Local project-owned agent notes.' "$out/docs/agent/SPEC_PRODUCT.md"
  grep -q 'Preserve this project-owned environment policy.' "$out/docs/agent/PROJECT_ENVIRONMENT.md"
  grep -q 'Preserve this project-owned UI policy.' "$out/docs/agent/PROJECT_UI_DESIGN.md"
  grep -q 'Integration Checklist' "$out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
  grep -q 'ci_autofix_mode: disabled' "$out/.copier-answers.yml"
  grep -q 'CI autofix mode: `disabled`' "$out/.project-agent-workflow/AGENTS.md"
  test ! -f "$out/.github/workflows/codex-ci-autofix.yml"
  test -f "$out/.codex/hooks/agent_log_event.py"
  grep -q 'Compatibility bridge' "$out/.codex/hooks/agent_log_event.py"
  grep -q 'project-agent-workflow:managed-core:start' "$out/AGENTS.md"
  if git -C "$out" ls-files -u | grep -q .; then
    echo "namespaced adoption left an unmerged index: $out" >&2
    exit 1
  fi
  git -C "$out" diff --diff-filter=D --name-only | while IFS= read -r path; do
    case "$path" in
      .github/workflows/codex-ci-autofix.yml|scripts/skillspector-scan.sh) ;;
      *)
        echo "namespaced adoption deleted project-owned or unclassified path: $out/$path" >&2
        exit 1
        ;;
    esac
  done

  if find "$out" -name '*.rej' -print -quit | grep -q .; then
    echo "copier update produced rejection files: $out" >&2
    exit 1
  fi
  if grep -R -n -E '^(<<<<<<<|=======|>>>>>>>)' "$out" --exclude-dir=.git >/dev/null; then
    echo "copier update produced inline conflict markers: $out" >&2
    exit 1
  fi
  git -C "$out" diff --check
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
  (cd "$out" && python3 .project-agent-workflow/scripts/format-plan-docs.py --check)
  (cd "$out" && python3 .project-agent-workflow/scripts/check-codex-toml.py >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py check >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/structure-map.py --check >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/security-static-check.py >/dev/null)
  python3 "$root/scripts/check-copier-template.py" --print-generated-required | while IFS= read -r path; do
    [ -n "$path" ] || continue
    test -f "$out/$path"
  done
}

earliest_out=$(prepare_lane earliest-supported "$earliest_ref" "$legacy_answers")
(cd "$earliest_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
validate_common_lane "$earliest_out"
grep -q 'Codex hooks mode: `install_templates`' "$earliest_out/.project-agent-workflow/AGENTS.md"
grep -q 'SkillSpector mode: `disabled`' "$earliest_out/.project-agent-workflow/AGENTS.md"
grep -q 'MCP: `documented`' "$earliest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear sync: `documented`' "$earliest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Graph memory: `documented`' "$earliest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
test ! -f "$earliest_out/.project-agent-workflow/scripts/skillspector-scan.sh"

oldest_out=$(prepare_lane oldest-supported "$oldest_ref" "$legacy_answers")
(cd "$oldest_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
validate_common_lane "$oldest_out"
grep -q 'Codex hooks mode: `install_templates`' "$oldest_out/.project-agent-workflow/AGENTS.md"
grep -q 'SkillSpector mode: `document_optional`' "$oldest_out/.project-agent-workflow/AGENTS.md"
grep -q 'MCP: `documented`' "$oldest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear sync: `documented`' "$oldest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Graph memory: `documented`' "$oldest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
test -f "$oldest_out/.project-agent-workflow/scripts/skillspector-scan.sh"
test -f "$oldest_out/scripts/skillspector-scan.sh"
grep -q '.project-agent-workflow/scripts/skillspector-scan.sh' "$oldest_out/scripts/skillspector-scan.sh"
test -f "$oldest_out/.project-agent-workflow-migration/v1-pre-namespace/.github/workflows/codex-ci-autofix.yml"
grep -q 'retired_legacy_optional_paths' "$oldest_out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json"
if grep -q 'use_hooks\|use_skillspector\|use_mcp_policy\|use_linear_sync\|use_graph_memory' "$oldest_out/.copier-answers.yml" "$oldest_out/.project-agent-workflow/AGENTS.md" "$oldest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"; then
  echo "old activation booleans leaked into generated policy" >&2
  exit 1
fi
if grep -q 'state: configured' "$oldest_out/docs/agent/external-services.yaml"; then
  echo "legacy activation booleans configured external services" >&2
  exit 1
fi

latest_out=$(prepare_lane latest-stable "$latest_ref" "$root/tests/fixtures/python.answers.yml")
(cd "$latest_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
validate_common_lane "$latest_out"
test -f "$latest_out/docs/agent/SPEC_COPIER_ADOPTION.md"
test -f "$latest_out/.codex/skills/decision-audit/SKILL.md"
grep -q 'Codex hooks mode: `install_templates`' "$latest_out/.project-agent-workflow/AGENTS.md"
grep -q 'SkillSpector mode: `disabled`' "$latest_out/.project-agent-workflow/AGENTS.md"
grep -q 'MCP: `disabled`' "$latest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
test ! -f "$latest_out/.project-agent-workflow/scripts/skillspector-scan.sh"

legacy_disabled_out=$(prepare_lane oldest-disabled "$oldest_ref" "$legacy_disabled_answers")
(cd "$legacy_disabled_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
validate_common_lane "$legacy_disabled_out"
grep -q 'Codex hooks mode: `disabled`' "$legacy_disabled_out/.project-agent-workflow/AGENTS.md"
grep -q 'SkillSpector mode: `disabled`' "$legacy_disabled_out/.project-agent-workflow/AGENTS.md"
grep -q 'MCP: `disabled`' "$legacy_disabled_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear sync: `disabled`' "$legacy_disabled_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Graph memory: `disabled`' "$legacy_disabled_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
test ! -f "$legacy_disabled_out/.project-agent-workflow/scripts/skillspector-scan.sh"

legacy_override_out=$(prepare_lane oldest-explicit-disabled "$oldest_ref" "$legacy_answers" \
  --data codex_hooks_mode=disabled \
  --data skillspector_mode=disabled \
  --data mcp_policy_mode=disabled \
  --data linear_sync_mode=disabled \
  --data graph_memory_mode=disabled \
  --data ci_autofix_mode=disabled)
(cd "$legacy_override_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
validate_common_lane "$legacy_override_out"
grep -q 'External service policy states: MCP=`disabled`, Linear=`disabled`, graph memory=`disabled`' "$legacy_override_out/.project-agent-workflow/AGENTS.md"
grep -q 'MCP: `disabled`' "$legacy_override_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear sync: `disabled`' "$legacy_override_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Graph memory: `disabled`' "$legacy_override_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
if grep -q 'state: documented' "$legacy_override_out/docs/agent/external-services.yaml"; then
  echo "legacy activation booleans overrode explicit disabled modes" >&2
  exit 1
fi
test ! -f "$legacy_override_out/.project-agent-workflow/scripts/skillspector-scan.sh"

modified_out="$tmp/oldest-modified-skillspector"
run_copier copy -q -f --vcs-ref "$oldest_ref" --data-file "$legacy_disabled_answers" "$update_source" "$modified_out" >/dev/null
git -C "$modified_out" init -b main >/dev/null
git -C "$modified_out" config user.email "ci@example.invalid"
git -C "$modified_out" config user.name "CI"
git -C "$modified_out" add -A
git -C "$modified_out" commit -m "Initial generated workflow" >/dev/null
printf '\n# project-owned modification\n' >>"$modified_out/scripts/skillspector-scan.sh"
git -C "$modified_out" add scripts/skillspector-scan.sh
git -C "$modified_out" commit -m "Customize SkillSpector helper" >/dev/null
run_adoption "$modified_out" "$target_ref" >/dev/null
if (cd "$modified_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null 2>&1); then
  echo "modified legacy optional file was not reported for manual review" >&2
  exit 1
fi
grep -q 'project-owned modification' "$modified_out/.project-agent-workflow-migration/v1-pre-namespace/scripts/skillspector-scan.sh"
grep -q 'project-owned modification' "$modified_out/scripts/skillspector-scan.sh"
grep -q 'scripts/skillspector-scan.sh' "$modified_out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json"
test -f "$modified_out/.project-agent-workflow/scripts/migrate-legacy-template-files.py"
(cd "$modified_out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py check >/dev/null)
git -C "$modified_out" diff --check

mature_out="$tmp/mature-customized-project"
run_copier copy -q -f --vcs-ref "$latest_ref" --data-file "$root/tests/fixtures/python.answers.yml" "$update_source" "$mature_out" >/dev/null
git -C "$mature_out" init -b main >/dev/null
git -C "$mature_out" config user.email "ci@example.invalid"
git -C "$mature_out" config user.name "CI"
git -C "$mature_out" add -A
git -C "$mature_out" commit -m "Initial generated workflow" >/dev/null

printf '\n# project agent marker\n' >>"$mature_out/.codex/agents/docs_researcher.toml"
printf '\n# project agent marker\n' >>"$mature_out/.codex/agents/scoped_worker.toml"
printf '\n# legacy hook marker\n' >>"$mature_out/.codex/hooks/pre_tool_hardening_gate.py"
printf '\n# legacy hook marker\n' >>"$mature_out/.codex/hooks/stop_review_gate.py"
printf '\nProject adoption policy marker.\n' >>"$mature_out/docs/agent/SPEC_COPIER_ADOPTION.md"
printf '\nProject environment policy marker.\n' >>"$mature_out/docs/agent/SPEC_ENVIRONMENT.md"
printf '\nProject UI policy marker.\n' >>"$mature_out/docs/agent/SPEC_UI_DESIGN.md"
printf '\n# project plan lifecycle marker\n' >>"$mature_out/scripts/complete-plan.sh"
printf '\nProject implementation skill marker.\n' >>"$mature_out/.codex/skills/implementation-guidelines/SKILL.md"
cat >"$mature_out/docs/agent/SPEC_PRODUCT.md" <<'EOF_MATURE_PRODUCT'
# Product Notes

Local project-owned agent notes.
EOF_MATURE_PRODUCT
cat >"$mature_out/docs/agent/PROJECT_ENVIRONMENT.md" <<'EOF_MATURE_ENVIRONMENT'
# Project Environment

Preserve this project-owned environment policy.
EOF_MATURE_ENVIRONMENT
cat >"$mature_out/docs/agent/PROJECT_UI_DESIGN.md" <<'EOF_MATURE_UI'
# Project UI Design

Preserve this project-owned UI policy.
EOF_MATURE_UI
mkdir -p "$mature_out/.github/workflows"
cat >"$mature_out/.github/workflows/product-verify.yml" <<'EOF_MATURE_WORKFLOW'
name: Product verification
on: workflow_dispatch
jobs: {}
EOF_MATURE_WORKFLOW
cat >"$mature_out/scripts/validate-project-adoption.sh" <<'EOF_MATURE_VALIDATOR'
#!/bin/sh
set -eu
grep -q '^_commit: v0.4.6$' .copier-answers.yml
EOF_MATURE_VALIDATOR
git -C "$mature_out" add -A
git -C "$mature_out" commit -m "Customize mature project workflow" >/dev/null

run_adoption "$mature_out" "$target_ref" >/dev/null
(cd "$mature_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
validate_common_lane "$mature_out"
grep -q 'project agent marker' "$mature_out/.codex/agents/docs_researcher.toml"
grep -q 'project agent marker' "$mature_out/.codex/agents/scoped_worker.toml"
grep -q 'Project adoption policy marker.' "$mature_out/docs/agent/SPEC_COPIER_ADOPTION.md"
grep -q 'Project environment policy marker.' "$mature_out/docs/agent/SPEC_ENVIRONMENT.md"
grep -q 'Project UI policy marker.' "$mature_out/docs/agent/SPEC_UI_DESIGN.md"
grep -q 'project plan lifecycle marker' "$mature_out/scripts/complete-plan.sh"
grep -q 'Project implementation skill marker.' "$mature_out/.codex/skills/implementation-guidelines/SKILL.md"
grep -q 'name: Product verification' "$mature_out/.github/workflows/product-verify.yml"
grep -q 'legacy hook marker' "$mature_out/.project-agent-workflow-migration/v1-pre-namespace/.codex/hooks/pre_tool_hardening_gate.py"
grep -q 'legacy hook marker' "$mature_out/.project-agent-workflow-migration/v1-pre-namespace/.codex/hooks/stop_review_gate.py"
if grep -q 'legacy hook marker' "$mature_out/.codex/hooks/pre_tool_hardening_gate.py" "$mature_out/.codex/hooks/stop_review_gate.py"; then
  echo "legacy hook implementation remained active after adoption" >&2
  exit 1
fi
grep -q 'Compatibility bridge' "$mature_out/.codex/hooks/pre_tool_hardening_gate.py"
grep -q 'No-op bridge' "$mature_out/.codex/hooks/stop_review_gate.py"
grep -q 'scripts/validate-project-adoption.sh' "$mature_out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json"

future_source="$tmp/future-source"
future_out="$tmp/future-project"
git clone -q "$update_source" "$future_source"
# Keep Copier bound to this mutable test source instead of the clone's origin.
git -C "$future_source" remote remove origin
run_copier copy -q -f --vcs-ref HEAD --data-file "$root/tests/fixtures/typescript.answers.yml" "$future_source" "$future_out" >/dev/null
git -C "$future_out" init -b main >/dev/null
git -C "$future_out" config user.email "ci@example.invalid"
git -C "$future_out" config user.name "CI"
git -C "$future_out" add -A
git -C "$future_out" commit -m "Initial namespaced workflow" >/dev/null

printf '\nProject AGENTS marker.\n' >>"$future_out/AGENTS.md"
printf '\nProject README marker.\n' >>"$future_out/README.md"
printf '\n# project ignore marker\n' >>"$future_out/.gitignore"
printf '\n# project config marker\n' >>"$future_out/.codex/config.toml"
sed -i '1s/^{/{\n  "_project_owned_marker": true,/' "$future_out/.codex/hooks.json"
printf '\nProject environment marker.\n' >>"$future_out/docs/agent/PROJECT_ENVIRONMENT.md"
printf '\nProject policy marker.\n' >>"$future_out/docs/agent/PROJECT_POLICY.md"
printf '\n# project external-service marker\n' >>"$future_out/docs/agent/external-services.yaml"
printf '\nProject plan marker.\n' >>"$future_out/docs/plan/README.md"
cat >"$future_out/docs/agent/SPEC_PRODUCT.md" <<'EOF_FUTURE_SPEC'
# Product Policy

Project product marker.
EOF_FUTURE_SPEC
mkdir -p "$future_out/.agents/skills/product-rules" "$future_out/.github/workflows"
cat >"$future_out/.agents/skills/product-rules/SKILL.md" <<'EOF_FUTURE_SKILL'
---
name: product-rules
description: Apply project-owned product rules.
---

# Product Rules
EOF_FUTURE_SKILL
cat >"$future_out/.github/workflows/ci.yml" <<'EOF_FUTURE_CI'
name: Product CI
on: workflow_dispatch
jobs: {}
EOF_FUTURE_CI
git -C "$future_out" add -A
git -C "$future_out" commit -m "Add project-owned extensions" >/dev/null

printf '\nFuture managed core marker.\n' >>"$future_source/template/.project-agent-workflow/README.md"
git -C "$future_source" add template/.project-agent-workflow/README.md
git -C "$future_source" -c user.email=ci@example.invalid -c user.name=CI commit -m "Update managed core" >/dev/null
run_copier update -q -f --vcs-ref HEAD "$future_out" >/dev/null

grep -q 'Future managed core marker.' "$future_out/.project-agent-workflow/README.md"
grep -q 'Project AGENTS marker.' "$future_out/AGENTS.md"
grep -q 'Project README marker.' "$future_out/README.md"
grep -q 'project ignore marker' "$future_out/.gitignore"
grep -q 'project config marker' "$future_out/.codex/config.toml"
grep -q '"_project_owned_marker": true' "$future_out/.codex/hooks.json"
grep -q 'Project environment marker.' "$future_out/docs/agent/PROJECT_ENVIRONMENT.md"
grep -q 'Project policy marker.' "$future_out/docs/agent/PROJECT_POLICY.md"
grep -q 'project external-service marker' "$future_out/docs/agent/external-services.yaml"
grep -q 'Project plan marker.' "$future_out/docs/plan/README.md"
grep -q 'Project product marker.' "$future_out/docs/agent/SPEC_PRODUCT.md"
test -f "$future_out/.agents/skills/product-rules/SKILL.md"
grep -q 'name: Product CI' "$future_out/.github/workflows/ci.yml"
if find "$future_out" -name '*.rej' -print -quit | grep -q .; then
  echo "namespaced copier update produced rejection files" >&2
  exit 1
fi
if grep -R -n -E '^(<<<<<<<|=======|>>>>>>>)' "$future_out" --exclude-dir=.git >/dev/null; then
  echo "namespaced copier update produced inline conflict markers" >&2
  exit 1
fi
git -C "$future_out" diff --check

echo "copier update test passed"
