# Integrate reached Copier dispatch

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
  - docs/plan/active/258-project-reachable-wrapper-shadowing.md
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
predecessor_plans:
  - docs/plan/active/258-project-reachable-wrapper-shadowing.md
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
checked_summary_ja: 到達可能なshadowingを除外したうえで、wrapperの全正常終了経路が実際のCopier dispatchへ到達することを統合する。

## Decisions

- Activate only after Plan 258 is checked and its exact checked archive replaces the active predecessor.
- Reuse the graph-projected shadowing analysis Plan 258 accepts; do not duplicate it.
- Require every normal wrapper exit to reach a direct `copier` or unshadowed `uv run copier` dispatch.
- Keep `tests/copier-update.sh` and `tests/lib-copier.sh` read-only and byte-identical.

## Tasks

- [ ] Replace the Plan 258 active predecessor with its exact checked archive before activation.
- [ ] Integrate the reached-dispatch path analysis using the accepted graph-projected shadowing rule.
- [ ] Cover guarded dispatches, both reachable arms, nested helper failure handling, normal-name dispatch helpers, explicit returns, and real versus fake `uv run copier` calls.
- [ ] Complete focused validation and one independent read-only review with no unresolved High or Medium finding.
- [ ] Run authoritative validation once, archive, and commit only the declared code, test, and lifecycle files.

## Validation Notes

- Plan 257's unaccepted candidate remains excluded. Plan 258 must establish the reusable reachable-shadowing premise before this integration begins.
