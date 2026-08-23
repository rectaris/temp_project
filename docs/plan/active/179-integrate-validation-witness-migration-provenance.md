# Integrate validation-witness migration provenance

status: in_progress
primary_invariant: the accepted guardian protocol, policy, source inventory, and genuine Copier transition jointly prove the Plan 163 migration boundary before downstream witness enforcement begins
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - CHANGELOG.md
  - tests/smoke.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/176-establish-live-validation-witness-provenance.md
  - docs/plan/active/177-align-validation-witness-provenance-policy.md
  - docs/plan/active/178-wire-validation-witness-copier-transition.md
  - docs/plan/replanned/2026/08/16-31/163-capture-validation-witness-migration-provenance.md
  - references/validation.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - pytest tests/test-copier-migration.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - pytest tests/test-copier-migration.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"authoritative","witness":"tests/copier-update.sh --require-copier","authoritative_only_reason":"the genuine pre-update boundary requires a complete versioned Copier transition from a clean committed downstream project"}
replan_source: docs/plan/active/163-capture-validation-witness-migration-provenance.md
replan_contract: docs/plan/replanned/contracts/163-capture-validation-witness-migration-provenance.json
integration_gates:
  - Plans 176 through 178 must be checked and their exact checked archive paths must replace active context paths before integration starts
  - validation-witness-migration-integration-gate requires all focused checks and independent review to report zero unresolved High or Medium findings
  - run the Plan 163 authoritative Copier transition exactly once and make its checked archive the only migration dependency consumed by Plan 164
successor_plans:
  - docs/plan/active/176-establish-live-validation-witness-provenance.md
  - docs/plan/active/177-align-validation-witness-provenance-policy.md
  - docs/plan/active/178-wire-validation-witness-copier-transition.md
  - docs/plan/active/179-integrate-validation-witness-migration-provenance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: guardian protocol、方針、inventory、実際のCopier更新を統合し、旧形式witness移行境界を確定する。

## Decisions

- validation-witness-migration-integration-gate means the condition that every migration slice and the real versioned transition pass without unresolved High or Medium review findings.
- Treat Plans 176 through 178 as the only implementation slices replacing Plan 163 and this plan as their combined acceptance boundary.
- Replace predecessor active paths with exact checked archive paths only after each predecessor is accepted.
- Keep the narrower focused checks executable before the sole authoritative v1.4.4-to-v1.4.5 Copier transition.
- Make this checked plan, rather than any individual implementation slice or the replanned Plan 163 archive, the dependency consumed by Plan 164 and the remaining Plan 130 chain.

## Tasks

- [ ] Confirm Plans 176 through 178 are checked and refresh their exact archive paths.
- [ ] Reconcile policy markers, template checks, smoke coverage, and the Unreleased change record.
- [ ] Complete focused validation and independent read-only review with zero unresolved High or Medium findings.
- [ ] Run the authoritative Copier transition exactly once, archive, commit, and refresh Plan 164 to this checked archive.

## Validation Notes

- This plan validates only the replacement for Plan 163. Plan 167 retains the unchanged complete Plan 130 authoritative suite.
