# Integrate ordered sourced Copier dispatch

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
  - docs/plan/active/260-integrate-ordered-sourced-copier-dispatch.md
replan_contract: docs/plan/replanned/contracts/260-integrate-ordered-sourced-copier-dispatch.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/261-source-aware-copier-dispatch.md
inherited_acceptance_digests:
  - sha256:4eb4303761f318ee3b775f758771b9cbc4cccbb5cbdca2a509cb315f93bd01f4
checked_summary_ja: source文を実行位置で展開した実行グラフにより、実際のCopier dispatchへ全正常終了経路が到達することを確認する。

## Decisions

- Replace a bound source command at its reached position with the exact supplied library bytes before deriving the shared lexical, function, and execution projections.
- Resolve recursive bound sources from the inherited checked root anchor, reject an unbound, cyclic, or structurally invalid source, and preserve source order.
- Apply function, hash, PATH, and helper-file shadowing only to operations that reach the wrapper dispatch in that ordered graph.
- Use the same ordered graph to require every normal wrapper exit to reach a direct `copier` or unshadowed `uv run copier` dispatch.
- Keep `tests/copier-update.sh` and `tests/lib-copier.sh` read-only and byte-identical.

## Tasks

- [ ] Build one bounded ordered source-expansion projection from supplied fixture and bound-library bytes without executing shell code.
- [ ] Apply command-shadowing checks to the wrapper's reachable dispatch context and reject fake `uv` created before the dispatch through the caller, a sourced library, or a reachable helper.
- [ ] Require every normal wrapper exit to reach a real dispatch; preserve valid direct dispatches, valid `uv run copier`, and non-dispatching predicates.
- [ ] Add source-order, wrapper and helper shadowing, guarded-path, normal-helper, nested-failure, explicit-return, and post-dispatch / uncalled-helper regression coverage.
- [ ] Complete focused validation and one independent read-only review with no unresolved High or Medium finding.
- [ ] Run authoritative validation once, archive, and commit only the declared code, test, and lifecycle files.

## Validation Notes

- The Plan 258 concatenation candidate is excluded because it combined state after the real wrapper call and uncalled helpers with the wrapper context.
- Plan 259 is reconstructed in the same transaction because it is an immutable dependent successor whose predecessor could otherwise become a permanently stale path.
