# Release v1.2.1 after v1.2.0 CI recovery

status: in_progress
task_types:
  - security
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: approved
write_scope:
  - .github/workflows/ci.yml
  - CHANGELOG.md
  - docs/plan/
  - tests/copier-update.sh
  - tests/test-validation-tools.py
context_files:
  - README.md
  - references/template-development.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/test-hooks.py
  - tests/copier-update.sh
  - tests/copier-minimum.sh
  - git diff --check
acceptance:
  - Preserve the published v1.2.0 tag without rewriting it and record its tag-push whitespace failure.
  - Fix the new-tag whitespace comparison without weakening branch, pull-request, or ordinary push checks.
  - Isolate the Copier update fixture tag from real release tags so post-release validation remains deterministic.
  - Publish the correction and accumulated backward-compatible feature additions as v1.2.1.
  - Complete every documented release validation with pinned dependencies and required Copier coverage.
  - Create an annotated v1.2.1 tag at the corrected release commit and push main and the tag to origin.
  - Confirm the GitHub Actions runs triggered by the release complete successfully.
checked_summary_ja: v1.2.0 の tag push で判明した whitespace gate を修正し、後方互換機能を v1.2.1 として検証、タグ作成、GitHub への公開まで完了した。

## Decisions

- Keep the published v1.2.0 tag immutable and release its CI correction as v1.2.1.
- Keep the Copier update fixture's target contents unchanged while assigning its expected tag to a separate test-only commit.
- Release the accumulated backward-compatible Copier questions, template features, generated policy, and helper-agent additions as v1.2.1.
- Use an annotated tag matching the existing stable-tag convention.
- Treat the pushed main branch, pushed tag, and successful release-triggered CI as the release completion boundary.
- Do not create a GitHub Release object because the repository release flow uses Git tags and no prior GitHub Release exists.

## Tasks

- [x] Update the changelog for v1.2.0 and its v1.2.1 CI correction.
- [x] Run the documented release validation with pinned tools.
- [x] Fix and validate the new-tag whitespace comparison.
- [ ] Archive this release plan and commit the release record.
- [ ] Create and verify the annotated v1.2.1 tag.
- [ ] Push main and v1.2.1 to origin.
- [ ] Confirm release-triggered GitHub Actions complete successfully.

## Validation Notes

- `UV_CACHE_DIR=.uv-cache uv sync` passed and `UV_CACHE_DIR=.uv-cache uv run copier --version` reported Copier 9.15.1.
- Pinned actionlint 1.7.12 installed with checksum verification under the ignored `.agent-artifacts/release-tools/` path.
- `scripts/lint-project-workflow.sh` passed the complete root workflow test suite.
- `REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh` passed every generated-project and pairwise fixture with pinned actionlint available.
- `tests/test-hooks.py` passed 28 tests.
- `REQUIRE_COPIER=1 tests/copier-update.sh` passed the direct-update and pre-v1 adoption lanes.
- `REQUIRE_MINIMUM_COMPAT=1 tests/copier-minimum.sh` passed under Python 3.11.12 and Copier 9.6.0.
- `UV_CACHE_DIR=.uv-cache uv run python scripts/check-yaml.py .`, `REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh .`, and `git diff --check` passed.
- `origin/main` is an ancestor of the release commit candidate with no remote-only commit, and `v1.2.0` does not yet exist.
- The published v1.2.0 tag run passed lint, smoke, YAML, actionlint, hooks, Copier update, and minimum compatibility, then failed because the tag event's all-zero `before` value caused the whitespace gate to compare the repository against an empty tree and report four unchanged legacy files.
- The concurrent main run passed through hooks and failed in Copier update without a reported assertion; the same commit's tag run and the pre-release local run passed Copier update, so v1.2.1 must re-run both release-triggered workflows before completion.
- The Copier update failure reproduced after publishing v1.2.0 because the fixture moved `v1.1.2` onto a commit that already had the real `v1.2.0` tag; an empty test-only commit now keeps the expected fixture tag unambiguous.
- The tag-range regression test, pinned actionlint, root workflow lint, smoke test, 28 hook tests, Copier update test, Python 3.11.12 with Copier 9.6.0 minimum-compatibility test, YAML parse, and `git diff --check` passed after both corrections.
