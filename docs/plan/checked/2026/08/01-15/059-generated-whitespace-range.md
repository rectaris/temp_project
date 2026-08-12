# Check committed whitespace ranges in generated CI

status: checked
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

- [x] Add deterministic source and generated-workflow assertions for event-aware range selection.
- [x] Replace the clean-worktree check with pull-request, push, and empty-tree branches.
- [x] Add a committed whitespace regression fixture.
- [x] Run the required validation commands.

## Validation Notes

- Accepted sandbox candidate `16395482c856e9da93eef4983d40036c3c94424dcee45bc910647d9782a2310c` after scope and patch review.
- `scripts/lint-project-workflow.sh` and `tests/smoke.sh` passed in the independent review clone and source repository. The smoke fixture committed trailing whitespace and confirmed the selected push range failed.
- `python3 scripts/check-yaml.py .` parsed 29 YAML files in both environments.
- `REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh .` passed with local actionlint 1.7.12 in both environments.
- `python3 scripts/validate-changes.py --all` and `git diff --check` passed in both environments.
