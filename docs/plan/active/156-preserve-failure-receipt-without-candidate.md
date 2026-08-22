# Preserve failure receipts without a candidate

status: replan_required
replan_reason_codes:
  - spec_drift
task_types:
  - planning_docs
  - referent_first
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
parent_direct_reason: the remaining defect is in the parent-owned runner and its validation-authority tests
primary_invariant: emit one valid bounded failure receipt and preserve the separate process result when a worker exits nonzero with valid failure claims before any candidate exists
write_scope:
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - tests/test-sandboxed-plan-worker.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/153-freeze-worker-completion-receipt-scenarios.md
  - docs/plan/replanned/2026/08/16-31/154-enforce-structured-worker-completion-receipt.md
  - docs/plan/checked/2026/08/16-31/136-integrate-plan-bound-worker-contract.md
  - tests/fixtures/orchestration/worker-completion-receipt-scenarios.json
  - tests/fixtures/orchestration/worker-completion-receipt-holdout.json
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Define one versioned, size-bounded worker completion receipt for each successful or failed initial and correction attempt, written only inside the isolated attempt output boundary.
  - Bind the receipt to repository identity, source HEAD, plan path and digest, worker execution contract digest, orchestration run identifier, attempt identifier, correction lineage when applicable, candidate patch digest when emitted, and normalized changed paths.
  - Require bounded fields for claimed acceptance evidence, commands attempted with observed exit status, blockers, residual risks, and an explicit out-of-scope-change declaration; allow empty evidence only when the attempt reports failure before a candidate exists.
  - Validate schema, exact fields, types, bounds, normalized paths, identity, lineage, cross-linked digests, and consistency with the admitted candidate before using the receipt; fail closed on missing, duplicate, unknown, malformed, oversized, stale, replayed, or symlink-escaping content.
  - Preserve worker process exit status and bounded sanitized diagnostics separately from receipt validity so malformed reporting cannot convert a failed implementation into success or erase failure evidence.
replan_source: docs/plan/active/154-enforce-structured-worker-completion-receipt.md
replan_contract: docs/plan/replanned/contracts/154-enforce-structured-worker-completion-receipt.json
integration_gates:
  - preserve the stopped Plan 154 implementation as read-only baseline except for the exact no-candidate failure branch and its regression test
  - keep the tuned scenarios read-only and do not inspect or execute the digest-sealed holdout
  - Plan 157 must integrate every unchanged Plan 154 acceptance item after this plan is checked
successor_plans:
  - docs/plan/active/156-preserve-failure-receipt-without-candidate.md
  - docs/plan/active/157-integrate-structured-worker-completion-enforcement.md
inherited_acceptance_digests:
  - sha256:95ab4926d09833304ba7223b6dfc8ce15fdf4a870566265e03aaf579795b14dd
  - sha256:b29da5035ef6c28f6cb15dd7c9e74e6d0aaea22550eb83d451f147533ca3d089
  - sha256:33683401587ba19a91f7cec022b9a60135cfa8cf6f90b899ef9ad5cd325a4076
  - sha256:43997ad5fe2020050017d78b835084d1ea3efa60b8f3ddad9d672573e88dcab8
  - sha256:00287f9ca9cb9ea1bb9e2ebb4ee5fc1d0badca83daa7d712e3fe48658055ac51
checked_summary_ja: 候補がない正当な失敗試行でも、空の受入証拠を持つ受領書と独立したprocess結果を必ず保存する。

## Context

Plan 154 stopped after two bounded parent remediation rounds because one valid nonzero worker failure path retained parent-derived acceptance evidence even though no candidate existed, causing final receipt validation to reject the receipt.

## Decisions

- Preserve empty acceptance evidence only for a valid failure before a candidate exists.
- Preserve parent-derived bounded failure evidence when a candidate exists.
- Add one end-to-end regression that proves both the failure receipt and separate process-result artifact survive without a candidate or patch.
- Keep every other stopped Plan 154 implementation path unchanged in this bounded successor.

## Tasks

- [ ] Correct the no-candidate failure receipt branch without changing candidate-present behavior.
- [ ] Add the exact nonzero valid-failure-claims regression and verify no patch or manifest is published.
- [ ] Review the bounded diff, run focused validation, obtain independent review, run this plan's validation once, and archive the plan.

## Validation Notes

- The stopped Plan 154 ledger is `/tmp/project-agent-workflow-plan154-20260822-b/execution-state.json` with state `replan_required` and reason `parent_remediation_budget_exhausted`.
- The Plan 156 ledger is `/tmp/project-agent-workflow-plan156-20260822-a/execution-state.json`; its one authoritative suite passed 92 tests but exposed a self-test worker that did not emit the newly required claims artifact, so the validation method requires restructuring.
- The tuned fixture remains sealed at `sha256:264462e6276aa4ab6da320e4773b570ac90353a793bb83abccc01993af21793a`; the holdout remains opaque at `sha256:4473bf88c87cc99b16b3817d2d57169d2f3a5266ba08ece0758811d7644b3f76`.
