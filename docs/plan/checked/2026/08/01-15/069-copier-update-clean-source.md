# Allow the Copier update fixture to run from a clean source

status: checked
task_types:
  - testing
review_class: B
human_design_required: no
human_approval_status: approved
write_scope:
  - tests/copier-update.sh
  - docs/plan/
context_files:
  - AGENTS.md
  - .github/workflows/ci.yml
  - docs/plan/checked/2026/08/01-15/054-copier-update-fail-closed.md
  - docs/plan/checked/2026/08/01-15/068-release-v130.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_VALIDATION.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - scripts/lint-project-workflow.sh
  - REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh
  - git diff --check
acceptance:
  - Make the temporary migration-target fixture commit succeed when every copied candidate file already matches a clean source HEAD.
  - Preserve the candidate overlay and v1.2.1-to-v1.2.2 update boundary used by the existing test.
  - Change no production behavior and do not weaken any Copier conflict, rejection-file, source-mutation, or unclassified-deletion assertion.
  - Reproduce the clean-source path locally and complete the normal repository validation.
  - Keep the already-published v1.3.0 tag immutable; land the correction only as a later dev and pull-request commit.
checked_summary_ja: クリーンな source HEAD でも Copier 更新 fixture の境界 commit を作成し、既存の失敗閉鎖検証を最後まで実行できるようにした。

## Context

Pull request 2 failed before exercising Copier update assertions because the fixture copied files from a clean source HEAD onto an identical temporary checkout and then required a non-empty Git commit. Local release validation emitted the same `nothing to commit, working tree clean` result, but its nonzero exit was initially not retained by the orchestration wrapper.

## Decision

- Restore empty-commit allowance only for the isolated fixture boundary commit. The tagged commit still represents the selected target state, while dirty candidate overlays remain included when present.

## Tasks

- [x] Make the isolated boundary commit deterministic for both clean and dirty source states.
- [x] Run focused and repository validation.
- [x] Archive and commit the correction before pushing dev again.

## Validation Notes

- GitHub Actions run 31611352762 failed at `git commit` with `nothing to commit, working tree clean`; later Copier assertions did not run.
- The accepted candidate came from `/tmp/sandboxed-plan-worker-output-pVFOSj/manifest.json` at source HEAD `81210e3197f48ccc2298a57993f5d9c8442580f1`; GPT-5.3-Codex-Spark medium returned bounded `usage_limit`, and a fresh GPT-5.6-Luna max attempt succeeded.
- Parent review accepted the single-line `tests/copier-update.sh` change. It adds `--allow-empty` only to the isolated candidate-boundary commit and leaves all safety assertions unchanged.
- `REQUIRE_COPIER=1 tests/copier-update.sh`: passed from the clean committed source and reached `copier update test passed`.
- `scripts/lint-project-workflow.sh`: passed, including 26 external-service authorization tests.
- `REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh`: passed with the pinned actionlint available on `PATH`.
- `git diff --check`: passed.
