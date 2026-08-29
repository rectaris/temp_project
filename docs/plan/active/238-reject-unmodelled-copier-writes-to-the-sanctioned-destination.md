# Reject unmodelled Copier writes to the sanctioned destination

status: in_progress
primary_invariant: no fixture operation writes the sanctioned destination through a Copier command other than the modelled update without the checker rejecting it
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: high
implementation_tier: 2
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
  - docs/plan/checked/2026/08/16-31/237-restore-the-resolution-model-as-the-single-update-authority.md
  - docs/plan/checked/2026/08/16-31/231-scope-fixture-alternate-path-rule.md
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
  - docs/plan/checked/2026/08/16-31/237-restore-the-resolution-model-as-the-single-update-authority.md
successor_plans:
  - none
integration_gates:
  - do not edit tests/copier-update.sh; Plan 227 owns the fixture runtime
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
  - do not reject a Copier copy whose destination does not settle; the lane copy in the committed fixture writes an unsettleable path and must stay accepted

## Decisions

- Keep this invariant separate from the update authority. Plan 237 fixed which operations run a Copier update. A Copier copy or recopy is not an update, so covering it is a second independently validatable invariant and was ruled out of Plan 237 by independent review.
- Read a destination only when it settles. A copy whose destination carries an unsettled expansion must stay accepted, because the committed fixture copies into a lane path that can never be proven separate from the sanctioned destination. Rejecting an unsettled copy destination would block the fixture runtime work.
- Reject only a proven reach. The rule fires when a settled Copier write destination is proven not lexically separate from the sanctioned destination, which is the narrowest reading that closes the disclosed hole.
- Treat the existing acceptance as accidental, not as an invariant. The previous validator rejected this shape only when the surrounding text happened to contain the update word, so no checked behaviour is being weakened here.

## Tasks

- [ ] Read the Copier subcommand of a modelled operation and collect the settled write destination of a copy or recopy in the same way the update reading collects an update destination.
- [ ] Reject a reachable operation whose settled Copier write destination is not lexically separate from the sanctioned destination, and accept one whose destination does not settle.
- [ ] Add regression tests covering a copy and a recopy into the sanctioned destination through a helper the fixture does not define, a copy into a separate project, and a copy whose destination carries an unsettled expansion.
- [ ] Confirm the committed tests/copier-update.sh still passes --check without editing it, including the lane copy that writes an unsettleable path.
- [ ] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Pending. The Plan 237 record holds the disclosed residual, the independent review ruling that it belongs in a separate bounded plan, and the evidence that the previous validator also accepted this shape.
