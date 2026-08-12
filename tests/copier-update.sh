#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
scratch_base=${SANDBOXED_PLAN_WORKER_SCRATCH_DIR:-${TMPDIR:-/tmp}}
tmp=$(mktemp -d "$scratch_base/project-agent-workflow-update.XXXXXX")
tmp=$(CDPATH= cd -- "$tmp" && pwd -P)
source_head_before=$(git -C "$root" rev-parse HEAD)
source_status_before=$(git -C "$root" status --porcelain=v1 --untracked-files=all)

cleanup() {
  result=$?
  trap - EXIT HUP INT TERM
  source_head_after=$(git -C "$root" rev-parse HEAD 2>/dev/null || true)
  source_status_after=$(git -C "$root" status --porcelain=v1 --untracked-files=all 2>/dev/null || true)
  if [ "$source_head_after" != "$source_head_before" ] || [ "$source_status_after" != "$source_status_before" ]; then
    echo "Copier fixture mutated the source repository" >&2
    result=1
  fi
  rm -rf "$tmp"
  exit "$result"
}
trap cleanup EXIT HUP INT TERM
. "$root/tests/lib-copier.sh"

require_fixture_path() {
  fixture_path=$1
  fixture_resolved=$(CDPATH= cd -- "$fixture_path" && pwd -P)
  case "$fixture_resolved" in
    "$tmp"|"$tmp"/*) ;;
    *)
      echo "refusing fixture Git operation outside temporary root: $fixture_resolved" >&2
      exit 1
      ;;
  esac
}

fixture_git() {
  fixture_repository=$1
  shift
  require_fixture_path "$fixture_repository"
  git -C "$fixture_repository" "$@"
}

fixture_clone() {
  fixture_source=$1
  fixture_destination=$2
  fixture_parent=$(dirname -- "$fixture_destination")
  require_fixture_path "$fixture_parent"
  git clone -q "$fixture_source" "$fixture_destination"
}

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
if ! command -v copier >/dev/null 2>&1; then
  mkdir -p "$tmp/bin"
  cat >"$tmp/bin/copier" <<'EOF_COPIER_SHIM'
#!/bin/sh
exec env UV_CACHE_DIR="$COPIER_TEST_CACHE" uv run --project "$COPIER_TEST_ROOT" copier "$@"
EOF_COPIER_SHIM
  chmod +x "$tmp/bin/copier"
  COPIER_TEST_CACHE="$tmp/uv-cache"
  COPIER_TEST_ROOT="$root"
  export COPIER_TEST_CACHE COPIER_TEST_ROOT
  PATH="$tmp/bin:$PATH"
  export PATH
fi
earliest_ref=${COPIER_UPDATE_EARLIEST_REF:-v0.3.1}
oldest_ref=${COPIER_UPDATE_OLDEST_REF:-v0.4.1}
latest_ref=${COPIER_UPDATE_LATEST_REF:-v0.4.6}
target_commit=${COPIER_UPDATE_TARGET_REF:-HEAD}
update_source="$tmp/update-source"
fixture_clone "$root" "$update_source"
fixture_git "$update_source" fetch -q "$root" "$target_commit"
fixture_git "$update_source" switch -q -c migration-target FETCH_HEAD
fixture_git "$update_source" merge-base --is-ancestor v1.2.1 HEAD
for candidate_path in \
  copier.yml \
  scripts/validate-copier-update.py \
  template/README.md.jinja \
  template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md \
  template/.project-agent-workflow/scripts/update-from-copier.sh \
  template/.project-agent-workflow/scripts/validate-copier-update.py \
  template/.agents/skills/browser-ops/SKILL.md \
  template/.project-agent-workflow/AGENTS.md.jinja \
  template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja \
  template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja \
  template/.project-agent-workflow/ownership.yaml \
  template/.project-agent-workflow/skills/browser-ops/SKILL.md \
  template/.project-agent-workflow/skills/browser-ops/agents/openai.yaml \
  template/.project-agent-workflow/skills/browser-ops/references/browser-run-policy.md \
  template/docs/agent/external-services.yaml.jinja
do
  mkdir -p "$(dirname "$update_source/$candidate_path")"
  cp "$root/$candidate_path" "$update_source/$candidate_path"
done
fixture_git "$update_source" add \
  copier.yml \
  scripts/validate-copier-update.py \
  template/README.md.jinja \
  template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md \
  template/.project-agent-workflow/scripts/update-from-copier.sh \
  template/.project-agent-workflow/scripts/validate-copier-update.py \
  template/.agents/skills/browser-ops/SKILL.md \
  template/.project-agent-workflow/AGENTS.md.jinja \
  template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja \
  template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja \
  template/.project-agent-workflow/ownership.yaml \
  template/.project-agent-workflow/skills/browser-ops/SKILL.md \
  template/.project-agent-workflow/skills/browser-ops/agents/openai.yaml \
  template/.project-agent-workflow/skills/browser-ops/references/browser-run-policy.md \
  template/docs/agent/external-services.yaml.jinja
fixture_git "$update_source" -c user.name=CI -c user.email=ci@example.invalid \
  commit -qm "Make Copier updates fail closed"
fixture_git "$update_source" tag v1.2.2
target_ref=v1.2.2

browser_legacy_out="$tmp/browser-run-legacy-policy"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.1 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$update_source" "$browser_legacy_out" >/dev/null
fixture_git "$browser_legacy_out" init -b main >/dev/null
fixture_git "$browser_legacy_out" config user.email "ci@example.invalid"
fixture_git "$browser_legacy_out" config user.name "CI"
fixture_git "$browser_legacy_out" add -A
fixture_git "$browser_legacy_out" commit -m "Initial older generated workflow" >/dev/null
if grep -q '^  browser_run:$' "$browser_legacy_out/docs/agent/external-services.yaml"; then
  echo "older Browser Run fixture unexpectedly contains browser_run" >&2
  exit 1
fi
browser_legacy_policy_before="$tmp/browser-run-legacy-policy-before.yaml"
cp "$browser_legacy_out/docs/agent/external-services.yaml" "$browser_legacy_policy_before"
run_copier update -q --trust --defaults --vcs-ref "$target_ref" "$browser_legacy_out" >/dev/null
if ! cmp -s "$browser_legacy_policy_before" "$browser_legacy_out/docs/agent/external-services.yaml"; then
  echo "Copier update changed project-owned older external-service policy bytes" >&2
  exit 1
fi
if grep -q '^  browser_run:$' "$browser_legacy_out/docs/agent/external-services.yaml"; then
  echo "Copier update rewrote project-owned older external-service policy" >&2
  exit 1
fi
(cd "$browser_legacy_out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py check >/dev/null)
test -f "$browser_legacy_out/.agents/skills/browser-ops/SKILL.md"
test -f "$browser_legacy_out/.project-agent-workflow/skills/browser-ops/references/browser-run-policy.md"
fixture_git "$browser_legacy_out" diff --check

validator="$root/scripts/validate-copier-update.py"

initial_copy="$tmp/non-git-initial-copy"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.2 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$update_source" "$initial_copy" >/dev/null
python3 "$validator" --destination "$initial_copy" >/dev/null
test -x "$initial_copy/.project-agent-workflow/scripts/update-from-copier.sh"
cmp "$validator" "$initial_copy/.project-agent-workflow/scripts/validate-copier-update.py"
if "$initial_copy/.project-agent-workflow/scripts/update-from-copier.sh" -f >/dev/null 2>&1; then
  echo "Copier update wrapper accepted -f" >&2
  exit 1
fi
if "$initial_copy/.project-agent-workflow/scripts/update-from-copier.sh" --force >/dev/null 2>&1; then
  echo "Copier update wrapper accepted --force" >&2
  exit 1
fi

validator_out="$tmp/validator-fixture"
mkdir -p "$validator_out/.github/workflows" "$validator_out/scripts"
fixture_git "$validator_out" init -b main >/dev/null
fixture_git "$validator_out" config user.email "ci@example.invalid"
fixture_git "$validator_out" config user.name "CI"
cat >"$validator_out/.gitignore" <<'EOF_VALIDATOR_IGNORE'
*.rej
EOF_VALIDATOR_IGNORE
printf 'baseline\n' >"$validator_out/product.txt"
printf 'optional workflow\n' >"$validator_out/.github/workflows/codex-ci-autofix.yml"
printf 'optional helper\n' >"$validator_out/scripts/skillspector-scan.sh"
fixture_git "$validator_out" add -A
fixture_git "$validator_out" commit -m "Create validator fixture" >/dev/null

printf 'ignored rejection\n' >"$validator_out/ignored-result.rej"
if python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted an ignored rejection file" >&2
  exit 1
fi
rm -f "$validator_out/ignored-result.rej"

printf '%s\n' \
  '<<<<<<< project' \
  'project value' \
  '=======' \
  'template value' \
  '>>>>>>> template' >"$validator_out/conflicted.txt"
if python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted a complete conflict block" >&2
  exit 1
fi
rm -f "$validator_out/conflicted.txt"

printf '<<<<<<< incomplete marker only\n' >"$tmp/symlink-conflict-target"
ln -s "$tmp/symlink-conflict-target" "$validator_out/linked-result.rej"
python3 "$validator" --destination "$validator_out" >/dev/null

rm -f "$validator_out/.github/workflows/codex-ci-autofix.yml" "$validator_out/scripts/skillspector-scan.sh"
python3 "$validator" --destination "$validator_out" >/dev/null
rm -f "$validator_out/product.txt"
if python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted an unclassified tracked deletion" >&2
  exit 1
fi
fixture_git "$validator_out" checkout -q -- product.txt .github/workflows/codex-ci-autofix.yml scripts/skillspector-scan.sh

base_blob=$(fixture_git "$validator_out" rev-parse HEAD:product.txt)
ours_blob=$(printf 'project value\n' | fixture_git "$validator_out" hash-object -w --stdin)
theirs_blob=$(printf 'template value\n' | fixture_git "$validator_out" hash-object -w --stdin)
{
  printf '100644 %s 1\tproduct.txt\n' "$base_blob"
  printf '100644 %s 2\tproduct.txt\n' "$ours_blob"
  printf '100644 %s 3\tproduct.txt\n' "$theirs_blob"
} | fixture_git "$validator_out" update-index --index-info
if python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted an unmerged index" >&2
  exit 1
fi
fixture_git "$validator_out" reset -q --hard HEAD

real_git=$(command -v git)
mkdir -p "$tmp/failing-git"
cat >"$tmp/failing-git/git" <<EOF_FAILING_GIT
#!/bin/sh
if [ "\${LC_ALL:-}" != C ] || [ "\${LANG:-}" != C ]; then
  echo "Git inspection did not use the C locale" >&2
  exit 9
fi
if [ "\${3:-}" = rev-parse ]; then
  exec "$real_git" "\$@"
fi
echo "simulated Git inspection failure" >&2
exit 7
EOF_FAILING_GIT
chmod +x "$tmp/failing-git/git"
if PATH="$tmp/failing-git:$PATH" python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted a Git inspection failure" >&2
  exit 1
fi

boundary_clean="$tmp/v121-to-v122-clean"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.1 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$update_source" "$boundary_clean" >/dev/null
fixture_git "$boundary_clean" init -b main >/dev/null
fixture_git "$boundary_clean" config user.email "ci@example.invalid"
fixture_git "$boundary_clean" config user.name "CI"
fixture_git "$boundary_clean" add -A
fixture_git "$boundary_clean" commit -m "Create v1.2.1 boundary fixture" >/dev/null
run_copier update -q --trust --defaults --vcs-ref v1.2.2 "$boundary_clean" >/dev/null
grep -q '^_commit: v1.2.2$' "$boundary_clean/.copier-answers.yml"
test -x "$boundary_clean/.project-agent-workflow/scripts/update-from-copier.sh"
python3 "$validator" --destination "$boundary_clean" >/dev/null

boundary_conflict="$tmp/v121-to-v122-conflict"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.1 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$update_source" "$boundary_conflict" >/dev/null
fixture_git "$boundary_conflict" init -b main >/dev/null
fixture_git "$boundary_conflict" config user.email "ci@example.invalid"
fixture_git "$boundary_conflict" config user.name "CI"
fixture_git "$boundary_conflict" add -A
fixture_git "$boundary_conflict" commit -m "Create conflicting v1.2.1 boundary fixture" >/dev/null
sed -i 's|2\. Run `copier update --trust` without force-overwriting local conflicts\.|2. Run the project-specific update command without replacing this line.|' \
  "$boundary_conflict/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md"
grep -q 'project-specific update command' "$boundary_conflict/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md"
fixture_git "$boundary_conflict" add .project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
fixture_git "$boundary_conflict" commit -m "Customize the update instruction" >/dev/null
if run_copier update -q --trust --defaults --vcs-ref v1.2.2 "$boundary_conflict" >/dev/null 2>&1; then
  echo "v1.2.2 after migration accepted a same-line merge conflict" >&2
  exit 1
fi
if ! fixture_git "$boundary_conflict" ls-files -u | grep -q .; then
  echo "v1.2.1-to-v1.2.2 fixture did not create a real index conflict" >&2
  exit 1
fi

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
    (cd "$root" && UV_CACHE_DIR="$tmp/uv-cache" uv run python \
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
  fixture_git "$out" init -b main >/dev/null
  fixture_git "$out" config user.email "ci@example.invalid"
  fixture_git "$out" config user.name "CI"
  fixture_git "$out" add -A
  fixture_git "$out" commit -m "Initial generated workflow" >/dev/null

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
  fixture_git "$out" add docs/agent/SPEC_PRODUCT.md docs/agent/PROJECT_ENVIRONMENT.md docs/agent/PROJECT_UI_DESIGN.md
  fixture_git "$out" commit -m "Add local project notes" >/dev/null
  if [ "$lane" = "earliest-supported" ]; then
    status_before=$(fixture_git "$out" status --porcelain=v1)
    if run_copier update -q -f --trust --vcs-ref "$target_ref" "$out" >/dev/null 2>&1; then
      echo "direct pre-v1 copier update unexpectedly succeeded" >&2
      exit 1
    fi
    status_after=$(fixture_git "$out" status --porcelain=v1)
    [ "$status_after" = "$status_before" ]
    test ! -e "$out/.project-agent-workflow"
    test ! -e "$out/.project-agent-workflow-migration"
  fi
  run_adoption "$out" "$target_ref" "$@" >/dev/null
  printf '%s\n' "$out"
}

assert_agent_profiles() {
  out=$1
  grep -qE '^[[:space:]]*model = "gpt-5.6-sol"$' "$out/.codex/agents/change_reviewer.toml"
  grep -qE '^[[:space:]]*model_reasoning_effort = "high"$' "$out/.codex/agents/change_reviewer.toml"
  grep -qE '^[[:space:]]*model = "gpt-5.6-luna"$' "$out/.codex/agents/docs_researcher.toml"
  grep -qE '^[[:space:]]*model_reasoning_effort = "medium"$' "$out/.codex/agents/docs_researcher.toml"
  grep -qE '^[[:space:]]*model = "gpt-5.6-luna"$' "$out/.codex/agents/evidence_synthesizer.toml"
  grep -qE '^[[:space:]]*model_reasoning_effort = "xhigh"$' "$out/.codex/agents/evidence_synthesizer.toml"
  grep -qE '^[[:space:]]*model = "gpt-5.6-luna"$' "$out/.codex/agents/repo_explorer.toml"
  grep -qE '^[[:space:]]*model_reasoning_effort = "low"$' "$out/.codex/agents/repo_explorer.toml"
  grep -qE '^[[:space:]]*model = "gpt-5.6-terra"$' "$out/.codex/agents/scoped_worker.toml"
  grep -qE '^[[:space:]]*model_reasoning_effort = "medium"$' "$out/.codex/agents/scoped_worker.toml"
  grep -qE '^[[:space:]]*model = "gpt-5.3-codex-spark"$' "$out/.codex/agents/fast_scoped_worker.toml"
  grep -qE '^[[:space:]]*model_reasoning_effort = "medium"$' "$out/.codex/agents/fast_scoped_worker.toml"
  grep -qE '^[[:space:]]*model = "gpt-5.3-codex-spark"$' "$out/.codex/agents/sequential_plan_worker.toml"
  grep -qE '^[[:space:]]*model_reasoning_effort = "medium"$' "$out/.codex/agents/sequential_plan_worker.toml"
}

validate_common_lane() {
  out=$1
  expect_legacy_root=${2:-1}
  expected_ci_autofix=${3:-disabled}
  managed_agents="$out/.project-agent-workflow/AGENTS.md"
  managed_orchestration="$out/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"

  assert_managed_orchestration_reports() {
    test -f "$managed_agents"
    test -f "$managed_orchestration"
    grep -Eqi 'without waiting for per-task user instruction|without requiring a per-task user instruction' "$managed_agents" "$managed_orchestration"
    grep -qi 'final ownership' "$managed_agents"
    grep -q 'final high-risk' "$managed_agents" "$managed_orchestration"
    grep -q 'authorization decisions' "$managed_agents" "$managed_orchestration"
    grep -q 'external writes' "$managed_agents" "$managed_orchestration"
    grep -q 'main session' "$managed_agents" "$managed_orchestration"
    grep -Eqi 'final report transparency is mandatory|final report must state whether helpers were used' "$managed_agents" "$managed_orchestration"
    grep -qi 'helpers were used' "$managed_agents" "$managed_orchestration"
    grep -qi 'context files read-only' "$managed_orchestration" "$managed_agents"
  }

  assert_managed_orchestration_reports

  test -f "$out/.copier-answers.yml"
  test -f "$out/.project-agent-workflow/AGENTS.md"
  test -f "$out/.project-agent-workflow/docs/agent/spec-index.yaml"
  test -f "$out/.project-agent-workflow/docs/agent/SPEC_FILE_MANAGEMENT.md"
  test -f "$out/.project-agent-workflow/docs/agent/SPEC_HUMAN_REPORTING.md"
  test -f "$out/.project-agent-workflow/human-report.json"
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
  test -f "$out/.project-agent-workflow/scripts/human-report.py"
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
  if [ "$expect_legacy_root" = "1" ]; then
    test -f "$out/scripts/create-plan.sh"
  else
    test ! -f "$out/scripts/create-plan.sh"
  fi
  grep -q 'Local project-owned agent notes.' "$out/docs/agent/SPEC_PRODUCT.md"
  grep -q 'Preserve this project-owned environment policy.' "$out/docs/agent/PROJECT_ENVIRONMENT.md"
  grep -q 'Preserve this project-owned UI policy.' "$out/docs/agent/PROJECT_UI_DESIGN.md"
  grep -q 'Integration Checklist' "$out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
  grep -q "ci_autofix_mode: $expected_ci_autofix" "$out/.copier-answers.yml"
  grep -q 'human_report_mode: agent_select_local' "$out/.copier-answers.yml"
  grep -q '"mode": "agent_select_local"' "$out/.project-agent-workflow/human-report.json"
  grep -Fq "CI autofix mode: \`$expected_ci_autofix\`" "$out/.project-agent-workflow/AGENTS.md"
  if [ "$expected_ci_autofix" = "disabled" ]; then
    test ! -f "$out/.github/workflows/codex-ci-autofix.yml"
  else
    test -f "$out/.github/workflows/codex-ci-autofix.yml"
  fi
  test -f "$out/.codex/hooks/agent_log_event.py"
  grep -q 'Compatibility bridge' "$out/.codex/hooks/agent_log_event.py"
  if [ -f "$out/.codex/hooks.json" ]; then
    grep -q 'stop_review_gate.py' "$out/.codex/hooks.json"
  fi
  grep -q 'repository-wide' "$out/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
  grep -q 'main agent owns' "$out/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
  grep -q 'Do not delegate short deterministic commands' "$out/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
  grep -q 'external writes' "$out/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
  grep -q 'project-agent-workflow:managed-core:start' "$out/AGENTS.md"
  if fixture_git "$out" ls-files -u | grep -q .; then
    echo "namespaced adoption left an unmerged index: $out" >&2
    exit 1
  fi
  fixture_git "$out" diff --diff-filter=D --name-only | while IFS= read -r path; do
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
  fixture_git "$out" diff --check
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
  (cd "$out" && python3 .project-agent-workflow/scripts/format-plan-docs.py --check)
  (cd "$out" && python3 .project-agent-workflow/scripts/check-codex-toml.py >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py check >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/structure-map.py --check >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/security-static-check.py --managed >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/validate-changes.py --all >/dev/null)
  if (cd "$out" && HEADROOM_DISABLED=1 .project-agent-workflow/scripts/context-compress.sh .project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md namespaced-policy >/dev/null 2>&1); then
    echo "context-compress.sh accepted namespaced normative policy after adoption: $out" >&2
    exit 1
  fi
  test ! -e "$out/.agent-logs/namespaced-policy"
  python3 "$root/scripts/check-copier-template.py" --print-generated-required | while IFS= read -r path; do
    [ -n "$path" ] || continue
    test -f "$out/$path"
  done
  assert_agent_profiles "$out"
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

pre_v1_plan_out="$tmp/v050-managed-index-plans"
run_copier copy -q -f --vcs-ref v0.5.0 --data-file "$root/tests/fixtures/python.answers.yml" "$update_source" "$pre_v1_plan_out" >/dev/null
fixture_git "$pre_v1_plan_out" init -b main >/dev/null
fixture_git "$pre_v1_plan_out" config user.email "ci@example.invalid"
fixture_git "$pre_v1_plan_out" config user.name "CI"
fixture_git "$pre_v1_plan_out" add -A
fixture_git "$pre_v1_plan_out" commit -m "Initial v0.5.0 workflow" >/dev/null

pre_v1_active=docs/plan/active/901-pre-v1-validation.md
pre_v1_checked=docs/plan/checked/2025/01/01-15/900-pre-v1-checked.md
mkdir -p "$pre_v1_plan_out/docs/plan/active" "$pre_v1_plan_out/docs/plan/checked/2025/01/01-15"
cat >"$pre_v1_plan_out/$pre_v1_active" <<'EOF_PRE_V1_ACTIVE'
# Pre-v1 validation plan

status: in_progress
task_types:
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - scripts/security-static-check.py
context_files:
  - docs/agent/spec-index.yaml
required_specs:
  - docs/agent/SPEC_VALIDATION.md
  - docs/agent/SPEC_GIT_WORKFLOW.md
  - docs/agent/SPEC_FILE_MANAGEMENT.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_DEVELOPMENT_FLOW.md
  - docs/agent/SPEC_SECURITY.md
validation:
  - python3 scripts/security-static-check.py
  - python3 scripts/lint-plan-docs.py
acceptance:
  - Preserve the open plan across adoption.
checked_summary_ja: 移行前の作業計画を維持する。

## Tasks

- [ ] Preserve the open plan.
EOF_PRE_V1_ACTIVE
cat >"$pre_v1_plan_out/$pre_v1_checked" <<'EOF_PRE_V1_CHECKED'
# Pre-v1 checked plan

status: checked
task_types:
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - scripts/security-static-check.py
context_files:
  - docs/agent/spec-index.yaml
required_specs:
  - docs/agent/SPEC_VALIDATION.md
  - docs/agent/SPEC_GIT_WORKFLOW.md
  - docs/agent/SPEC_FILE_MANAGEMENT.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_DEVELOPMENT_FLOW.md
  - docs/agent/SPEC_SECURITY.md
validation:
  - python3 scripts/security-static-check.py
  - python3 scripts/lint-plan-docs.py
acceptance:
  - Preserve the checked plan across adoption.
checked_summary_ja: 移行前の完了記録を維持する。

## Tasks

- [x] Preserve the checked plan.

## Validation Notes

- Pre-v1 validation passed.
EOF_PRE_V1_CHECKED
(cd "$pre_v1_plan_out" && python3 scripts/lint-plan-docs.py --add-active 901 "$pre_v1_active")
(cd "$pre_v1_plan_out" && python3 scripts/lint-plan-docs.py --append-checked 900 "$pre_v1_checked")
(cd "$pre_v1_plan_out" && python3 scripts/lint-plan-docs.py)
fixture_git "$pre_v1_plan_out" add -A
fixture_git "$pre_v1_plan_out" commit -m "Add pre-v1 managed-index plan history" >/dev/null
active_digest_before=$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/$pre_v1_active")
active_index_digest_before=$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/docs/plan/plan.md")
checked_digest_before=$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/$pre_v1_checked")
checked_index_digest_before=$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/docs/plan/checked.md")
for legacy_cli in scripts/lint-plan-docs.py scripts/security-static-check.py scripts/validate-changes.py; do
  source_digest=$(fixture_git "$update_source" show "v0.5.0:template/$legacy_cli" | git hash-object --stdin)
  destination_digest=$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/$legacy_cli")
  test "$destination_digest" = "$source_digest"
done

run_adoption "$pre_v1_plan_out" "$target_ref" >/dev/null
manifest="$pre_v1_plan_out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json"
if ! grep -q '^def has_pre_v1_adoption_provenance()' "$pre_v1_plan_out/.project-agent-workflow/scripts/planlib.py"; then
  echo "adoption did not install the candidate managed plan compatibility helper" >&2
  exit 1
fi
python3 - "$manifest" "$pre_v1_plan_out" <<'PY_PRE_V1_BRIDGES'
import json
import stat
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
repository = Path(sys.argv[2])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
expected_paths = {
    "scripts/lint-plan-docs.py",
    "scripts/security-static-check.py",
    "scripts/validate-changes.py",
}
bridged = set(manifest.get("bridged_legacy_cli_paths", []))
missing = sorted(expected_paths - bridged)
if missing:
    raise SystemExit(f"adoption manifest is missing bridged legacy CLI paths: {missing}")
if manifest.get("operation") != "recopy_adoption" or manifest.get("previous_ref") != "v0.5.0":
    raise SystemExit("adoption manifest has unexpected pre-v1 provenance")
if "docs/agent/spec-index.yaml" not in set(manifest.get("adoption_copied", [])):
    raise SystemExit("adoption manifest did not preserve the pre-v1 routing index")

for relative in sorted(expected_paths):
    path = repository / relative
    managed = f".project-agent-workflow/{relative}"
    expected = f'''#!/usr/bin/env python3
"""Compatibility bridge to Copier-managed workflow."""

from __future__ import annotations

import os
import sys
from pathlib import Path


managed = Path(__file__).resolve().parents[1] / "{managed}"
os.execv(sys.executable, [sys.executable, str(managed), *sys.argv[1:]])
'''
    if path.read_text(encoding="utf-8") != expected:
        raise SystemExit(f"legacy CLI is not the deterministic compatibility bridge: {relative}")
    if stat.S_IMODE(path.stat().st_mode) != 0o755:
        raise SystemExit(f"legacy CLI bridge is not executable: {relative}")
PY_PRE_V1_BRIDGES
test "$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/$pre_v1_active")" = "$active_digest_before"
test "$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/docs/plan/plan.md")" = "$active_index_digest_before"
test "$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/$pre_v1_checked")" = "$checked_digest_before"
test "$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/docs/plan/checked.md")" = "$checked_index_digest_before"
(cd "$pre_v1_plan_out" && PYTHONDONTWRITEBYTECODE=1 python3 - "$pre_v1_active" <<'PY_PRE_V1_PLAN'
import sys
from pathlib import Path

sys.path.insert(0, ".project-agent-workflow/scripts")
import plan_validation_commands
import planlib

if not planlib.has_pre_v1_adoption_provenance():
    raise SystemExit("managed plan lint did not recognize pre-v1 adoption provenance")
plan_validation_commands.check_legacy_plan_for_lint(Path(sys.argv[1]), Path.cwd())
PY_PRE_V1_PLAN
)
(cd "$pre_v1_plan_out" && python3 scripts/validate-changes.py --all >/dev/null)
(cd "$pre_v1_plan_out" && python3 .project-agent-workflow/scripts/validate-changes.py --all >/dev/null)
(cd "$pre_v1_plan_out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
fixture_git "$pre_v1_plan_out" diff --check

v100_out=$(prepare_lane v100-repair v1.0.0 "$root/tests/fixtures/python.answers.yml")
(cd "$v100_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
validate_common_lane "$v100_out" 0 patch_only
grep -q '^_commit: v1.2.2$' "$v100_out/.copier-answers.yml"

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
fixture_git "$modified_out" init -b main >/dev/null
fixture_git "$modified_out" config user.email "ci@example.invalid"
fixture_git "$modified_out" config user.name "CI"
fixture_git "$modified_out" add -A
fixture_git "$modified_out" commit -m "Initial generated workflow" >/dev/null
printf '\n# project-owned modification\n' >>"$modified_out/scripts/skillspector-scan.sh"
fixture_git "$modified_out" add scripts/skillspector-scan.sh
fixture_git "$modified_out" commit -m "Customize SkillSpector helper" >/dev/null
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
fixture_git "$modified_out" diff --check

mature_out="$tmp/mature-customized-project"
run_copier copy -q -f --vcs-ref "$latest_ref" --data-file "$root/tests/fixtures/python.answers.yml" "$update_source" "$mature_out" >/dev/null
fixture_git "$mature_out" init -b main >/dev/null
fixture_git "$mature_out" config user.email "ci@example.invalid"
fixture_git "$mature_out" config user.name "CI"
fixture_git "$mature_out" add -A
fixture_git "$mature_out" commit -m "Initial generated workflow" >/dev/null

printf '\n# project agent marker\n' >>"$mature_out/.codex/agents/docs_researcher.toml"
printf '\n# project agent marker\n' >>"$mature_out/.codex/agents/scoped_worker.toml"
printf '\n# legacy hook marker\n' >>"$mature_out/.codex/hooks/pre_tool_hardening_gate.py"
printf '\n# legacy hook marker\n' >>"$mature_out/.codex/hooks/stop_review_gate.py"
cat >"$mature_out/.codex/hooks.json" <<'EOF_MATURE_HOOKS'
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 scripts/project-hook.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 .codex/hooks/agent_log_event.py --event Stop"
          }
        ]
      }
    ]
  }
}
EOF_MATURE_HOOKS
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
cat >"$mature_out/.codex/agents/docs_researcher.toml" <<'EOF_MATURE_DOCS_RESEARCHER'
name = "docs_researcher"
description = "Customized docs_researcher profile."
  model = "legacy-model"
  model_reasoning_effort = "legacy-effort"
sandbox_mode = "workspace-write"

developer_instructions = """
Keep this project instruction.
"""
EOF_MATURE_DOCS_RESEARCHER
cat >"$mature_out/.codex/agents/repo_explorer.toml" <<'EOF_MATURE_REPO_EXPLORER'
  name = "repo_explorer"
  description = "Customized repo_explorer profile."
sandbox_mode = "workspace-write"

developer_instructions = """
Keep this project instruction.
"""
EOF_MATURE_REPO_EXPLORER
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
fixture_git "$mature_out" add -A
fixture_git "$mature_out" commit -m "Customize mature project workflow" >/dev/null

run_adoption "$mature_out" "$target_ref" >/dev/null
(cd "$mature_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
validate_common_lane "$mature_out"
grep -q 'Keep this project instruction.' "$mature_out/.codex/agents/docs_researcher.toml"
grep -q 'Keep this project instruction.' "$mature_out/.codex/agents/repo_explorer.toml"
grep -q '^  model = "gpt-5.6-luna"$' "$mature_out/.codex/agents/docs_researcher.toml"
grep -q '^  model_reasoning_effort = "medium"$' "$mature_out/.codex/agents/docs_researcher.toml"
if grep -q 'legacy-model' "$mature_out/.codex/agents/docs_researcher.toml" || grep -q 'legacy-effort' "$mature_out/.codex/agents/docs_researcher.toml"; then
  echo "normalized agent profile left legacy model values" >&2
  exit 1
fi
grep -q '^  model = "gpt-5.6-luna"$' "$mature_out/.codex/agents/repo_explorer.toml"
grep -q '^  model_reasoning_effort = "low"$' "$mature_out/.codex/agents/repo_explorer.toml"
grep -q '^  name = "repo_explorer"$' "$mature_out/.codex/agents/repo_explorer.toml"
grep -q '^  description = "Customized repo_explorer profile\."' "$mature_out/.codex/agents/repo_explorer.toml"
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
grep -q 'Compatibility bridge' "$mature_out/.codex/hooks/stop_review_gate.py"
grep -q 'scripts/project-hook.py' "$mature_out/.codex/hooks.json"
grep -q '.project-agent-workflow/hooks/stop_review_gate.py' "$mature_out/.codex/hooks.json"
test "$(grep -c 'stop_review_gate.py' "$mature_out/.codex/hooks.json")" -eq 1
grep -q 'scripts/validate-project-adoption.sh' "$mature_out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json"

repair_out="$tmp/v110-preserved-hooks"
run_copier copy -q -f --vcs-ref v1.1.0 --data-file "$root/tests/fixtures/typescript.answers.yml" "$update_source" "$repair_out" >/dev/null
fixture_git "$repair_out" init -b main >/dev/null
fixture_git "$repair_out" config user.email "ci@example.invalid"
fixture_git "$repair_out" config user.name "CI"
cat >"$repair_out/.codex/hooks.json" <<'EOF_REPAIR_HOOKS'
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 .codex/hooks/agent_log_event.py --event Stop"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 scripts/project-hook.py"
          }
        ]
      }
    ]
  }
}
EOF_REPAIR_HOOKS
fixture_git "$repair_out" add -A
fixture_git "$repair_out" commit -m "Preserve pre-v1 Hook configuration" >/dev/null
run_copier update -q -f --trust --vcs-ref v1.2.1 "$repair_out" >/dev/null
grep -q 'scripts/project-hook.py' "$repair_out/.codex/hooks.json"
grep -q '.project-agent-workflow/hooks/stop_review_gate.py' "$repair_out/.codex/hooks.json"
test "$(grep -c 'stop_review_gate.py' "$repair_out/.codex/hooks.json")" -eq 1
grep -q 'Compatibility bridge' "$repair_out/.codex/hooks/stop_review_gate.py"
fixture_git "$repair_out" diff --check

v111_out="$tmp/v111-without-plan-placeholders"
run_copier copy -q -f --vcs-ref v1.1.1 --data-file "$root/tests/fixtures/python.answers.yml" "$update_source" "$v111_out" >/dev/null
fixture_git "$v111_out" init -b main >/dev/null
fixture_git "$v111_out" config user.email "ci@example.invalid"
fixture_git "$v111_out" config user.name "CI"
fixture_git "$v111_out" add -A
fixture_git "$v111_out" commit -m "Initial v1.1.1 workflow" >/dev/null
for plan_dir in active backlog checked handoffs; do
  test -f "$v111_out/docs/plan/$plan_dir/.gitkeep"
  fixture_git "$v111_out" rm -q "docs/plan/$plan_dir/.gitkeep"
done
fixture_git "$v111_out" commit -m "Remove plan directory placeholders" >/dev/null
run_copier update -q -f --trust --vcs-ref v1.2.1 "$v111_out" >/dev/null
assert_agent_profiles "$v111_out"
for plan_dir in active backlog checked handoffs; do
  if [ -e "$v111_out/docs/plan/$plan_dir/.gitkeep" ]; then
    echo "copier update recreated removed plan placeholder: docs/plan/$plan_dir/.gitkeep" >&2
    exit 1
  fi
done
grep -q '^_commit: v1.2.1$' "$v111_out/.copier-answers.yml"
fixture_git "$v111_out" diff --check

future_source="$update_source"
future_out="$tmp/future-project"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.2 --data-file "$root/tests/fixtures/typescript.answers.yml" "$future_source" "$future_out" >/dev/null
fixture_git "$future_out" init -b main >/dev/null
fixture_git "$future_out" config user.email "ci@example.invalid"
fixture_git "$future_out" config user.name "CI"
fixture_git "$future_out" add -A
fixture_git "$future_out" commit -m "Initial namespaced workflow" >/dev/null

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
fixture_git "$future_out" add -A
fixture_git "$future_out" commit -m "Add project-owned extensions" >/dev/null

sed -i 's|Update files here through `copier update` and do not add project-specific policy or runtime facts here\.|Update files here through the generated update wrapper; keep project-specific policy and runtime facts outside this core.|' \
  "$future_source/template/.project-agent-workflow/README.md"
grep -q 'generated update wrapper' "$future_source/template/.project-agent-workflow/README.md"
fixture_git "$future_source" add template/.project-agent-workflow/README.md
fixture_git "$future_source" -c user.email=ci@example.invalid -c user.name=CI commit -m "Update managed core through the wrapper" >/dev/null
fixture_git "$future_source" tag v1.2.3

outside_cwd="$tmp/outside-cwd"
mkdir -p "$outside_cwd"
if [ -n "$(fixture_git "$future_out" status --porcelain=v1)" ]; then
  echo "clean recurring wrapper fixture is dirty before update" >&2
  fixture_git "$future_out" status --short >&2
  exit 1
fi
if ! (cd "$outside_cwd" && "$future_out/.project-agent-workflow/scripts/update-from-copier.sh" --defaults --vcs-ref v1.2.3 >/dev/null); then
  echo "clean recurring Copier wrapper update failed" >&2
  exit 1
fi

grep -q 'generated update wrapper' "$future_out/.project-agent-workflow/README.md"
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
fixture_git "$future_out" diff --check

wrapper_conflict_out="$tmp/v122-to-v123-conflict"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.2 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$future_source" "$wrapper_conflict_out" >/dev/null
fixture_git "$wrapper_conflict_out" init -b main >/dev/null
fixture_git "$wrapper_conflict_out" config user.email "ci@example.invalid"
fixture_git "$wrapper_conflict_out" config user.name "CI"
fixture_git "$wrapper_conflict_out" add -A
fixture_git "$wrapper_conflict_out" commit -m "Create recurring wrapper fixture" >/dev/null
sed -i 's|Update files here through `copier update` and do not add project-specific policy or runtime facts here\.|Keep this project-specific managed-core instruction for the conflict fixture.|' \
  "$wrapper_conflict_out/.project-agent-workflow/README.md"
grep -q 'project-specific managed-core instruction' "$wrapper_conflict_out/.project-agent-workflow/README.md"
fixture_git "$wrapper_conflict_out" add .project-agent-workflow/README.md
fixture_git "$wrapper_conflict_out" commit -m "Customize the recurring update line" >/dev/null
if [ -n "$(fixture_git "$wrapper_conflict_out" status --porcelain=v1)" ]; then
  echo "conflicting recurring wrapper fixture is dirty before update" >&2
  fixture_git "$wrapper_conflict_out" status --short >&2
  exit 1
fi
if (cd "$outside_cwd" && "$wrapper_conflict_out/.project-agent-workflow/scripts/update-from-copier.sh" --defaults --vcs-ref v1.2.3 >/dev/null 2>&1); then
  echo "recurring Copier wrapper accepted a same-line merge conflict" >&2
  exit 1
fi
if ! fixture_git "$wrapper_conflict_out" ls-files -u | grep -q .; then
  echo "v1.2.2-to-v1.2.3 fixture did not create a real index conflict" >&2
  exit 1
fi

echo "copier update test passed"
