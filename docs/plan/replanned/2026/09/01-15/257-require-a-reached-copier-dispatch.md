# Require a reached Copier dispatch in the sourced wrapper

status: replanned
replan_reason_codes:
  - parent_remediation_budget_exhausted
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: low
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
  - docs/plan/checked/2026/09/01-15/249-reject-sourced-library-command-shadowing.md
  - docs/plan/backlog/250-require-reachable-fixture-constructions.md
  - tests/copier-update.sh
  - tests/lib-copier.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Reject a sourced Copier wrapper whose only Copier dispatch sits on a command list the shell can skip, while accepting a wrapper whose every normal exit reaches one direct Copier or `uv run copier` dispatch.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:4eb4303761f318ee3b775f758771b9cbc4cccbb5cbdca2a509cb315f93bd01f4","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
predecessor_plans:
  - docs/plan/checked/2026/09/01-15/249-reject-sourced-library-command-shadowing.md
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/257-require-a-reached-copier-dispatch.md
replan_contract: docs/plan/replanned/contracts/257-require-a-reached-copier-dispatch.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/258-project-reachable-wrapper-shadowing.md
  - docs/plan/active/259-integrate-reached-copier-dispatch.md
inherited_acceptance_digests:
  - sha256:4eb4303761f318ee3b775f758771b9cbc4cccbb5cbdca2a509cb315f93bd01f4
checked_summary_ja: 分岐で必ず通るとは限らない位置にしかCopier dispatchがないwrapperを拒否し、Copier観測が空虚になる余地を残さない。

## Decisions

- Close the residual boundary checked Plan 249 recorded rather than restate it. Requiring that some operation of the wrapper body dispatches Copier proves a dispatch is written; it proves nothing about that dispatch being reached.
- Read the whole operation text rather than only its command-word places when deciding that an arm performs a Copier operation, because the committed library writes one arm as `uv run copier "$@"`, whose command word is `uv`.
- Keep one reachability model in the validator. Plan 250 settles reachability for the pre-schema constructions; this plan applies the same model to the wrapper body instead of introducing a second reading.
- Use bounded parent implementation because this is a validation-authority path and writable delegation is prohibited for it.

## Tasks

- [ ] Reproduce the admission read-only by reducing the library wrapper to `if [ -n "${COPIER_ENABLED:-}" ]; then copier "$@"; fi`, and again to `if false; then copier "$@"; fi`, and confirming the checker accepts both.
- [ ] Require that no terminating path through a Copier wrapper body avoids a Copier operation, and keep the committed library accepted unchanged.
- [ ] Add mutation coverage for the guarded dispatch, for the `if false` dispatch, and for the committed `if`/`else` shape that must stay accepted.
- [ ] Complete one fresh independent read-only review and focused validation with zero unresolved High or Medium findings.
- [ ] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending. The reproduction is recorded as the round 3 Medium finding of the Plan 249 independent review and was confirmed in the main session against that plan's checker, with `tests/copier-update.sh` and `tests/lib-copier.sh` left byte-identical. The owner deferred it from Plan 249 rather than dropping it.
