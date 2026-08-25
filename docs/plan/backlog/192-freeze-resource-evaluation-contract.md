# Freeze the resource-bounded orchestration evaluation contract

status: backlog
primary_invariant: fixed paired workloads, schemas, holdouts, measures, and tampering cases preserve comparable evaluation inputs without collecting or interpreting an outcome
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
  - scripts/check-root-agent-policy.py
  - tests/fixtures/orchestration/staged-acceptance.json
  - tests/fixtures/orchestration/staged-baseline-events.json
  - tests/fixtures/orchestration/staged-holdout-events.json
  - tests/fixtures/orchestration/resource-evaluation-schema-v1.json
  - tests/fixtures/orchestration/resource-session-regression-v1.json
preservation_scope:
  - scripts/check-copier-template.py
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/167-integrate-validation-witness-enforcement.md
  - docs/plan/replanned/2026/08/16-31/133-evaluate-resource-bounded-orchestration.md
  - tests/fixtures/orchestration/evaluation-protocol.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - git diff --check
validation:
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - git diff --check
acceptance:
  - Keep holdout cases physically outside reusable implementation prompts and configuration tuning, and fail evaluation when any required scenario class or pair is missing, reordered without a version change, or not backed by raw runner and ledger evidence.
  - Add deterministic tampering and holdout checks for side swapping, digest mismatch, missing raw evidence, synthetic summary promotion, absent scenario class, hidden manual restart, unobserved token inference, quality regression, threshold boundary, p95 regression, and attempted safety-gate weakening.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:fbc1c1c96eb6501b3b5d9f0216dbca4b9c9effaba938fef770699862afeeaa07","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
  - {"acceptance_sha256":"sha256:089ede7f008b392e945178ad74cfb61e714a468f7a74ebb565f44f1343fc45e1","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
replan_source: docs/plan/active/133-evaluate-resource-bounded-orchestration.md
replan_contract: docs/plan/replanned/contracts/133-evaluate-resource-bounded-orchestration.json
predecessor_plans:
  - docs/plan/active/167-integrate-validation-witness-enforcement.md
integration_gates:
  - Plan 167 must be checked and its exact checked archive path must replace this active predecessor before implementation
  - freeze fixtures and checker behavior without running paired model executions or changing the default path
  - Plan 193 remains deferred until this plan is checked and its exact checked archive path replaces its active predecessor
successor_plans:
  - docs/plan/active/192-freeze-resource-evaluation-contract.md
  - docs/plan/active/193-collect-resource-evaluation-evidence.md
  - docs/plan/active/194-apply-resource-evaluation-outcome.md
  - docs/plan/active/195-verify-plan133-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:fbc1c1c96eb6501b3b5d9f0216dbca4b9c9effaba938fef770699862afeeaa07
  - sha256:089ede7f008b392e945178ad74cfb61e714a468f7a74ebb565f44f1343fc45e1
checked_summary_ja: 同一条件で比較するworkload、schema、holdout、計測項目、改ざん拒否条件を固定する。

## Decisions

- Freeze median, edge, negative, untuned holdout, late-integration, and session-reuse regression workloads as distinct versioned cases.
- Bind source commit, workload bytes, runner and configuration identities, plan and invariant digests, schemas, model route, and directly observed resource fields.
- Keep holdouts physically outside reusable prompts and reject missing, reordered, duplicated, or synthetic scenario evidence.
- Do not collect paired results, select a default, or claim an improvement in this slice.
- Freeze outcome-independent default-selection and rollback cases before any paired result exists; later plans may supply evidence but cannot change this checker behavior.
- Use bounded parent implementation and independent review because the checker is validation authority.

## Tasks

- [ ] Define the versioned evidence schema and exact fixed workloads.
- [ ] Add positive and tampering fixtures for every accepted identity, measurement, holdout, and reviewer boundary.
- [ ] Extend the checker for schema and fixture integrity without embedding expected measured outcomes.
- [ ] Freeze positive and negative default-selection and rollback cases that do not encode a measured result.
- [ ] Complete focused validation and independent review, archive, commit, and activate Plan 193.

## Validation Notes

- This plan freezes inputs only and preserves both current validation-witness product candidates.
