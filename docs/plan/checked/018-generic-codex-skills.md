# Generic Codex Skills

## Manifest

- `status`: `checked`
- `task_type`: `template_workflow`
- `review_class`: `B`
- `human_design_required`: `no`
- `human_approval_status`: `not_required`
- `target_files`:
  - `.codex/skills/`
  - `template/.codex/skills/`
  - `template/AGENTS.md.jinja`
  - `scripts/check-copier-template.py`
  - `tests/smoke.sh`
  - `docs/plan/plan.md`
- `required_specs`:
  - `AGENTS.md`
  - `docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `docs/agent/SPEC_DECISION_AUDIT.md`
- `validation`:
  - `scripts/lint-project-workflow.sh`
  - `tests/smoke.sh`
  - `tests/copier-update.sh`
  - `git diff --check`
  - `python3 /home/rectaris/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-dir>`
- `acceptance`:
  - Generated projects receive generic Codex skills for MCP, Linear, graph memory, plan completion, and implementation guidance.
  - Skills contain no `supportcard-status` hardcoded project facts.
  - External-service skills require `docs/agent/external-services.yaml` configured states before reads or writes.
  - Root self-applied `.codex/skills` stays aligned with generated skill assets.
  - Static checks and smoke tests require the new skill files.
- `acceptance_focus`:
  - generic skill packaging
  - project-specific policy separation
  - external-service disabled-by-default safety
- `expected_output`: generic skill files in root and template `.codex/skills`, generated-project validation coverage, checked plan record.
- `checked_summary_ja`: supportcard-status 由来のローカル Codex skill を汎用化し、生成テンプレートと root `.codex` に追加した。
- `completion_deferred_reason`: ``

## Goal

Move reusable behavior from supportcard-status local Codex skills into generic generated-project skills without carrying supportcard-status-specific facts.

## Decisions

1. Add generic skills to generated projects by default; activation is controlled by their instructions and project-local policy, not by Copier prompts.

2. Keep service-specific identifiers, credentials, allowed operations, and write authorization rules in `docs/agent/external-services.yaml` or project-local specs.

3. External-service skills must stop at local fallback when the matching service state is `disabled` or `documented`.

4. Use `implementation-guidelines` as the generic successor for supportcard-status `karpathy-guidelines`; project-specific invariants remain in project specs.

5. Use the generated plan lifecycle scripts as the normal `plan-archive` implementation path.

## Tasks

- [x] Add generic skill files under `template/.codex/skills/`.
- [x] Add matching root self-applied skill files under `.codex/skills/`.
- [x] Update generated AGENTS profile text.
- [x] Update static template required-file checks.
- [x] Update smoke tests for generated skill presence and absence of supportcard-status hardcoding.
- [x] Run `scripts/lint-project-workflow.sh`.
- [x] Run `tests/smoke.sh`.
- [x] Run `tests/copier-update.sh`.
- [x] Run `git diff --check`.
- [x] Archive this plan after validation.

## Validation Notes

Validated with:

- `scripts/lint-project-workflow.sh`
- `tests/smoke.sh`
- `tests/copier-update.sh`
- `git diff --check`
- `python3 /home/rectaris/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-dir>` for each new root and template skill directory.

`tests/smoke.sh` and `tests/copier-update.sh` emitted Copier `DirtyLocalWarning` because they rendered or updated from uncommitted local template changes, then passed.
