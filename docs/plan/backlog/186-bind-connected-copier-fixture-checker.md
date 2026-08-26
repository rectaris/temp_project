# Bind the connected Copier fixture checker

status: backlog
primary_invariant: the focused checker rejects removal, duplication, redefinition, or bypass of every committed fixture operation needed to witness the unchanged Plan 183 acceptance
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - scripts/check-copier-template.py
preservation_scope:
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/185-complete-bounded-copier-fixture-runtime.md
  - docs/plan/active/205-integrate-bounded-copier-fixture-validator.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - docs/plan/checked/2026/08/16-31/182-admit-v145-copier-wiring.md
  - tests/test-copier-migration.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - sh -n tests/copier-update.sh
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - sh -n tests/copier-update.sh
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
predecessor_plans:
  - docs/plan/active/185-complete-bounded-copier-fixture-runtime.md
replan_source: docs/plan/active/183-build-bounded-copier-transition-fixture.md
replan_contract: docs/plan/replanned/contracts/183-build-bounded-copier-transition-fixture.json
integration_gates:
  - Plan 185 must be checked and its exact checked archive path must replace the active dependency before implementation
  - after Plan 185 is checked, remove tests/copier-update.sh from preservation_scope and add it as exact read-only context in the same parent-owned activation update
  - do not edit, stage, or recommit tests/copier-update.sh in this slice
  - Plan 187 must start only after this plan is checked and its exact checked archive path replaces the active dependency
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
successor_plans:
  - docs/plan/active/185-complete-bounded-copier-fixture-runtime.md
  - docs/plan/active/186-bind-connected-copier-fixture-checker.md
  - docs/plan/active/187-verify-plan183-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: committed fixtureの必須操作の欠落、重複、再定義、迂回をfocused checkerで拒否する。

## Decisions

- connected Copier fixture checker slice means the proposed successor that owns only scripts/check-copier-template.py, rejects missing or duplicate inventory and version operations, rejects direct snapshot-script invocation, binds the ready emission, both bounded polling loops, three release paths, update-process reap and PID clearing, ordered pending and consumed assertions, positive guardian PID validation, and guardian cleanup, and rejects missing, duplicate, or redefined waiter, guardian-stop, state-assertion, and guardian-PID-reader helpers.
- Validate the checker against the exact checked Plan 185 runtime bytes and retain Plan 182's parsed YAML and one-inventory checks.
- Import and invoke the checked bounded_copier_fixture_validator rather than maintaining a second disconnected copy of its structural rules.
- Require the checker to bind construction and commit of the v1.4.4 pre-schema active plan, replanned source archive, and replan contract, and to reject their omission or movement after the update begins.
- Use bounded parent implementation because the checker is a validation-authority path and writable delegation is prohibited.
- Treat the stopped Plan 183 reviews as advisory input; require a fresh ledger and independent review.

## Tasks

- [ ] Re-admit only checker behavior that remains valid against checked Plans 182, 185, and 191 without changing the committed fixture.
- [ ] Bind the ready emission, wrapper release polling loop, parent ready polling loop, and cleanup, ready-failure, and normal release blocks.
- [ ] Reject removal or bypass of the committed v1.4.4 pre-schema active plan, replanned source archive, replan contract, and consumed-record assertion for that active plan.
- [ ] Require exactly one bounded waiter, guardian-stop helper, state-assertion helper, and guardian-PID-reader helper, and inspect each helper's required behavior.
- [ ] Retain unique version ordering, one-inventory copy and staging, direct-script prohibition, update-process reap and PID clearing, pending then consumed ordering, positive guardian PID, and guardian cleanup checks.
- [ ] Complete fresh independent review and focused validation with zero unresolved High or Medium findings.
- [ ] Archive and commit only scripts/check-copier-template.py plus parent-owned lifecycle files.

## Validation Notes

- Mutation probes should cover removal of each ready, polling, release, helper, state, process ownership, and guardian edge.
- Do not execute tests/copier-update.sh in this slice.
