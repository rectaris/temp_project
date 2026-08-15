# Release v1.4.4 with Copier runtime and nested-plan fixes

status: checked
task_types:
  - planning_docs
  - template_workflow
  - external_services
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: ordinary
write_scope:
  - CHANGELOG.md
  - README.md
  - copier.yml
  - docs/plan/
  - references/orchestration.md
  - scripts/
  - template/
  - tests/
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/checked/2026/08/01-15/092-release-v143-tag-fixture.md
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
  - Integrate the v1.4.3 Copier runtime remediation and nested-plan durable verification without losing either branch's committed history.
  - Preserve the published Plan 092 and runtime-remediation Plan 093 records, and remap the unpublished nested-plan lineage to unused IDs with valid durable contract digests.
  - Keep root and generated template files byte-identical where the repository inventory requires parity.
  - Keep an empty Unreleased section and add a 2026-08-15 v1.4.4 entry describing the hardlink normalization, untracked-file ownership check, and nested durable-state verification fixes.
  - Update README fixed stable-version examples from v1.4.3 to v1.4.4 without changing external link targets.
  - Complete release validation with Actionlint, Copier, minimum-version compatibility, and all repository checks before publication.
  - Finish with zero unresolved High or Medium independent-review findings.
  - Archive this plan and commit release preparation before any post-plan publication operation.
  - Publish through `rectaris/temp_project:refs/heads/agent/v144-release`, `rectaris/temp_project:refs/heads/agent/v144-release->refs/heads/main`, `rectaris/temp_project:refs/tags/v1.4.4`, and `rectaris/temp_project:release:v1.4.4`, with a fresh external-service gate before each call.
  - Before tagging, verify the merged remote main exact OID in a clean checkout, confirm local and remote v1.4.4 are unused, create an annotated tag at that OID, and require the tag workflow to pass before publishing the GitHub Release.
checked_summary_ja: Copier隔離検証と再計画履歴検証の修正を統合し、v1.4.4の公開対象を確定した。

## Decisions

- Base the release branch on the published v1.4.3 commit from `origin/main`.
- Integrate both committed fix branches and preserve published plan history by remapping only unpublished nested-plan IDs.
- Release the backward-compatible corrections as v1.4.4.
- Keep branch, pull-request, tag, and GitHub Release publication outside the archived implementation plan.

## Tasks

- [x] Integrate the Copier runtime remediation and nested-plan verification commits.
- [x] Remap colliding unpublished plan IDs and verify every durable restructuring contract.
- [x] Update CHANGELOG and README for v1.4.4.
- [x] Run independent review and complete release validation.
- [x] Record the exact post-plan branch, pull-request, tag, and GitHub Release publication targets and gates.

## Validation Notes

- Integrated the Copier runtime remediation and nested-plan durable verification while preserving the published Plan 092 and runtime-remediation Plan 093 records.
- Recorded remap provenance at `039f29f6753913916cb087b8085d855120d8f542`; every Plan 094-096 contract source path, source commit, stored source content, and SHA-256 digest matched.
- Independent read-only review reported zero unresolved High or Medium findings after the provenance and v1.4.2 tag-fixture corrections.
- The authoritative release suite passed once on 2026-08-15 with Actionlint 1.7.12, Copier 9.15.1, Python 3.11.12, and minimum Copier 9.6.0.
- `scripts/lint-project-workflow.sh`, `REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh`, hook tests, Copier update and minimum-version tests, YAML and GitHub Actions lint, `scripts/validate-changes.py --all`, and `git diff --check` all passed.
- Post-plan publication remains limited to the exact branch, pull-request, tag, and release targets recorded in acceptance, with a fresh external-service gate before each operation.
