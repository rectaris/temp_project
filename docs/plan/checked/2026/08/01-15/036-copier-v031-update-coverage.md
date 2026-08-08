# Cover Copier updates from v0.3.1

status: checked
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - docs/plan/
  - tests/copier-update.sh
context_files:
  - ../curiretas-gakumas-portal/.copier-answers.yml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_VALIDATION.md
validation:
  - tests/copier-update.sh
  - scripts/lint-project-workflow.sh
  - git diff --check
acceptance:
  - The update suite covers v0.3.1 without assuming answers introduced by later template versions.
  - The v0.3.1 migration preserves project-owned files and produces no rejection files or inline conflict markers.
checked_summary_ja: v0.3.1からのCopier更新を回帰テストへ追加し、既存の利用リポジトリを移行対象として検証した。

## Problem

One named downstream repository records v0.3.1, while the existing migration suite starts at v0.4.1.

## Goal

Prove that the namespaced-layout migration works from the earliest version used by the named downstream repositories.

## Decisions

- Add a dedicated v0.3.1 lane because that version predates the SkillSpector answer covered by the v0.4.1 lane.
- Keep the v0.4.1 lane for legacy-answer conversion coverage.

## Tasks

- [x] Add the v0.3.1 update lane.
- [x] Run the update and repository validation suites.
- [x] Archive this plan and commit the follow-up.

## Validation Notes

- `tests/copier-update.sh` passed from v0.3.1, v0.4.1, and v0.4.6, including the modified legacy-file and future namespaced-update lanes.
- `scripts/lint-project-workflow.sh` passed.
- `git diff --check` passed.
