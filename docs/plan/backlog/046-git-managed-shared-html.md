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

## Accepted Decisions

A decision audit ran against this plan and the user accepted the outcome below. These decisions bound the design; they do not approve promotion.

- Store the shared report under the project-owned path `docs/human-report/`. The existing local output root `.agent-artifacts/human-reports/` is Git ignored and cannot carry a tracked file, and `.project-agent-workflow/` is Copier managed and cannot own project report content.
- Review the Git-tracked structured source, and treat the HTML as a derived publication file that a freshness check binds to that source.
- Limit publishing to a repository file. Keep CI artifacts and hosted static sites out of scope until a separate approved plan grants that authority.
- Regenerate through an explicit command and let a human review, stage, and commit. Enable automatic commits only after a generated-project fixture proves team access and stale-report detection, and only through explicit project configuration.
- Record the source commit, source path, source SHA-256, generator version, and generation time in both the structured source and the HTML, and let the validator fail closed when the current repository bytes no longer match.
- Update a shared report only through an explicit supersede or removal commit. Do not prune automatically, and treat an unresolved merge conflict as stale or blocked rather than overwriting it.
- Run the publication gates over both the structured source and the rendered HTML, and fail closed on raw logs, local artifacts, secret-like material, unreviewed private data, and unsafe source paths.
- Keep the shared HTML standalone with embedded CSS, no JavaScript, no external resources, semantic headings, table headers, a document language, and a print-friendly layout.
- Keep Copier managing only the generator, policy, configuration, and validator. The shared report source and generated HTML stay project-owned and outside inventory-managed replacement.
- Prove team access and stale-report detection in a new generated-project fixture that commits an approved report to the tracked path, confirms visibility from a separate checkout, and confirms that the freshness validator fails after the source changes.
- Treat the shared report as a reviewed project document rather than a raw agent artifact. Do not place it under `.agent-artifacts/` and do not use raw logs or unreviewed local artifacts as its source.

## Decisions Required Before Promotion

- Obtain explicit human approval for promotion to active implementation.
- Confirm the exact explicit project configuration that would later enable automatic commits.

## Tasks

- [x] Resolve the storage, publication, ownership, and retention decisions.
- [x] Define the security and accessibility acceptance gates.
- [ ] Update the write scope and validation list after the decisions are accepted.
- [ ] Obtain explicit human approval before promotion to active implementation.

## Validation Notes

Pending promotion and implementation.
