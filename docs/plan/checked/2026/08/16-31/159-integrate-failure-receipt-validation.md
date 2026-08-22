# Integrate failure receipt validation

status: checked
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
parent_direct_reason: the integration regression and validation lifecycle are parent-owned validation authority
primary_invariant: accept the candidate-free failure receipt only when the production regression and the contract-compliant self-test both pass without weakening candidate binding or separate process evidence
write_scope:
  - tests/test-sandboxed-plan-worker.py
context_files:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/158-emit-structured-claims-in-runner-self-test.md
  - docs/plan/replanned/2026/08/16-31/156-preserve-failure-receipt-without-candidate.md
  - docs/plan/checked/2026/08/16-31/153-freeze-worker-completion-receipt-scenarios.md
  - tests/fixtures/orchestration/worker-completion-receipt-scenarios.json
  - tests/fixtures/orchestration/worker-completion-receipt-holdout.json
required_specs:
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
replan_source: docs/plan/active/156-preserve-failure-receipt-without-candidate.md
replan_contract: docs/plan/replanned/contracts/156-preserve-failure-receipt-without-candidate.json
integration_gates:
  - Plan 158 must be checked at docs/plan/checked/2026/08/16-31/158-emit-structured-claims-in-runner-self-test.md before integration validation starts
  - preserve the exact Plan 156 production correction and regression test
  - Plan 157 must replace its Plan 156 predecessor with this plan's exact checked archive before full Plan 154 integration starts
successor_plans:
  - docs/plan/active/158-emit-structured-claims-in-runner-self-test.md
  - docs/plan/active/159-integrate-failure-receipt-validation.md
inherited_acceptance_digests:
  - sha256:95ab4926d09833304ba7223b6dfc8ce15fdf4a870566265e03aaf579795b14dd
  - sha256:b29da5035ef6c28f6cb15dd7c9e74e6d0aaea22550eb83d451f147533ca3d089
  - sha256:33683401587ba19a91f7cec022b9a60135cfa8cf6f90b899ef9ad5cd325a4076
  - sha256:43997ad5fe2020050017d78b835084d1ea3efa60b8f3ddad9d672573e88dcab8
  - sha256:00287f9ca9cb9ea1bb9e2ebb4ee5fc1d0badca83daa7d712e3fe48658055ac51
checked_summary_ja: 候補なし失敗の受領書・process結果・回帰testと契約準拠self-testを一体で確認する。

## Context

This integration boundary combines the reviewed candidate-free production failure receipt correction, its end-to-end regression, and Plan 158's contract-compliant self-test worker.

## Decisions

- Preserve empty acceptance evidence only for a valid failure without a candidate.
- Preserve parent-derived not-satisfied evidence and candidate binding when a candidate exists.
- Require the complete unit suite and self-test to pass before Plan 157 may integrate the retained policy changes.

## Tasks

- [x] Refresh Plan 158 to its exact checked archive.
- [x] Inspect the production branch and regression against every inherited acceptance item.
- [x] Obtain independent review with zero unresolved High or Medium findings.
- [x] Run focused validation, run the authoritative suite exactly once, and archive the plan.

## Validation Notes

- This plan does not inspect or execute the frozen holdout.
- The Plan 156 acceptance text and accepted safety conditions are unchanged.
- Plan 158 is checked at `docs/plan/checked/2026/08/16-31/158-emit-structured-claims-in-runner-self-test.md`.
- Independent review reported High 0, Medium 0, Low 1 and accepted the integration candidate; the Low item is a non-blocking candidate-present evidence assertion gap. Receipt: `sha256:8500ab83cea08676187f531e1135e55c6b99084c559aca7176fbc89949df181e`.
- Focused validation passed once with 92 tests, Copier static check, and `git diff --check`.
- Authoritative validation passed exactly once with 92 tests, runner self-test, Copier static check, and `git diff --check`; ledger: `/tmp/project-agent-workflow-plan159-20260822-a/execution-state.json`.
