# Integrate plan restructuring across generated updates

status: in_progress
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - CHANGELOG.md
  - docs/plan/
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - template/docs/plan/
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
  - tests/smoke.sh
  - tests/test-plan-execution-state.py
  - tests/test-plan-restructure.py
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/active/076-plan-restructuring-policy-schema.md
  - docs/plan/active/077-atomic-plan-restructuring.md
  - docs/plan/active/078-plan-execution-budget-ledger.md
  - docs/plan/checked/2026/08/01-15/071-orchestration-throughput-foundation.md
  - docs/plan/checked/2026/08/01-15/073-orchestration-execution-state.md
  - docs/plan/checked/2026/08/01-15/074-isolated-candidate-correction.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-plan-restructure.py
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Add fixed median, edge, negative, and untuned holdout scenarios for requirement preservation, exhausted delegated corrections, repeated parent-direct review findings, multi-invariant findings, scope drift, and post-authoritative design changes.
  - Prove that every hard trigger blocks continued implementation and requires an atomic successor and integration-plan transition.
  - Prove that requirement changes remain pending until explicit user authorization and cannot be disguised as clarification or successor mapping.
  - Keep root and generated policy, schemas, commands, Skills, tests, indexes, and lifecycle behavior aligned.
  - Preserve project-owned product code, policy, configuration, plan history, and validation behavior through supported Copier copy and update paths.
  - Reject unresolved conflicts, rejection files, unclassified tracked-file deletion, destination collisions, index divergence, and partial transition artifacts.
  - Run one independent final High/Medium review before the authoritative suite and keep zero unresolved High or Medium findings.
checked_summary_ja: plan再構成を固定scenario、generated lifecycle、Copier更新へ統合し、要件保持と停止条件を検証した。

## Decisions

- Plans 076 through 078 must be accepted before this integration plan starts.
- This plan adds no new lifecycle state or execution transition.
- Historical plans 071, 073, 074, and 075 provide negative and edge shapes, not synthetic performance claims.
- Run the authoritative full suite only after final independent review reports zero High or Medium findings.

## Tasks

- [ ] Add fixed restructuring and trigger evaluation scenarios.
- [ ] Add generated copy/update and non-destructive migration coverage.
- [ ] Run final independent review and resolve every High or Medium finding.
- [ ] Run the authoritative suite once, archive plans 076 through 079, and commit.

## Validation Notes

- Pending plans 076 through 078.
