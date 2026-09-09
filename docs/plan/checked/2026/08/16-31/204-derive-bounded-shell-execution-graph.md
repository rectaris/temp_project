# Derive the bounded shell execution graph

status: checked
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
  - docs/plan/checked/2026/08/16-31/203-derive-bounded-shell-function-table.md
checked_summary_ja: checked字句recordと関数表から到達可能なcommand graphを構成し、隠れた分岐と早期終了を拒否する。

## Decisions

- bounded_shell_execution_graph means the checked command and control-transfer graph used to determine permitted reachable fixture regions.
- Consume only the checked lexical records from Plan 202 and the checked function table from Plan 203.
- Model lists, pipelines, AND/OR operands, conditions with multiple commands, loops, asynchronous commands, function calls, terminal effects, and one explicit permitted success path.
- Reject unreachable required regions, early termination, alternate control transfer, conditional enclosure, loop enclosure, and disconnected branch bodies.
- Keep Copier-specific operation rules out of this slice; Plan 205 owns them.
- Use bounded parent implementation and independent review because this slice creates validation-authority code and tests.

## Tasks

- [x] Implement the reachable command and control-transfer graph over checked lexical and function records.
- [x] Add independent synthetic cases for early exit, alternate transfer, multi-command conditions, asynchronous lists, terminal function calls, and disconnected branch bodies.
- [x] Keep the graph API explicit so Plan 205 adds Copier operations without replacing execution modelling.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, archive, commit, and activate Plan 205 with this plan's exact checked archive path.

## Validation Notes

- The rejected `scripts/project_workflow/copier_fixture.py` and `tests/test-copier-fixture.py` candidates are advisory evidence only and must not be written, imported, executed, or used as expected output.
- This slice is intentionally insufficient to accept the Plan 197 and Plan 198 source requirement; Plan 205 retains that acceptance.

### Implementation

`scripts/project_workflow/shell_execution.py` derives the graph in two bounded
passes over the checked records. It never re-tokenizes, executes, sources, or
imports the supplied script.

- `derive(records: LexicalProjection, table: FunctionTable) -> ExecutionGraph`
  first parses the checked lexical records into a command tree with `_Parser`,
  then walks that tree with `_Builder` to emit nodes and explicitly labelled
  edges. Both passes are bounded by `MAX_DEPTH`, `MAX_CALL_DEPTH`, and
  `MAX_NODES`, and `_require_matching_table` rejects a table derived from
  different records.
- Every graph starts with the fixed `entry`, `end`, and `abort` nodes, so
  successful and failing termination are separate reachable states rather than
  one exit. `ExecutionGraph.success_path` is the dominator chain of `end`: the
  commands the shell reaches on every execution that terminates successfully.
- Control transfer is carried only by labelled edges: `sequential`, `pipeline`,
  `on_success`, `on_failure`, `condition_true`, `condition_false`,
  `loop_enter`, `loop_repeat`, `loop_exit`, `case_match`, `case_skip`, `call`,
  `returned`, `async`, `substitution`, `expansion_skip`, `redirection_skip`,
  `process_abort`, `terminate`, `break`, and `continue`. No transfer is
  implied by node order.
- A declared function is inlined per call site under a `call_path`, against the
  declaration that closes at or before the call site's activation offset, so a
  call that runs before its declaration executes is not resolved against it.
  Recursion is rejected.
- `ExecutionGraph` exposes `commands`, `success_path`, `reachable`,
  `unreachable`, `terminal_nodes`, `transfer_nodes`, `asynchronous_nodes`,
  `calls`, `dynamic_commands`, `included_sources`, `shell_options`,
  `trap_registrations`, `is_fully_resolved`, `incoming`, `outgoing`, `find`,
  `find_reachable`, `find_guaranteed`, `dominates`, `postdominates`, and
  `precedes`, so Plan 205 adds Copier operation rules without replacing
  execution modelling.

### Rejected and reported paths

Rejected with an exact position: recursion, a transfer with no enclosing loop
in the current shell or function, a non-bounded transfer level, a construct the
bounded parser does not accept, a graph past `MAX_NODES`, nesting past
`MAX_DEPTH` or `MAX_CALL_DEPTH`, a table that does not match the records,
`alias`, `unalias`, an `unset` that can remove a declaration, and any operand
of `time`.

Reported instead of rejected, by clearing `is_fully_resolved`: a command word
that is not an exact literal, `.`/`source`, `trap`, and an undeclared
`builtin`. Six of this repository's own tracked scripts rely on these, so
rejecting them would reject real input.

### Validation

Focused validation passed: `python3 tests/test-shell-execution.py`
(118 tests), `python3 -m py_compile
scripts/project_workflow/shell_execution.py tests/test-shell-execution.py`,
and `git diff --check`.

Derivation was also run over all 30 tracked `*.sh` files. Twenty-nine derive a
graph. The sole rejection is `tests/copier-update.sh`, which the Plan 203
function table already rejects for its nested declaration; no file is rejected
by this slice.

### Independent review

Two bounded read-only reviewers ran with no write scope over five rounds; every
acceptance decision was made in the main session.

- Round 1: nine findings. A conditional parameter expansion, a case-arm pattern
  substitution, and an empty `for` word list were dropped; a transparent prefix
  invented a function call; a function was callable before its declaration ran.
- Round 2: eight findings. `alias`/`unalias`/`unset -f` could silently rewrite
  the resolved table; early failure inside a child process, redirection failure
  around a compound command, and per-prefix option grammar were unmodelled;
  `exit 256` was misclassified.
- Round 3: two High and two Medium. Here-document expansion was ordered before
  an earlier redirection could fail; `builtin` was assumed transparent; `unset
  -v` over-rejected a variable sharing a function name.
- Round 4: one High and three Medium. A `break` or `continue` in a loop
  condition resolved to the *enclosing* loop and marked live commands
  unreachable; `time` silently picked one reference shell's reading and hid a
  declared body; an unbounded or non-ASCII numeric literal escaped as a raw
  `ValueError`; an `elif` condition was not reported as conditional.
- Round 5: one High and two Medium. A `break` in a called body escaped into a
  caller loop; a zero-padded numeric literal still reached an unbounded
  conversion; the disputed-operand set for `time` was incomplete.
- Round 6: no High or Medium findings from either reviewer. The enumerated
  disputed-operand set was replaced by rejecting every `time` operand, and one
  remaining Low finding was fixed: the assignment prefix of a simple command
  was expanded before its command words, which reversed the order every
  reference shell uses.

Each round's fix is pinned by regression tests, and the reviewers' test-suite
findings (one tautological assertion and four weak cases) were also fixed.

### Known limitations

- The graph over-approximates in one direction only: it can withhold a
  guarantee the shell would keep, never grant one the shell can skip. A child
  process is modelled as able to end early at every command, a redirection is
  modelled as able to fail before the words after it, and a loop condition that
  can never fail still reports a reachable exit. A consumer must therefore
  prove a required region with `guaranteed`, not with `reachable`.
- The reference shells disagree about redirection target expansion and about
  `time`. The graph keeps the reading both allow, and rejects `time` with an
  operand rather than choosing a side.
- A transfer that no loop in the current function encloses is rejected although
  both reference shells ignore it. No tracked script uses the form.
- `is_fully_resolved` answers only whether the graph describes the whole
  script. It is not a general trust signal.
- The bounded-subset rejections of the checked lexical projection and the
  checked function table still apply.
