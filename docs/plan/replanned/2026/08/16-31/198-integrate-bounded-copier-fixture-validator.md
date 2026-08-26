# Integrate the bounded Copier fixture validator

status: replanned
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
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/197-freeze-bounded-shell-structure-parser.md
  - docs/plan/checked/2026/08/16-31/190-migrate-live-plan-contracts.md
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
  - docs/plan/active/197-freeze-bounded-shell-structure-parser.md
primary_invariant: preserve the complete coupled source acceptance baseline
replan_sources:
  - docs/plan/active/197-freeze-bounded-shell-structure-parser.md
  - docs/plan/active/198-integrate-bounded-copier-fixture-validator.md
replan_contract: docs/plan/replanned/contracts/197-freeze-bounded-shell-structure-parser.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/205-integrate-bounded-copier-fixture-validator.md
inherited_acceptance_digests:
  - sha256:97c3ea5b9905b9928471e61108bd1cb44c0e3ee87e766e42e5754531e5fb3c02
checked_summary_ja: checked shell parserへCopier fixtureの全operationとmutation contractを接続する。

## Decisions

- bounded_copier_fixture_validator means the checked validator that applies the Copier fixture operation contract to supplied bytes using the accepted shell structure parser.
- Preserve the exact `python3 scripts/project_workflow/copier_fixture.py --check tests/copier-update.sh` CLI contract.
- Require unique version commits, one inventory copy and staging region, ready and release ordering, both bounded polls, three release paths, child termination and reap, PID clearing, pending and consumed order, positive guardian PID, and guardian cleanup.
- Reject removal, duplication, redefinition, reordering, direct snapshot invocation, early termination, conditional enclosure, and alternate update paths through independent mutations.
- Do not read the runtime candidate as expected output and do not execute tests/copier-update.sh.
- Use bounded parent implementation and independent review because the validator becomes the focused validation authority for Plan 185.

## Tasks

- [ ] Rebind the checked Plan 197 parser through its exact checked archive and retain its structural mutation cases unchanged.
- [ ] Add the complete Copier operation contract and exact check CLI over supplied bytes.
- [ ] Add positive, removal, duplication, redefinition, reordering, reachability, direct-invocation, and alternate-path mutation cases without reading the runtime candidate as expected output.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 185 with this plan's exact checked archive as predecessor and read-only validator context.

## Validation Notes

- Plan 197 owns generic shell structure and reachability; this plan may extend but must not replace that accepted behavior.
- The runtime and broad checker remain advisory inputs and cannot authorize this validator.
