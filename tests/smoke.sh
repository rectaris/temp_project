#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
scratch_base=${SANDBOXED_PLAN_WORKER_SCRATCH_DIR:-${TMPDIR:-/tmp}}
tmp=$(mktemp -d "$scratch_base/project-agent-workflow-smoke.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
. "$root/tests/lib-copier.sh"
source_ref=${COPIER_SMOKE_REF:-}
render_source=$root

run_root_python() {
  if command -v uv >/dev/null 2>&1 && [ -f "$root/pyproject.toml" ]; then
    (cd "$root" && UV_CACHE_DIR="$tmp/uv-cache" uv run python "$@")
  else
    python3 "$@"
  fi
}

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

if [ -z "$source_ref" ]; then
  render_source="$tmp/render-source"
  git clone -q "$root" "$render_source"
  for candidate_path in \
    copier.yml \
    scripts/migrate-sequential-plan-worker.py \
    scripts/validate-copier-update.py \
    template/README.md.jinja \
    template/.github/workflows/project-agent-workflow.yml \
    template/.github/workflows/codex-ci-autofix.yml.jinja \
    template/.project-agent-workflow/docs/agent/CODEX_CI_AUTOFIX.md \
    template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md \
    template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md \
    template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md \
    template/.project-agent-workflow/docs/agent/SPEC_SECURITY.md \
    template/.project-agent-workflow/scripts/check-external-service-policy.py \
    template/.project-agent-workflow/scripts/lint-plan-docs.py \
    template/.project-agent-workflow/scripts/migrate-sequential-plan-worker.py \
    template/.project-agent-workflow/scripts/planlib.py \
    template/.project-agent-workflow/scripts/restructure-plan.py \
    template/.project-agent-workflow/scripts/plan-execution-state.py \
    template/docs/plan/replanned.md \
    template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py \
    template/.project-agent-workflow/scripts/sync-plan-to-linear.sh \
    template/.project-agent-workflow/scripts/validate-changes.py \
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
    template/.project-agent-workflow/skills/graph-memory/SKILL.md \
    template/.project-agent-workflow/skills/linear-ops/SKILL.md \
    template/.project-agent-workflow/skills/mcp-ops/SKILL.md \
    template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md \
    template/docs/agent/external-services.yaml.jinja
  do
    mkdir -p "$(dirname "$render_source/$candidate_path")"
    cp "$root/$candidate_path" "$render_source/$candidate_path"
  done
  git -C "$render_source" add \
    copier.yml \
    scripts/migrate-sequential-plan-worker.py \
    scripts/validate-copier-update.py \
    template/README.md.jinja \
    template/.github/workflows/project-agent-workflow.yml \
    template/.github/workflows/codex-ci-autofix.yml.jinja \
    template/.project-agent-workflow/docs/agent/CODEX_CI_AUTOFIX.md \
    template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md \
    template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md \
    template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md \
    template/.project-agent-workflow/docs/agent/SPEC_SECURITY.md \
    template/.project-agent-workflow/scripts/check-external-service-policy.py \
    template/.project-agent-workflow/scripts/lint-plan-docs.py \
    template/.project-agent-workflow/scripts/migrate-sequential-plan-worker.py \
    template/.project-agent-workflow/scripts/planlib.py \
    template/.project-agent-workflow/scripts/restructure-plan.py \
    template/.project-agent-workflow/scripts/plan-execution-state.py \
    template/docs/plan/replanned.md \
    template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py \
    template/.project-agent-workflow/scripts/sync-plan-to-linear.sh \
    template/.project-agent-workflow/scripts/validate-changes.py \
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
    template/.project-agent-workflow/skills/graph-memory/SKILL.md \
    template/.project-agent-workflow/skills/linear-ops/SKILL.md \
    template/.project-agent-workflow/skills/mcp-ops/SKILL.md \
    template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md \
    template/docs/agent/external-services.yaml.jinja
  git -C "$render_source" -c user.name=CI -c user.email=ci@example.invalid \
    commit --allow-empty -qm "Create isolated smoke candidate"
  git -C "$render_source" tag v1.2.2
  source_ref=v1.2.2
fi

render_fixture() {
  fixture=$1
  out=$2
  set -- copy -q -f --trust --data-file "$fixture"
  if [ -n "$source_ref" ]; then
    set -- "$@" --vcs-ref "$source_ref"
  fi
  set -- "$@" "$render_source" "$out"
  run_copier "$@" >/dev/null
}

render_defaults() {
  out=$1
  set -- copy -q -f --trust --defaults
  if [ -n "$source_ref" ]; then
    set -- "$@" --vcs-ref "$source_ref"
  fi
  run_copier "$@" "$render_source" "$out" >/dev/null
}

assert_generated_inventory() {
  out=$1
  fixture=$2
  expected="$tmp/expected-inventory-$$"
  actual="$tmp/actual-inventory-$$"
  python3 "$root/scripts/check-copier-template.py" --print-expected-generated "$fixture" >"$expected"
  find "$out" -type f -printf '%P\n' | LC_ALL=C sort >"$actual"
  diff -u "$expected" "$actual"
}

assert_managed_orchestration_reports() {
  out=$1
  managed_agents="$out/.project-agent-workflow/AGENTS.md"
  managed_orchestration="$out/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"

  grep -Eqi 'without waiting for per-task user instruction|without requiring a per-task user instruction' "$managed_agents" "$managed_orchestration"
  grep -qi 'final ownership' "$managed_agents"
  grep -q 'authorization decisions' "$managed_agents" "$managed_orchestration"
  grep -q 'external writes' "$managed_agents" "$managed_orchestration"
  grep -q 'main session' "$managed_agents" "$managed_orchestration"
  grep -Eqi 'final report transparency is mandatory|final report must state whether helpers were used' "$managed_agents" "$managed_orchestration"
  grep -qi 'helpers were used' "$managed_agents" "$managed_orchestration"
  grep -qi 'advisory' "$managed_orchestration"
  grep -qi 'repository breadth alone is insufficient' "$managed_agents" "$managed_orchestration"
  grep -q 'implementation_risk' "$managed_agents" "$managed_orchestration"
  grep -q 'implementation_ambiguity' "$managed_agents" "$managed_orchestration"
  grep -qi 'admissible implementation slice' "$managed_orchestration"
  grep -qi 'state path outside the repository' "$managed_orchestration"
  grep -qi 'skipped known-unavailable starts' "$managed_orchestration"
  grep -qi 'aggregate patch' "$managed_orchestration"
  grep -qi 'at most two correction rounds' "$managed_orchestration"
  grep -qi 'candidate generation and correction do not run plan validation' "$managed_orchestration"
  grep -q 'focused_validation' "$managed_orchestration"
  grep -qi 'bounded parent implementation' "$managed_orchestration"
}

assert_ci_autofix_validation_graph() {
  workflow=$1
  grep -q '^  prepare:$' "$workflow"
  grep -q '^  generate-fix:$' "$workflow"
  if grep -q '^  validate-patch:\|^  apply-patch:\|^  patch-only-notice:' "$workflow"; then
    echo "generated CI autofix workflow retained a removed write graph" >&2
    exit 1
  fi
  if grep -q 'direct-push\|max_attempts\|git push\|createComment\|git commit' "$workflow"; then
    echo "generated CI autofix workflow retained a removed direct-write marker" >&2
    exit 1
  fi
  if grep -Eq '^\s*permissions:\s+(write|write-all)$|^\s+[A-Za-z0-9_-]+:\s+write(-all)?$' "$workflow"; then
    echo "generated CI autofix workflow retained a write permission" >&2
    exit 1
  fi
  grep -Fq 'let mode = "patch-only";' "$workflow"
  grep -Fq 'set("mode", mode);' "$workflow"
  grep -Fq 'git status --porcelain=v1 --untracked-files=all' "$workflow"
  grep -Fq 'git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]' "$workflow"
  grep -Fq 'dependency setup changed tracked, staged, or non-ignored untracked paths' "$workflow"
  grep -Fq 'git diff --quiet "origin/${BASE_BRANCH}...HEAD" -- .github/codex/prompts/ci-autofix.md' "$workflow"
  grep -Fq 'git show "origin/${BASE_BRANCH}:.github/codex/prompts/ci-autofix.md" > "$RUNNER_TEMP/codex-ci-autofix-prompt.md"' "$workflow"
  python3 - "$workflow" <<'PY'
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")


def job(name: str) -> str:
    match = re.search(
        rf"^  {re.escape(name)}:\n.*?(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise SystemExit(f"generated CI autofix workflow missing job: {name}")
    return match.group(0)


jobs_section = text.split("jobs:\n", 1)[1]
jobs = re.findall(r"^  ([a-zA-Z0-9_-]+):\n", jobs_section, re.MULTILINE)
if jobs != ["prepare", "generate-fix"]:
    raise SystemExit(f"generated CI autofix workflow has unexpected jobs: {jobs}")
for marker in ("permissions: write", "permissions: write-all", "contents: write", "pull-requests: write"):
    if marker in text:
        raise SystemExit(f"generated CI autofix workflow has write marker: {marker}")
PY
}

assert_dependency_setup_rejection() {
  fixture="$tmp/dependency-mutation-fixture"
  mkdir -p "$fixture"
  git -C "$fixture" init -q -b main
  git -C "$fixture" config user.email ci@example.invalid
  git -C "$fixture" config user.name CI
  printf 'baseline\n' >"$fixture/tracked.txt"
  printf 'staged baseline\n' >"$fixture/staged.txt"
  git -C "$fixture" add tracked.txt staged.txt
  git -C "$fixture" commit -qm baseline
  cat >"$fixture/installer.sh" <<'EOF_INSTALLER'
#!/bin/sh
set -eu
printf 'installer changed\n' > tracked.txt
printf 'installer staged\n' > staged.txt
git add staged.txt
printf 'installer created\n' > generated.txt
EOF_INSTALLER
  chmod +x "$fixture/installer.sh"
  (cd "$fixture" && ./installer.sh)
  if (
    cd "$fixture" &&
    git diff --quiet &&
    git diff --cached --quiet &&
    [ -z "$(git ls-files --others --exclude-standard)" ]
  ); then
    echo "dependency mutation fixture was not rejected" >&2
    exit 1
  fi
  test -n "$(git -C "$fixture" status --porcelain=v1 --untracked-files=all)"
}

assert_dependency_setup_rejection

assert_generated_whitespace_range() {
  out=$1
  workflow="$out/.github/workflows/project-agent-workflow.yml"

  grep -Fq 'BASE_SHA: ${{ github.event.pull_request.base.sha }}' "$workflow"
  grep -Fq 'BEFORE_SHA: ${{ github.event.before }}' "$workflow"
  grep -Fq 'PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}' "$workflow"
  grep -Fq 'REF_TYPE: ${{ github.ref_type }}' "$workflow"
  grep -Fq 'git diff --check "$BASE_SHA...$PR_HEAD_SHA"' "$workflow"
  grep -Fq 'git diff --check "$HEAD_SHA^..$HEAD_SHA"' "$workflow"
  grep -Fq 'git diff --check "$BEFORE_SHA..$HEAD_SHA"' "$workflow"
  grep -Fq 'EMPTY_TREE=$(git hash-object -t tree /dev/null)' "$workflow"
  grep -Fq 'git diff --check "$EMPTY_TREE" "$HEAD_SHA"' "$workflow"

  git -C "$out" init -b whitespace-range-main >/dev/null
  git -C "$out" add .
  git -C "$out" -c user.name=CI -c user.email=ci@example.invalid commit -qm 'Baseline generated project'
  before_sha=$(git -C "$out" rev-parse HEAD)
  printf 'committed trailing whitespace \n' >"$out/committed-whitespace.txt"
  git -C "$out" add committed-whitespace.txt
  git -C "$out" -c user.name=CI -c user.email=ci@example.invalid commit -qm 'Add whitespace regression fixture'
  head_sha=$(git -C "$out" rev-parse HEAD)
  if git -C "$out" diff --check "$before_sha..$head_sha" >/dev/null 2>&1; then
    echo "generated workflow push range missed committed trailing whitespace" >&2
    exit 1
  fi
}

run_plan_lifecycle_smoke() {
  out=$1
  (cd "$out" && .project-agent-workflow/scripts/create-plan.sh active sample --summary "Sample work." --summary-ja "サンプル作業を行う。" >/dev/null)
  (cd "$out" && test -f docs/plan/active/001-sample.md)
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
  (cd "$out" && .project-agent-workflow/scripts/select-task-context.sh docs/plan/active/001-sample.md | grep -q '^TASK_TYPES=environment_data_flow$')
  (cd "$out" && .project-agent-workflow/scripts/select-task-context.sh docs/plan/active/001-sample.md | grep -q '^WRITE_SCOPE=TBD$')
  (cd "$out" && .project-agent-workflow/scripts/select-task-context.sh docs/plan/active/001-sample.md | grep -q '^CONTEXT_FILES=$')
  if grep -q '^expected_output:' "$out/docs/plan/active/001-sample.md"; then
    echo "create-plan emitted removed expected_output field" >&2
    exit 1
  fi
  (cd "$out" && .project-agent-workflow/scripts/clean-handoffs.sh --dry-run >/dev/null)
  sed -i 's/^- \[ \] TBD$/- [x] TBD/' "$out/docs/plan/active/001-sample.md"
  printf 'smoke validation passed\n' >>"$out/docs/plan/active/001-sample.md"
  (cd "$out" && .project-agent-workflow/scripts/complete-plan.sh docs/plan/active/001-sample.md >/dev/null)
  archive_path=$(cd "$out" && .project-agent-workflow/scripts/finalize-active-plan.sh docs/plan/active/001-sample.md)
  case "$archive_path" in
    docs/plan/checked/[0-9][0-9][0-9][0-9]/[0-9][0-9]/01-15/001-sample.md) ;;
    docs/plan/checked/[0-9][0-9][0-9][0-9]/[0-9][0-9]/16-31/001-sample.md) ;;
    *) echo "unexpected checked archive path: $archive_path" >&2; exit 1 ;;
  esac
  test -f "$out/$archive_path"
  grep -q '^status: checked$' "$out/$archive_path"
  printf '%s\n' "$archive_path" >"$out/.sample-archive-path"
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
}

run_plan_archive_compatibility_smoke() {
  out=$1
  archive_path=$(cat "$out/.sample-archive-path")
  original="$out/.sample-archive-original.md"
  cp "$out/$archive_path" "$original"

  sed -i \
    -e '0,/  - git diff --check/s//  - historical-validation-record/' \
    -e '0,/  - environment_data_flow/s//  - historical_removed_route/' \
    -e '0,/  - \.project-agent-workflow\/docs\/agent\/SPEC_VALIDATION\.md/s//  - docs\/agent\/HISTORICAL_VALIDATION.md/' \
    "$out/$archive_path"
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
  if (cd "$out" && python3 .project-agent-workflow/scripts/plan_validation_commands.py check-plan "$archive_path" >/dev/null 2>&1); then
    echo "explicit plan validation accepted a historical non-allowlisted command" >&2
    exit 1
  fi

  sed -i '/^task_types:/a\  - historical_removed_route' "$out/$archive_path"
  if (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
    echo "lint-plan-docs accepted duplicate historical task types" >&2
    exit 1
  fi
  cp "$original" "$out/$archive_path"
  sed -i '/^checked_summary_ja:/d' "$out/$archive_path"
  if (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
    echo "lint-plan-docs accepted a checked archive with a missing required field" >&2
    exit 1
  fi
  cp "$original" "$out/$archive_path"
  rm "$original"
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
}

write_legacy_lint_bridge() {
  destination=$1
  mkdir -p "$destination/scripts"
  cat >"$destination/scripts/lint-plan-docs.py" <<'EOF_LEGACY_LINT_BRIDGE'
#!/usr/bin/env python3
"""Compatibility bridge to Copier-managed workflow."""

from __future__ import annotations

import os
import sys
from pathlib import Path


managed = Path(__file__).resolve().parents[1] / ".project-agent-workflow/scripts/lint-plan-docs.py"
os.execv(sys.executable, [sys.executable, str(managed), *sys.argv[1:]])
EOF_LEGACY_LINT_BRIDGE
  chmod 0755 "$destination/scripts/lint-plan-docs.py"
}

run_pre_v1_plan_compatibility_smoke() {
  out=$1
  mkdir -p "$out/docs/agent"
  cat >"$out/docs/agent/spec-index.yaml" <<'EOF_LEGACY_SPEC_INDEX'
version: 1

default_reads:
  - docs/agent/SPEC_VALIDATION.md

task_types:
  environment_data_flow:
    required:
      - docs/agent/SPEC_ENVIRONMENT.md

rules: []
EOF_LEGACY_SPEC_INDEX
  write_legacy_lint_bridge "$out"

  legacy_plan=docs/plan/active/997-pre-v1-plan.md
  cat >"$out/$legacy_plan" <<'EOF_PRE_V1_PLAN'
# Pre-v1 plan

status: in_progress
task_types:
  - environment_data_flow
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - src/legacy.ts
context_files:
  - none
required_specs:
  - docs/agent/SPEC_VALIDATION.md
  - docs/agent/SPEC_ENVIRONMENT.md
validation:
  - python3 scripts/lint-plan-docs.py
  - git diff --check
acceptance:
  - Preserve the pre-v1 plan.
checked_summary_ja: v1 より前の計画を維持する。

## Tasks

- [ ] Preserve the plan.
EOF_PRE_V1_PLAN
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --add-active 997 "$legacy_plan")
  if (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
    echo "lint-plan-docs accepted root compatibility aliases without adoption provenance" >&2
    exit 1
  fi
  mkdir -p "$out/.project-agent-workflow-migration/v1-pre-namespace"
  cat >"$out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json" <<'EOF_ADOPTION_MANIFEST'
{
  "adoption_copied": ["docs/agent/spec-index.yaml"],
  "bridged_legacy_cli_paths": ["scripts/lint-plan-docs.py"],
  "operation": "recopy_adoption",
  "previous_ref": "v0.5.0"
}
EOF_ADOPTION_MANIFEST
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)

  if (cd "$out" && python3 .project-agent-workflow/scripts/plan_validation_commands.py check-plan "$legacy_plan" >/dev/null 2>&1); then
    echo "explicit plan validation accepted a pre-v1 root command alias" >&2
    exit 1
  fi
  printf '# modified project script\n' >>"$out/scripts/lint-plan-docs.py"
  if (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
    echo "lint-plan-docs accepted a modified pre-v1 root command alias" >&2
    exit 1
  fi
  write_legacy_lint_bridge "$out"
  sed -i 's|python3 scripts/lint-plan-docs.py|python3 scripts/lint-plan-docs.py; rm -rf .|' "$out/$legacy_plan"
  if (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
    echo "lint-plan-docs accepted shell syntax in a pre-v1 validation command" >&2
    exit 1
  fi
  sed -i 's|python3 scripts/lint-plan-docs.py; rm -rf .|python3 scripts/lint-plan-docs.py|' "$out/$legacy_plan"

  managed_plan=$(cd "$out" && .project-agent-workflow/scripts/create-plan.sh active managed-root-alias --summary "Managed root alias." --summary-ja "managed 計画の root alias を拒否する。")
  sed -i 's|  - git diff --check|  - python3 scripts/lint-plan-docs.py|' "$out/$managed_plan"
  if (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
    echo "lint-plan-docs accepted a root command alias in a managed plan" >&2
    exit 1
  fi
  sed -i 's|  - python3 scripts/lint-plan-docs.py|  - git diff --check|' "$out/$managed_plan"
  sed -i '0,/  - \.project-agent-workflow\/docs\/agent\/SPEC_VALIDATION\.md/s//  - docs\/agent\/SPEC_VALIDATION.md/' "$out/$managed_plan"
  if (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
    echo "lint-plan-docs accepted a root policy alias in a managed plan" >&2
    exit 1
  fi
  managed_base=$(basename "$managed_plan")
  managed_id=${managed_base%%-*}
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --remove-active "$managed_id")
  rm "$out/$managed_plan"

  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --remove-active 997)
  rm "$out/$legacy_plan" "$out/scripts/lint-plan-docs.py" "$out/docs/agent/spec-index.yaml"
  rm "$out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json"
  rmdir "$out/.project-agent-workflow-migration/v1-pre-namespace" "$out/.project-agent-workflow-migration"
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
}

run_plan_fail_closed_smoke() {
  out=$1

  evidence_plan=$(cd "$out" && .project-agent-workflow/scripts/create-plan.sh active evidence-gate --summary "Evidence gate." --summary-ja "完了根拠を確認する。")
  sed -i 's/^- \[ \] TBD$/-  [ ] TBD/' "$out/$evidence_plan"
  evidence_base=$(basename "$evidence_plan")
  evidence_id=${evidence_base%%-*}
  if (cd "$out" && .project-agent-workflow/scripts/complete-plan.sh "$evidence_plan" >/dev/null 2>&1); then
    echo "complete-plan accepted unchecked tasks" >&2
    exit 1
  fi
  grep -q '^status: in_progress$' "$out/$evidence_plan"
  grep -q "^$evidence_id[[:space:]]$evidence_plan[[:space:]]in_progress$" "$out/docs/plan/plan.md"
  sed -i 's/^-  \[ \] TBD$/- [x] TBD/' "$out/$evidence_plan"
  printf '%s\n' '1. Pending validation.' >>"$out/$evidence_plan"
  if (cd "$out" && .project-agent-workflow/scripts/complete-plan.sh "$evidence_plan" >/dev/null 2>&1); then
    echo "complete-plan accepted pending Validation Notes" >&2
    exit 1
  fi
  grep -q '^status: in_progress$' "$out/$evidence_plan"
  grep -q "^$evidence_id[[:space:]]$evidence_plan[[:space:]]in_progress$" "$out/docs/plan/plan.md"
  sed -i 's/^1\. Pending validation\.$/- focused validation passed/' "$out/$evidence_plan"
  (cd "$out" && .project-agent-workflow/scripts/complete-plan.sh "$evidence_plan" >/dev/null)
  evidence_archive=$(cd "$out" && .project-agent-workflow/scripts/finalize-active-plan.sh "$evidence_plan")
  grep -q '^status: checked$' "$out/$evidence_archive"
  sed -i 's/^status: checked$/status: ready_to_archive/' "$out/$evidence_archive"
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
  sed -i 's/^status: ready_to_archive$/status: checked/' "$out/$evidence_archive"

  archive_plan=$(cd "$out" && .project-agent-workflow/scripts/create-plan.sh active archive-preflight --summary "Archive preflight." --summary-ja "アーカイブ前提条件を確認する。")
  archive_base=$(basename "$archive_plan")
  archive_id=${archive_base%%-*}
  sed -i 's/^- \[ \] TBD$/- [x] TBD/' "$out/$archive_plan"
  printf 'archive preflight validation passed\n' >>"$out/$archive_plan"
  (cd "$out" && .project-agent-workflow/scripts/complete-plan.sh "$archive_plan" >/dev/null)
  sed -i "s/^$archive_id\t\(.*\)\tready_to_archive$/$archive_id\t\1\tin_progress/" "$out/docs/plan/plan.md"
  if (cd "$out" && .project-agent-workflow/scripts/finalize-active-plan.sh "$archive_plan" >/dev/null 2>&1); then
    echo "finalize-active-plan accepted a mismatched active index" >&2
    exit 1
  fi
  test -f "$out/$archive_plan"
  sed -i "s/^$archive_id\t\(.*\)\tin_progress$/$archive_id\t\1\tready_to_archive/" "$out/docs/plan/plan.md"
  archive_year=$(date +%Y)
  archive_month=$(date +%m)
  archive_day=$(date +%d)
  case "$archive_day" in 0[1-9]|1[0-5]) archive_half=01-15 ;; *) archive_half=16-31 ;; esac
  collision_dst="docs/plan/checked/$archive_year/$archive_month/$archive_half/$archive_base"
  mkdir -p "$out/docs/plan/checked/$archive_year/$archive_month/$archive_half"
  printf 'existing archive\n' >"$out/$collision_dst"
  if (cd "$out" && .project-agent-workflow/scripts/finalize-active-plan.sh "$archive_plan" >/dev/null 2>&1); then
    echo "finalize-active-plan overwrote an existing archive" >&2
    exit 1
  fi
  test -f "$out/$archive_plan"
  rm "$out/$collision_dst"
  archive_result=$(cd "$out" && .project-agent-workflow/scripts/finalize-active-plan.sh "$archive_plan")
  grep -q '^status: checked$' "$out/$archive_result"

  destination_plan=$(cd "$out" && .project-agent-workflow/scripts/create-plan.sh backlog promotion-destination --summary "Promotion destination." --summary-ja "昇格先の競合を確認する。")
  destination_base=$(basename "$destination_plan")
  cp "$out/$destination_plan" "$out/docs/plan/active/$destination_base"
  if (cd "$out" && .project-agent-workflow/scripts/promote-plan.sh "$destination_plan" >/dev/null 2>&1); then
    echo "promote-plan overwrote an existing destination" >&2
    exit 1
  fi
  test -f "$out/$destination_plan"
  rm "$out/docs/plan/active/$destination_base"

  id_plan=$(cd "$out" && .project-agent-workflow/scripts/create-plan.sh backlog promotion-id --summary "Promotion id." --summary-ja "計画 ID の競合を確認する。")
  id_base=$(basename "$id_plan")
  id_value=${id_base%%-*}
  mkdir -p "$out/docs/plan/checked/2000/01/01-15"
  legacy_path="docs/plan/checked/2000/01/01-15/$id_value-legacy.md"
  sed 's/^status: .*/status: checked/' "$out/$id_plan" >"$out/$legacy_path"
  if (cd "$out" && .project-agent-workflow/scripts/promote-plan.sh "$id_plan" >/dev/null 2>&1); then
    echo "promote-plan accepted a duplicate plan id" >&2
    exit 1
  fi
  test -f "$out/$id_plan"
  rm "$out/$legacy_path"

  index_plan=$(cd "$out" && .project-agent-workflow/scripts/create-plan.sh backlog promotion-index --summary "Promotion index." --summary-ja "索引の競合を確認する。")
  index_base=$(basename "$index_plan")
  index_id=${index_base%%-*}
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --add-active "$index_id" "docs/plan/active/$index_base")
  if (cd "$out" && .project-agent-workflow/scripts/promote-plan.sh "$index_plan" >/dev/null 2>&1); then
    echo "promote-plan accepted a conflicting active index mapping" >&2
    exit 1
  fi
  test -f "$out/$index_plan"
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --remove-active "$index_id")

  mapping_plan=$(cd "$out" && .project-agent-workflow/scripts/create-plan.sh active index-id-mapping --summary "Index ID mapping." --summary-ja "索引 ID を確認する。")
  mapping_base=$(basename "$mapping_plan")
  mapping_id=${mapping_base%%-*}
  sed -i "s/^$mapping_id\t/999\t/" "$out/docs/plan/plan.md"
  if (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
    echo "lint-plan-docs accepted an index ID that differs from the filename" >&2
    exit 1
  fi
  sed -i "s/^999\t/$mapping_id\t/" "$out/docs/plan/plan.md"

  concurrent_dst=docs/plan/active/998-concurrent-destination.md
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --copy-status-exclusive "$mapping_plan" "$concurrent_dst" in_progress >/dev/null 2>&1) &
  copy_pid_one=$!
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --copy-status-exclusive "$mapping_plan" "$concurrent_dst" in_progress >/dev/null 2>&1) &
  copy_pid_two=$!
  copy_successes=0
  if wait "$copy_pid_one"; then copy_successes=$((copy_successes + 1)); fi
  if wait "$copy_pid_two"; then copy_successes=$((copy_successes + 1)); fi
  [ "$copy_successes" -eq 1 ] || { echo "exclusive plan copy expected one successful writer" >&2; exit 1; }
  test -f "$out/$concurrent_dst"
  rm "$out/$concurrent_dst"

  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --remove-active "$mapping_id")
  rm "$out/$mapping_plan"

  unsafe_validation=$(cd "$out" && .project-agent-workflow/scripts/create-plan.sh active unsafe-validation --summary "Unsafe validation." --summary-ja "危険な検証コマンドを拒否する。")
  unsafe_base=$(basename "$unsafe_validation")
  unsafe_id=${unsafe_base%%-*}
  sed -i 's|  - git diff --check|  - rm -rf .|' "$out/$unsafe_validation"
  if (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-manifest "$unsafe_validation" >/dev/null 2>&1); then
    echo "lint-plan-docs accepted an unsafe validation command" >&2
    exit 1
  fi
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --remove-active "$unsafe_id")
  rm "$out/$unsafe_validation"

  deferred_plan=$(cd "$out" && .project-agent-workflow/scripts/create-plan.sh active deferred-work --summary "Deferred work." --summary-ja "延期状態を確認する。")
  deferred_base=$(basename "$deferred_plan")
  deferred_id=${deferred_base%%-*}
  sed -i 's/^status: in_progress$/status: deferred/; /^checked_summary_ja:/a completion_deferred_reason: Waiting for an external prerequisite.' "$out/$deferred_plan"
  sed -i "s/^$deferred_id\t\(.*\)\tin_progress$/$deferred_id\t\1\tdeferred/" "$out/docs/plan/plan.md"
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
  if (cd "$out" && .project-agent-workflow/scripts/complete-plan.sh "$deferred_plan" >/dev/null 2>&1); then
    echo "complete-plan archived deferred work" >&2
    exit 1
  fi
  grep -q '^status: deferred$' "$out/$deferred_plan"
  grep -q "^$deferred_id[[:space:]]$deferred_plan[[:space:]]deferred$" "$out/docs/plan/plan.md"
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --remove-active "$deferred_id")
  rm "$out/$deferred_plan"

  replan_plan=$(cd "$out" && .project-agent-workflow/scripts/create-plan.sh active replan-required --summary "Replan required." --summary-ja "再構成停止状態を確認する。")
  replan_base=$(basename "$replan_plan")
  replan_id=${replan_base%%-*}
  sed -i 's/^status: in_progress$/status: replan_required/; /^checked_summary_ja:/a replan_reason_codes:\n  - multiple_independent_invariants' "$out/$replan_plan"
  sed -i "s/^$replan_id\t\(.*\)\tin_progress$/$replan_id\t\1\treplan_required/" "$out/docs/plan/plan.md"
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
  if (cd "$out" && .project-agent-workflow/scripts/complete-plan.sh "$replan_plan" >/dev/null 2>&1); then
    echo "complete-plan archived replan-required work" >&2
    exit 1
  fi
  sed -i 's/multiple_independent_invariants/unbounded_custom_reason/' "$out/$replan_plan"
  if (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
    echo "lint-plan-docs accepted an unknown replan reason" >&2
    exit 1
  fi
  sed -i 's/unbounded_custom_reason/multiple_independent_invariants/' "$out/$replan_plan"
  replanned_path="docs/plan/replanned/2000/01/01-15/$replan_base"
  mkdir -p "$out/docs/plan/replanned/2000/01/01-15"
  sed \
    -e 's/^status: replan_required$/status: replanned/' \
    -e '/^replan_reason_codes:/i primary_invariant: preserve the source acceptance baseline\nreplan_source: docs/plan/active/001-source.md\nreplan_contract: docs/plan/replanned/contracts/001-source.json\nintegration_gates:\n  - combined source acceptance\nsuccessor_plans:\n  - docs/plan/active/002-successor.md\ninherited_acceptance_digests:\n  - sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
    "$out/$replan_plan" >"$out/$replanned_path"
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
  sed -i '/^replan_contract:/d' "$out/$replanned_path"
  if (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
    echo "lint-plan-docs accepted a replanned record with incomplete lineage" >&2
    exit 1
  fi
  sed -i '/^replan_source:/a replan_contract: docs/plan/replanned/contracts/001-source.json' "$out/$replanned_path"
  sed -i '/^successor_plans:/d; /^  - docs\/plan\/active\/002-successor.md$/d' "$out/$replanned_path"
  if (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
    echo "lint-plan-docs accepted replanned lineage without a successor" >&2
    exit 1
  fi
  rm "$out/$replanned_path"
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --remove-active "$replan_id")
  rm "$out/$replan_plan"
}

run_referent_contract_smoke() {
  out=$1
  contract=.agent-artifacts/referent-contracts/smoke/contract.json
  target=docs/referent-smoke.md
  (cd "$out" && python3 .project-agent-workflow/scripts/referent-contract.py init "$contract" --slug smoke --task-kind naming --source docs/source.md --target "$target" --mode advisory >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/referent-contract.py review-unknowns "$contract" --none)
  (cd "$out" && python3 .project-agent-workflow/scripts/referent-contract.py add-referent "$contract" --id R1 --purpose 'exercise generated lifecycle' --concrete-target 'generated smoke target' --kind artifact --reasoning-role result --relation 'source precedes target' --evidence 'smoke fixture' --certainty confirmed)
  (cd "$out" && python3 .project-agent-workflow/scripts/referent-contract.py seal-referents "$contract" >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/referent-contract.py assign-label "$contract" --id R1 --label 'Smoke term' --definition 'Smoke term means generated smoke target.')
  (cd "$out" && python3 .project-agent-workflow/scripts/referent-contract.py finalize-labels "$contract")
  printf 'Smoke term means generated smoke target.\n' >"$out/$target"
  (cd "$out" && python3 .project-agent-workflow/scripts/referent-contract.py record-draft "$contract" >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/referent-contract.py close-advisory "$contract" --reason 'generated smoke completed')
  (cd "$out" && python3 .project-agent-workflow/scripts/referent-contract.py check "$contract" >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/referent-contract.py semantic-diff "$contract" | grep -q 'Smoke term')
}

run_human_report_smoke() {
  out=$1
  input=human-report-smoke.json
  python3 - "$out/$input" <<'PY'
from pathlib import Path
import json
import sys

report = {
    "version": 1,
    "title": "Generated <report>",
    "language": "en",
    "audience": "developer",
    "purpose": "decision",
    "summary": "Compare three generated-project options.",
    "facts": [
        {
            "label": "Plan policy",
            "value": "The generated plan README is present.",
            "certainty": "confirmed",
            "source": "docs/plan/README.md",
        }
    ],
    "decisions": [
        {
            "question": "Which option should be selected?",
            "options": [
                {"label": label, "summary": label, "advantages": [], "disadvantages": []}
                for label in ("A", "B", "C")
            ],
            "recommendation": "A",
            "reason": "Smoke validation.",
        }
    ],
    "relations": [],
    "risks": [],
    "next_actions": [],
    "presentation": {
        "explicit_html": False,
        "needs_cross_comparison": True,
        "needs_filtering": False,
    },
    "content_safety": {
        "reviewed": True,
        "contains_raw_logs": False,
        "contains_unredacted_sensitive_data": False,
    },
    "sources": ["docs/plan/README.md"],
}
Path(sys.argv[1]).write_text(json.dumps(report), encoding="utf-8")
PY
  (cd "$out" && python3 .project-agent-workflow/scripts/human-report.py assess "$input" | grep -q '"decision": "generate"')
  output=$(cd "$out" && python3 .project-agent-workflow/scripts/human-report.py render "$input" --report-id smoke-decision)
  test "$output" = ".agent-artifacts/human-reports/smoke-decision/index.html"
  test -f "$out/$output"
  grep -q '&lt;report&gt;' "$out/$output"
  grep -q 'docs/plan/README.md' "$out/$output"
  git -C "$out" check-ignore "$output" >/dev/null
  rm "$out/$input"
}

run_external_policy_smoke() {
  out=$1
  policy="$out/.agent-artifacts/external-services-configured.yaml"
  broad_policy="$out/.agent-artifacts/external-services-task-scoped.yaml"
  unsupported_policy="$out/.agent-artifacts/external-services-unsupported.yaml"
  ordinary_confirmation_policy="$out/.agent-artifacts/external-services-ordinary-confirmation.yaml"
  ordinary_denied_policy="$out/.agent-artifacts/external-services-ordinary-denied.yaml"
  mkdir -p "$out/.agent-artifacts"
  cat >"$policy" <<'EOF_EXTERNAL_POLICY'
version: 1
external_services:
  example:
    state: configured_write_capable
    connection: "local-example"
    authentication: environment
    credential_reference: "EXAMPLE_TOKEN"
    allowed_reads:
      - issue.read
    allowed_writes:
      - issue.update
    write_authorization_rule: "explicit-user-request"
    dry_run_or_local_validation: "preview"
    unavailable_fallback: "Keep the change local."
EOF_EXTERNAL_POLICY
  (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py --policy "$policy" check)
  (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py --policy "$policy" authorize example read issue.read)
  (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py --policy "$policy" authorize example write issue.update --authorization-rule explicit-user-request)
  if (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py --policy "$policy" authorize example write issue.update --authorization-rule stale-rule >/dev/null 2>&1); then
    echo "external-service validator accepted a mismatched write authorization rule" >&2
    exit 1
  fi
  sed -i 's|authentication: environment|authentication: platform|; s|credential_reference: "EXAMPLE_TOKEN"|credential_reference: "secret:example"|' "$policy"
  (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py --policy "$policy" check)
  sed -i 's|credential_reference: "secret:example"|credential_reference: "ghp_abcdefghijklmnopqrstuvwxyz1234567890"|' "$policy"
  if (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py --policy "$policy" check >/dev/null 2>&1); then
    echo "external-service validator accepted credential material as a platform identifier" >&2
    exit 1
  fi
  cat >"$broad_policy" <<'EOF_BROAD_EXTERNAL_POLICY'
version: 2
access_profile: task_scoped_default_allow
provider_requirement: runtime_configured
task_scope_rule: current_user_request
confirmation_required_effects:
  - remote_delete
  - public_communication
  - financial_commitment
  - production_change
  - access_control_change
denied_effects:
  - credential_material_transfer
  - secret_persistence
  - write_credentials_to_untrusted_code
unclassified_write_effect: require_confirmation
unavailable_fallback: "Keep work local."
external_services:
  example:
    unavailable_fallback: "Keep the example local."
EOF_BROAD_EXTERNAL_POLICY
  broad_check="python3 .project-agent-workflow/scripts/check-external-service-policy.py --policy $broad_policy"
  (cd "$out" && $broad_check check)
  (cd "$out" && $broad_check authorize example read issue.read --provider-configured --task-authorized --target issue-123 --effect ordinary)
  (cd "$out" && $broad_check authorize example write issue.update --provider-configured --task-authorized --target issue-123 --effect ordinary)
  if (cd "$out" && $broad_check authorize example write issue.delete --provider-configured --task-authorized --target issue-123 --effect remote_delete >/dev/null 2>&1); then
    echo "version 2 validator accepted deletion without exact confirmation" >&2
    exit 1
  fi
  (cd "$out" && $broad_check authorize example write issue.delete --provider-configured --task-authorized --target issue-123 --effect remote_delete --confirmed-target issue-123 --confirmed-effect remote_delete)
  if (cd "$out" && $broad_check authorize example write issue.delete --provider-configured --task-authorized --target issue-123 --effect remote_delete --confirmed-target issue-456 --confirmed-effect remote_delete >/dev/null 2>&1); then
    echo "version 2 validator accepted mismatched confirmation" >&2
    exit 1
  fi
  if (cd "$out" && $broad_check authorize example write secret.send --provider-configured --task-authorized --target provider --effect credential_material_transfer --confirmed-target provider --confirmed-effect credential_material_transfer >/dev/null 2>&1); then
    echo "version 2 validator accepted a denied credential effect" >&2
    exit 1
  fi
  if (cd "$out" && $broad_check authorize example read secret.query --provider-configured --task-authorized --target provider --effect credential_material_transfer >/dev/null 2>&1); then
    echo "version 2 validator accepted credential transfer during a read" >&2
    exit 1
  fi
  if (cd "$out" && $broad_check authorize example read secret.query --provider-configured --task-authorized --target provider --effect ordinary --effect credential_material_transfer >/dev/null 2>&1); then
    echo "version 2 validator let ordinary override credential transfer during a read" >&2
    exit 1
  fi
  if (cd "$out" && $broad_check authorize example write custom.write --provider-configured --task-authorized --target object-1 --effect custom_effect >/dev/null 2>&1); then
    echo "version 2 validator accepted an unclassified write without confirmation" >&2
    exit 1
  fi
  (cd "$out" && $broad_check authorize example write custom.write --provider-configured --task-authorized --target object-1 --effect custom_effect --confirmed-target object-1 --confirmed-effect custom_effect)
  if (cd "$out" && $broad_check authorize example read issue.read --task-authorized --target issue-123 --effect ordinary >/dev/null 2>&1); then
    echo "version 2 validator accepted a read without a configured provider" >&2
    exit 1
  fi
  if (cd "$out" && $broad_check authorize example read issue.read --provider-configured --task-authorized >/dev/null 2>&1); then
    echo "version 2 validator accepted a read without exact target and effect facts" >&2
    exit 1
  fi
  cp "$broad_policy" "$ordinary_confirmation_policy"
  sed -i '/^confirmation_required_effects:$/a\  - ordinary' "$ordinary_confirmation_policy"
  if (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py --policy "$ordinary_confirmation_policy" check >/dev/null 2>&1); then
    echo "version 2 validator accepted ordinary as a confirmation-required effect" >&2
    exit 1
  fi
  cp "$broad_policy" "$ordinary_denied_policy"
  sed -i '/^denied_effects:$/a\  - ordinary' "$ordinary_denied_policy"
  if (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py --policy "$ordinary_denied_policy" check >/dev/null 2>&1); then
    echo "version 2 validator accepted ordinary as a denied effect" >&2
    exit 1
  fi
  cp "$broad_policy" "$unsupported_policy"
  sed -i 's/^version: 2$/version: 3/' "$unsupported_policy"
  if (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py --policy "$unsupported_policy" check >/dev/null 2>&1); then
    echo "external-service validator accepted an unsupported policy version" >&2
    exit 1
  fi
}

for fixture in "$root"/tests/fixtures/*.answers.yml; do
  name=$(basename "$fixture" .answers.yml)
  out="$tmp/$name"
  render_fixture "$fixture" "$out"
  assert_generated_inventory "$out" "$fixture"
  assert_managed_orchestration_reports "$out"
  assert_generated_whitespace_range "$out"
  run_root_python "$root/tests/assert-generated-semantics.py" "$out"
  run_root_python "$root/scripts/check-yaml.py" "$out" >/dev/null
  REQUIRE_ACTIONLINT=${REQUIRE_ACTIONLINT:-0} "$root/scripts/lint-github-actions.sh" "$out"
  (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py check)
  git -C "$out" init -b main >/dev/null
  git -C "$out" diff --check
  git -C "$out" check-ignore .agent-logs/sample/manifest.json >/dev/null
  git -C "$out" check-ignore .agent-artifacts/sample/output.txt >/dev/null
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
  (cd "$out" && python3 .project-agent-workflow/scripts/format-plan-docs.py --check)
  (cd "$out" && python3 .project-agent-workflow/scripts/structure-map.py --check >/dev/null)
done

tab=$(printf '\t')
while IFS="$tab" read -r case_name primary_language human_report_mode codex_hooks_mode skillspector_mode external_access_profile mcp_policy_mode linear_sync_mode graph_memory_mode ci_autofix_mode; do
  [ "$case_name" != "case" ] || continue
  [ -n "$case_name" ] || continue
  fixture="$tmp/$case_name.answers.yml"
  out="$tmp/pairwise-$case_name"
  {
    printf 'project_name: %s\n' "$case_name"
    printf 'project_slug: %s\n' "$case_name"
    printf 'project_purpose: Exercise Copier pairwise generation.\n'
    printf 'primary_language: %s\n' "$primary_language"
    printf 'human_report_mode: %s\n' "$human_report_mode"
    printf 'codex_hooks_mode: %s\n' "$codex_hooks_mode"
    printf 'skillspector_mode: %s\n' "$skillspector_mode"
    printf 'external_access_profile: %s\n' "$external_access_profile"
    printf 'mcp_policy_mode: %s\n' "$mcp_policy_mode"
    printf 'linear_sync_mode: %s\n' "$linear_sync_mode"
    printf 'graph_memory_mode: %s\n' "$graph_memory_mode"
    printf 'ci_autofix_mode: %s\n' "$ci_autofix_mode"
  } >"$fixture"
  render_fixture "$fixture" "$out"
  assert_generated_inventory "$out" "$fixture"
  assert_managed_orchestration_reports "$out"
  run_root_python "$root/tests/assert-generated-semantics.py" "$out"
  run_root_python "$root/scripts/check-yaml.py" "$out" >/dev/null
  REQUIRE_ACTIONLINT=${REQUIRE_ACTIONLINT:-0} "$root/scripts/lint-github-actions.sh" "$out"
done <"$root/tests/fixtures/copier-pairwise.tsv"

default_out="$tmp/defaults"
render_defaults "$default_out"
assert_managed_orchestration_reports "$default_out"
run_root_python "$root/tests/assert-generated-semantics.py" "$default_out"
run_root_python "$root/scripts/check-yaml.py" "$default_out" >/dev/null
(cd "$default_out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py check)
run_root_python - "$default_out/.copier-answers.yml" <<'PY'
from pathlib import Path
import sys
import yaml

answers = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {
    "primary_language": "mixed",
    "human_report_mode": "agent_select_local",
    "codex_hooks_mode": "install_templates",
    "skillspector_mode": "disabled",
    "external_access_profile": "restricted",
    "mcp_policy_mode": "disabled",
    "linear_sync_mode": "disabled",
    "graph_memory_mode": "disabled",
    "ci_autofix_mode": "disabled",
}
actual = {key: answers.get(key) for key in expected}
if actual != expected:
    raise SystemExit(f"default Copier answers changed: expected={expected}, actual={actual}")
PY

assert_rejected_input() {
  label=$1
  question=$2
  value=$3
  if run_copier copy -f --trust --vcs-ref HEAD --data-file "$root/tests/fixtures/docs.answers.yml" --data "$question=$value" "$root" "$tmp/invalid-$label" >/dev/null 2>&1; then
    echo "copier accepted invalid input: $label" >&2
    exit 1
  fi
}

if run_copier copy -f --trust --vcs-ref HEAD --data-file "$root/tests/fixtures/docs.answers.yml" --data project_slug='invalid slug' "$root" "$tmp/invalid-slug" >/dev/null 2>&1; then
  echo "copier accepted an invalid project slug" >&2
  exit 1
fi
assert_rejected_input empty-name project_name ''
assert_rejected_input whitespace-name project_name '   '
assert_rejected_input empty-purpose project_purpose ''
multiline_name='First line
Second line'
assert_rejected_input multiline-name project_name "$multiline_name"
multiline_purpose='First line
Second line'
assert_rejected_input multiline-purpose project_purpose "$multiline_purpose"

run_plan_lifecycle_smoke "$tmp/typescript"
run_plan_archive_compatibility_smoke "$tmp/typescript"
run_pre_v1_plan_compatibility_smoke "$tmp/typescript"
run_plan_fail_closed_smoke "$tmp/typescript"
run_referent_contract_smoke "$tmp/typescript"
run_human_report_smoke "$tmp/typescript"
run_external_policy_smoke "$tmp/typescript"

bad_design=$(cd "$tmp/typescript" && .project-agent-workflow/scripts/create-plan.sh backlog bad-human-design --summary "Bad human design." --summary-ja "設計承認の不整合を確認する。")
sed -i 's/^human_design_required: .*/human_design_required: yes/' "$tmp/typescript/$bad_design"
if (cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
  echo "lint-plan-docs accepted human design outside Class C" >&2
  exit 1
fi
sed -i 's/^review_class: .*/review_class: C/' "$tmp/typescript/$bad_design"
if (cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
  echo "lint-plan-docs accepted Class C with human_approval_status: not_required" >&2
  exit 1
fi
rm "$tmp/typescript/$bad_design"

class_c=$(cd "$tmp/typescript" && .project-agent-workflow/scripts/create-plan.sh backlog class-c-approval --summary "Class C approval." --summary-ja "承認待ち計画を確認する。")
sed -i 's/^review_class: .*/review_class: C/; s/^human_design_required: .*/human_design_required: yes/; s/^human_approval_status: .*/human_approval_status: pending/' "$tmp/typescript/$class_c"
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
if (cd "$tmp/typescript" && .project-agent-workflow/scripts/promote-plan.sh "$class_c" >/dev/null 2>&1); then
  echo "promote-plan accepted an unapproved class C plan" >&2
  exit 1
fi
sed -i 's/^human_approval_status: .*/human_approval_status: approved/' "$tmp/typescript/$class_c"
class_c_active=$(cd "$tmp/typescript" && .project-agent-workflow/scripts/promote-plan.sh "$class_c")
grep -q '^status: in_progress$' "$tmp/typescript/$class_c_active"
sed -i 's/^- \[ \] TBD$/- [x] TBD/' "$tmp/typescript/$class_c_active"
printf 'class C lifecycle validation passed\n' >>"$tmp/typescript/$class_c_active"
(cd "$tmp/typescript" && .project-agent-workflow/scripts/complete-plan.sh "$class_c_active" >/dev/null)
(cd "$tmp/typescript" && .project-agent-workflow/scripts/finalize-active-plan.sh "$class_c_active" >/dev/null)

route_union=$(cd "$tmp/typescript" && .project-agent-workflow/scripts/create-plan.sh active route-union --summary "Route union." --summary-ja "複数ルートを確認する。")
sed -i '/^review_class:/i\  - security' "$tmp/typescript/$route_union"
if (cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
  echo "lint-plan-docs accepted a route union with missing required specs" >&2
  exit 1
fi
sed -i '/^validation:/i\  - .project-agent-workflow/docs/agent/SPEC_SECURITY.md' "$tmp/typescript/$route_union"
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
sed -i '/^context_files:/{n;s/  - none/  - TBD/;}' "$tmp/typescript/$route_union"
if (cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
  echo "lint-plan-docs accepted overlapping write_scope and context_files" >&2
  exit 1
fi
sed -i '/^context_files:/{n;s/  - TBD/  - none/;}' "$tmp/typescript/$route_union"
route_base=$(basename "$route_union")
route_id=${route_base%%-*}
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --remove-active "$route_id")
rm "$tmp/typescript/$route_union"

good_plan=$(cd "$tmp/typescript" && .project-agent-workflow/scripts/create-plan.sh active final-decisions --summary "Final decision plan." --summary-ja "最終決定を記録する。" )
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
sed -i 's/^- \[ \] TBD$/- [x] TBD/' "$tmp/typescript/$good_plan"
printf 'smoke validation passed\n' >>"$tmp/typescript/$good_plan"
(cd "$tmp/typescript" && .project-agent-workflow/scripts/complete-plan.sh "$good_plan" >/dev/null)
(cd "$tmp/typescript" && .project-agent-workflow/scripts/finalize-active-plan.sh "$good_plan" >/dev/null)

bad_plan=$(cd "$tmp/typescript" && .project-agent-workflow/scripts/create-plan.sh active recommendation-matrix --summary "Recommendation matrix." --summary-ja "推奨案を比較する。" )
cat >>"$tmp/typescript/$bad_plan" <<'EOF_BAD_PLAN'
## Decision Audit

1. Storage location
   Compare possible storage locations.

   A: Store the full audit in the active plan.
   B: Store the full audit in a separate artifact.

   推奨: B
   理由: Active plans should keep only final decisions.
EOF_BAD_PLAN
if (cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/lint-plan-docs.py >/dev/null 2>&1); then
  echo "lint-plan-docs.py accepted an active-plan recommendation matrix" >&2
  exit 1
fi
bad_base=$(basename "$bad_plan")
bad_id=${bad_base%%-*}
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/lint-plan-docs.py --remove-active "$bad_id")
rm "$tmp/typescript/$bad_plan"
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)

test -f "$tmp/typescript/.codex/agents/repo_explorer.toml"
test -f "$tmp/typescript/.codex/agents/evidence_synthesizer.toml"
test -f "$tmp/typescript/.codex/agents/fast_scoped_worker.toml"
test -f "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
test -f "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
test -x "$root/scripts/run-sandboxed-plan-worker.py"
test -x "$root/template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
test -x "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q '^model = "gpt-5.6-sol"$' "$tmp/typescript/.codex/agents/change_reviewer.toml"
grep -q '^model_reasoning_effort = "high"$' "$tmp/typescript/.codex/agents/change_reviewer.toml"
grep -q '^model = "gpt-5.6-luna"$' "$tmp/typescript/.codex/agents/docs_researcher.toml"
grep -q '^model_reasoning_effort = "medium"$' "$tmp/typescript/.codex/agents/docs_researcher.toml"
grep -q '^model = "gpt-5.6-luna"$' "$tmp/typescript/.codex/agents/evidence_synthesizer.toml"
grep -q '^model_reasoning_effort = "xhigh"$' "$tmp/typescript/.codex/agents/evidence_synthesizer.toml"
grep -q '^sandbox_mode = "read-only"$' "$tmp/typescript/.codex/agents/evidence_synthesizer.toml"
grep -q 'Do not edit files, execute external writes' "$tmp/typescript/.codex/agents/evidence_synthesizer.toml"
grep -q '^model = "gpt-5.6-luna"$' "$tmp/typescript/.codex/agents/repo_explorer.toml"
grep -q '^model_reasoning_effort = "low"$' "$tmp/typescript/.codex/agents/repo_explorer.toml"
grep -q '^model = "gpt-5.6-terra"$' "$tmp/typescript/.codex/agents/scoped_worker.toml"
grep -q '^model_reasoning_effort = "medium"$' "$tmp/typescript/.codex/agents/scoped_worker.toml"
grep -q '^model = "gpt-5.3-codex-spark"$' "$tmp/typescript/.codex/agents/fast_scoped_worker.toml"
grep -q '^model_reasoning_effort = "medium"$' "$tmp/typescript/.codex/agents/fast_scoped_worker.toml"
grep -q 'Require an explicit write scope and predetermined validation' "$tmp/typescript/.codex/agents/fast_scoped_worker.toml"
grep -q 'Do not commit, tag, push, release' "$tmp/typescript/.codex/agents/fast_scoped_worker.toml"
grep -q '^model = "gpt-5.3-codex-spark"$' "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
grep -q '^model_reasoning_effort = "medium"$' "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
grep -q '^sandbox_mode = "read-only"$' "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
grep -q 'Do not process the next active plan' "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
grep -q 'Do not spawn descendant agents' "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
grep -q "Do not edit the assigned plan's status" "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
grep -q 'Do not commit changes' "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
grep -q '.project-agent-workflow/scripts/run-sandboxed-plan-worker.py run <plan>' "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
python3 "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py" --help >/dev/null
grep -q 'DEFAULT_CODEX_MODEL = "gpt-5.3-codex-spark"' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q 'TERRA_CODEX_MODEL = "gpt-5.6-terra"' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q 'def select_plan_writable_profile' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q 'def open_availability_state' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q -- '--availability-state' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q 'skipped_known_unavailable_starts' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q 'def correct_worker' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q 'correction_lineage' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q 'def validate_candidate' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q 'def open_lifecycle_state' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q -- '--lifecycle-state' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q 'VALIDATION_AUTHORITY_SCOPE' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q 'network_enabled=False' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q 'implementation_risk' "$tmp/typescript/.project-agent-workflow/scripts/planlib.py"
grep -q 'implementation_ambiguity' "$tmp/typescript/.project-agent-workflow/scripts/planlib.py"
grep -q 'focused_validation' "$tmp/typescript/.project-agent-workflow/scripts/planlib.py"
grep -q 'validation_authority_scope' "$tmp/typescript/.project-agent-workflow/scripts/planlib.py"
grep -q 'DEFAULT_FALLBACK_CODEX_MODEL = "gpt-5.6-luna"' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q 'DEFAULT_FALLBACK_CODEX_REASONING = "max"' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q -- '--fallback-codex-model' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
grep -q -- '--no-model-fallback' "$tmp/typescript/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
test -f "$tmp/typescript/.codex/hooks/pre_tool_hardening_gate.py"
test -f "$tmp/typescript/.codex/hooks/agent_log_event.py"
test -f "$tmp/typescript/.codex/hooks/semantic_guard_advisory.py"
test -f "$tmp/typescript/.codex/hooks/stop_review_gate.py"
test -f "$tmp/typescript/.project-agent-workflow/hooks/pre_tool_hardening_gate.py"
test -f "$tmp/typescript/.project-agent-workflow/hooks/agent_log_event.py"
test -f "$tmp/typescript/.project-agent-workflow/hooks/semantic_guard_advisory.py"
test -f "$tmp/typescript/.project-agent-workflow/hooks/stop_review_gate.py"
test -f "$tmp/typescript/.codex/hooks.json"
test -f "$tmp/python/.codex/agents/repo_explorer.toml"
test -f "$tmp/python/.codex/hooks/pre_tool_hardening_gate.py"
test ! -f "$tmp/python/.codex/hooks.json"
test -f "$tmp/docs/.codex/agents/repo_explorer.toml"
test ! -f "$tmp/docs/.codex/hooks.json"
grep -q 'agent_log_event.py' "$tmp/typescript/.codex/hooks.json"
grep -q 'pre_tool_hardening_gate.py' "$tmp/typescript/.codex/hooks.json"
grep -q 'semantic_guard_advisory.py' "$tmp/typescript/.codex/hooks.json"
grep -q 'stop_review_gate.py' "$tmp/typescript/.codex/hooks.json"
grep -q '.project-agent-workflow/hooks/stop_review_gate.py' "$tmp/typescript/.codex/hooks.json"
grep -q '.project-agent-workflow/AGENTS.md' "$tmp/typescript/AGENTS.md"
test -f "$tmp/typescript/.project-agent-workflow/ownership.yaml"
grep -q '^copier_managed:' "$tmp/typescript/.project-agent-workflow/ownership.yaml"
grep -q '^  - .agents/skills/decision-audit/SKILL.md$' "$tmp/typescript/.project-agent-workflow/ownership.yaml"
if grep -q '^  - .agents/skills/\*\*$' "$tmp/typescript/.project-agent-workflow/ownership.yaml"; then
  echo "ownership manifest claims project-specific skills are Copier-managed" >&2
  exit 1
fi
grep -q 'エージェントワークフロー' "$tmp/typescript/README.md"
grep -q '外部サービス連携' "$tmp/typescript/README.md"
grep -q 'Codex hooks mode: `enable_local_logging`' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'Codex hooks mode: `install_templates`' "$tmp/python/.project-agent-workflow/AGENTS.md"
grep -q 'Codex hooks mode: `disabled`' "$tmp/docs/.project-agent-workflow/AGENTS.md"
grep -q 'SkillSpector mode: `document_optional`' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'SkillSpector mode: `disabled`' "$tmp/python/.project-agent-workflow/AGENTS.md"
grep -q 'SkillSpector mode: `document_optional`' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_VALIDATION.md"
grep -q 'SkillSpector is not enabled' "$tmp/python/.project-agent-workflow/docs/agent/SPEC_VALIDATION.md"
test -f "$tmp/typescript/.project-agent-workflow/scripts/skillspector-scan.sh"
test ! -f "$tmp/python/.project-agent-workflow/scripts/skillspector-scan.sh"
grep -q 'External service policy states: MCP=`disabled`, Linear=`disabled`, graph memory=`disabled`' "$tmp/python/.project-agent-workflow/AGENTS.md"
python3 - "$tmp/typescript/.copier-answers.yml" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
if text.endswith("\n\n"):
    raise SystemExit(f"{path} has extra blank line at EOF")
PY
grep -q 'External service policy states: MCP=`documented`, Linear=`documented`, graph memory=`documented`' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'SPEC_COPIER_ADOPTION.md' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'copier_adoption:' "$tmp/typescript/.project-agent-workflow/docs/agent/spec-index.yaml"
grep -q 'Copier Adoption' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md"
grep -q 'Conflict Handling' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md"
grep -q 'Copier may represent a conflict with inline conflict markers' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md"
grep -q '.project-agent-workflow/scripts/update-from-copier.sh' "$tmp/typescript/README.md"
test -x "$tmp/typescript/.project-agent-workflow/scripts/update-from-copier.sh"
cmp "$root/scripts/validate-copier-update.py" "$tmp/typescript/.project-agent-workflow/scripts/validate-copier-update.py"
test -f "$tmp/typescript/docs/agent/external-services.yaml"
grep -q 'external_services:' "$tmp/typescript/docs/agent/external-services.yaml"
grep -q 'state: documented' "$tmp/typescript/docs/agent/external-services.yaml"
grep -q 'Codex helper agents: installed by default' "$tmp/docs/.project-agent-workflow/AGENTS.md"
grep -q 'Local workflow modules: installed by default and activated by task routing' "$tmp/docs/.project-agent-workflow/AGENTS.md"
grep -q 'planning_style: "active_backlog_checked"' "$tmp/docs/.project-agent-workflow/docs/agent/spec-index.yaml"
grep -q 'max_concurrent_threads_per_session = 4' "$tmp/docs/.codex/config.toml"
if grep -q 'max_threads\|max_depth' "$tmp/docs/.codex/config.toml"; then
  echo "generated project config used legacy or unsupported agent settings" >&2
  exit 1
fi
if grep -q '^model = ' "$tmp/docs/.codex/config.toml"; then
  echo "generated project config pinned a project-wide model" >&2
  exit 1
fi
grep -q 'CI autofix mode: `direct_push`' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'CI autofix mode: `patch_only`' "$tmp/python/.project-agent-workflow/AGENTS.md"
grep -q 'CI autofix mode: `disabled`' "$tmp/docs/.project-agent-workflow/AGENTS.md"
test -f "$tmp/typescript/.github/workflows/codex-ci-autofix.yml"
test -f "$tmp/python/.github/workflows/codex-ci-autofix.yml"
test ! -f "$tmp/docs/.github/workflows/codex-ci-autofix.yml"
grep -q 'let mode = "patch-only";' "$tmp/typescript/.github/workflows/codex-ci-autofix.yml"
grep -q 'let mode = "patch-only";' "$tmp/python/.github/workflows/codex-ci-autofix.yml"
grep -Fq 'ref: ${{ needs.prepare.outputs.head_sha }}' "$tmp/typescript/.github/workflows/codex-ci-autofix.yml"
assert_ci_autofix_validation_graph "$tmp/typescript/.github/workflows/codex-ci-autofix.yml"
assert_ci_autofix_validation_graph "$tmp/python/.github/workflows/codex-ci-autofix.yml"
grep -q 'Use tmux for long-running, shared, or interactive commands' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'Command Sessions' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'Proactive bounded delegation' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'main agent owns' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'non-delegation' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'Do not delegate short deterministic commands' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'external writes' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'sequential_plan_worker.*exactly one assigned active plan' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q '.project-agent-workflow/scripts/run-sandboxed-plan-worker.py run' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'gpt-5.3-codex-spark.*medium reasoning' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'gpt-5.6-luna.*max reasoning' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'usage limit, rate limit, unavailable model, or denied model access' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'fast_scoped_worker.*predetermined validation' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'evidence_synthesizer.*multiple evidence sources' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'Use xhigh through `evidence_synthesizer`' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'gpt-5.6-sol.*high reasoning.*change_reviewer' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'Do not redefine it here as a custom candidate' "$tmp/typescript/docs/plan/sub-agents/custom-agents.md"
grep -q 'Name tmux sessions descriptively' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'docs/agent/external-services.yaml' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'MCP=`documented`' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear=`documented`' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'graph memory=`documented`' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'configured_write_capable' "$tmp/python/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Agent Logging' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md"
grep -q 'agent_log_event.py' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md"
grep -q 'external_transcript' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md"
grep -q 'transcript_log' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md"
grep -q 'hook_event_log' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md"
grep -q 'Headroom is an optional backend' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_CONTEXT_COMPRESSION.md"
grep -q 'redaction_status' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_CONTEXT_COMPRESSION.md"
grep -q 'agent_logging:' "$tmp/typescript/.project-agent-workflow/docs/agent/spec-index.yaml"
grep -q 'Context compression helper: optional' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'external transcript logs as primary full-turn evidence' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q '.project-agent-workflow/scripts/context-compress.sh' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_CONTEXT_COMPRESSION.md"
test -f "$tmp/typescript/.project-agent-workflow/scripts/check-agent-log-manifest.py"
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/check-agent-log-manifest.py --self-test >/dev/null)
test -f "$tmp/typescript/.project-agent-workflow/scripts/import-codex-transcript.py"
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/import-codex-transcript.py --self-test >/dev/null)
test -f "$tmp/typescript/.project-agent-workflow/skills/decision-audit/SKILL.md"
test -f "$tmp/typescript/.project-agent-workflow/skills/decision-audit/agents/openai.yaml"
test -f "$tmp/typescript/.project-agent-workflow/skills/define-referents-first/SKILL.md"
test -f "$tmp/typescript/.project-agent-workflow/skills/define-referents-first/agents/openai.yaml"
test -f "$tmp/typescript/.project-agent-workflow/skills/define-referents-first/references/workflow.md"
grep -q 'name: define-referents-first' "$tmp/typescript/.project-agent-workflow/skills/define-referents-first/SKILL.md"
grep -q 'without candidate labels or controlled terms' "$tmp/typescript/.project-agent-workflow/skills/define-referents-first/SKILL.md"
grep -q 'show an unnamed referent and uncertainty stage before any candidate or controlled term' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'name: decision-audit' "$tmp/typescript/.project-agent-workflow/skills/decision-audit/SKILL.md"
test -f "$tmp/typescript/.project-agent-workflow/skills/mcp-ops/SKILL.md"
test -f "$tmp/typescript/.project-agent-workflow/skills/linear-ops/SKILL.md"
test -f "$tmp/typescript/.project-agent-workflow/skills/graph-memory/SKILL.md"
test -f "$tmp/typescript/.project-agent-workflow/skills/plan-archive/SKILL.md"
test -f "$tmp/typescript/.project-agent-workflow/skills/implementation-guidelines/SKILL.md"
test -f "$tmp/typescript/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
test -f "$tmp/typescript/.project-agent-workflow/skills/sequential-plan-orchestrator/agents/openai.yaml"
test -f "$tmp/typescript/.project-agent-workflow/skills/write-for-reader/SKILL.md"
test -f "$tmp/typescript/.project-agent-workflow/skills/write-for-reader/agents/openai.yaml"
test -f "$tmp/typescript/.agents/skills/write-for-reader/SKILL.md"
grep -q '.project-agent-workflow/skills/write-for-reader/SKILL.md' "$tmp/typescript/.agents/skills/write-for-reader/SKILL.md"
grep -q 'name: mcp-ops' "$tmp/typescript/.project-agent-workflow/skills/mcp-ops/SKILL.md"
grep -q 'name: linear-ops' "$tmp/typescript/.project-agent-workflow/skills/linear-ops/SKILL.md"
grep -q 'name: graph-memory' "$tmp/typescript/.project-agent-workflow/skills/graph-memory/SKILL.md"
grep -q 'name: plan-archive' "$tmp/typescript/.project-agent-workflow/skills/plan-archive/SKILL.md"
awk '
  /Run `.project-agent-workflow\/scripts\/complete-plan.sh/ { complete=NR }
  /Run `.project-agent-workflow\/scripts\/finalize-active-plan.sh/ { finalize=NR }
  END { exit(complete && finalize && complete < finalize ? 0 : 1) }
' "$tmp/typescript/.project-agent-workflow/skills/plan-archive/SKILL.md"
grep -q 'name: implementation-guidelines' "$tmp/typescript/.project-agent-workflow/skills/implementation-guidelines/SKILL.md"
grep -q 'name: sequential-plan-orchestrator' "$tmp/typescript/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
grep -q 'name: write-for-reader' "$tmp/typescript/.project-agent-workflow/skills/write-for-reader/SKILL.md"
grep -q 'SPEC_USER_COMMUNICATION.md' "$tmp/typescript/.project-agent-workflow/skills/write-for-reader/SKILL.md"
grep -q 'sequential_plan_worker' "$tmp/typescript/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
grep -q '.project-agent-workflow/scripts/run-sandboxed-plan-worker.py run' "$tmp/typescript/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
grep -q 'gpt-5.6-luna.*max fallback' "$tmp/typescript/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
grep -q 'gpt-5.6-terra' "$tmp/typescript/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
grep -qi 'admissible implementation slice' "$tmp/typescript/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
grep -qi 'state path outside the repository' "$tmp/typescript/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
grep -q 'run-sandboxed-plan-worker.py correct' "$tmp/typescript/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
grep -q 'run-sandboxed-plan-worker.py validate' "$tmp/typescript/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
grep -q 'one bounded worker at a time' "$tmp/typescript/.project-agent-workflow/skills/sequential-plan-orchestrator/agents/openai.yaml"
grep -q 'Generic Codex skills: installed by default' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'SPEC_SKILL_AUTHORING.md' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'Union the `required` docs from every matching route' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'Union their `required` docs, add matching `conditional` docs' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_DEVELOPMENT_FLOW.md"
grep -q 'SPEC_SKILL_AUTHORING.md' "$tmp/typescript/README.md"
grep -q 'docs/agent/external-services.yaml' "$tmp/typescript/.project-agent-workflow/skills/mcp-ops/SKILL.md"
grep -q 'external_services.linear_sync' "$tmp/typescript/.project-agent-workflow/skills/linear-ops/SKILL.md"
grep -q 'external_services.graph_memory' "$tmp/typescript/.project-agent-workflow/skills/graph-memory/SKILL.md"
if grep -R 'supportcard-status' "$tmp/typescript/.project-agent-workflow/skills" >/dev/null; then
  echo "generated skills contain supportcard-status hardcoding" >&2
  exit 1
fi
grep -q 'decision_audit:' "$tmp/typescript/.project-agent-workflow/docs/agent/spec-index.yaml"
grep -q 'skill_authoring:' "$tmp/typescript/.project-agent-workflow/docs/agent/spec-index.yaml"
grep -q 'referent_first:' "$tmp/typescript/.project-agent-workflow/docs/agent/spec-index.yaml"
grep -q 'user_communication:' "$tmp/typescript/.project-agent-workflow/docs/agent/spec-index.yaml"
grep -q 'User Communication' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md"
grep -q 'write-for-reader' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'Referent-First Semantic Guard' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_REFERENT_FIRST.md"
grep -q 'referent-contract.py' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_REFERENT_FIRST.md"
grep -q 'SPEC_DECISION_AUDIT.md' "$tmp/typescript/.project-agent-workflow/docs/agent/spec-index.yaml"
grep -q 'SPEC_SKILL_AUTHORING.md' "$tmp/typescript/.project-agent-workflow/docs/agent/spec-index.yaml"
grep -q 'Skill Authoring' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_SKILL_AUTHORING.md"
grep -q 'Keep `SKILL.md` concise' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_SKILL_AUTHORING.md"
grep -q 'Decision Audit Preflight' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md"
grep -q 'Run decision audit before creating or materially updating active plans' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'Full decision-audit output does not belong in `docs/plan/active`' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_DECISION_AUDIT.md"
test -f "$tmp/typescript/.project-agent-workflow/scripts/plan_validation_commands.py"
test -f "$tmp/typescript/.project-agent-workflow/scripts/check-codex-toml.py"
test -f "$tmp/typescript/.project-agent-workflow/scripts/sync-plan-to-linear.sh"
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/plan_validation_commands.py --self-test)
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/check-codex-toml.py >/dev/null)
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/validate-changes.py --print-only >/dev/null)
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/validate-changes.py --print-only --json | python3 -m json.tool >/dev/null)
(cd "$tmp/typescript" && .project-agent-workflow/scripts/search-plan-archive.py --text sample --json | python3 -m json.tool | grep -q '"count":')
(cd "$tmp/typescript" && .project-agent-workflow/scripts/workflow-status.sh --json | python3 -m json.tool | grep -q '"git_status"')
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/plan_validation_commands.py check-commands "python3 .project-agent-workflow/scripts/validate-changes.py --print-only --json")
sample_archive_path=$(cat "$tmp/typescript/.sample-archive-path")
(cd "$tmp/typescript" && .project-agent-workflow/scripts/sync-plan-to-linear.sh "$sample_archive_path" --dry-run | grep -q 'Desired status: Done')
(cd "$tmp/broad" && .project-agent-workflow/scripts/create-plan.sh active broad-linear --summary "Exercise the Linear version 2 gate." --summary-ja "Linear version 2 ゲートを検証する。" >/dev/null)
if (cd "$tmp/broad" && .project-agent-workflow/scripts/sync-plan-to-linear.sh docs/plan/active/001-broad-linear.md --ensure-issue 2>"$tmp/broad-linear.err"); then
  echo "generic Linear adapter treated the version 2 profile as operation authorization" >&2
  exit 1
fi
grep -q 'check-external-service-policy.py with provider, current-task, target, effect, and confirmation facts' "$tmp/broad-linear.err"
grep -q 'Plan Validation Commands' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_VALIDATION.md"
grep -q 'Linear sync dry-run' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md"
grep -q 'Machine-readable workflow status' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md"
grep -q 'Next: .project-agent-workflow/scripts/finalize-active-plan.sh' "$tmp/typescript/.project-agent-workflow/scripts/check-agent-completion.sh"
grep -q 'generic template script still fails closed' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"

mkdir -p "$tmp/typescript/.agent-logs/sample/raw"
printf 'line 1\nline 2\n' >"$tmp/typescript/.agent-logs/sample/raw/session.log"
(cd "$tmp/typescript" && HEADROOM_DISABLED=1 .project-agent-workflow/scripts/context-compress.sh .agent-logs/sample/raw/session.log sample >/dev/null)
find "$tmp/typescript/.agent-logs/sample/compressed" -maxdepth 1 -type f -name 'session.log.*.compressed.md' -print -quit | grep -q .
test -f "$tmp/typescript/.agent-logs/sample/manifest.json"
(cd "$tmp/typescript" && python3 .project-agent-workflow/scripts/check-agent-log-manifest.py .agent-logs/sample/manifest.json >/dev/null)
if (cd "$tmp/typescript" && .project-agent-workflow/scripts/context-compress.sh AGENTS.md >/dev/null 2>&1); then
  echo "context-compress.sh accepted AGENTS.md" >&2
  exit 1
fi
if (cd "$tmp/typescript" && .project-agent-workflow/scripts/context-compress.sh .project-agent-workflow/docs/agent/SPEC_VALIDATION.md >/dev/null 2>&1); then
  echo "context-compress.sh accepted validation policy" >&2
  exit 1
fi
if (cd "$tmp/typescript" && HEADROOM_DISABLED=1 .project-agent-workflow/scripts/context-compress.sh .project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md namespaced-policy >/dev/null 2>&1); then
  echo "context-compress.sh accepted namespaced normative policy" >&2
  exit 1
fi
test ! -e "$tmp/typescript/.agent-logs/namespaced-policy"

echo "smoke test passed"
