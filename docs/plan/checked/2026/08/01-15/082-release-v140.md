# Release v1.4.0

status: checked
task_types:
  - planning_docs
  - template_workflow
  - external_services
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: medium
implementation_ambiguity: low
write_scope:
  - CHANGELOG.md
  - README.md
  - docs/plan/
context_files:
  - AGENTS.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/external-services.yaml
  - references/template-development.md
  - docs/plan/checked/2026/08/01-15/068-release-v130.md
required_specs:
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 -m pytest tests/test-hooks.py
  - tests/copier-update.sh --require-copier
  - tests/copier-minimum.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Release the backward-compatible orchestration and plan-restructuring additions since v1.3.0 as v1.4.0 without changing pyproject.toml's package placeholder version.
  - Keep an empty Unreleased section and move the current accumulated entries under a 2026-08-13 v1.4.0 heading.
  - Update README fixed stable-version copy and examples from v1.3.0 to v1.4.0 without changing external link targets.
  - Preserve every published tag and avoid history rewriting.
  - Complete every documented release validation and resolve generated rejection files, conflicts, or unclassified tracked-file deletion before publication.
  - Archive this plan and commit the release record before creating an annotated v1.4.0 tag at the final main release commit.
  - Publish only the exact targets `rectaris/temp_project:refs/heads/main`, `rectaris/temp_project:refs/tags/v1.4.0`, and `rectaris/temp_project:release:v1.4.0`, each after a fresh applicable external-service policy authorization.
  - Prepare confirmation of the main and tag GitHub Actions runs and the published GitHub Release target as post-plan release operations.
checked_summary_ja: オーケストレーションとplan再構成の後方互換機能を v1.4.0 として検証し、公開対象を確定した。

## Decisions

- Use v1.4.0 because the release adds backward-compatible generated workflow and orchestration features.
- Use an annotated tag matching the current stable-tag convention.
- Keep repository release preparation and validation in the checked plan; execute and report remote publication after archival.

## Tasks

- [x] Update README stable-version examples and the CHANGELOG release heading for v1.4.0.
- [x] Run every required local release validation and inspect the release diff for blockers.
- [x] Archive this plan and commit the release record on main.
- [x] Fix main, tag, and GitHub Release publication targets for post-plan execution and CI confirmation.

## Validation Notes

- `UV_CACHE_DIR=.uv-cache uv sync` passed, and Copier reported version 9.15.1.
- Pinned actionlint 1.7.12 was installed with checksum verification under the ignored `.agent-artifacts/release-tools/` path.
- `scripts/lint-project-workflow.sh` and the required Actionlint/Copier smoke suite passed.
- `python3 tests/test-hooks.py` passed 34 tests.
- `tests/copier-update.sh --require-copier` passed with plan-history preservation coverage.
- The ambient Python 3.12 run correctly rejected the minimum-version mismatch; Python 3.11.12 with Copier 9.6.0 passed `REQUIRE_MINIMUM_COMPAT=1 tests/copier-minimum.sh`.
- YAML parsing, required GitHub Actions lint, `python3 scripts/validate-changes.py --all`, and `git diff --check` passed.
- No `*.rej`, `*.orig`, `*.backup`, or `*.pre-*` blocker exists. Local and remote tag `v1.4.0` are both unused.
- External link targets are unchanged. Remote publication remains a post-plan operation requiring a fresh exact authorization for each write.
