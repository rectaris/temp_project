# Integrate the bounded Copier fixture validator

status: in_progress
implementation_tier: 2
primary_invariant: the checked lexical, function, and execution projections plus Copier operation rules reject every missing, reordered, duplicated, unreachable, or alternate-path bounded fixture operation through the exact check CLI
replan_sources:
  - docs/plan/active/197-freeze-bounded-shell-structure-parser.md
  - docs/plan/active/198-integrate-bounded-copier-fixture-validator.md
replan_contract: docs/plan/replanned/contracts/197-freeze-bounded-shell-structure-parser.json
integration_gates:
  - combined successors must satisfy every source acceptance item
  - consume the checked Plan 202, 203, and 204 projections through their exact checked archive paths and do not restate their structural rules
  - preserve the exact --check tests/copier-update.sh contract under the newly admitted CLI path
  - do not write, import, execute, or read scripts/project_workflow/copier_fixture.py or tests/test-copier-fixture.py as expected output
successor_plans:
  - docs/plan/active/205-integrate-bounded-copier-fixture-validator.md
inherited_acceptance_digests:
  - sha256:97c3ea5b9905b9928471e61108bd1cb44c0e3ee87e766e42e5754531e5fb3c02
integration_source_ids:
  - 197
  - 198
reserved_by: 223
task_types:
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
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
  - docs/plan/checked/2026/08/16-31/199-admit-decomposed-shell-validation.md
  - docs/plan/checked/2026/08/16-31/202-freeze-bounded-shell-lexical-projection.md
  - docs/plan/checked/2026/08/16-31/203-derive-bounded-shell-function-table.md
  - docs/plan/checked/2026/08/16-31/204-derive-bounded-shell-execution-graph.md
  - docs/plan/replanned/2026/08/16-31/197-freeze-bounded-shell-structure-parser.md
  - docs/plan/replanned/2026/08/16-31/198-integrate-bounded-copier-fixture-validator.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 -m py_compile scripts/project_workflow/copier_fixture_validator.py tests/test-copier-fixture-validator.py
  - git diff --check
validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 -m py_compile scripts/project_workflow/shell_lexical.py tests/test-shell-lexical.py scripts/project_workflow/shell_functions.py tests/test-shell-functions.py scripts/project_workflow/shell_execution.py tests/test-shell-execution.py scripts/project_workflow/copier_fixture_validator.py tests/test-copier-fixture-validator.py
  - git diff --check
acceptance:
  - Provide a separately accepted bounded Copier fixture parser and mutation suite that can validate the runtime without depending on unaccepted changes to scripts/check-copier-template.py or executing the complete Copier transition.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:97c3ea5b9905b9928471e61108bd1cb44c0e3ee87e766e42e5754531e5fb3c02","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/204-derive-bounded-shell-execution-graph.md
checked_summary_ja: checked字句、関数表、実行graphの上にCopier固有のoperation規則とmutation contractを接続する。

## Decisions

- bounded_copier_fixture_validator means the Copier-specific predicates evaluated over the three checked shell projections through the exact fixture check CLI.
- Preserve the exact `python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh` CLI contract.
- Import the checked Plan 202, 203, and 204 modules rather than restating their structural rules.
- Require unique version commits, one inventory copy and staging region, ready and release ordering, both bounded polls, three release paths, child termination and reap, PID clearing, pending and consumed order, positive guardian PID, and guardian cleanup.
- Reject removal, duplication, redefinition, reordering, direct snapshot invocation, early termination, conditional enclosure, and alternate update paths through independent mutations.
- Do not read the runtime candidate as expected output and do not execute `tests/copier-update.sh`.
- Use bounded parent implementation and independent review because this validator becomes the focused validation authority for Plans 185 and 186.

## Tasks

- [ ] Bind the checked Plan 202, 203, and 204 modules through their exact checked archive paths.
- [ ] Add the complete Copier operation contract and exact check CLI over supplied bytes.
- [ ] Add positive, removal, duplication, redefinition, reordering, reachability, direct-invocation, and alternate-path mutation cases without reading the runtime candidate as expected output.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 185 with this plan's exact checked archive as predecessor and read-only validator context.

## Validation Notes

- This plan owns final acceptance of the Plan 197 and Plan 198 source requirement; Plans 202 through 204 do not.
- Plans 202, 203, and 204 own generic shell projection; this plan may extend but must not replace that accepted behavior.
- The rejected `scripts/project_workflow/copier_fixture.py` and `tests/test-copier-fixture.py` candidates stay committed as non-authoritative evidence and cannot authorize this validator.
