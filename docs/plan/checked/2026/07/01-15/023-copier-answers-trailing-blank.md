# Copier Answers Trailing Blank

status: checked
task_type: template_workflow
review_class: A
human_design_required: no
human_approval_status: not_required
target_files:
  - template/[[ _copier_conf.answers_file ]].jinja
  - tests/smoke.sh
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - git diff --check
checked_summary_ja: 生成された .copier-answers.yml の余分な末尾空行を防いだ。

## Summary

Trimmed generated Copier answers YAML so downstream repositories with `git diff --check` do not receive an extra blank line at EOF after `copier update`.

## Completed Work

- Added `trim` to the generated answers template output.
- Added smoke coverage that fails when generated `.copier-answers.yml` ends with an extra blank line.

## Validation Notes

- `scripts/lint-project-workflow.sh` passed.
- `tests/smoke.sh` passed. Copier emitted `DirtyLocalWarning` because the smoke test intentionally rendered the in-progress dirty template.
- `tests/copier-update.sh` passed. Copier emitted `DirtyLocalWarning` for the in-progress template.
- `git diff --check` passed.
