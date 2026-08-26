# Derive the bounded shell execution graph

status: deferred
completion_deferred_reason: Plan 203 must be checked and its exact checked archive path must replace the active predecessor before implementation.
implementation_tier: 2
primary_invariant: the checked lexical and function records yield one explicit reachable command graph in which every control transfer, terminal effect, and permitted success path is modelled rather than assumed
reserved_by: 223
task_types:
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - scripts/project_workflow/shell_execution.py
  - tests/test-shell-execution.py
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
  - docs/plan/replanned/2026/08/16-31/197-freeze-bounded-shell-structure-parser.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-shell-execution.py
  - python3 -m py_compile scripts/project_workflow/shell_execution.py tests/test-shell-execution.py
  - git diff --check
validation:
  - python3 tests/test-shell-execution.py
  - python3 -m py_compile scripts/project_workflow/shell_execution.py tests/test-shell-execution.py
  - git diff --check
acceptance:
  - Derive one explicit reachable command graph from checked lexical and function records and reject every hidden or terminal bypass.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b4eacba1c2f2efe8189ac9666ec287f6e5ecbe286d54dcbee6b94f95cf9eedf4","stage":"focused","witness":"python3 tests/test-shell-execution.py"}
predecessor_plans:
  - docs/plan/active/203-derive-bounded-shell-function-table.md
checked_summary_ja: checked字句recordと関数表から到達可能なcommand graphを構成し、隠れた分岐と早期終了を拒否する。

## Decisions

- bounded_shell_execution_graph means the checked command and control-transfer graph used to determine permitted reachable fixture regions.
- Consume only the checked lexical records from Plan 202 and the checked function table from Plan 203.
- Model lists, pipelines, AND/OR operands, conditions with multiple commands, loops, asynchronous commands, function calls, terminal effects, and one explicit permitted success path.
- Reject unreachable required regions, early termination, alternate control transfer, conditional enclosure, loop enclosure, and disconnected branch bodies.
- Keep Copier-specific operation rules out of this slice; Plan 205 owns them.
- Use bounded parent implementation and independent review because this slice creates validation-authority code and tests.

## Tasks

- [ ] Implement the reachable command and control-transfer graph over checked lexical and function records.
- [ ] Add independent synthetic cases for early exit, alternate transfer, multi-command conditions, asynchronous lists, terminal function calls, and disconnected branch bodies.
- [ ] Keep the graph API explicit so Plan 205 adds Copier operations without replacing execution modelling.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 205 with this plan's exact checked archive path.

## Validation Notes

- The rejected `scripts/project_workflow/copier_fixture.py` and `tests/test-copier-fixture.py` candidates are advisory evidence only and must not be written, imported, executed, or used as expected output.
- This slice is intentionally insufficient to accept the Plan 197 and Plan 198 source requirement; Plan 205 retains that acceptance.
