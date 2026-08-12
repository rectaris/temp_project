# Keep smoke render source committable without template drift

status: checked
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - docs/plan/active/063-smoke-render-source.md
  - tests/smoke.sh
context_files:
  - docs/plan/checked/2026/08/01-15/054-copier-update-fail-closed.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - tests/smoke.sh
  - scripts/lint-project-workflow.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - The smoke test succeeds from a clean repository when the selected render-source files have no local differences.
  - The smoke test still creates an isolated commit before tagging and rendering the candidate template.
  - The render-source workaround changes only temporary test state and does not modify the repository under test.
checked_summary_ja: smoke 用 render source を差分の有無にかかわらず固定できるようにする。

## Context

Plan 054 made the smoke test create an isolated render-source clone and commit selected candidate files. Once those files match the committed source, the unconditional commit exits nonzero because there is nothing to commit, so the required smoke validation fails on a clean repository.

## Decisions

- Permit an empty commit in the temporary render-source clone so every smoke run has one deterministic isolated candidate commit.
- Keep the fix separate from plan 058 and regenerate the plan 058 candidate from the repaired HEAD.

## Tasks

- [x] Add the minimal empty-commit behavior to the temporary render-source commit.
- [x] Verify smoke behavior from a clean source tree.
- [x] Run the required validation commands.

## Validation Notes

- Accepted sandbox candidate `095acafa6fd3711b4820318e649b9416bd1b6688eca5ebe4e7db7955fcf4d2c4` after scope and patch review.
- `tests/smoke.sh` passed in an independent clean review clone and after applying the candidate to the source repository. The existing fallback backend reported that `actionlint` was unavailable.
- `scripts/lint-project-workflow.sh` passed in both environments.
- `python3 scripts/validate-changes.py --all` passed in both environments.
- `git diff --check` passed in both environments.
