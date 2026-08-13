# Prepare the v1.4.1 pull request and post-merge release

status: checked
task_types:
  - planning_docs
  - template_workflow
  - external_services
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: low
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
  - docs/plan/checked/2026/08/01-15/082-release-v140.md
  - docs/plan/checked/2026/08/01-15/083-pr3-codex-review-remediation.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - tests/copier-minimum.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Prepare the backward-compatible fixes and documentation corrections since v1.4.0 as v1.4.1 without changing the package placeholder version.
  - Keep an empty Unreleased section and move the current entries under a 2026-08-13 v1.4.1 heading.
  - Update README fixed stable-version examples from v1.4.0 to v1.4.1 without changing external link targets.
  - Preserve every published tag and avoid history rewriting.
  - Complete release validation and resolve rejection files, conflicts, or unclassified tracked-file deletion before publishing the pull request.
  - Archive this plan and commit release preparation before pushing `agent/v141-review-remediation` and opening its draft pull request to `main`.
  - Do not create or push the v1.4.1 tag or publish the GitHub Release until the pull request is merged and the final main commit is verified.
  - Fix the post-merge publication targets as `rectaris/temp_project:refs/tags/v1.4.1` and `rectaris/temp_project:release:v1.4.1` for a later explicitly authorized release operation.
checked_summary_ja: PR 3のreview修正と文書更新をv1.4.1として検証し、マージ後のリリース対象を確定した。

## Decisions

- Use v1.4.1 because the post-v1.4.0 changes are backward-compatible fixes and documentation corrections.
- Include README and CHANGELOG release preparation in the pull request so the merged main commit can be tagged without another repository change.
- Publish only the branch and draft pull request now; defer the tag and GitHub Release until after merge.

## Tasks

- [x] Update README stable-version examples and the CHANGELOG release heading for v1.4.1.
- [x] Run the required local release validation and inspect blockers.
- [x] Archive this plan and commit release preparation.
- [x] Fix the release branch and draft pull request targets for post-plan publication.

## Validation Notes

- `UV_CACHE_DIR=.uv-cache uv sync` passed, and `uv run copier --version` reported Copier 9.15.1.
- `scripts/lint-project-workflow.sh` passed with pinned Actionlint 1.7.12 available on `PATH`.
- `REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh` passed.
- `tests/copier-update.sh --require-copier` passed, including the replanned-contract and plan-history preservation lanes.
- Python 3.11.12 passed `REQUIRE_MINIMUM_COMPAT=1 tests/copier-minimum.sh`.
- `python3 scripts/validate-changes.py --all` and `git diff --check` passed.
- No `*.rej`, `*.orig`, `*.backup`, or `*.pre-*` blocker exists outside ignored tool/cache directories, and the local `v1.4.1` tag is unused.
- The branch and draft pull request are the only publication operations in this plan. Tag and GitHub Release publication remain deferred until the pull request is merged.
