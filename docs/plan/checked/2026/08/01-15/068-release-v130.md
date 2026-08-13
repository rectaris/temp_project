# Release v1.3.0 and open dev-to-main pull request

status: checked
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
  - Prepare exact post-plan publication targets for dev, v1.3.0, the dev-to-main draft pull request, and the v1.3.0 GitHub Release; execute each only after this plan is archived and its applicable fresh policy check succeeds.
  - Do not merge the pull request, rewrite tags, publish credentials, or change the reusable external-service template policy.
  - Treat remote publication and confirmation as post-plan release operations, and report their results separately without rewriting this checked archive.
checked_summary_ja: 後方互換機能を v1.3.0 として公開するための変更、検証、GitHub 公開対象を確定した。

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

- [x] Update README stable-version examples and CHANGELOG release headings for v1.3.0.
- [x] Run and record every required local release validation.
- [x] Fix the post-plan publication targets as `rectaris/temp_project:refs/heads/dev`, `rectaris/temp_project:refs/tags/v1.3.0`, `rectaris/temp_project:refs/heads/dev->refs/heads/main`, and `rectaris/temp_project:release:v1.3.0`.
- [x] Archive the plan and commit the release record before creating the annotated tag.

## Validation Notes

- `UV_CACHE_DIR=.uv-cache uv sync` and `UV_CACHE_DIR=.uv-cache uv run copier --version`: passed with Copier 9.15.1.
- `scripts/lint-project-workflow.sh`: passed, including 26 root external-service policy tests.
- `REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh`: passed.
- `python3 tests/test-hooks.py`: 34 tests passed.
- `REQUIRE_COPIER=1 tests/copier-update.sh`: passed with a clean migration target.
- `REQUIRE_MINIMUM_COMPAT=1 tests/copier-minimum.sh`: the ambient Python 3.12 run correctly rejected the version mismatch; rerun with the repository's installed Python 3.11.12 and Copier 9.6.0 passed.
- YAML parsing, required actionlint, `git diff --check`, rejection-file search, and tracked-file status checks passed.
- No external link target changed. No `*.rej` or `*.orig` file was produced, and the only pre-archive worktree changes are this plan, `CHANGELOG.md`, and `README.md`.
- Remote publication is intentionally outside the checked-plan lifecycle. Each external write still requires an immediate versioned policy authorization, and its result will be reported in the final response.
