# Validate a structured worker completion receipt

status: replanned
replan_reason_codes:
  - spec_drift
  - multiple_independent_invariants
task_types:
  - planning_docs
  - referent_first
  - security
  - skill_authoring
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: ordinary
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
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
  - docs/plan/checked/2026/08/16-31/136-integrate-plan-bound-worker-contract.md
  - docs/plan/checked/2026/08/01-15/074-isolated-candidate-correction.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
  - docs/plan/checked/2026/08/01-15/078-plan-execution-budget-ledger.md
  - references/orchestration.md
  - references/validation.md
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
  - REQUIRE_COPIER=1 tests/copier-update.sh
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
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/114-validate-structured-worker-completion.md
replan_contract: docs/plan/replanned/contracts/114-validate-structured-worker-completion.json
integration_gates:
  - combined successors must satisfy every source acceptance item
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
checked_summary_ja: worker完了受領書を構造化して検証するが、その主張は助言的証拠に限定し、差分確認と受理権限は親に保持する。

## Context

The current worker prompt requests a prose report of changed paths, validation, blockers, residual risks, and out-of-scope confirmation. That report is not one schema-bound artifact cross-linked to the candidate and plan.

The worker completion receipt is the versioned size-bounded advisory record emitted by one worker attempt and validated before parent diff review and validation acceptance.

A structured receipt can reduce review ambiguity, but it cannot prove that the patch is correct or transfer acceptance authority to the worker.

## Decisions

- Emit one structured receipt per attempt and bind it to the plan-derived contract and candidate lineage.
- Keep the receipt free of raw interaction content, secrets, patches, and host-specific paths.
- Validate identity and consistency before review while treating all worker claims as advisory.
- Keep Git-derived changed paths, parent diff review, parent-owned validation, lifecycle transitions, and final reporting authoritative.

## Tasks

- [ ] Define the receipt schema, field bounds, failure representation, and candidate cross-linking.
- [ ] Integrate receipt production and validation into initial and correction attempts without advancing lifecycle from worker claims.
- [ ] Align root and generated policy, Skill, runner, inventories, and Copier behavior.
- [ ] Add deterministic accepted, failed, malformed, deceptive, tampering, isolation, and holdout coverage.
- [ ] Review the candidate diff and primary invariant, run focused validation, complete independent review, run the authoritative suite once, and archive the accepted plan before plan 115 starts.

## Validation Notes

- Decision audit selected a structured result artifact while preserving the manager-style parent as the only final acceptance owner.
- The advisory referent contract sealed the worker completion receipt as bounded advisory evidence rather than a validation receipt or acceptance decision.
- Plan 136 is the accepted Plan 113 successor and a hard predecessor because this plan binds completion evidence to its generated contract identity.
- Plan 136's context path now names its exact checked archive; the parent must preserve it when invoking a worker for this plan.
- Execution ledger run `plan114-restructure-20260822-a` stopped before worker start with `multiple_independent_invariants`; do not reopen or reuse that run.
- Independent preimplementation review also confirmed `spec_drift`: the current fail-closed runner rejects this plan's directory-prefix, protected-input, and validation-authority write scopes before invocation.
- Preserve all thirteen acceptance items while restructuring into separate scenario-freeze, receipt-enforcement, and integration plans.
