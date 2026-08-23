# Capture pre-schema validation witness provenance

status: replanned
replan_reason_codes:
  - parent_remediation_budget_exhausted
  - scope_drift
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
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/163-capture-validation-witness-migration-provenance.md
replan_contract: docs/plan/replanned/contracts/163-capture-validation-witness-migration-provenance.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/176-establish-live-validation-witness-provenance.md
  - docs/plan/active/177-align-validation-witness-provenance-policy.md
  - docs/plan/active/178-wire-validation-witness-copier-transition.md
  - docs/plan/active/179-integrate-validation-witness-migration-provenance.md
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
- Focused checks passed 17 Copier migration tests, the Copier template static check, and `git diff --check`; the authoritative Copier transition was not run.
- Two parent-direct review rounds still found High and Medium defects in cross-clone replay prevention and recoverable receipt transitions.
- The authoritative v1.4.5 transition also requires `tests/copier-update.sh` and `tests/fixtures/orchestration/copier-update-source-inventory.txt`, which are outside this plan's write scope and assigned to Plan 166.
- Execution ledger `/tmp/plan163-execution-state.json` entered `replan_required` with `parent_remediation_budget_exhausted`; stop implementation, validation, completion, archival, and commit until the scope and ordering are restructured.
