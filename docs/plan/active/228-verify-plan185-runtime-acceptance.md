# Verify Plan 185 runtime acceptance

status: deferred
completion_deferred_reason: Plans 226 and 227 must be checked before their combined result can be verified against the unchanged Plan 185 acceptance
primary_invariant: the checked destination-aware checker and the checked fixture runtime jointly satisfy the unchanged Plan 185 acceptance, and every downstream plan that referenced Plan 185 resolves to this lineage
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - docs/plan/backlog/186-bind-connected-copier-fixture-checker.md
  - docs/plan/backlog/187-verify-plan183-successor-acceptance.md
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/182-admit-v145-copier-wiring.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - docs/plan/checked/2026/08/16-31/231-scope-fixture-alternate-path-rule.md
  - docs/plan/checked/2026/08/16-31/227-complete-bounded-copier-fixture-runtime.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 scripts/restructure-plan.py --verify
  - scripts/lint-project-workflow.sh
  - git diff --check
validation:
  - python3 scripts/restructure-plan.py --verify
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"scripts/lint-project-workflow.sh"}
predecessor_plans:
  - docs/plan/active/231-scope-fixture-alternate-path-rule.md
  - docs/plan/active/227-complete-bounded-copier-fixture-runtime.md
successor_plans:
  - docs/plan/active/226-scope-fixture-alternate-path-rule.md
  - docs/plan/active/227-complete-bounded-copier-fixture-runtime.md
  - docs/plan/active/228-verify-plan185-runtime-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
replan_sources:
  - docs/plan/active/185-complete-bounded-copier-fixture-runtime.md
replan_contract: docs/plan/replanned/contracts/185-complete-bounded-copier-fixture-runtime.json
integration_source_ids:
  - 185
integration_gates:
  - Plans 226 and 227 must be checked and their exact checked archive paths must replace these active context paths before focused validation
  - do not edit scripts/project_workflow/copier_fixture_validator.py or tests/copier-update.sh in this plan
  - rebind Plan 186 and Plan 187 lineage references from the archived Plan 185 to the checked Plan 227 archive
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
checked_summary_ja: Plan 226と227の結果が変更のないPlan 185 acceptanceを満たすことと、下流planの参照解決を確認する。

## Decisions

- Retain the complete Plan 185 acceptance here so no requirement is lost by the split.
- Own only the downstream backlog plans that still name the archived Plan 185, because their lineage references are what the split invalidates.
- Verify rather than reimplement. Neither the checker nor the fixture runtime may be edited here.

## Tasks

- [ ] Confirm checked Plans 226 and 227 jointly satisfy the unchanged Plan 185 acceptance item.
- [ ] Rebind Plan 186 and Plan 187 predecessor and lineage references from the archived Plan 185 to the checked Plan 227 archive.
- [ ] Confirm repository lineage verification and the workflow lint still pass after the rebinding.

## Validation Notes

- Pending. This plan starts only after Plans 226 and 227 are checked.
