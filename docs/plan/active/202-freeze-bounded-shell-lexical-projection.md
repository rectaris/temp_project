# Freeze the bounded shell lexical projection

status: in_progress
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

- [ ] Implement the lexical record projection over supplied text without shell execution.
- [ ] Add independent synthetic cases for quoted here-documents, commented here-documents, truncated here-documents, comment continuations, redirection prefixes, and interleaved prefixes.
- [ ] Keep the record API explicit so Plans 203 and 204 add behavior without replacing lexical projection.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 203 with this plan's exact checked archive path.

## Validation Notes

- The rejected `scripts/project_workflow/copier_fixture.py` and `tests/test-copier-fixture.py` candidates are advisory evidence only and must not be written, imported, executed, or used as expected output.
- This slice is intentionally insufficient to accept the Plan 197 and Plan 198 source requirement; Plan 205 retains that acceptance.
