# Reject command shadowing in sourced fixture libraries

status: backlog
primary_invariant: the focused checker reads every file the transition fixture sources and rejects a redefinition of an observed command or of the Copier wrapper wherever it is written, so no bound observation can be made vacuous from outside the fixture file
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
  - scripts/check-copier-template.py
  - tests/test-copier-fixture-validator.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
  - docs/plan/checked/2026/08/16-31/244-reject-fixture-command-redefinition.md
  - docs/plan/checked/2026/08/16-31/246-bind-pre-schema-fixture-contents.md
  - tests/copier-update.sh
  - tests/lib-copier.sh
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
  - docs/plan/checked/2026/08/16-31/244-reject-fixture-command-redefinition.md
integration_gates:
  - do not edit, stage, or commit tests/copier-update.sh or tests/lib-copier.sh in this plan; both are read-only subjects under test
  - keep the committed fixture and the committed library passing the checker unchanged
  - Plan 248 must be checked before this plan starts, so the validator carries one settled inventory rule
  - Plan 247 must not resume until this plan is checked
checked_summary_ja: fixtureがsourceするlibraryまで読み、observed commandとCopier wrapperの再定義をどこに書かれても拒否する。

## Decisions

- Read what the fixture executes, not only the file it is named after. `tests/copier-update.sh` sources `tests/lib-copier.sh` into the current shell before every bound observation, and the gate never reads that file, so a one-line declaration there rebinds a name for every observation while the gate stays green.
- Treat the Copier wrapper as an observed name. A no-op `run_copier` leaves every bound needle intact while no Copier run happens at all, which is the same defect class checked Plan 244 named.
- Bind the sourced set in the gate rather than by following arbitrary runtime paths, so the checker keeps its text-only boundary and its refusal stays decidable.
- Use bounded parent implementation because this is a validation-authority path and writable delegation is prohibited for it.

## Tasks

- [ ] Reproduce both admissions read-only: a `grep` declaration added to `tests/lib-copier.sh`, and a `run_copier() { return 0; }` declaration added to the fixture after the source line.
- [ ] Feed every file the fixture sources through the shadowing rule and reject a redefinition of the Copier wrapper, keeping the committed fixture and library accepted unchanged.
- [ ] Add mutation coverage for a shadowed observed command in the sourced library, for a shadowed Copier wrapper, and for an unbound sourced path.
- [ ] Complete one fresh independent read-only review and focused validation with zero unresolved High or Medium findings.
- [ ] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending. Both reproductions are recorded as High finding 2 of the Plan 247 independent review and were confirmed in the main session against the committed gate with `tests/copier-update.sh` left byte-identical.
