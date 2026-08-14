# Repair Copier update and isolated validation contracts

status: checked
primary_invariant: supported Copier updates preserve existing project-owned bytes except exact declared field transitions, and isolated npm validation receives only a lock-bound read-only dependency snapshot
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - copier.yml
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/migrate-sequential-plan-worker.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/run-sandboxed-plan-worker.py
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/migrate-sequential-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/update-from-copier.sh
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - tests/copier-update.sh
  - tests/smoke.sh
  - tests/test-copier-migration.py
  - tests/test-sandboxed-plan-worker.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - template/.project-agent-workflow/ownership.yaml
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-copier-migration.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
validation:
  - python3 tests/test-copier-migration.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Add a v1.4.2 after-migration that replaces only the byte-identical v1.2.1 generated sequential worker profile with the current read-only profile, is idempotent, and stops without overwriting customized workspace-write content.
  - Require the recurring update wrapper to start from a clean Git worktree and make the final validator reject changes to existing project-owned or unclassified bytes outside exact model-field normalization and the recognized sequential-worker transition.
  - Add an explicit dependency-snapshot operation that copies an npm dependency tree outside the repository only after its hidden lock records match package-lock.json, records a complete tree digest, and rejects unsafe file types or escaping links.
  - Let parent-authorized candidate validation accept an explicit dependency snapshot, recheck its package and tree digests against each fresh clone, and bind node_modules read-only while keeping validation network-disabled and PATH fixed.
  - Cover a v1.2.1-to-v1.4.2 synthetic update, AGENTS.md overwrite rejection, customized worker refusal, dependency snapshot tampering, lock mismatch, and npm run verify success in a clone that has no committed or ambient node_modules.
  - Keep root and generated scripts byte-identical where parity is required and finish with zero unresolved High or Medium independent-review findings.
checked_summary_ja: Copier更新の所有ファイル保全、旧ワーカー移行、隔離npm検証の依存物供給を失敗閉鎖で修正した。

## Decisions

- Compare existing project-owned and unclassified paths with committed HEAD after requiring the recurring wrapper to start clean.
- Permit only Copier-managed paths, metadata, exact fixed model-field normalization, and the exact recognized legacy-to-read-only sequential worker transition.
- Replace the sequential worker automatically only when its bytes match the v1.2.1 generated profile; stop for manual review on customized workspace-write content.
- Prepare npm dependencies from an existing project-approved node_modules tree, bind the snapshot to package.json and package-lock.json digests, verify its complete tree digest, and mount it read-only into each fresh validation clone.
- Use a new v1.4.2 migration boundary because the released v1.4.1 tag is immutable.
- Use bounded parent implementation because validation authority and security boundaries change; require independent review before authoritative validation.

## Tasks

- [x] Add regression tests for the legacy worker transition and project-owned byte preservation.
- [x] Implement the worker migration and update-result ownership validation.
- [x] Add dependency snapshot preparation, verification, and read-only validation mounting with regression coverage.
- [x] Update generated policy, inventories, and static parity checks.
- [x] Run focused validation, independent review, and the authoritative suites.
- [x] Archive and commit the accepted change.

## Validation Notes

- `python3 tests/test-copier-migration.py`: passed, 11 tests.
- `python3 tests/test-sandboxed-plan-worker.py`: passed, including fresh-clone npm validation with a read-only private dependency copy.
- `TMPDIR=/var/tmp python3 scripts/check-copier-template.py`: passed.
- `REQUIRE_COPIER=1 tests/copier-update.sh`: passed, including the synthetic v1.2.1-to-v1.4.2 update.
- `TMPDIR=/var/tmp scripts/lint-project-workflow.sh`: passed.
- `TMPDIR=/var/tmp REQUIRE_COPIER=1 tests/smoke.sh`: passed; actionlint was unavailable and its existing optional checks were skipped by the suite.
- `python3 scripts/validate-changes.py --all`: passed.
- `git diff --check`: passed.
- Independent read-only review completed after two parent-direct remediation rounds with zero remaining High, Medium, or Low findings.
- Root and generated migration, validator, and sandboxed-runner scripts are byte-identical where required. No unresolved risk, deferred work, or link change remains.
