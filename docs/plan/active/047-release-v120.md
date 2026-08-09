# Release v1.2.0

status: in_progress
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: approved
write_scope:
  - CHANGELOG.md
  - docs/plan/
context_files:
  - README.md
  - references/template-development.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/test-hooks.py
  - tests/copier-update.sh
  - tests/copier-minimum.sh
  - git diff --check
acceptance:
  - Move the accumulated backward-compatible feature additions from Unreleased to v1.2.0 in the changelog.
  - Complete every documented release validation with pinned dependencies and required Copier coverage.
  - Create an annotated v1.2.0 tag at the release commit and push main and the tag to origin.
  - Confirm the GitHub Actions runs triggered by the release complete successfully.
checked_summary_ja: 未リリースの後方互換機能を v1.2.0 として記録し、検証、タグ作成、GitHub への公開を完了した。

## Decisions

- Release the accumulated backward-compatible Copier questions, template features, generated policy, and helper-agent additions as v1.2.0.
- Use an annotated tag matching the existing stable-tag convention.
- Treat the pushed main branch, pushed tag, and successful release-triggered CI as the release completion boundary.
- Do not create a GitHub Release object because the repository release flow uses Git tags and no prior GitHub Release exists.

## Tasks

- [x] Update the changelog for v1.2.0.
- [x] Run the documented release validation with pinned tools.
- [ ] Archive this release plan and commit the release record.
- [ ] Create and verify the annotated v1.2.0 tag.
- [ ] Push main and v1.2.0 to origin.
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
