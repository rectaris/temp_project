# Enforce active-plan predecessor identities

status: checked
primary_invariant: a dependent active plan cannot become in_progress until every exact predecessor is checked and no active predecessor edge forms a cycle
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - tests/validation_tools/plan.py
preservation_scope:
  - scripts/check-copier-template.py
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/188-separate-replan-preservation-authority.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 tests/test-validation-tools.py
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Require every deferred dependency chain to declare exact predecessor plan identities, reject cycles or premature activation, and replace each active predecessor path with its exact checked archive before the dependent plan becomes in_progress.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:58e4bb384e9d49ab1b6dcb65c9faa1e870172cbe37a1ca48f7b6a184c3f56c4b","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/188-separate-replan-preservation-authority.md
integration_gates:
  - Plan 188 is checked at docs/plan/checked/2026/08/16-31/188-separate-replan-preservation-authority.md
  - preserve scripts/check-copier-template.py and tests/copier-update.sh without editing, staging, or committing them
  - Plan 164 remains deferred until this plan is checked and its exact checked archive path replaces its active predecessor
checked_summary_ja: active planの依存先、循環、checked移行、実行可能状態を機械的に検証する。

## Decisions

- predecessor_plans means the exact active or checked plan paths whose checked lifecycle state is required before the dependent plan may become in_progress.
- Keep historical numeric plan identifiers immutable and derive readiness from exact predecessor identities rather than numeric sort order.
- Require deferred status while any predecessor remains active, require exact checked archive paths before activation, and reject missing, duplicate, stale, cross-id, or cyclic edges.
- Keep successor_plans as immutable restructuring lineage and never interpret it as operational execution order.
- Validate the root active index and generated-project plan lifecycle with the same predecessor semantics.
- Use bounded parent implementation and independent review because this plan changes lifecycle validation authority.

## Tasks

- [x] Add predecessor parsing, identity resolution, acyclicity, status, and active-to-checked refresh checks.
- [x] Add positive chains and negative cycle, premature activation, stale path, wrong id, duplicate edge, and successor-lineage-confusion tests.
- [x] Align root and generated plan workflow policy and validation behavior.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, archive, commit, and activate Plan 164 with the exact checked predecessor path.

## Validation Notes

- Focused validation passed with 27 restructuring tests, 41 validation-tool tests, and `git diff --check`.
- Independent review identified and cleared three Medium findings: unreachable root validation, dropped active index identities, and a worker-admission bypass.
- The initial authoritative run failed in `tests/smoke.sh` because predecessor checking made `add_active` require a materialized active plan, breaking the deliberate conflicting-index fixture.
- Independent diagnosis confirmed the affected invariant that `add_active` remains a pure index registration operation; the bounded repair restored that contract while keeping worker admission and lifecycle transitions fail-closed.
- The fresh authoritative suite passed: both focused test files, Copier template checking, project workflow lint, smoke tests, and `git diff --check`.
