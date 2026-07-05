# Half-Month Checked Archive

status: checked
task_type: template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
target_files:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/checked.md
  - references/planning.md
  - scripts/sync-plan-to-linear.sh
  - template/docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/docs/plan/README.md
  - template/docs/plan/checked.md
  - template/docs/plan/handoffs/README.md
  - template/scripts/complete-plan.sh
  - template/scripts/planlib.py
  - template/scripts/lint-plan-docs.py
  - template/scripts/search-plan-archive.py
  - template/scripts/sync-plan-to-linear.sh
  - tests/smoke.sh
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Completed plans archive to docs/plan/checked/YYYY/MM/01-15 or 16-31.
  - Checked indexes, search, lint, and Linear dry-run support nested checked paths.
  - Root project and generated template documentation describe the half-month archive policy.
expected_output: Commit scoped project and template changes for half-month checked archive buckets.
checked_summary_ja: 完了済みプランを半月単位のディレクトリへアーカイブする方針をプロジェクトとテンプレートへ適用した。

## Decisions

- Store completed plan records under `docs/plan/checked/YYYY/MM/01-15/` or `docs/plan/checked/YYYY/MM/16-31/` based on the completion date.
- Keep `docs/plan/checked.md` as the machine-readable lookup index that points at the nested archive path.
- Preserve existing root checked records in place unless a reliable completion date is available for migration.

## Summary

Applied the half-month checked archive policy to the root project workflow docs and generated template lifecycle.

## Completed Work

- Updated root and generated plan workflow documentation to define `YYYY/MM/01-15` and `YYYY/MM/16-31` checked archive buckets.
- Updated generated `complete-plan.sh` to archive completed active plans into the completion-date bucket and emit only the archive path on stdout.
- Updated generated archive helpers so next-id allocation, archive search, and Linear dry-runs support nested checked paths.
- Updated smoke coverage to assert the nested archive path and reuse the emitted archive path for downstream checks.

## Validation Notes

- `scripts/lint-project-workflow.sh` passed.
- `tests/smoke.sh` passed. Copier emitted `DirtyLocalWarning` because the smoke test intentionally rendered the in-progress dirty template.
- `git diff --check` passed.
