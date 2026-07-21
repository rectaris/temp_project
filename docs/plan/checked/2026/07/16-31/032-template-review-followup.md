# Implement template review follow-up hardening

status: checked
task_type: template_workflow
review_class: B
human_design_required: no
human_approval_status: approved
target_files:
  - copier.yml
  - README.md
  - .codex/skills/
  - docs/agent/
  - template/.codex/
  - template/.github/
  - template/docs/agent/
  - template/scripts/
  - scripts/
  - tests/
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - tests/copier-minimum.sh
  - tests/root-plan-lifecycle.sh
  - git diff --check
acceptance:
  - Hook logging uses stable session identity, metadata-only persistence, and the actual hardening-gate payload schema.
  - Completion and promotion lifecycle scripts fail closed on invalid state, evidence, indexes, or destination collisions.
  - Compression and manifest handling preserve run containment and collision-free derived outputs.
  - Generated CI autofix is disabled unless explicitly selected.
  - Fresh-copy and update validation cover supported boundaries, conditional outputs, and project-owned files.
  - Routing, helper-role, skill metadata, conflict, and adoption documentation agree with generated behavior.
expected_output: full-implementation
checked_summary_ja: テンプレートレビュー後に残ったログ、計画、Copier、CI、検証の境界不整合を修正した。

## Problem

The previous remediation established the main generated workflow but left reproducible gaps in session-correlated logging, hook payload filtering, lifecycle terminal state, promotion collision handling, compression containment, Copier coverage, and generated automation activation.

## Goal

Close the confirmed review gaps with deterministic contracts and tests while preserving project-owned files and current generated behavior outside the accepted scope.

## Terms

A log run unit means hook events that carry the same runtime session identifier.

An archive transition means the ordered transition from completed work through validation and finalization into a checked archive.

Update compatibility lanes mean separate validation paths for the latest stable template update and the oldest supported template migration.

## Decisions

- Derive a stable run id from explicit run identity or runtime session identity, and test the default hook path without injecting a run id.
- Persist allowlisted hook metadata only; keep automatic redaction marked pending review and keep transcript import as the full-turn evidence path.
- Inspect the actual `tool_input` command fields in the pre-tool hardening gate and cover real hook payload fixtures.
- Enforce completion, validation, finalization, checked terminal status, index consistency, and destination absence in the archive transition.
- Reject plan promotion when the destination, plan id, or index mapping conflicts.
- Canonicalize compression input paths, derive collision-free output names, and validate every raw, transcript, hook, artifact, compressed-output, and redaction-report path declared by a run manifest.
- Generate CI autofix only after explicit Copier selection; keep patch-only as the safest enabled mode.
- Add update compatibility lanes and exercise the declared minimum Copier and Python support or raise the declaration when minimum support cannot be maintained.
- Expand deterministic coverage for Copier answer combinations, conditional outputs, skip-if-exists files, and input-boundary cases exercised by deterministic fixtures.
- Document inline and reject-file Copier conflicts and direct mature-repository adoption through temporary rendering and reviewed diffs.
- Align route-union wording, helper-role classification, and root/template skill metadata checks.
- Defer immutable external Action and installer pinning until the repository adopts a supply-chain maintenance policy.

## Implementation Instructions

1. Add focused failing tests for each confirmed runtime and lifecycle defect before or with the corresponding fix.
2. Repair logging, hardening-gate, compression, manifest, plan completion, finalization, and promotion behavior.
3. Add an explicit disabled CI-autofix choice and align generated workflow, docs, fixtures, and update behavior.
4. Strengthen fresh-render and update validation with data-driven answer coverage, exact conditional inventory, all skip-if-exists paths, and input boundaries.
5. Align routing, helper-role, skill metadata, Copier conflict, and adoption documentation with executable behavior.
6. Run the full validation matrix, review the diff, record concise validation and deferred-risk notes, complete the plan, and finalize it.

## Tasks

- [x] Repair and test hook logging and pre-tool payload handling.
- [x] Repair and test plan archive and promotion lifecycle handling.
- [x] Repair and test compression and manifest containment.
- [x] Add disabled-by-default CI autofix generation.
- [x] Strengthen Copier fresh-copy, update, ownership, and input coverage.
- [x] Align routing, helper-role, skill metadata, conflict, and adoption documentation.
- [x] Run validation and archive the completed plan.

## Validation Notes

- `scripts/lint-project-workflow.sh`: passed with 23 hook tests, 8 referent-contract tests, and the root plan lifecycle test.
- `tests/smoke.sh`: passed across four primary fixtures, 11 pairwise fixtures, exact generated inventories, lifecycle failures, and compression handling.
- `tests/copier-update.sh`: passed for the oldest supported `v0.4.1` migration and latest stable `v0.4.6` update lanes while preserving both skip-if-exists files.
- `tests/copier-minimum.sh`: passed with Copier 9.6.0 on local Python 3.12; the CI job is configured to exercise the declared Python 3.11 minimum.
- `python3 scripts/validate-changes.py --all`: passed.
- `git diff --check`: passed.
- Four root/template skill directories passed `quick_validate.py`.
- Independent integration review findings for root completion, pending evidence forms, index ID consistency, and exclusive destination creation were remediated and rechecked.
- Deferred work: immutable GitHub Action and installer pinning remains outside this plan until the repository adopts a supply-chain maintenance policy.
- Remaining risk: hosted GitHub Actions and live CI autofix branch writes were not executed against an external pull request.
