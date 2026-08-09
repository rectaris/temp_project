#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/project-agent-workflow-smoke.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
. "$root/tests/lib-copier.sh"
source_ref=${COPIER_SMOKE_REF:-HEAD}

run_root_python() {
  if command -v uv >/dev/null 2>&1 && [ -f "$root/pyproject.toml" ]; then
    (cd "$root" && UV_CACHE_DIR="$root/.uv-cache" uv run python "$@")
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

render_fixture() {
  fixture=$1
  out=$2
  set -- copy -q -f --vcs-ref "$source_ref" --data-file "$fixture"
  set -- "$@" "$root" "$out"
  run_copier "$@" >/dev/null
}

render_defaults() {
  out=$1
  run_copier copy -q -f --defaults --vcs-ref "$source_ref" "$root" "$out" >/dev/null
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

run_external_policy_smoke() {
  out=$1
  policy="$out/.agent-artifacts/external-services-configured.yaml"
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
}

for fixture in "$root"/tests/fixtures/*.answers.yml; do
  name=$(basename "$fixture" .answers.yml)
  out="$tmp/$name"
  render_fixture "$fixture" "$out"
  assert_generated_inventory "$out" "$fixture"
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
while IFS="$tab" read -r case_name primary_language codex_hooks_mode skillspector_mode mcp_policy_mode linear_sync_mode graph_memory_mode ci_autofix_mode; do
  [ "$case_name" != "case" ] || continue
  [ -n "$case_name" ] || continue
  fixture="$tmp/$case_name.answers.yml"
  out="$tmp/pairwise-$case_name"
  {
    printf 'project_name: %s\n' "$case_name"
    printf 'project_slug: %s\n' "$case_name"
    printf 'project_purpose: Exercise Copier pairwise generation.\n'
    printf 'primary_language: %s\n' "$primary_language"
    printf 'codex_hooks_mode: %s\n' "$codex_hooks_mode"
    printf 'skillspector_mode: %s\n' "$skillspector_mode"
    printf 'mcp_policy_mode: %s\n' "$mcp_policy_mode"
    printf 'linear_sync_mode: %s\n' "$linear_sync_mode"
    printf 'graph_memory_mode: %s\n' "$graph_memory_mode"
    printf 'ci_autofix_mode: %s\n' "$ci_autofix_mode"
  } >"$fixture"
  render_fixture "$fixture" "$out"
  assert_generated_inventory "$out" "$fixture"
  run_root_python "$root/tests/assert-generated-semantics.py" "$out"
  run_root_python "$root/scripts/check-yaml.py" "$out" >/dev/null
  REQUIRE_ACTIONLINT=${REQUIRE_ACTIONLINT:-0} "$root/scripts/lint-github-actions.sh" "$out"
done <"$root/tests/fixtures/copier-pairwise.tsv"

default_out="$tmp/defaults"
render_defaults "$default_out"
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
    "codex_hooks_mode": "install_templates",
    "skillspector_mode": "disabled",
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
  if run_copier copy -f --vcs-ref HEAD --data-file "$root/tests/fixtures/docs.answers.yml" --data "$question=$value" "$root" "$tmp/invalid-$label" >/dev/null 2>&1; then
    echo "copier accepted invalid input: $label" >&2
    exit 1
  fi
}

if run_copier copy -f --vcs-ref HEAD --data-file "$root/tests/fixtures/docs.answers.yml" --data project_slug='invalid slug' "$root" "$tmp/invalid-slug" >/dev/null 2>&1; then
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
test -f "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
if grep -q 'gpt-5.3-codex-spark' "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"; then
  echo "sequential worker pinned an entitlement-specific preview model" >&2
  exit 1
fi
grep -q 'Do not process the next active plan' "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
grep -q 'Do not spawn descendant agents' "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
grep -q "Do not edit the assigned plan's status" "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
grep -q 'Do not commit changes' "$tmp/typescript/.codex/agents/sequential_plan_worker.toml"
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
grep -q 'mode = "direct-push";' "$tmp/typescript/.github/workflows/codex-ci-autofix.yml"
grep -q 'mode = "patch-only";' "$tmp/python/.github/workflows/codex-ci-autofix.yml"
grep -Fq 'ref: ${{ needs.prepare.outputs.head_sha }}' "$tmp/typescript/.github/workflows/codex-ci-autofix.yml"
grep -q 'Use tmux for long-running, shared, or interactive commands' "$tmp/typescript/.project-agent-workflow/AGENTS.md"
grep -q 'Command Sessions' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'sequential_plan_worker.*exactly one assigned active plan' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'Do not redefine it here as a custom candidate' "$tmp/typescript/docs/plan/sub-agents/custom-agents.md"
grep -q 'Name tmux sessions descriptively' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q 'docs/agent/external-services.yaml' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'MCP: `documented`' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear sync: `documented`' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Graph memory: `documented`' "$tmp/typescript/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
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
