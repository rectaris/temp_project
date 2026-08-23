# Unify Copier update copy and staging inventory

status: in_progress
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
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/179-integrate-validation-witness-migration-provenance.md
  - docs/plan/active/165-enforce-validation-witness-maps.md
  - docs/plan/replanned/2026/08/16-31/130-map-acceptance-validation-witnesses.md
  - tests/validation_tools/plan.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
replan_source: docs/plan/active/130-map-acceptance-validation-witnesses.md
replan_contract: docs/plan/replanned/contracts/130-map-acceptance-validation-witnesses.json
integration_gates:
  - Plans 179 and 165 must be checked and their exact checked archive paths must replace active context paths before implementation
  - the inventory must include every source path accepted through Plan 179 and introduced by Plans 164 and 165 before the complete Copier fixture runs
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

- [ ] Review and retain only the valid parts of the existing inventory candidate.
- [ ] Add deterministic inventory drift and invalid-path checks without duplicating the path set in test code.
- [ ] Run focused validation and the authoritative Copier fixture once, archive, and commit.

## Validation Notes

- This plan owns the preserved tests/copier-update.sh and inventory candidate; it does not change witness lifecycle policy or parsing.
- `successor_plans` preserves the immutable Plan 130 lineage; Plan 179 replaces Plan 163 only in operational dependencies.
