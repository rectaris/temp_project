# Make Skill Copier copy commands trusted and non-destructive

status: checked
task_types:
  - skill_authoring
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - SKILL.md
  - docs/plan/
  - scripts/check-copier-template.py
context_files:
  - copier.yml
  - references/template-development.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Show --trust in every Copier copy command in the distributed Skill because the template always runs a post-render task.
  - Use --defaults rather than --force for the non-interactive example so selecting default answers does not also authorize overwrite.
  - Add deterministic checks that reject a missing trust flag, a missing defaults flag, or a force-based non-interactive example.
  - Keep copier.yml and generated template files unchanged.
  - Preserve the final namespaced paths established by plan 050.
checked_summary_ja: 配布 Skill の Copier copy 例に必須の trust を追加し、非対話実行で不要な上書きを有効にしないよう修正する。

## Context

The distributed Skill must show trusted Copier copy commands without enabling overwrite merely to select default answers.

The current commands omit `--trust`, and the non-interactive example uses `-f`, which combines default answers with overwrite behavior.

## Decisions

- Implement this plan after plan 050 because both plans edit `SKILL.md` and the static checker.
- Use `copier copy --trust` for the ordinary example.
- Use `copier copy --defaults --trust` for the non-interactive example.
- Extend the existing documentation-contract check instead of adding generated files or changing Copier task wiring.

## Tasks

- [x] Update both Copier copy examples in the root Skill.
- [x] Add direct static checks for trusted ordinary copy and trusted non-interactive defaults.
- [x] Add a negative assertion that the non-interactive example does not use `-f` or `--force`.
- [x] Confirm that no generated template file changes are required.
- [x] Run required static and generated-project validation.

## Validation Notes

- The ordinary Skill example now uses `copier copy --trust`, and the non-interactive example uses `copier copy --defaults --trust` without enabling overwrite.
- The Copier documentation contract now requires both trusted forms and rejects force flags in the non-interactive defaults form.
- `copier.yml` and generated template files remained unchanged.
- `python3 scripts/check-copier-template.py`, `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, `python3 scripts/validate-changes.py --all`, and `git diff --check` passed with pinned actionlint 1.7.12 available on `PATH`.
