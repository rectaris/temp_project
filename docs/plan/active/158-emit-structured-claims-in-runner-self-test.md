# Emit structured claims in the runner self-test

status: in_progress
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
parent_direct_reason: the defect is confined to the parent-owned runner self-test and its byte-identical generated copy
primary_invariant: make the deterministic self-test worker emit one valid success claims artifact bound to its derived worker contract before the runner validates its completion receipt
write_scope:
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
context_files:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/replanned/2026/08/16-31/156-preserve-failure-receipt-without-candidate.md
  - docs/plan/checked/2026/08/16-31/153-freeze-worker-completion-receipt-scenarios.md
  - tests/fixtures/orchestration/worker-completion-receipt-scenarios.json
  - tests/fixtures/orchestration/worker-completion-receipt-holdout.json
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Define one versioned, size-bounded worker completion receipt for each successful or failed initial and correction attempt, written only inside the isolated attempt output boundary.
  - Bind the receipt to repository identity, source HEAD, plan path and digest, worker execution contract digest, orchestration run identifier, attempt identifier, correction lineage when applicable, candidate patch digest when emitted, and normalized changed paths.
replan_source: docs/plan/active/156-preserve-failure-receipt-without-candidate.md
replan_contract: docs/plan/replanned/contracts/156-preserve-failure-receipt-without-candidate.json
integration_gates:
  - change only the deterministic self-test worker's claims emission and keep the production failure-receipt correction unchanged
  - keep root and generated runners byte-identical
  - keep the tuned scenarios read-only and do not inspect or execute the digest-sealed holdout
successor_plans:
  - docs/plan/active/158-emit-structured-claims-in-runner-self-test.md
  - docs/plan/active/159-integrate-failure-receipt-validation.md
inherited_acceptance_digests:
  - sha256:95ab4926d09833304ba7223b6dfc8ce15fdf4a870566265e03aaf579795b14dd
  - sha256:b29da5035ef6c28f6cb15dd7c9e74e6d0aaea22550eb83d451f147533ca3d089
checked_summary_ja: 内蔵self-test workerも契約由来の成功claimsを出力し、完了受領書の必須経路を通す。

## Context

Plan 156's one authoritative suite exposed that the deterministic self-test worker predated the required completion claims artifact. The production worker path correctly rejected its missing claims.

## Decisions

- Read the self-test worker contract and derive exactly one satisfied acceptance evidence entry per contract acceptance item.
- Write only the bounded claims artifact through the supplied completion-claims path.
- Preserve the already reviewed production failure receipt branch.

## Tasks

- [ ] Add contract-bound success claims to the deterministic self-test worker.
- [ ] Keep root and generated runners byte-identical.
- [ ] Obtain independent review, run focused validation, run this plan's validation exactly once, and archive it.

## Validation Notes

- Plan 156 stopped at `/tmp/project-agent-workflow-plan156-20260822-a/execution-state.json` after its single authoritative run exposed validation-method drift.
- The holdout remains opaque and unexecuted.
