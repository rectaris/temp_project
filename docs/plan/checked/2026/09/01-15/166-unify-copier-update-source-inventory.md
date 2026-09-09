# Unify Copier update copy and staging inventory

status: checked
primary_invariant: the Copier update fixture copies and stages exactly one normalized repository-relative inventory with no parallel hand-maintained path list
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
preservation_scope:
  - scripts/check-copier-template.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/09/01-15/179-integrate-validation-witness-migration-provenance.md
  - docs/plan/checked/2026/09/01-15/165-enforce-validation-witness-maps.md
  - docs/plan/checked/2026/08/16-31/164-bind-replan-contract-validation-baseline.md
  - docs/plan/checked/2026/08/16-31/202-freeze-bounded-shell-lexical-projection.md
  - docs/plan/checked/2026/08/16-31/203-derive-bounded-shell-function-table.md
  - docs/plan/checked/2026/08/16-31/204-derive-bounded-shell-execution-graph.md
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
  - docs/plan/replanned/2026/08/16-31/130-map-acceptance-validation-witnesses.md
  - tests/validation_tools/plan.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
predecessor_plans:
  - docs/plan/checked/2026/09/01-15/165-enforce-validation-witness-maps.md
replan_source: docs/plan/active/130-map-acceptance-validation-witnesses.md
replan_contract: docs/plan/replanned/contracts/130-map-acceptance-validation-witnesses.json
integration_gates:
  - Plan 165 must be checked and its exact checked archive path must replace this active predecessor before implementation
  - the inventory must include every source path accepted through Plan 179 and introduced by Plans 164, 165, 186, and 191 before this plan's complete Copier fixture runs
successor_plans:
  - docs/plan/active/163-capture-validation-witness-migration-provenance.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - docs/plan/active/165-enforce-validation-witness-maps.md
  - docs/plan/active/166-unify-copier-update-source-inventory.md
  - docs/plan/active/167-integrate-validation-witness-enforcement.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: Copier更新fixtureのcopyとGit stagingを同一inventoryから生成する。

## Decisions

- copier-update-source-inventory means the one normalized path list consumed for both fixture copying and Git staging.
- Keep one line-oriented normalized repository-relative inventory as the sole source for both operations.
- Reject blank, duplicate, absolute, traversal, dot-segment, backslash, symlink, missing, directory, and out-of-root entries before copying.
- Stage each successfully copied path immediately and keep the complete required-Copier fixture authoritative.

## Tasks

- [x] Review and retain only the valid parts of the existing inventory candidate.
- [x] Add deterministic inventory drift and invalid-path checks without duplicating the path set in test code, and prove the copy and staging connection through the checked broad checker.
- [x] Run focused validation and the authoritative Copier fixture once, archive, and commit.

## Validation Notes

- This plan owns the preserved tests/copier-update.sh and inventory candidate; it does not change witness lifecycle policy or parsing.
- Its complete Copier update is its own inventory acceptance boundary and does not replace the earlier Plan 179 or later Plan 167 authoritative run.
- `successor_plans` preserves the immutable Plan 130 lineage; Plan 179 replaces Plan 163 only in operational dependencies.
- 44 inventory entries were reviewed: each names one existing, non-symlinked, repository-relative regular file, and no entry is duplicated.
- The second integration gate is met by adding `template/.project-agent-workflow/scripts/restructure-plan.py`, the generated command Plan 164 introduced and the fixture runs as `.project-agent-workflow/scripts/restructure-plan.py --verify`. Every other Plan 179, 164, and 165 source path was already declared.
- Plans 186 and 191 introduced only root checker sources (`scripts/check-copier-template.py`, `scripts/project_workflow/*.py`). The fixture runs them from the repository, never from the update source, so they are not update source paths and stay out of the inventory.
- The fixture now rejects duplicate, symlinked, missing, non-regular, and out-of-root entries before copying, next to the existing blank, absolute, traversal, dot-segment, and backslash checks. The path set is read only from the inventory file; no rejection duplicates it.
- Each rejection was exercised once against the real fixture with one temporarily appended entry: duplicate, missing, directory, symlinked file, and a path under a root symlink that resolves outside the repository. Every case stopped before any copy or staging.
- Focused validation: `python3 tests/test-validation-tools.py`, `python3 scripts/check-copier-template.py`, `git diff --check`. The checker still binds the single inventory declaration and the single inventory-driven copy and staging loop.
- Authoritative validation ran once after the candidate was complete: `python3 tests/test-validation-tools.py`, `tests/copier-update.sh --require-copier`, `git diff --check`, plus `scripts/lint-project-workflow.sh` and `tests/smoke.sh`.
- Activation required one recorded activation rebind record, because the rebind baseline projection for this plan was still `deferred`. The plan was restored to that recorded deferred state before the activation transaction cleared the deferred reason and rebound the checked Plan 165 predecessor.
