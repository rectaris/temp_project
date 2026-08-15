# Release v1.4.2

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
  - docs/plan/checked/2026/08/01-15/084-prepare-release-v141-pr.md
  - docs/plan/checked/2026/08/01-15/085-ai-test-modularization.md
  - docs/plan/checked/2026/08/01-15/086-copier-checker-inventory.md
  - docs/plan/checked/2026/08/01-15/087-ai-facing-layout.md
  - docs/plan/checked/2026/08/01-15/088-copier-update-safety-contract.md
  - docs/plan/checked/2026/08/01-15/089-copier-wrapper-self-update.md
required_specs:
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
  - tests/copier-update.sh --require-copier
  - REQUIRE_MINIMUM_COMPAT=1 tests/copier-minimum.sh
  - python3 scripts/check-yaml.py .
  - REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh .
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Release the backward-compatible source organization, Copier-update preservation, isolated npm validation, and self-replacing wrapper fixes since v1.4.1 as v1.4.2 without changing pyproject.toml's package placeholder version.
  - Keep an empty Unreleased section and add a 2026-08-15 v1.4.2 heading containing the complete user-relevant changes since v1.4.1.
  - Update README fixed stable-version examples from v1.4.1 to v1.4.2 without changing external link targets.
  - Preserve every published tag and avoid history rewriting.
  - Complete the documented release validation and resolve rejection files, conflicts, backup artifacts, or unclassified tracked-file deletion before publication.
  - Archive this plan and commit release preparation before any post-plan publication operation.
  - Fix the post-plan publication targets as `rectaris/temp_project:refs/heads/agent/ai-context-refactor`, `rectaris/temp_project:refs/heads/agent/ai-context-refactor->refs/heads/main`, `rectaris/temp_project:refs/tags/v1.4.2`, and `rectaris/temp_project:release:v1.4.2`; public-communication operations require a current user confirmation that names the exact target and effect.
  - Before tagging, record the remote `main` exact OID, require that it contains the release-preparation commit, validate a clean checkout of that OID, and confirm that the local and remote `v1.4.2` tag names are unused.
  - Create an annotated `v1.4.2` tag only at that recorded OID, verify that `v1.4.2^{}` dereferences to the same OID, and publish the GitHub Release only after the tag push is verified.
checked_summary_ja: Copier更新と隔離検証の後方互換修正を v1.4.2 として検証し、公開対象とマージ後の検証条件を確定した。

## Decisions

- Use v1.4.2 because all generated-project effects since v1.4.1 are backward-compatible fixes or internal source/test organization.
- Publish the existing release branch through a main pull request; create the annotated tag and GitHub Release only from the verified merged main commit.
- Keep pyproject.toml's placeholder version unchanged and use the Git tag as the Copier release identity.
- Keep publication outside this plan. A branch or tag push may proceed only after its fresh ordinary-write policy gate; a pull request or GitHub Release needs current user confirmation for its exact target and `public_communication` effect before the corresponding gate and call.
- Do not merge the pull request as an agent operation. Treat a merge completed by the user or GitHub as the condition that enables the recorded remote-main verification and later tag publication.

## Tasks

- [x] Update CHANGELOG and README for v1.4.2.
- [x] Run the complete local release validation and inspect publication blockers.
- [x] Confirm the validated release-preparation files to archive and commit before publication.
- [x] Fix the branch, pull-request, tag, release, and post-merge verification targets for post-plan publication.

## Validation Notes

- `UV_CACHE_DIR=.uv-cache uv sync` passed, and `UV_CACHE_DIR=.uv-cache uv run copier --version` reported Copier 9.15.1.
- `scripts/lint-project-workflow.sh` passed with Actionlint 1.7.12 available on `PATH`.
- `REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh` passed.
- `python3 tests/test-hooks.py` passed 34 tests.
- `tests/copier-update.sh --require-copier` passed, including v1.4.1 wrapper replacement and the v1.2.1 migration path.
- Python 3.11.12 passed `REQUIRE_MINIMUM_COMPAT=1 tests/copier-minimum.sh` with Copier 9.6.0.
- `python3 scripts/check-yaml.py .` parsed 33 YAML files, and `REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh .` passed.
- `python3 scripts/validate-changes.py --all` and `git diff --check` passed.
- No unresolved index entries, tracked conflicts, `*.rej`, `*.orig`, `*.backup`, or `*.pre-*` release blocker exists outside ignored tool/cache directories.
- `pyproject.toml` remains unchanged at the `0.0.0` placeholder version, and no file mode or symbolic-link change is present.
- README changes only the three fixed stable-version examples from v1.4.1 to v1.4.2 and preserves every external URL target.
- The local and remote `v1.4.2` tag names and the remote release branch are unused; remote `main` was `1446c8df0d076c3db43ded371f87b38470c0d827` at the read-only publication check.
- Independent review found no remaining High, Medium, or Low finding before authoritative validation.
