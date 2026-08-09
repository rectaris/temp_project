# Preserve namespaced policy from context compression

status: checked
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
write_scope:
  - README.md
  - docs/plan/
  - scripts/
  - template/
  - tests/
context_files:
  - ../gakumasu-timeline/.project-agent-workflow/scripts/context-compress.sh
  - .agent-artifacts/referent-contracts/context-compression-namespaced-policy/contract.json
required_specs:
  - docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 scripts/validate-changes.py --all
  - python3 tests/test-hooks.py
  - python3 tests/test-copier-adoption.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - tests/copier-minimum.sh
  - tests/root-plan-lifecycle.sh
  - git diff --check
acceptance:
  - Generated context compression rejects every resolved path at or below the Copier-managed docs/agent directory before creating output.
  - Existing normative, validation, and security refusal rules retain their behavior.
  - Copier adoption from v1.0.0 renders the rejection rule and passes the existing non-destructive adoption checks.
  - Published v1.1.1 remains unchanged, and first-time adoption requires v1.1.2 or newer after release.
checked_summary_ja: namespaced な規範文書を圧縮前に拒否し、v1.0.0 からの Copier 採用で安全境界が退行しないよう修正した。

## Problem

The v1.1.1 generated context-compression wrapper rejects root policy paths but accepts policy under the Copier-managed docs/agent directory.

Adopting v1.1.1 from gakumasu-timeline v1.0.0 therefore overwrites the downstream correction and allows a normative plan policy to be compressed.

## Goal

Render the confirmed downstream safety boundary from the template and prove that initial adoption preserves it without broadening the refusal scope.

## Decisions

- Ensure generated context-compress.sh rejects a resolved repository-relative input equal to .project-agent-workflow/docs/agent or located below it.
- Preserve this invariant: existing rejection rules for AGENTS.md, root docs/agent, active plans, validation policy, and security policy remain unchanged.
- Make direct boundary tests and every validated Copier adoption lane require namespaced plan policy compression to fail before output creation.
- Preserve this release boundary: published v1.1.1 remains unchanged and the correction is prepared as a v1.1.2 release candidate.

## Tasks

- [x] Add the namespaced policy path to the generated compression refusal boundary.
- [x] Add focused and rendered-artifact regression tests.
- [x] Reject v1.1.1 as an initial-adoption target and update adoption guidance to v1.1.2.
- [x] Reproduce v1.0.0 adoption against a temporary gakumasu-timeline clone.
- [x] Run the full template validation matrix and archive the plan.

## Validation Notes

- `scripts/lint-project-workflow.sh`: passed; 28 hook tests, 2 migration tests, 7 adoption tests, 8 referent-contract tests, 14 validation-tool tests, and the root plan lifecycle test passed.
- `PATH=/tmp/project-agent-workflow-actionlint:$PATH REQUIRE_ACTIONLINT=1 COPIER_SMOKE_REF=<candidate-commit> REQUIRE_COPIER=1 tests/smoke.sh`: passed with actionlint 1.7.12 and rendered-project context-compression checks.
- `COPIER_UPDATE_TARGET_REF=<candidate-commit> tests/copier-update.sh`: passed all pre-v1, v1.0.0 repair, disabled-mode, modified-file, and mature-update lanes.
- `COPIER_MINIMUM_REF=<candidate-commit> tests/copier-minimum.sh`: passed with Copier 9.6.0.
- `tests/root-plan-lifecycle.sh`: passed.
- `python3 scripts/validate-changes.py --all`: passed.
- `git diff --check`: passed.
- An isolated clone of `gakumasu-timeline` at `_commit: v1.0.0` adopted the local v1.1.2 candidate without unmerged paths or tracked-file deletions. The generated wrapper rejected `.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md` with exit code 1 before creating `.agent-logs/v112-sandbox-smoke`, and managed validation passed.
- No implementation risk remains within this plan. Creating or publishing the v1.1.2 tag is a separate release action.
