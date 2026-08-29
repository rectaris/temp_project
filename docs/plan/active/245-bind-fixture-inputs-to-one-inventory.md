# Bind fixture inputs to one inventory

status: deferred
completion_deferred_reason: Plan 244 must be checked and its exact checked archive path must replace the active predecessor before implementation
primary_invariant: the focused checker rejects any copy into or Git staging against the fixture update source that the single Copier update inventory loop does not perform, so the fixture cannot take an undeclared source input
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
  - docs/plan/checked/2026/08/16-31/182-admit-v145-copier-wiring.md
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
predecessor_plans:
  - docs/plan/active/244-reject-fixture-command-redefinition.md
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
  - Plan 244 must be checked and its exact checked archive path must replace the active dependency before implementation
  - do not edit, stage, or commit tests/copier-update.sh in this plan; the committed fixture is the read-only subject under test
  - do not edit scripts/check-copier-template.py in this plan; Plan 246 owns that file
  - do not change tests/fixtures/orchestration/copier-update-source-inventory.txt in this plan
  - Plan 246 must start only after this plan is checked and its exact checked archive path replaces the active dependency
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
checked_summary_ja: 単一inventory以外からのcopyとGit stagingをfocused checkerで拒否する。

## Decisions

- The existing rule only rejects an outside operation that references the loop variable, so a hard-coded destination path escapes it. Bind the prohibition to the update source destination instead of to the variable spelling.
- Keep the inventory file itself unchanged. This plan constrains how the fixture may consume the inventory, not what the inventory declares.
- Use bounded parent implementation because this is a validation-authority path.

## Tasks

- [ ] Reproduce the admission by adding a hard-coded copy into the update source and a matching staging call after the inventory loop in a scratch copy.
- [ ] Reject every copy into and staging against the update source that the unique inventory loop does not perform, regardless of how the destination is written.
- [ ] Add mutation coverage for a hard-coded path, an indirect variable, and a staged path that no inventory line declares.
- [ ] Complete fresh independent review and focused validation with zero unresolved High or Medium findings.
- [ ] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending. The reproduction is recorded in the Plan 187 replanned archive as High finding 2.
