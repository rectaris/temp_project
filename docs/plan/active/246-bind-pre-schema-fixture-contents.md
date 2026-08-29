# Bind pre-schema fixture contents

status: deferred
completion_deferred_reason: Plan 245 must be checked and its exact checked archive path must replace the active predecessor before implementation
primary_invariant: the focused checker binds the constructed contents of the committed v1.4.4 pre-schema active plan, replanned source archive, and replan contract, so emptying or neutralizing them is rejected rather than admitted as an unchanged heredoc opening
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
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/182-admit-v145-copier-wiring.md
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
  - docs/plan/checked/2026/08/16-31/227-complete-bounded-copier-fixture-runtime.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - tests/copier-update.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 scripts/check-copier-template.py
  - python3 tests/test-copier-fixture-validator.py
  - sh -n tests/copier-update.sh
  - git diff --check
validation:
  - python3 scripts/check-copier-template.py
  - python3 tests/test-copier-fixture-validator.py
  - sh -n tests/copier-update.sh
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
predecessor_plans:
  - docs/plan/active/245-bind-fixture-inputs-to-one-inventory.md
successor_plans:
  - docs/plan/active/244-reject-fixture-command-redefinition.md
  - docs/plan/active/245-bind-fixture-inputs-to-one-inventory.md
  - docs/plan/active/246-bind-pre-schema-fixture-contents.md
  - docs/plan/active/247-verify-plan187-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
replan_sources:
  - docs/plan/active/187-verify-plan183-successor-acceptance.md
replan_contract: docs/plan/replanned/contracts/187-verify-plan183-successor-acceptance.json
integration_gates:
  - Plan 245 must be checked and its exact checked archive path must replace the active dependency before implementation
  - do not edit, stage, or commit tests/copier-update.sh in this plan; the committed fixture is the read-only subject under test
  - do not edit scripts/project_workflow/copier_fixture_validator.py in this plan; Plans 244 and 245 own that file
  - Plan 247 must start only after this plan is checked and its exact checked archive path replaces the active dependency
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
checked_summary_ja: v1.4.4 pre-schema plan、replanned archive、replan contractの生成内容をcheckerに束縛する。

## Decisions

- COPIER_FIXTURE_OPERATIONS binds only the heredoc opening lines, so an empty pre-schema plan or archive body keeps every bound operation and still passes. Bind the constructed contents so effective omission is rejected by the same focused witness.
- Keep the existing region, exactly-once, and ordering rules unchanged and add content binding on top of them, so no currently rejected mutation becomes admitted.
- Use bounded parent implementation because this is a validation-authority path.

## Tasks

- [ ] Reproduce the admission by emptying the pre-schema active plan body and the replanned source archive body in a scratch copy.
- [ ] Bind the constructed contents of the pre-schema active plan, replanned source archive, and replan contract writer, and keep the committed fixture accepted unchanged.
- [ ] Confirm the 45 previously bound operations still reject removal and duplication after the change.
- [ ] Complete fresh independent review and focused validation with zero unresolved High or Medium findings.
- [ ] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending. The reproduction is recorded in the Plan 187 replanned archive as High finding 3.
