# Capture pre-schema validation witness provenance

status: in_progress
primary_invariant: only integration-plan evidence captured from the clean committed project before a Copier update may authorize the pre-schema witness compatibility path
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
  - AGENTS.md
  - copier.yml
  - references/orchestration.md
  - scripts/project_workflow/copier_inventory.py
  - scripts/snapshot-validation-witness-provenance.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - tests/test-copier-migration.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/replanned/2026/08/16-31/130-map-acceptance-validation-witnesses.md
  - template/.project-agent-workflow/scripts/validate-copier-update.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"authoritative","witness":"tests/copier-update.sh --require-copier","authoritative_only_reason":"the genuine pre-update boundary requires a complete versioned Copier transition from a clean committed downstream project"}
replan_source: docs/plan/active/130-map-acceptance-validation-witnesses.md
replan_contract: docs/plan/replanned/contracts/130-map-acceptance-validation-witnesses.json
integration_gates:
  - capture provenance before the Copier update installs schema-1 validation and never infer legacy status from field absence alone
  - Plan 164 must not start until this plan is checked and its exact checked archive path replaces this active dependency
successor_plans:
  - docs/plan/active/163-capture-validation-witness-migration-provenance.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - docs/plan/active/165-enforce-validation-witness-maps.md
  - docs/plan/active/166-unify-copier-update-source-inventory.md
  - docs/plan/active/167-integrate-validation-witness-enforcement.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: Copier更新前のcommit済みplanから旧形式witnessの移行証拠を固定する。

## Decisions

- validation-witness-migration-snapshot means the bounded pre-update record of exact committed pre-schema integration-plan evidence.
- Add one versioned pre-update migration step that reads only a clean committed project baseline and records exact bounded plan, acceptance, contract, and validation identities outside project-owned plan history.
- Reject a missing, stale, symlinked, untracked, post-update, or newly synthesized provenance record.
- Keep the compatibility record migration-owned and preserve it across non-destructive updates without treating it as product acceptance evidence.
- Use bounded parent implementation and independent read-only review because this plan defines a validation migration boundary.

## Tasks

- [ ] Define the exact migration record schema, byte bounds, normalized paths, Git baseline, and single-use version boundary.
- [ ] Add the pre-update Copier migration and deterministic tests for genuine, missing, forged, stale, dirty, and replayed provenance.
- [ ] Align root and generated policy with the concrete compatibility evidence.
- [ ] Run focused validation, independent review, the authoritative Copier transition once, archive, and commit.

## Validation Notes

- Plan 130 final review proved that a replan contract created alongside a new plan cannot establish pre-schema provenance.
