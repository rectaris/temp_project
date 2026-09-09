# Project reachable wrapper shadowing

status: replanned
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
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
  - docs/plan/checked/2026/09/01-15/249-reject-sourced-library-command-shadowing.md
  - scripts/project_workflow/shell_execution.py
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
primary_invariant: preserve the complete coupled source acceptance baseline
replan_sources:
  - docs/plan/active/258-project-reachable-wrapper-shadowing.md
  - docs/plan/active/259-integrate-reached-copier-dispatch.md
replan_contract: docs/plan/replanned/contracts/258-project-reachable-wrapper-shadowing.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/260-integrate-ordered-sourced-copier-dispatch.md
inherited_acceptance_digests:
  - sha256:4eb4303761f318ee3b775f758771b9cbc4cccbb5cbdca2a509cb315f93bd01f4
checked_summary_ja: wrapperとその到達可能なhelperの実行グラフ上でcommand shadowingを判定し、偽のuvによるCopier dispatchの空文化を拒否する。

## Decisions

- Reuse `shell_execution`'s function-expanded execution graph; do not add a separate reachability or shadowing model.
- Project the existing function, hash, PATH, and helper-file shadowing checks onto operations reached by each Copier wrapper.
- Treat `uv` as an observed command when recognizing `uv run copier`.
- Keep `tests/copier-update.sh` and `tests/lib-copier.sh` read-only and byte-identical.

## Tasks

- [ ] Refactor the existing shadowing analysis so it can consume reachable graph operations without weakening its top-level checks.
- [ ] Reject fake `uv` files and PATH updates created directly in a wrapper and in an ordinary helper it calls.
- [ ] Preserve the committed library's direct Copier and `uv run copier` fallback behavior.
- [ ] Complete focused validation and one independent read-only review with no unresolved High or Medium finding.
- [ ] Archive and commit only the declared code, test, and lifecycle files.

## Validation Notes

- Plan 257 stopped after two parent remediation rounds left a reachable wrapper-local PATH shadowing gap. This plan isolates graph-projected shadowing before the dispatch integration plan consumes it.
- The first independent review found that declaration-only reconstruction dropped source-time PATH state. The first parent remediation retained complete library state and added direct wrapper/helper regressions.
- The second independent review found that caller or sibling-library PATH state remained absent. The second parent remediation added caller and sibling-library regression coverage and included all sourced text.
- The third independent review found that concatenating all source text loses actual source and invocation order, combining future state and uncalled helpers with the wrapper execution. Two parent remediation rounds still leave a Medium finding, so this plan is stopped pending a reconstructed exact source-expansion boundary.
