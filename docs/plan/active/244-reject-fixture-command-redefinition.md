# Reject fixture command redefinition

status: replan_required
replan_reason_codes:
  - parent_remediation_budget_exhausted
primary_invariant: the focused checker rejects a fixture that redefines or shadows any shell command a bound transition observation depends on, so no bound assertion can be made vacuous while its committed text survives
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
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
  - docs/plan/checked/2026/08/16-31/227-complete-bounded-copier-fixture-runtime.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - tests/copier-update.sh
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
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
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
  - do not edit, stage, or commit tests/copier-update.sh in this plan; the committed fixture is the read-only subject under test
  - do not edit scripts/check-copier-template.py in this plan; Plan 246 owns that file
  - keep the committed fixture passing --check and keep every existing rejection test passing
  - Plan 245 must start only after this plan is checked and its exact checked archive path replaces the active dependency
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
checked_summary_ja: bound観測が依存するcommandの再定義やshadowingをfocused checkerで拒否する。

## Decisions

- Reject the defect class, not one spelling. A fixture that defines grep, test, touch, sed, kill, wait, or fixture_git as a shell function keeps every bound operation's committed text while the observation it performs becomes vacuous, so the checker must reject the redefinition itself.
- Own the validator and its test together, because widening the prohibition is only acceptable with the mutation coverage that proves it holds.
- Use bounded parent implementation because this is a validation-authority path and writable delegation is prohibited for it.

## Tasks

- [x] Reproduce the admission by defining grep, test, and touch as no-op functions in a scratch copy of the committed fixture.
- [ ] Reject redefinition or shadowing of every command a bound transition observation depends on, and keep the committed fixture accepted unchanged.
- [ ] Add mutation coverage for a function definition, an alias, and a shadowing helper for each protected command.
- [ ] Complete fresh independent review and focused validation with zero unresolved High or Medium findings.
- [ ] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending. The reproduction is recorded in the Plan 187 replanned archive as High finding 1.
- Reproduced the admission: no-op `grep`, `test`, and `touch` declarations appended to a scratch copy of `tests/copier-update.sh` were accepted by the checker before this work.
- A `command_shadowing` rule was implemented in the working tree and passed every declared validation command: `python3 tests/test-copier-fixture-validator.py` (381 tests OK), `python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh`, `python3 scripts/check-copier-template.py`, and `git diff --check`.
- Three independent reviews were run against the working-tree diff. The first returned 2 High and 3 Medium findings, the second returned 4 High and 2 Medium findings after the first parent-direct remediation, and the third returned 2 High and 2 Medium findings after the second parent-direct remediation.
- The remaining findings are that a prefixed search path still reaches an observed command through an unlisted forwarder such as `nice`, that an option word the checker cannot read is dropped rather than reported, and that two search-path binding readings reject fixtures that only mention `PATH` as data.
- Two independently reviewed parent-direct remediation rounds therefore left High and Medium findings, which is the `parent_remediation_budget_exhausted` stop condition. Execution stopped before completion and archival, and no product change was committed.
- The working-tree changes to `scripts/project_workflow/copier_fixture_validator.py` and `tests/test-copier-fixture-validator.py` are preserved uncommitted for the restructuring transaction to record in successor `preservation_scope`.
