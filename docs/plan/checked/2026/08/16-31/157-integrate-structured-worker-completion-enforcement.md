# Integrate structured worker completion enforcement

status: checked
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
parent_direct_reason: integration of parent-owned runner policy checkers and validation authority requires bounded parent implementation and independent review
primary_invariant: accept the complete Plan 154 implementation only when every attempt has bounded cross-linked advisory evidence while every lifecycle validation and completion decision remains parent-owned
write_scope:
  - AGENTS.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/copier-update.sh
  - tests/smoke.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/153-freeze-worker-completion-receipt-scenarios.md
  - docs/plan/checked/2026/08/16-31/159-integrate-failure-receipt-validation.md
  - docs/plan/replanned/2026/08/16-31/154-enforce-structured-worker-completion-receipt.md
  - docs/plan/checked/2026/08/16-31/136-integrate-plan-bound-worker-contract.md
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
  - Keep root and generated runner behavior byte-identical, keep root and generated policy and Skill semantics aligned after path normalization, and preserve supported non-destructive Copier updates.
replan_source: docs/plan/active/154-enforce-structured-worker-completion-receipt.md
replan_contract: docs/plan/replanned/contracts/154-enforce-structured-worker-completion-receipt.json
integration_gates:
  - Plan 159 must be checked at docs/plan/checked/2026/08/16-31/159-integrate-failure-receipt-validation.md before integration validation starts
  - keep the tuned scenarios read-only and do not inspect or execute the digest-sealed holdout
  - Plan 155 must replace its Plan 154 predecessor with this plan's exact checked archive before holdout evaluation
successor_plans:
  - docs/plan/active/156-preserve-failure-receipt-without-candidate.md
  - docs/plan/active/157-integrate-structured-worker-completion-enforcement.md
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
  - sha256:5906dbdbacb32377ea164fff882c5cb1f5b10878410be01b008e50d93015212e
checked_summary_ja: 全試行の完了受領書を候補差分へ結び付けて検証しつつ、受理・検証・完了権限を親に保持する。

## Context

This integration boundary adopts the stopped Plan 154 implementation plus the checked Plan 156 correction, then evaluates every unchanged Plan 154 acceptance item without opening the frozen holdout.

## Decisions

- Treat checked Plans 158 and 159 as the accepted correction and integration boundary for the no-candidate failure receipt.
- Integrate the retained policy, Skill, checker, smoke, and Copier changes from stopped Plan 154.
- Require byte-identical root and generated runners and semantically aligned root and generated policy.
- Leave holdout execution and final original Plan 114 acceptance evaluation to Plan 155.

## Tasks

- [x] Refresh Plan 159 to its exact checked archive and inspect the complete retained diff against all Plan 154 acceptance items.
- [x] Verify root/template runner parity, policy and Skill alignment, tuned scenario behavior, and non-destructive Copier preservation.
- [x] Obtain independent review with zero unresolved High or Medium findings.
- [x] Run focused validation, run the authoritative suite exactly once, and archive this plan before Plan 155 starts.

## Validation Notes

- The Plan 154 source acceptance text is copied exactly and requirements, accepted safety conditions, validation authority, and external-effect authority are unchanged.
- The holdout remains sealed at `sha256:4473bf88c87cc99b16b3817d2d57169d2f3a5266ba08ece0758811d7644b3f76` and is not inspected or executed here.
- Plan 159 is checked at `docs/plan/checked/2026/08/16-31/159-integrate-failure-receipt-validation.md`.
- Independent review reported High 0, Medium 0, Low 1 and accepted all eleven acceptance items; the Low item is the previously accepted candidate-present evidence assertion gap. Receipt: `sha256:5fde0ee2e7254d47f66738c1c27ef036e8a778a8bfd9bea78f11af2e0d551480`.
- Focused validation passed once with 92 tests, root policy, Copier static, and diff checks.
- Authoritative validation passed exactly once with 92 tests, runner self-test, root and Copier checks, all-change validation, workflow lint, smoke, real Copier update, and diff check; ledger: `/tmp/project-agent-workflow-plan157-20260822-a/execution-state.json`.
