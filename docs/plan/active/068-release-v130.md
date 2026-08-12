# Release v1.3.0 and open dev-to-main pull request

status: in_progress
task_types:
  - planning_docs
  - template_workflow
  - external_services
review_class: C
human_design_required: yes
human_approval_status: approved
write_scope:
  - CHANGELOG.md
  - README.md
  - docs/plan/
context_files:
  - AGENTS.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/external-services.yaml
  - references/template-development.md
  - .agent-artifacts/decision-audits/release-v130.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - UV_CACHE_DIR=.uv-cache uv sync
  - UV_CACHE_DIR=.uv-cache uv run copier --version
  - scripts/lint-project-workflow.sh
  - REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh
  - python3 tests/test-hooks.py
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - REQUIRE_MINIMUM_COMPAT=1 tests/copier-minimum.sh
  - UV_CACHE_DIR=.uv-cache uv run python scripts/check-yaml.py .
  - REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh .
  - git diff --check
acceptance:
  - Release the backward-compatible additions since v1.2.1 as v1.3.0 without changing pyproject.toml's package placeholder version.
  - Keep an empty Unreleased section and move the current accumulated entries under a 2026-08-13 v1.3.0 heading.
  - Update README fixed stable-version copy and update examples from v1.2.1 to v1.3.0 without changing external link targets.
  - Preserve every published tag and avoid history rewriting; use the local merge of origin/main into dev as the reconciled release history.
  - Complete every documented release validation and resolve generated rejection files, conflicts, or unclassified tracked-file deletion before publication.
  - Archive this plan and commit the release record before creating an annotated v1.3.0 tag at the final dev release commit.
  - Push exact branch target rectaris/temp_project:refs/heads/dev and exact tag target rectaris/temp_project:refs/tags/v1.3.0 only after fresh ordinary-write policy checks.
  - Open a draft pull request with exact target rectaris/temp_project:refs/heads/dev->refs/heads/main only after a fresh public_communication policy check and matching current-user confirmation.
  - Publish a GitHub Release for exact target rectaris/temp_project:release:v1.3.0 only after a fresh public_communication policy check and matching current-user confirmation.
  - Do not merge the pull request, rewrite tags, publish credentials, or change the reusable external-service template policy.
  - Confirm the resulting remote branch, tag, pull request, GitHub Release, and triggered CI state.
checked_summary_ja: 後方互換機能を v1.3.0 として検証・公開し、dev から main への pull request と同 tag の GitHub Release を作成する。

## Context

Plans 066 and 067 are checked. The sandboxed sequential worker now falls back from unavailable GPT-5.3-Codex-Spark medium to one isolated GPT-5.6-Luna max attempt, and the root external-service gate can authorize exact GitHub operations.

The latest stable tag is v1.2.1. The user explicitly requested tag, release, and dev-to-main pull-request creation.

## Decisions

- Use v1.3.0 for backward-compatible feature additions.
- Keep release-preparation edits inside the sandboxed worker; keep validation acceptance, Git history, tags, external policy decisions, pushes, PR creation, Release publication, and final reporting in the parent session.
- Create a GitHub Release object for this request even though the prior repository release used tags only.
- Open the pull request as draft under the GitHub publish skill default and leave merge authority with the user.
- Use no external link changes; only version text and release history change locally.

## Tasks

- [ ] Update README stable-version examples and CHANGELOG release headings for v1.3.0.
- [ ] Run and record every required local release validation.
- [ ] Archive the plan and commit the release record.
- [ ] Create and verify annotated tag v1.3.0.
- [ ] Push dev and v1.3.0 after exact ordinary-write authorization checks.
- [ ] Create the draft dev-to-main pull request after exact publication authorization.
- [ ] Publish the v1.3.0 GitHub Release after exact publication authorization.
- [ ] Confirm remote objects and CI state.

## Validation Notes

- Pending release preparation.
