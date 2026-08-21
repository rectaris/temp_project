# Validate a structured worker completion receipt

status: in_progress
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
primary_invariant: accept a worker completion receipt only as bounded advisory evidence while retaining all diff review and validation authority in the parent
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
  - docs/plan/active/136-integrate-plan-bound-worker-contract.md
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
  - After plan 136 is archived, replace its active `context_files` entry with the exact checked archive path before worker start; treat this as a dependency-path refresh only, rerun plan checks, and do not change accepted requirements or broaden scope.
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
- The parent must refresh Plan 136's context path after archival before invoking a worker for this plan.
