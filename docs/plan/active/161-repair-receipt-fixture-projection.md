# Repair receipt fixture baseline projection

status: in_progress
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
parent_direct_reason: the generic fixture evaluator and root validation checker are parent-owned validation authority
primary_invariant: project every fixture baseline command identifier from its one-based list position before applying the selected case operation without changing production receipt validation or sealed fixture bytes
write_scope:
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - tests/test-sandboxed-plan-worker.py
context_files:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/160-freeze-replacement-receipt-holdout-evidence.md
  - docs/plan/replanned/2026/08/16-31/155-integrate-structured-worker-completion-receipt.md
  - docs/plan/checked/2026/08/16-31/157-integrate-structured-worker-completion-enforcement.md
  - tests/fixtures/orchestration/worker-completion-receipt-scenarios.json
  - tests/fixtures/orchestration/worker-completion-receipt-holdout.json
  - tests/fixtures/orchestration/worker-completion-receipt-holdout-v2.json
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Validate schema, exact fields, types, bounds, normalized paths, identity, lineage, cross-linked digests, and consistency with the admitted candidate before using the receipt; fail closed on missing, duplicate, unknown, malformed, oversized, stale, replayed, or symlink-escaping content.
  - Add deterministic median, edge, negative, and untuned holdout cases for successful and failed attempts, partial command execution, stale or replayed receipt, plan and contract mismatch, patch and path mismatch, false success claims, missing out-of-scope declaration, unknown fields, oversized values, traversal and symlink escape, and attempted secret or raw-output inclusion.
replan_source: docs/plan/active/155-integrate-structured-worker-completion-receipt.md
replan_contract: docs/plan/replanned/contracts/155-integrate-structured-worker-completion-receipt.json
integration_gates:
  - Plan 160 must be checked before evaluator repair starts
  - do not inspect or execute the replacement holdout in this plan
  - preserve production validation and both sealed holdout files byte-for-byte
successor_plans:
  - docs/plan/active/160-freeze-replacement-receipt-holdout-evidence.md
  - docs/plan/active/161-repair-receipt-fixture-projection.md
  - docs/plan/active/162-integrate-structured-worker-completion-receipt.md
inherited_acceptance_digests:
  - sha256:43997ad5fe2020050017d78b835084d1ea3efa60b8f3ddad9d672573e88dcab8
  - sha256:82556513f481a08d6941fd122a8a4e8633391421047d5e7803cd57a89a328fe4
checked_summary_ja: fixture baselineのcommand IDを位置から導出し、case固有の検証が先行する無関係なbaselineエラーに遮られないようにする。

## Context

The exposed original holdout expected a prohibited-content rejection, but its older baseline command identifier failed before the selected case operation. Production correctly requires `worker-check-N`; only the generic fixture projection is stale.

## Decisions

- Canonicalize fixture baseline command identifiers from one-based list position inside the evaluator.
- Keep case-provided command lists unchanged so positional-command negative coverage remains possible.
- Re-run tuned and exposed original fixtures as known regression evidence only; keep replacement holdout opaque.

## Tasks

- [ ] Canonicalize only baseline command identifiers before case mutation.
- [ ] Add a regression proving the exposed original holdout now reaches its selected prohibited-content boundary.
- [ ] Verify tuned observations remain unchanged and production code is untouched.
- [ ] Obtain independent review, run validation once, and archive the plan.

## Validation Notes

- The original holdout's initial failure remains recorded in `/tmp/project-agent-workflow-plan155-20260822-a/execution-state.json` and is not claimed as untuned passing evidence.
