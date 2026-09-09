# Freeze the bounded Copier fixture validator

status: replanned
replan_reason_codes:
  - parent_remediation_budget_exhausted
  - multiple_independent_invariants
task_types:
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - scripts/project_workflow/copier_fixture.py
  - tests/test-copier-fixture.py
preservation_scope:
  - scripts/check-copier-template.py
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/190-migrate-live-plan-contracts.md
  - docs/plan/checked/2026/08/16-31/180-admit-live-validation-witness-guardian.md
  - docs/plan/checked/2026/08/16-31/182-admit-v145-copier-wiring.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-copier-fixture.py
  - git diff --check
validation:
  - python3 tests/test-copier-fixture.py
  - python3 -m py_compile scripts/project_workflow/copier_fixture.py tests/test-copier-fixture.py
  - git diff --check
acceptance:
  - Provide a separately accepted bounded Copier fixture parser and mutation suite that can validate the runtime without depending on unaccepted changes to scripts/check-copier-template.py or executing the complete Copier transition.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:97c3ea5b9905b9928471e61108bd1cb44c0e3ee87e766e42e5754531e5fb3c02","stage":"focused","witness":"python3 tests/test-copier-fixture.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/190-migrate-live-plan-contracts.md
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/191-freeze-bounded-copier-fixture-validator.md
replan_contract: docs/plan/replanned/contracts/191-freeze-bounded-copier-fixture-validator.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/197-freeze-bounded-shell-structure-parser.md
  - docs/plan/active/198-integrate-bounded-copier-fixture-validator.md
inherited_acceptance_digests:
  - sha256:97c3ea5b9905b9928471e61108bd1cb44c0e3ee87e766e42e5754531e5fb3c02
checked_summary_ja: bounded Copier fixtureをruntimeや全体checkerの未受理差分に依存せず検証できるparserとmutation testを確定する。

## Decisions

- bounded_copier_fixture_validator means the separately committed parser and mutation-test authority used to validate the bounded Copier fixture runtime before the broad template checker changes.
- Parse supplied fixture bytes rather than importing or executing tests/copier-update.sh.
- Cover unique version commits, inventory copy and staging, ready and release ordering, both bounded polls, three release paths, child termination and reap, PID clearing, pending and consumed order, positive guardian PID, and guardian cleanup.
- Include mutations for each required operation, helper uniqueness and body, reordering, direct snapshot invocation, and bypass through an alternate path.
- Keep the broad scripts/check-copier-template.py integration in Plan 186 and the next Plan 163-lineage complete transition in Plan 179; Plans 166 and 167 retain their later authoritative runs.
- Use bounded parent implementation and independent review because this parser becomes validation authority for Plan 185.

## Tasks

- [ ] Implement the bounded parser over supplied text and the exact `python3 scripts/project_workflow/copier_fixture.py --check tests/copier-update.sh` CLI contract.
- [ ] Add positive, removal, duplication, redefinition, reordering, and bypass mutation tests without reading the dirty runtime candidate as expected output.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 185 with the exact checked predecessor path.

## Validation Notes

- The dirty runtime and broad checker remain advisory input and cannot authorize this validator.
- The validator's synthetic positive case must be defined independently from the dirty runtime candidate.
- Parent-direct implementation produced an unaccepted parser and 13-case mutation suite in the declared two-file write scope.
- Focused validation passed `python3 tests/test-copier-fixture.py` with 13 tests and `git diff --check`.
- Independent review round 1 reported High 2 and Medium 2; parent remediation bound background process ownership, connected control-flow blocks, direct snapshot rejection, and inventory copy/staging.
- Independent review round 2 reported Medium 1; parent remediation fixed the inventory loop body and conditional bypass case.
- Independent review round 3 reported High 1 because an early top-level termination can still make the required fixture sequence unreachable.
- Two parent-direct remediation rounds still leave a High finding, so this execution is stopped and requires a reconstructed implementation and validation boundary before further edits, validation, archival, or commit.
