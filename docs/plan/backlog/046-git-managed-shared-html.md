# Design Git-managed HTML reports for team sharing

status: backlog
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: pending
write_scope:
  - copier.yml
  - docs/plan/
  - template/
  - tests/
context_files:
  - docs/plan/checked/045-local-human-report-html.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Select a project-owned Git-tracked destination and define whether HTML or structured source is the reviewed artifact.
  - Define regeneration ownership, source-hash freshness checks, retention, removal, and merge-conflict behavior.
  - Define secret, private-data, untrusted-content, accessibility, and external-resource review gates before publication.
  - Preserve non-destructive Copier updates and prevent managed template files from owning project report content.
  - Prove team access and stale-report detection in a generated-project fixture before enabling automatic commits.
checked_summary_ja: チーム共有する HTML を Git 管理する場合の保存先、更新責任、鮮度確認、機密情報検査を決定して実装する。

## Decisions Required Before Promotion

- Run a fresh decision audit before moving this plan to active work.
- Decide the project-owned output path and whether generated HTML is reviewed directly or rebuilt from a tracked structured source.
- Decide whether publishing means a repository file, CI artifact, or hosted static site; do not combine these lifecycles implicitly.
- Decide who may regenerate, approve, supersede, and delete a shared report.
- Decide how a report proves that its source commit and evidence are still current.

## Tasks

- [ ] Resolve the storage, publication, ownership, and retention decisions.
- [ ] Define the security and accessibility acceptance gates.
- [ ] Update the write scope and validation list after the decisions are accepted.
- [ ] Obtain explicit human approval before promotion to active implementation.

## Validation Notes

Pending promotion and implementation.
