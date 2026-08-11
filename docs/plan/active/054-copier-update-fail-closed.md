# Make the documented Copier update path fail closed

status: in_progress
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - copier.yml
  - docs/plan/active/054-copier-update-fail-closed.md
  - scripts/
  - template/README.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
  - tests/copier-update.sh
context_files:
  - AGENTS.md
  - references/template-development.md
  - tests/lib-copier.sh
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - The documented `copier update --trust` path exits nonzero when unresolved index conflicts, rejection files, complete inline conflict blocks, or unclassified tracked-file deletions remain.
  - A clean initial copy remains supported outside a Git repository.
  - A conflict-free update continues to preserve project-owned files and validation behavior.
  - An intentionally overlapping managed-file update fixture proves the failure is surfaced by the supported command itself.
checked_summary_ja: 文書化された Copier update 経路を競合、rej、未分類削除で失敗させ、成功終了のまま不整合を残さない。

## Context

The documented Copier update path must exit nonzero when conflicts, rejection files, or unclassified deletions remain.

Copier can return success while leaving an unresolved Git conflict, but the generated documentation currently directs users to the raw command without a deterministic post-update gate.

## Decisions

- Keep Copier and `copier.yml` as the long-term interface.
- Run the result gate as part of the trusted Copier task sequence rather than relying on a separate optional manual command.
- Detect complete conflict blocks so valid Markdown setext headings are not rejected.

## Tasks

- [ ] Add a post-copy/update result validator that is safe for initial non-Git copies.
- [ ] Wire the validator into the trusted Copier task sequence.
- [ ] Add a conflict-producing update fixture and retain the conflict-free update lane.
- [ ] Align generated update documentation with the enforced behavior.
- [ ] Run the required validation commands.

## Validation Notes

- Pending.
