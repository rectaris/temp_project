# Correct v1.1 adoption validation and Stop-hook wiring

status: checked
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
write_scope:
  - README.md
  - copier.yml
  - docs/plan/
  - references/
  - scripts/
  - template/
  - tests/
context_files:
  - ../supportcard-status/.codex/hooks.json
  - ../supportcard-status/.gitignore
  - ../supportcard-status/scripts/validate-copier-adoption.sh
  - .agent-artifacts/referent-contracts/copier-v111-correction/contract.json
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - tests/copier-minimum.sh
  - tests/root-plan-lifecycle.sh
  - git diff --check
acceptance:
  - Adoption conflict scanning ignores Git-ignored dependency environments while still rejecting index conflicts, repository-visible conflict markers, and rejection files.
  - Generated validate-changes excludes the migration backup from command selection while continuing to validate current managed and project-owned changes.
  - Generated validate-changes selects managed plan validation only when the project-owned plan index uses the managed format.
  - Change-aware security validation ignores unchanged project-owned fixtures while continuing to scan changed files and managed workflow files.
  - Managed external-service validation does not reinterpret a customized legacy credential schema and reports the policy for project review.
  - Existing Hook configuration keeps its project entries and invokes the managed Stop lifecycle gate after adoption.
  - The legacy Stop-hook path forwards to the managed gate instead of disabling it.
  - Downstream assertions that pin the previous Copier tag remain project-owned and are reported for review.
checked_summary_ja: Git 管理対象外の環境と移行バックアップによる誤検出を除き、既存 Hook 設定から managed Stop gate が動作するように v1.1 採用処理を修正した。

## Problem

The released v1.1.0 adoption operation changes the destination successfully but can fail afterward because its conflict scan reads ignored dependency environments.

The generated change-aware validator also treats archived migration code as current code, and a preserved pre-v1 Hook configuration does not register the managed Stop lifecycle gate.

## Goal

Make the one-time adoption operation complete successfully in repositories with ignored dependency environments and preserved Hook configuration without weakening conflict, validation, or lifecycle checks.

## Decisions

- Scan files reported by Git as tracked or unignored and untracked, excluding the migration backup.
- Keep paths under .project-agent-workflow-migration excluded from validate-changes changed-file selection; do not require the backup to be ignored or deleted.
- Keep managed plan lint selected only when docs/plan/plan.md uses the managed index format; preserve other project-owned plan formats for repository-specific validation.
- Use static security scans limited to Git-visible changed files during change-aware validation, with explicit managed-only and repository-wide modes for other callers.
- Keep managed external-service policy check selected only when docs/agent/external-services.yaml declares authentication and credential_reference and does not declare credential_env; report the legacy project-owned policy for explicit review.
- Use existing hook configuration extended with one missing Stop command while the legacy Stop path forwards to the managed implementation.
- Ensure downstream files that assert the previous Copier tag remain unchanged and are listed in the migration manifest for repository-specific follow-up.
- Keep v1.1.0 immutable and prepare a later patch release after validation.

## Tasks

- [x] Add regression tests for ignored conflict markers and repository-visible conflicts.
- [x] Exclude migration backup paths from generated change-aware validation.
- [x] Gate managed plan validation on the managed plan-index format.
- [x] Align static security scanning with changed-file and managed ownership boundaries.
- [x] Gate managed external-service validation on its schema and preserve ambiguous legacy credential descriptions.
- [x] Restore managed Stop-gate execution for preserved Hook configuration and legacy paths.
- [x] Reproduce the corrected adoption against a customized downstream clone.
- [x] Run the full template validation matrix and prepare the checked plan without moving v1.1.0.

## Validation Notes

- Focused regression suites passed: Copier adoption 6 tests, Hook behavior 27 tests, and validation tooling 14 tests.
- `scripts/lint-project-workflow.sh`, `tests/smoke.sh` with actionlint, `tests/copier-update.sh`, and the Copier 9.6.0 minimum-version lane passed against the staged snapshot.
- A temporary `supportcard-status` clone completed adoption and generated change-aware validation with no tracked deletion or unmerged index. Its build, 351 unit tests, structure check, static security check, and repository-specific plan lint passed.
- The downstream adoption validator passed after omitting only its two project-owned v0.4.5 assertions. Those assertions and the legacy external-service credential descriptions remain explicit downstream follow-up.
- No link target changed. A v1.1.1 tag and remote release remain deferred until explicitly requested.
