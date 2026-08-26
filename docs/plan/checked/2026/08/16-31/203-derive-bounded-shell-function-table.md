# Derive the bounded shell function table

status: checked
implementation_tier: 2
primary_invariant: the checked lexical records yield exactly one unique top-level function declaration table and every alternate, hidden, or dynamic definition path is rejected
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
  - scripts/project_workflow/shell_functions.py
  - tests/test-shell-functions.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/199-admit-decomposed-shell-validation.md
  - docs/plan/checked/2026/08/16-31/202-freeze-bounded-shell-lexical-projection.md
  - docs/plan/replanned/2026/08/16-31/197-freeze-bounded-shell-structure-parser.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-shell-functions.py
  - python3 -m py_compile scripts/project_workflow/shell_functions.py tests/test-shell-functions.py
  - git diff --check
validation:
  - python3 tests/test-shell-functions.py
  - python3 -m py_compile scripts/project_workflow/shell_functions.py tests/test-shell-functions.py
  - git diff --check
acceptance:
  - Derive one unique top-level function table from checked lexical records and reject every alternate definition path.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:c4fce8b4e2eed5938124658fa1e59f9147abc9dcc6150ad571df1abf5efd780a","stage":"focused","witness":"python3 tests/test-shell-functions.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/202-freeze-bounded-shell-lexical-projection.md
checked_summary_ja: checked字句recordから一意なtop-level関数表を導出し、代替定義経路を拒否する。

## Decisions

- bounded_shell_function_table means the checked unique top-level function declaration table derived from the accepted lexical projection.
- Consume only the checked lexical records emitted by Plan 202; do not re-tokenize supplied bytes.
- Reject duplicate, nested, split, piped, dynamically evaluated, conditionally defined, and otherwise non-top-level function declarations.
- Reject `eval`-style function-table replacement so the table cannot be rewritten after derivation.
- Keep execution ordering and reachability out of this slice; Plan 204 owns them.
- Use bounded parent implementation and independent review because this slice creates validation-authority code and tests.

## Tasks

- [x] Implement the unique top-level function table over checked lexical records.
- [x] Add independent synthetic cases for duplicate, nested, split, piped, conditional, and dynamically evaluated declarations.
- [x] Keep the table API explicit so Plan 204 consumes it without replacing derivation.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, archive, commit, and activate Plan 204 with this plan's exact checked archive path.

## Validation Notes

- The rejected `scripts/project_workflow/copier_fixture.py` and `tests/test-copier-fixture.py` candidates are advisory evidence only and must not be written, imported, executed, or used as expected output.
- This slice is intentionally insufficient to accept the Plan 197 and Plan 198 source requirement; Plan 205 retains that acceptance.

### Implementation

`scripts/project_workflow/shell_functions.py` derives the table with one
single-pass `_Walker` over the checked lexical records. It never re-tokenizes,
executes, sources, or imports the supplied script.

- `derive(records: LexicalProjection) -> FunctionTable` walks the top-level
  record sequence, then walks every nested command-substitution region with
  `top_level=False`. Nested regions are enumerated recursively through segment
  trees, so a declaration or `eval` hidden inside `${...}`, `$((...))`, double
  quotes, a here-document body, or a nested substitution is still reached.
- `FunctionTable` exposes `declarations`, `names`, `top_level`,
  `dynamic_commands`, `is_fully_resolved`, `get`, `__contains__`,
  `__getitem__`, `__iter__`, and `__len__`. `FunctionDeclaration` records the
  exact `name_token`, `open_brace`, `close_brace`, and `body` span so Plan 204
  consumes the table without replacing derivation.
- `ShellFunctionError` carries the exact `Position` of the rejected construct.

### Rejected declaration paths

Duplicate, nested, split (`a(` newline `)`), non-brace-body, non-literal-name,
reserved-name, piped (`x | f() { :; }` and `f() { :; } | cat`), asynchronous
(`f() { :; } &` and `f() { :; } && ls &`), conditional (inside `if`, `while`,
`for`, `case`, `{ }`, `( )`), command-substitution-local, `function`-keyword,
and `eval`-reachable declarations are all rejected. `eval` is also rejected
behind the transparent command prefixes `command`, `builtin`, `time`, `exec`,
`env`, and `nohup`, chained and with option or assignment arguments.

### Validation

Focused validation passed: `python3 tests/test-shell-functions.py` (42 tests),
`python3 -m py_compile scripts/project_workflow/shell_functions.py
tests/test-shell-functions.py`, and `git diff --check`.

The authoritative suite ran once and passed: the three focused commands,
`python3 scripts/restructure-plan.py --verify`,
`python3 scripts/check-root-agent-policy.py`,
`python3 scripts/check-copier-template.py`,
`scripts/lint-project-workflow.sh`, and `tests/smoke.sh`.

Derivation was also run over all 30 tracked `*.sh` files. Twenty-nine derive a
unique table. The sole rejection is `tests/copier-update.sh:729`, which
genuinely declares `assert_managed_orchestration_reports` inside
`validate_common_lane`; rejecting it is the decided behavior of this slice.
Plan 205 must therefore either restructure that fixture or record the nested
declaration as an accepted input before it can validate the fixture.

### Independent review

Four bounded read-only review rounds ran with no write scope; every acceptance
decision was made in the main session.

- Round 1: three High findings. `command`/`builtin` prefixes hid `eval` and so
  allowed a silent table rewrite; a declaration used as a pipeline component or
  terminated by `&` was reported although a real shell defines nothing; the
  nested-region recursion and the body close-brace guard were untested.
- Round 2: two further High findings. A newline after `|`, `&&`, or `||`
  reset the declaration guard and reopened the pipeline hole in the most common
  line-wrapping style; `time` was missing from the transparent prefix set. One
  Medium regression: a function named after a transparent prefix
  (`env() { ... }`) was rejected with a misattributed error. One Medium test
  gap on nested `dynamic_commands`.
- Round 3: one High finding. An and-or list terminated by `&` one operator
  further out (`f() { :; } && ls &`) still reported a declaration the shell
  never installs.
- Round 4: no High or Medium findings. Confirmed by differential fuzzing
  against bash and dash (three grammars, 38,000 generated scripts, 7,274
  accepted-and-compared, zero divergences), a 200,000-script instrumented leak
  hunt over the pending-declaration state, and 20 of 20 mutations killed.

Each round's fix is pinned by regression tests; 12 module mutations covering
every load-bearing guard are caught by the suite.

### Known limitations

- A command word that is not an exact literal name cannot be resolved without
  executing the script. Such words occur 22 times in this repository's own
  tracked scripts, so they are recorded in `FunctionTable.dynamic_commands`
  rather than rejected. `FunctionTable.is_fully_resolved` is the property a
  consumer must assert when it needs the table to describe the whole script.
  This answers only the dispatch-resolution question and is not a general
  trust signal for the table.
- A compound-command closer directly followed by another closer with no
  separator (`if x; then { y; } fi`) is valid POSIX but is rejected as an
  unterminated block. This is over-rejection, no tracked script uses the form,
  and adding a separator accepts it.
- `case x in esac) y;; esac`, a literal `esac` pattern, is rejected.
- The bounded-subset rejections of the checked lexical projection still apply.
