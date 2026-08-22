# Integrate validation witness enforcement

status: in_progress
primary_invariant: the combined successor state proves every Plan 130 acceptance clause through its earliest parent-owned witness while preserving the complete authoritative suite
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
  - docs/plan/active/131-require-confirmed-failure-diagnosis.md
  - docs/plan/active/132-checkpoint-plan-session-resources.md
  - docs/plan/active/133-evaluate-resource-bounded-orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - tests/smoke.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/163-capture-validation-witness-migration-provenance.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - docs/plan/active/165-enforce-validation-witness-maps.md
  - docs/plan/active/166-unify-copier-update-source-inventory.md
  - docs/plan/replanned/2026/08/16-31/130-map-acceptance-validation-witnesses.md
  - references/validation.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
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
  - Plans 163 through 166 must be checked and their exact checked archive paths must replace active context paths before integration starts
  - dependent Plans 131 through 133 must pass plan checks with exact accepted witness and dependency mappings
  - run the source authoritative suite exactly once only after focused validation and independent review report zero unresolved High or Medium findings
successor_plans:
  - docs/plan/active/163-capture-validation-witness-migration-provenance.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - docs/plan/active/165-enforce-validation-witness-maps.md
  - docs/plan/active/166-unify-copier-update-source-inventory.md
  - docs/plan/active/167-integrate-validation-witness-enforcement.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: 旧形式移行、再計画契約、witness検証、Copier inventoryを統合して最終検証する。

## Decisions

- validation-witness-integration means the final combined acceptance and authoritative-validation boundary for all Plan 130 successors.
- Treat Plans 163 through 166 as the only implementation slices and this plan as the combined acceptance boundary.
- Refresh active dependency paths only after each predecessor is checked and do not alter accepted requirements.
- Reconcile root and generated policy checks, retain the original authoritative command order, and require independent read-only review before the one authoritative run.
- Use bounded parent implementation because integration checks and active-plan witness mappings are validation authority.

## Tasks

- [ ] Confirm Plans 163 through 166 are checked and refresh their exact archive paths.
- [ ] Reconcile dependent active plans, policy markers, smoke coverage, and the Unreleased record.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the unchanged Plan 130 authoritative suite exactly once, archive, commit, and refresh Plan 133 to this checked archive.

## Validation Notes

- The source authoritative suite was never run under Plan 130 and remains available for this final integration plan.
