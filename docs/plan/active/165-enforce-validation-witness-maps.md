# Enforce validation witness maps before execution

status: in_progress
primary_invariant: plan command validation fails closed unless acceptance coverage, lifecycle provenance, authoritative command identity, and every static context path identity are proven
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/planlib.py
  - tests/validation_tools/plan.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/179-integrate-validation-witness-migration-provenance.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - docs/plan/replanned/2026/08/16-31/130-map-acceptance-validation-witnesses.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
replan_source: docs/plan/active/130-map-acceptance-validation-witnesses.md
replan_contract: docs/plan/replanned/contracts/130-map-acceptance-validation-witnesses.json
integration_gates:
  - Plans 179 and 164 must be checked and their exact checked archive paths must replace active context paths before implementation
  - accept legacy omission only from the exact guardian-backed migration evidence integrated by Plan 179 and authoritative identity only from the contract projection defined by Plan 164
successor_plans:
  - docs/plan/active/163-capture-validation-witness-migration-provenance.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - docs/plan/active/165-enforce-validation-witness-maps.md
  - docs/plan/active/166-unify-copier-update-source-inventory.md
  - docs/plan/active/167-integrate-validation-witness-enforcement.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: 受入条件、移行証拠、最終検証command、静的pathを実行前にfail-closedで検証する。

## Decisions

- validation-witness-enforcement means the pre-execution checks over acceptance mappings, migration provenance, contracted validation commands, and static path identity.
- Retain SHA-256 binding and exact source-order coverage for acceptance items.
- Accept a pre-schema integration plan only when its exact committed bytes match the guardian-backed evidence integrated by Plan 179 and its replan-contract lineage remains valid.
- Compare the live authoritative validation sequence with the immutable Plan 164 contract projection before accepting any witness map.
- Reject symlinks in every context path component, not only the final component.
- Use bounded parent implementation and independent review because every changed executable path is validation authority.

## Tasks

- [ ] Replace the current forgeable legacy exception with migration-bound validation.
- [ ] Enforce exact authoritative command preservation and witness-stage rules.
- [ ] Reject symlinked ancestors, traversal, duplicates, stale status, and out-of-root static paths.
- [ ] Add deterministic positive and negative tests, complete focused validation and independent review, archive, and commit.

## Validation Notes

- Preserve the current unaccepted parser and test changes as candidate input; review each hunk against the accepted Plan 179 and Plan 164 contracts before reuse.
- `successor_plans` preserves the immutable Plan 130 lineage; operational dependency paths use Plan 179.
