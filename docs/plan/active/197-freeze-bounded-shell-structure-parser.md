# Freeze the bounded shell structure parser

status: in_progress
primary_invariant: supplied shell bytes expose one unique function table and one reachable top-level execution sequence before any Copier-specific operation rule is evaluated
replan_source: docs/plan/active/191-freeze-bounded-copier-fixture-validator.md
replan_contract: docs/plan/replanned/contracts/191-freeze-bounded-copier-fixture-validator.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/197-freeze-bounded-shell-structure-parser.md
  - docs/plan/active/198-integrate-bounded-copier-fixture-validator.md
inherited_acceptance_digests:
  - sha256:97c3ea5b9905b9928471e61108bd1cb44c0e3ee87e766e42e5754531e5fb3c02
task_types:
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
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
  - docs/plan/checked/2026/08/16-31/190-migrate-live-plan-contracts.md
checked_summary_ja: shell fixtureの関数定義とtop-level到達可能性をCopier固有規則から分離して確定する。

## Decisions

- bounded_shell_structure_parser means the checked parser behavior that extracts the permitted shell structure and rejects unreachable required regions before Copier-specific rules run.
- Parse supplied bytes without executing or importing tests/copier-update.sh.
- Limit the accepted shell subset to unique top-level function definitions plus one explicit top-level sequence; reject duplicate or nested definitions, unmatched blocks, early termination, and conditional or loop enclosure that can skip required regions.
- Keep Copier commit, inventory, synchronization, process, provenance, guardian, and CLI rules out of this slice; Plan 198 owns those rules over the checked structure parser.
- Use bounded parent implementation and independent review because this slice creates validation-authority code and tests.

## Tasks

- [ ] Implement bounded function and top-level region parsing over supplied text without shell execution.
- [ ] Add independent synthetic cases for duplicate definitions, unmatched blocks, early exit, alternate control transfer, conditional enclosure, loop enclosure, and disconnected branch bodies.
- [ ] Keep the parser API explicit so Plan 198 can add Copier operations without replacing structural parsing.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 198 with the exact checked predecessor path.

## Validation Notes

- The rejected Plan 191 candidate remains advisory evidence only and is not copied into this successor.
- This slice is intentionally insufficient to accept the source requirement without Plan 198.
