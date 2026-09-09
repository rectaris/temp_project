# Wire the validation-witness Copier transition

status: replanned
replan_reason_codes:
  - parent_remediation_budget_exhausted
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - copier.yml
  - scripts/check-copier-template.py
  - scripts/project_workflow/copier_inventory.py
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/180-admit-live-validation-witness-guardian.md
  - docs/plan/checked/2026/08/16-31/181-verify-plan176-successor-acceptance.md
  - docs/plan/checked/2026/08/16-31/177-align-validation-witness-provenance-policy.md
  - docs/plan/active/166-unify-copier-update-source-inventory.md
  - docs/plan/replanned/2026/08/16-31/163-capture-validation-witness-migration-provenance.md
  - tests/test-copier-migration.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - pytest tests/test-copier-migration.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - pytest tests/test-copier-migration.py
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/178-wire-validation-witness-copier-transition.md
replan_contract: docs/plan/replanned/contracts/178-wire-validation-witness-copier-transition.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/182-admit-v145-copier-wiring.md
  - docs/plan/active/183-build-bounded-copier-transition-fixture.md
  - docs/plan/active/184-verify-plan178-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: v1.4.4からv1.4.5へのCopier更新でguardian protocolを単一inventoryから実行できるようにする。

## Decisions

- Define the concrete transition as one disposable downstream Git project copied at v1.4.4 and updated to a synthetic v1.4.5 target containing the snapshot script in the single source inventory.
- Wire v1.4.5 before and after migration commands only after Plan 180 establishes their exact CLI and recovery contract and Plan 181 verifies the nested successor lineage.
- Extend the existing normalized source inventory rather than creating a Plan 163-specific copy or staging list.
- Keep the full Copier transition reserved for Plan 179; focused checks must prove command selection, source availability, inventory membership, and fixture construction without performing the authoritative update.

## Tasks

- [ ] Align the preserved copier.yml and inventory-helper candidate with the checked Plan 180 CLI and Plan 181 dependency gate.
- [ ] Add the snapshot script and all required v1.4.5 source paths to the one fixture inventory.
- [ ] Construct and commit the synthetic v1.4.5 source ref in the disposable fixture, start from a committed v1.4.4 pre-schema downstream state, and assert pending then consumed provenance across the update.
- [ ] Extend the Copier template checker with deterministic checks for missing source, incorrect version boundary, bypassed inventory, and direct-script-only fixture coverage.
- [ ] Run focused validation and independent read-only review; archive and commit only after zero unresolved High or Medium findings.

## Validation Notes

- `tests/copier-update.sh --require-copier` is intentionally reserved for Plan 179 and must not run in this slice.
