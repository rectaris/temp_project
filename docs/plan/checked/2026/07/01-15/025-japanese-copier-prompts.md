# Japanese Copier Prompts

status: checked
task_type: template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
target_files:
  - copier.yml
  - scripts/check-copier-template.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - git diff --check
acceptance:
  - Copier interactive help text is Japanese for all template questions.
  - Choice prompts show Japanese labels while preserving existing saved values.
  - Static or smoke validation protects the Japanese prompt contract.
expected_output: Commit scoped Copier prompt localization changes.
checked_summary_ja: Copier の質問文と選択肢表示を日本語化し、保存値は既存互換のまま維持した。

## Decisions

- Localize `help` text and choice display labels in `copier.yml`.
- Preserve existing question keys and stored answer values for update compatibility.
- Keep Copier's built-in command/status messages unchanged because they are outside this template contract.

## Summary

Localized Copier prompt help text and choice labels in `copier.yml` while keeping existing internal answer values unchanged.

## Completed Work

- Replaced all template question `help` strings with Japanese text.
- Converted choice lists to Japanese display labels mapped to the existing saved values.
- Added static checks that require Japanese prompt text and verify that choice saved values stay compatible.

## Validation Notes

- `scripts/lint-project-workflow.sh` passed.
- `tests/smoke.sh` passed. Copier emitted `DirtyLocalWarning` because the smoke test intentionally rendered the in-progress dirty template.
- `tests/copier-update.sh` passed. Copier emitted `DirtyLocalWarning` for the in-progress template.
- `git diff --check` passed.
