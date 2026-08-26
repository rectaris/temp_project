# Freeze the bounded shell lexical projection

status: checked
implementation_tier: 2
primary_invariant: supplied shell bytes project into deterministic lexical records that expose every executable region and reject every ambiguous or unsupported construct before any function-table or execution rule runs
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
  - scripts/project_workflow/shell_lexical.py
  - tests/test-shell-lexical.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/199-admit-decomposed-shell-validation.md
  - docs/plan/replanned/2026/08/16-31/197-freeze-bounded-shell-structure-parser.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-shell-lexical.py
  - python3 -m py_compile scripts/project_workflow/shell_lexical.py tests/test-shell-lexical.py
  - git diff --check
validation:
  - python3 tests/test-shell-lexical.py
  - python3 -m py_compile scripts/project_workflow/shell_lexical.py tests/test-shell-lexical.py
  - git diff --check
acceptance:
  - Project supplied shell bytes into deterministic lexical records without hiding executable regions or accepting ambiguous unsupported syntax.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:f208a240abe31f5d39ee3d0cef5e33a8e3c299ead17f5a8876ab21246e0c6571","stage":"focused","witness":"python3 tests/test-shell-lexical.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/223-reconstruct-backlog-resident-shell-lineage.md
checked_summary_ja: 供給されたshell byteを引用、comment、here-documentを識別する決定的な字句recordへ射影する。

## Decisions

- bounded_shell_lexical_projection means the checked quote-aware, comment-aware, and here-document-aware record projection of supplied shell bytes.
- Parse supplied bytes without executing, sourcing, or importing `tests/copier-update.sh`.
- Reject undecodable bytes and NUL before projection so no executable region is silently dropped.
- Project single quotes, double quotes, backslash escapes, comments, command substitutions, arithmetic expansions, here-documents including quoted and indented forms, line continuations, separators, redirections, and operators as explicit records.
- Reject every unsupported or ambiguous construct instead of producing a partial projection.
- Keep function-table and execution-graph rules out of this slice; Plans 203 and 204 consume these records.
- Use bounded parent implementation and independent review because this slice creates validation-authority code and tests.

## Tasks

- [x] Implement the lexical record projection over supplied text without shell execution.
- [x] Add independent synthetic cases for quoted here-documents, commented here-documents, truncated here-documents, comment continuations, redirection prefixes, and interleaved prefixes.
- [x] Keep the record API explicit so Plans 203 and 204 add behavior without replacing lexical projection.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, archive, commit, and activate Plan 203 with this plan's exact checked archive path.

## Validation Notes

- The rejected `scripts/project_workflow/copier_fixture.py` and `tests/test-copier-fixture.py` candidates are advisory evidence only and must not be written, imported, executed, or used as expected output.
- This slice is intentionally insufficient to accept the Plan 197 and Plan 198 source requirement; Plan 205 retains that acceptance.
- Parent-direct implementation produced `scripts/project_workflow/shell_lexical.py` and a 49-case synthetic suite in `tests/test-shell-lexical.py`, inside the declared two-file write scope. The module imports only `bisect`, `dataclasses`, and `typing`, so it can neither execute, source, nor import a supplied script.
- The record API is `project`, `LexicalProjection`, `Token`, `Segment`, `Position`, and `executable_regions`. Plans 203 and 204 consume these records and add function-table and execution-graph rules without replacing lexical projection.
- Focused validation passed `python3 tests/test-shell-lexical.py` with 49 tests, `python3 -m py_compile scripts/project_workflow/shell_lexical.py tests/test-shell-lexical.py`, and `git diff --check`.
- Independent review ran three rounds. Round 1 reported High 3 and Medium 2, covering command substitutions hidden inside `${...}` and `$((...))`, a here-document delimiter line continuation misread as quoting, delimiter matching that ignored line continuations, a vacuous byte-coverage assertion, and two tests that asserted the hiding behavior. Round 2 reported High 1 and Medium 1, covering a bare `{` that shifted the `${...}` closing boundary and an over-broad here-document continuation rejection. Round 3 reported no High or Medium findings.
- Remediation exposes every nested executable region by scanning expansion interiors recursively, closes `${...}` at the first unquoted brace as bash, dash, and busybox do, and rejects only the two here-document continuations that change delimiter recognition.
- Round 1 also removed a false positive: a blanket rejection of here-documents inside command substitutions broke `scripts/context-compress.sh`. All 30 tracked `*.sh` files now project.
- Known bounded-subset limitations, each a rejection and never a partial projection: backquote command substitution, `$'` and `$"`, `((`, `<<<`, `&>`, `|&`, `;&`, `;;&`, process substitution, quoting inside an arithmetic expansion, a quoted literal brace inside a parameter expansion, and a here-document whose body begins after the end of the operator's own line, as in `x=$(cat <<EOF)`.
- The authoritative suite passed once: the three focused commands plus `python3 scripts/restructure-plan.py --verify`, `python3 scripts/check-root-agent-policy.py`, `scripts/lint-project-workflow.sh`, and `tests/smoke.sh`.
