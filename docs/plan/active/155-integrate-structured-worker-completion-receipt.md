# Integrate and evaluate the structured worker completion receipt

status: replan_required
replan_reason_codes:
  - spec_drift
task_types:
  - planning_docs
  - referent_first
  - security
  - skill_authoring
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
parent_direct_reason: final acceptance evidence, holdout execution, and validation lifecycle remain parent-owned
primary_invariant: accept the combined completion-receipt path only when every unchanged source acceptance item passes without transferring diff review validation or lifecycle authority from the parent
write_scope:
  - CHANGELOG.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/project_workflow/copier_inventory.py
  - tests/copier-update.sh
  - tests/fixtures/orchestration/worker-completion-receipt-evidence.json
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/153-freeze-worker-completion-receipt-scenarios.md
  - docs/plan/checked/2026/08/16-31/157-integrate-structured-worker-completion-enforcement.md
  - docs/plan/replanned/2026/08/16-31/114-validate-structured-worker-completion.md
  - docs/plan/checked/2026/08/16-31/136-integrate-plan-bound-worker-contract.md
  - references/orchestration.md
  - references/validation.md
  - tests/fixtures/orchestration/worker-completion-receipt-scenarios.json
  - tests/fixtures/orchestration/worker-completion-receipt-holdout.json
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
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
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Require plan 136, the accepted successor for plan 113, to be checked and archived before implementation starts, and consume its verified worker execution contract identity rather than reconstructing plan authority from worker output.
  - Use plan 136's exact checked archive path before worker start; treat this as a dependency-path refresh only, rerun plan checks, and do not change accepted requirements or broaden scope.
  - Define one versioned, size-bounded worker completion receipt for each successful or failed initial and correction attempt, written only inside the isolated attempt output boundary.
  - Bind the receipt to repository identity, source HEAD, plan path and digest, worker execution contract digest, orchestration run identifier, attempt identifier, correction lineage when applicable, candidate patch digest when emitted, and normalized changed paths.
  - Require bounded fields for claimed acceptance evidence, commands attempted with observed exit status, blockers, residual risks, and an explicit out-of-scope-change declaration; allow empty evidence only when the attempt reports failure before a candidate exists.
  - Keep command and evidence entries declarative and size-limited; never store prompts, free-form output bodies, environment values, credentials, raw logs, patches, or host-specific paths in the receipt.
  - Validate schema, exact fields, types, bounds, normalized paths, identity, lineage, cross-linked digests, and consistency with the admitted candidate before using the receipt; fail closed on missing, duplicate, unknown, malformed, oversized, stale, replayed, or symlink-escaping content.
  - Treat every receipt claim as advisory: the parent must independently inspect the admitted diff and critical invariants, verify changed paths from Git, choose validation from parent-owned plan data, and retain sole acceptance, apply, commit, archive, and completion-report authority.
  - Never allow a worker assertion of success, test passage, scope compliance, or acceptance coverage to advance candidate lifecycle or plan execution state without the existing parent-owned transition and evidence checks.
  - Preserve worker process exit status and bounded sanitized diagnostics separately from receipt validity so malformed reporting cannot convert a failed implementation into success or erase failure evidence.
  - Add deterministic median, edge, negative, and untuned holdout cases for successful and failed attempts, partial command execution, stale or replayed receipt, plan and contract mismatch, patch and path mismatch, false success claims, missing out-of-scope declaration, unknown fields, oversized values, traversal and symlink escape, and attempted secret or raw-output inclusion.
  - Keep root and generated runner behavior byte-identical, keep root and generated policy and Skill semantics aligned after path normalization, and preserve supported non-destructive Copier updates.
  - Record the behavior under Unreleased, run focused validation only after parent diff and critical-invariant review, run the authoritative suite exactly once for an otherwise acceptable candidate, and finish with zero unresolved High or Medium independent-review findings.
replan_source: docs/plan/active/114-validate-structured-worker-completion.md
replan_contract: docs/plan/replanned/contracts/114-validate-structured-worker-completion.json
integration_gates:
  - plans 153 and 157 must be checked and their exact archive paths must replace active context paths before evaluation starts
  - tuned scenarios must equal sha256:264462e6276aa4ab6da320e4773b570ac90353a793bb83abccc01993af21793a and holdout must equal sha256:4473bf88c87cc99b16b3817d2d57169d2f3a5266ba08ece0758811d7644b3f76 before any evaluation command starts
  - plan 115 may start only after this integration plan is checked and its dependency path is refreshed to this plan's exact checked archive
successor_plans:
  - docs/plan/active/153-freeze-worker-completion-receipt-scenarios.md
  - docs/plan/active/154-enforce-structured-worker-completion-receipt.md
  - docs/plan/active/155-integrate-structured-worker-completion-receipt.md
inherited_acceptance_digests:
  - sha256:06c51fc5b5f78aa822c035fccc95b51ce1f72a6f8a53ba7cb3979994c182a252
  - sha256:cc0e91a1c82a44375418b3d4dcfc6e9140da675727149aff02bffed945ce5cea
  - sha256:95ab4926d09833304ba7223b6dfc8ce15fdf4a870566265e03aaf579795b14dd
  - sha256:b29da5035ef6c28f6cb15dd7c9e74e6d0aaea22550eb83d451f147533ca3d089
  - sha256:33683401587ba19a91f7cec022b9a60135cfa8cf6f90b899ef9ad5cd325a4076
  - sha256:ed3224f61d6379b777c481ec2974d3dc706e94efb1506044254a8003e8e5a780
  - sha256:43997ad5fe2020050017d78b835084d1ea3efa60b8f3ddad9d672573e88dcab8
  - sha256:4b360c8a07c7174dbcadaa6e6261828d5ef34f007686bb8f52094529fa3b8daf
  - sha256:b8e2256526a3dcd71afae0f2d9e662e2ffd766c2528c4837bb43654663ee0ba7
  - sha256:00287f9ca9cb9ea1bb9e2ebb4ee5fc1d0badca83daa7d712e3fe48658055ac51
  - sha256:82556513f481a08d6941fd122a8a4e8633391421047d5e7803cd57a89a328fe4
  - sha256:5906dbdbacb32377ea164fff882c5cb1f5b10878410be01b008e50d93015212e
  - sha256:12d75a4567202438fa26035648ffeb23ead6ce2b0cd83483d63833776f706a3f
checked_summary_ja: worker完了受領書の主張を助言的証拠に限定したまま、固定caseと全受入条件でrootと生成物の統合結果を検証する。

## Context

The concrete implementation boundary is one active integration plan that refreshes predecessor archive paths, runs the frozen tuned and holdout scenarios, checks root/generated byte and semantic parity, checks non-destructive Copier behavior, records bounded Unreleased evidence, and requires zero unresolved High or Medium independent-review findings before Plan 115 may start.

## Decisions

- Treat plans 153 and 157 as immutable predecessors; stop for replan rather than changing either accepted design in this integration scope.
- Execute the frozen holdout only after tuned checks, parent diff review, and critical-invariant review pass.
- Record only bounded digest-linked observations and acceptance mapping; keep raw outputs outside the repository.
- Interpret this checked integration as the accepted successor for Plan 115's Plan 114 dependency.
- Use bounded parent implementation and independent review because integration evidence and validation lifecycle are parent-owned.

## Tasks

- [ ] Refresh predecessor context paths to their exact checked archives and verify frozen fixture digests.
- [ ] Execute the generic evaluator across every unchanged tuned and holdout scenario and record bounded digest-linked outcomes.
- [ ] Verify all thirteen source acceptance items, root/template parity, non-destructive Copier behavior, unchanged worker-exit evidence, and unchanged parent lifecycle authority.
- [ ] Record the accepted behavior under Unreleased without overstating receipt evidence.
- [ ] Review the complete diff, obtain independent review, run the authoritative suite exactly once, archive this plan, and refresh Plan 115's dependency path.

## Validation Notes

- This integration plan preserves every normalized Plan 114 acceptance item exactly.
- Any fixture drift or predecessor design change requires replan rather than an in-scope repair.
- Tuned evaluation passed all twenty-one cases, but the first sealed holdout execution observed `unexpected_error` instead of `prohibited_receipt_content` because its baseline command identifier predates the accepted positional `worker-check-N` rule. Ledger: `/tmp/project-agent-workflow-plan155-20260822-a/execution-state.json`.
- The exposed holdout remains byte-unchanged and is now known validation evidence; do not relabel a post-exposure evaluator correction as untuned holdout evidence.
