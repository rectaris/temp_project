# Root Codex Self Apply

## Manifest

- `status`: `checked`
- `task_type`: `template_workflow`
- `review_class`: `B`
- `human_design_required`: `no`
- `human_approval_status`: `not_required`
- `target_files`:
  - `.codex/`
  - `AGENTS.md`
  - `docs/agent/SPEC_DECISION_AUDIT.md`
  - `docs/plan/plan.md`
- `required_specs`:
  - `AGENTS.md`
  - `docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `docs/agent/SPEC_DECISION_AUDIT.md`
- `validation`:
  - `scripts/lint-project-workflow.sh`
  - `tests/smoke.sh`
  - `git diff --check`
- `acceptance`:
  - Root `.codex` contains the generated Codex agents, hooks, config, and decision-audit skill assets.
  - Root policy no longer states that operation must not depend on a repo-local decision-audit skill.
  - Root remains a template development repository and is not converted into a Copier-generated project.
  - Template checks and smoke tests still pass.
- `acceptance_focus`:
  - root Codex asset self-application
  - template boundary preservation
  - generated-project compatibility
- `expected_output`: root `.codex` assets, updated root policy, validation output, and checked plan record.
- `checked_summary_ja`: テンプレート root に生成用 `.codex` 資産を展開し、repo-local decision-audit skill を使える状態にした。
- `completion_deferred_reason`: ``

## Goal

Self-apply the template-defined `.codex` assets to this template development repository root without applying the full Copier generated-project structure.

## Decisions

1. Copy only `.codex` assets from the generated template into the root repository.

2. Enable the same local logging hooks that generated projects receive when hooks are enabled.

3. Keep root docs and scripts as template-development files rather than replacing them with generated-project files.

## Tasks

- [x] Add root `.codex` agents, hooks, config, and decision-audit skill files.
- [x] Update root policy that previously prohibited repo-local decision-audit skill dependency.
- [x] Validate with root lint and smoke tests.
- [x] Archive this plan after validation.

## Validation Notes

Validated with:

- `scripts/lint-project-workflow.sh`
- `tests/smoke.sh`
- `git diff --check`

`tests/smoke.sh` emitted Copier `DirtyLocalWarning` because it rendered the template with uncommitted local changes, then passed.
