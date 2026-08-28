# Scope the fixture alternate-path rule to the sanctioned destination

status: deferred
completion_deferred_reason: Plan 230 must be checked so the fail-closed resolution model exists before the alternate-path rule consumes it
primary_invariant: the bounded fixture checker rejects a second Copier update path only when it can reach the same downstream destination as the sanctioned update child, and keeps every accepted legacy lane and every existing bypass rejection unchanged
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - scripts/project_workflow/copier_fixture_validator.py
  - tests/test-copier-fixture-validator.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - docs/plan/checked/2026/08/16-31/233-collect-fixture-aliases-from-a-modelled-grammar.md
  - tests/copier-update.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - git diff --check
validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
predecessor_plans:
  - docs/plan/active/233-collect-fixture-aliases-from-a-modelled-grammar.md
successor_plans:
  - docs/plan/active/230-resolve-fixture-destinations-fail-closed.md
  - docs/plan/active/231-scope-fixture-alternate-path-rule.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
replan_sources:
  - docs/plan/active/226-scope-fixture-alternate-path-rule.md
replan_contract: docs/plan/replanned/contracts/226-scope-fixture-alternate-path-rule.json
integration_source_ids:
  - 226
integration_gates:
  - do not edit tests/copier-update.sh in this plan; Plan 227 owns the fixture runtime
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
  - Plan 230 must be checked and its exact checked archive path must replace this active predecessor before implementation
  - prove parity against the blanket rule: no operation the current rule rejects may become accepted
  - Plan 227 must start only after this plan is checked and its exact checked archive path replaces the active dependency
checked_summary_ja: alternate_path規則を送り先単位へ限定し、既存のbypass拒否と正規laneを保つ。

## Decisions

- Reconstruct the validation method rather than the requirement. The rule's own docstring already describes a same-project prohibition, so making the implementation destination aware restores the intended boundary instead of weakening it.
- Consume the checked resolution model and add no new resolution here. A rejection this plan cannot prove separate is a Plan 230 gap, not a rule change.
- Prove parity explicitly. The rule it replaces rejects every reachable update dispatch, so acceptance requires that no operation the blanket rule rejects becomes accepted.
- Own the checker and its test together, because the rule change is only acceptable with the mutation coverage that proves the prohibition still holds.

## Tasks

- [ ] Reproduce the alternate_path findings by supplying the committed fixture plus an accepted transition sample to the checker.
- [ ] Make the alternate-path rule resolve each reachable update operation's destination through the checked resolution model and reject every operation whose destination is not provably separate from the sanctioned child's destination.
- [ ] Prove parity by checking every rejected sample of the blanket rule against the destination-aware rule, including a renamed helper, a local alias, a launched link, a moved link, and a differently written same-destination dispatch.
- [ ] Confirm the committed tests/copier-update.sh still passes --check without editing it, and record any residual fail-closed rejection for Plan 227.
- [ ] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Pending. The Plan 226 archive records the reproduction commands and the residual fixture rejection.
