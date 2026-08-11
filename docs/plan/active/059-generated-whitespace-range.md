# Check committed whitespace ranges in generated CI

status: in_progress
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - docs/plan/active/059-generated-whitespace-range.md
  - scripts/check-copier-template.py
  - template/.github/workflows/project-agent-workflow.yml
  - tests/smoke.sh
context_files:
  - .github/workflows/ci.yml
  - tests/fixtures/
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/check-yaml.py .
  - REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh .
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Pull-request runs check the merge-base range through the pull-request head SHA.
  - Push runs check the before-to-head range when the before commit is available.
  - New branches or other events fall back to the empty tree through the event head SHA.
  - A committed trailing-whitespace fixture fails the generated workflow's selected command.
checked_summary_ja: 生成 CI の空白検査を clean worktree ではなくイベントの commit 範囲へ適用し、commit 済み違反を検出する。

## Context

The generated GitHub workflow must check committed event ranges for whitespace errors.

The generated workflow runs `git diff --check` on a clean checkout, so committed whitespace errors are not inspected.

## Decisions

- Reuse the event-aware range selection already implemented by the root CI workflow.
- Keep the generated workflow path filters unchanged.

## Tasks

- [ ] Add deterministic source and generated-workflow assertions for event-aware range selection.
- [ ] Replace the clean-worktree check with pull-request, push, and empty-tree branches.
- [ ] Add a committed whitespace regression fixture.
- [ ] Run the required validation commands.

## Validation Notes

- Pending.
