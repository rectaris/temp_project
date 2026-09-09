# Source-aware Copier dispatch

status: replanned
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: high
write_scope:
  - scripts/project_workflow/shell_execution.py
  - scripts/project_workflow/copier_fixture_validator.py
  - tests/test-shell-execution.py
  - tests/test-copier-fixture-validator.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/09/01-15/249-reject-sourced-library-command-shadowing.md
  - tests/copier-update.sh
  - tests/lib-copier.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-shell-execution.py
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-shell-execution.py
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
  - docs/plan/active/261-source-aware-copier-dispatch.md
replan_contract: docs/plan/replanned/contracts/261-defer-unbounded-copier-dispatch-proof.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/262-defer-unbounded-copier-dispatch-proof.md
inherited_acceptance_digests:
  - sha256:4eb4303761f318ee3b775f758771b9cbc4cccbb5cbdca2a509cb315f93bd01f4
checked_summary_ja: shared execution graphにsource、call、lookup provenanceを持たせ、各wrapper実行ごとに実際のCopier dispatchへの到達を検証する。

## Decisions

- Replace textual source expansion and offset-based occurrence reconstruction with source occurrences represented directly by `shell_execution`.
- Preserve one source command's exact caller state, source order, and repeated top-level effects without duplicating function declarations.
- Bind each nested helper call to its specific parent call occurrence and propagate operation arguments through that edge.
- Model persistent PATH, `hash`, helper-file writes, and trusted dynamic Copier resolution as lookup provenance at the exact dispatch occurrence; reject unproven dynamic dispatches.
- Keep `tests/copier-update.sh` and `tests/lib-copier.sh` read-only and byte-identical.

## Tasks

- [ ] Extend the shared execution graph with bounded source-library occurrence expansion and origin-aware call frames without executing shell code.
- [ ] Preserve per-occurrence shell state for persistent command lookup changes and distinguish shell-persistent assignments from command-local environments.
- [ ] Require each potentially successful sourced Copier-wrapper return to reach an unshadowed direct Copier or proven `uv run copier` dispatch in its exact occurrence.
- [ ] Add source, repeated-helper, root-rebinding, dynamic-dispatch, lookup-shadowing, and branch-feasibility regressions in the graph and fixture validator suites.
- [ ] Complete focused validation and one independent read-only review with no unresolved High or Medium finding.
- [ ] Run authoritative validation once, archive, and commit only the declared code, test, and lifecycle files.

## Validation Notes

- Plan 260 is stopped after two remediation rounds. Its string-spliced source projection could not preserve all lookup and assignment occurrence semantics, leaving real-dispatch bypasses and branch false positives.
