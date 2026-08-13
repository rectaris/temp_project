# Integrate plan restructuring across generated updates

status: replanned
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
  - docs/plan/checked/2026/08/01-15/076-plan-restructuring-policy-schema.md
  - docs/plan/checked/2026/08/01-15/077-atomic-plan-restructuring.md
  - docs/plan/checked/2026/08/01-15/078-plan-execution-budget-ledger.md
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
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/079-plan-restructuring-integration.md
replan_contract: docs/plan/replanned/contracts/079-plan-restructuring-integration.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/080-successor-acceptance-authority.md
  - docs/plan/active/081-plan-restructuring-integration.md
inherited_acceptance_digests:
  - sha256:e5ee0e951c5eef281fc3f54c22d549dffd750f43f0e232f724b12d8e0ed2e637
  - sha256:99fac9ef19ac18be11c578944c85b91c925efd945bf374f2bf6a5654e0b2e6b2
  - sha256:f63ec861469ec27fe14daef2ba73dc1cdeadae80e5a35395c09f35abfe486c57
  - sha256:675856f8d05166ebfc9efa5b4fffc5199d404792bf648a919f094bd3e9ea2c8e
  - sha256:30e8a6c3d65ec3e739284e02025847bf88f88901e855beec711bf8424f3866f7
  - sha256:6d763d5c86eacb20d1eb1cc7e29cb45707d57c2ec2c7fd9e74af6a4074ad7001
  - sha256:5cc609d78dd1464f9a71b7dde9005bb8ebe3db475048a24a2bd804dc86d8fef8
checked_summary_ja: plan再構成を固定scenario、generated lifecycle、Copier更新へ統合し、要件保持と停止条件を検証した。
replan_reason_codes:
  - scope_drift
  - multiple_independent_invariants

## Decisions

- Plans 076 through 078 must be accepted before this integration plan starts.
- This plan adds no new lifecycle state or execution transition.
- Historical plans 071, 073, 074, and 075 provide negative and edge shapes, not synthetic performance claims.
- Run the authoritative full suite only after final independent review reports zero High or Medium findings.

## Tasks

- [x] Add fixed restructuring and trigger evaluation scenarios.
- [x] Add generated copy/update and non-destructive migration coverage.
- [ ] Run final independent review and resolve every High or Medium finding.
- [ ] Run the authoritative suite once, archive plans 076 through 079, and commit.

## Validation Notes

- Plans 076 through 078 were accepted and archived before integration work began.
- Added fixed median, edge, and negative cases plus a physically separate untuned holdout.
- Added focused boundary-trigger coverage and verified the new test, fixture syntax, shell syntax, Python syntax, and diff whitespace before independent review.
- Copier update lanes now hash-check a project-owned replanned-plan history record created before the update.
- Independent review found that successor acceptance authority and integration evidence are separate invariants and that the former falls outside this plan's write scope. Stop this plan and restructure it atomically before further implementation.
