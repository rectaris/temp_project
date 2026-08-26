# Derive the bounded shell function table

status: in_progress
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

- [ ] Implement the unique top-level function table over checked lexical records.
- [ ] Add independent synthetic cases for duplicate, nested, split, piped, conditional, and dynamically evaluated declarations.
- [ ] Keep the table API explicit so Plan 204 consumes it without replacing derivation.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 204 with this plan's exact checked archive path.

## Validation Notes

- The rejected `scripts/project_workflow/copier_fixture.py` and `tests/test-copier-fixture.py` candidates are advisory evidence only and must not be written, imported, executed, or used as expected output.
- This slice is intentionally insufficient to accept the Plan 197 and Plan 198 source requirement; Plan 205 retains that acceptance.
