# Enforce active-plan completion lifecycle

status: ready_to_archive
task_type: template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
target_files:
  - .codex/hooks.json
  - .codex/hooks/stop_review_gate.py
  - scripts/check-agent-completion.sh
  - scripts/finalize-active-plan.sh
  - template/.codex/hooks.json.jinja
  - template/.codex/hooks/stop_review_gate.py
  - template/scripts/check-agent-completion.sh
  - template/scripts/complete-plan.sh
  - template/scripts/finalize-active-plan.sh
  - template/scripts/create-plan.sh
  - template/scripts/lint-plan-docs.py
  - scripts/check-copier-template.py
  - tests/smoke.sh
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Root and generated projects provide the same deterministic completion gate and finalization command.
  - A plan marked ready for archival cannot be left active when the completion gate runs.
  - Finalization records validation notes, removes the active index entry, appends the checked index entry, and moves the plan into the date-based checked archive.
  - Stop-hook and command-line checks report the exact plan and required next action when completion is blocked.
  - Ongoing or intentionally deferred plans do not block ordinary development turns.
  - Static checks and smoke tests cover the lifecycle contract without weakening existing validation.
expected_output: full-implementation
checked_summary_ja: 完了可能な active plan を完了ゲートで検出し、標準アーカイブ処理を必須化する。

## Problem

Implementation and validation can finish while an active plan remains under `docs/plan/active/` because the root repository has no standard finalization command and the Stop hook does not invoke the existing generated-project completion gate.

## Goal

Make plan completion deterministic by requiring an explicit machine-readable ready-to-archive state, blocking completion while that state remains active, and providing one standard command that performs the archive lifecycle.

## Decisions

- Use a deterministic completion gate as the enforcement mechanism; do not silently archive plans from a Stop hook before parent acceptance and validation.
- Add one explicit lifecycle state for `ready_to_archive`; ordinary `in_progress` and intentionally `deferred` plans remain eligible for continued work.
- Use `scripts/finalize-active-plan.sh <active-plan>` as the standard completion command in both the root repository and generated projects.
- Make finalization fail closed unless the plan has a non-empty `checked_summary_ja`, recorded validation notes, no unresolved completion blocker, and a matching active-plan index entry.
- Run the completion gate from the Stop-hook path and expose it as a direct command so both interactive and scripted workflows use the same checks.
- Keep root and generated-project lifecycle behavior semantically aligned while preserving their existing root-versus-template file boundaries.
- Keep detailed logs outside plan files and report only concise validation evidence and local artifact references in completion records.
- Represent the lifecycle state in the existing `status` field, using `ready_to_archive` as the only completion-blocking state.
- Treat `in_progress` and `deferred` as non-blocking during ordinary Stop-hook checks.
- Require a non-empty `Validation Notes` section and fail closed on missing active-index entries or archive-path collisions.
- Keep finalization non-committing; the caller commits lifecycle changes and reruns the direct completion gate.
- Make Stop-hook completion checks plan-only so dirty worktrees do not block ordinary development turns.

## Implementation Instructions

1. Add or align the machine-readable lifecycle field and validation rules in the plan parser, plan creator, and plan-document linter.
2. Implement root-side `check-agent-completion.sh` and `finalize-active-plan.sh` using the existing generated-project lifecycle semantics and date-based checked archive layout.
3. Update generated lifecycle scripts so finalization is the only supported transition from `ready_to_archive` to `checked`.
4. Connect the completion gate to root and generated Stop-hook configurations without blocking ordinary work on `in_progress` or `deferred` plans.
5. Make failure output identify the plan path, lifecycle state, missing evidence, and exact finalization command.
6. Register all new root and template files in Copier static checks and add smoke scenarios for in-progress, deferred, ready-to-archive, successful archive, and failed archive cases.
7. Preserve existing user changes, avoid automatic external-service writes, and do not weaken existing completion, security, or validation checks.

## Tasks

- [x] Define and validate the machine-readable ready-to-archive lifecycle state.
- [x] Add root completion and finalization commands.
- [x] Align generated lifecycle scripts and Stop-hook integration.
- [x] Add deterministic static and smoke coverage.
- [x] Run all required validation and archive this plan after acceptance.

## Validation Notes

- `python3 scripts/validate-changes.py --all` passed.
- `scripts/lint-project-workflow.sh` passed, including Copier static checks and hook tests.
- `tests/smoke.sh` passed for generated lifecycle scenarios.
- `git diff --check` passed.
