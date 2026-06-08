# 002 Copier Template

status: completed
review_class: B
target_files:
  - copier.yml
  - template/
  - migrations/
  - tests/
  - scripts/
  - README.md
  - SKILL.md
  - references/
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
  - uvx copier copy with TypeScript, Python, and docs fixtures

## Summary

Made Copier the long-term template interface. Moved generated files from copy-only `assets/templates/` to `template/`, added `copier.yml`, persisted `.copier-answers.yml` in generated repos, added answer fixtures, added static template validation, and documented update/migration practice.

