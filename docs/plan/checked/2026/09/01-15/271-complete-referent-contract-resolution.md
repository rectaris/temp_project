# Complete referent contract resolution with preserved draft identity

status: checked
primary_invariant: ending or relocating a referent contract preserves its recorded semantic evidence and cannot create semantic acceptance, while active records remain actionable
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
review_class: B
human_design_required: no
human_approval_status: approved
plan_purpose: implementation
replan_sources:
  - docs/plan/active/269-resolve-stale-referent-contracts.md
replan_contract: docs/plan/replanned/contracts/269-complete-referent-contract-resolution.json
successor_plans:
  - docs/plan/active/271-complete-referent-contract-resolution.md
inherited_acceptance_digests:
  - sha256:2cb05261df94708d4babddb2029c366cb71ab24978c8d66b31b0d54bddb22b35
integration_source_ids:
  - 269
task_types:
  - template_workflow
  - planning_docs
  - security
  - referent_first
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"The preserved Plan 269 candidate returns an empty pending --target archive.md report after relocate-target and reopen, despite retaining archive.md as the effective draft location."}
  - {"kind":"reproduced_defect","evidence":"The same candidate accepts relocation after draft.md is replaced with a directory. Both remaining defects have bounded branch-level fixes and regression scenarios."}
  - {"kind":"existing_mechanism","evidence":"The complete prior 12-file candidate is retained unchanged in the original worktree and at /tmp/referent-270-inherited.patch; its CLI, hook, and lifecycle regressions already pass 17 and 43 tests."}
completion_conditions:
  - Relocated draft references accept identical bytes only and preserve sealed target identity and previous locations; missing or changed draft bytes cannot become accepted by relocation.
  - Ending applicability preserves the previous contract and reason evidence, removes the reminder, and never satisfies semantic acceptance or required review.
  - The hook and plan completion or archival commands report relevant unfinished records with concrete next steps without completing contracts, mutating targets, or blocking unrelated work.
completion_witness_map:
  - {"condition_sha256": "sha256:fc6357bf4bbef7e4fde5c197ad249e5242563b46f7c04c007794189cec3e6155", "witness": "python3 tests/test-referent-contract.py"}
  - {"condition_sha256": "sha256:679f36c230b143712118d0c5e2cd915086a507a34d2ef6c3b4ced1d0ad820851", "witness": "python3 tests/test-referent-contract.py"}
  - {"condition_sha256": "sha256:be79e8ae9dfb852f4df57eac31e340b474641766d4678dbaf068a10988336a9d", "witness": "python3 tests/test-referent-contract.py"}
write_scope:
  - scripts/referent-contract.py
  - template/.project-agent-workflow/scripts/referent-contract.py
  - .project-agent-workflow/hooks/semantic_guard_advisory.py
  - template/.project-agent-workflow/hooks/semantic_guard_advisory.py
  - scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - docs/agent/SPEC_REFERENT_FIRST.md
  - template/.project-agent-workflow/docs/agent/SPEC_REFERENT_FIRST.md
  - tests/test-referent-contract.py
  - tests/hooks/semantic.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - references/orchestration.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-referent-contract.py
  - python3 tests/test-hooks.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Preserve evidence and semantic acceptance boundaries while resolving stale referent records through explicit draft relocation or documented ended applicability, and make root and generated lifecycle reminders actionable.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256": "sha256:2cb05261df94708d4babddb2029c366cb71ab24978c8d66b31b0d54bddb22b35", "stage": "focused", "witness": "python3 tests/test-referent-contract.py"}
integration_gates:
  - Use bounded parent implementation for inseparable contract-state policy, validation, and hook changes; obtain one independent read-only review before authoritative validation.
  - Preserve existing successful required-review semantics; ended applicability must remain a failed acceptance check.
  - Do not alter unrelated Plan 268 implementation; temporarily defer it while the owner-prioritized referent repair executes.
predecessor_plans:
  - docs/plan/checked/2026/09/01-15/270-admit-referent-validation-commands.md
checked_summary_ja: 用語の記録に下書きの参照先変更と適用終了の手続きを追加し、未完了の記録に必要な対応を通知する。

## Decisions

- The owner instructed 「作業を続けよ。」 after the two-review run stopped. Preserve that stopped execution and continue through this implementation successor.
- Preserve the entire source acceptance, safety conditions, write scope, and focused and authoritative validation commands.
- Keep the original working tree's unaccepted candidate intact while reconstructing in a clean independent copy. Use that candidate as implementation input, never as acceptance evidence.
- Include the effective draft location derived from all registration history in filtered reminders, including before re-registration after reopen.
- Distinguish a missing original draft from an existing non-regular replacement with lstat before relocation. Refuse directories, symlinks, FIFOs, and other non-regular replacements without reading them or changing the contract.
- Use bounded parent implementation because policy, tests, and hook behavior are inseparable; obtain a fresh independent review of the entire inherited and corrected diff before authoritative validation.
- End only the three obsolete local records identified by the owner after validating their history and evidence. Do not change the independent Plan 268 record or claim any historical semantic review.

## Tasks

- [x] Apply the preserved candidate in the isolated implementation copy and correct the two remaining defects in root and template.
- [x] Add focused regressions for filtered reminders across reopen and non-regular previous-target replacements.
- [x] Obtain independent review of the complete candidate and pass all focused and authoritative validation.
- [x] Reconcile the three local contracts with preserved evidence, integrate the tested commits, archive this plan, and restore Plan 268 to its pre-existing active state.

## Validation Notes

- Source Plan 269 is stopped with two unresolved Medium findings and no authoritative validation attempt. This successor inherits no successful product acceptance.
- Original candidate SHA-256: bd6e1f368809ac6d9b0106310c169b8e34e3d0881d650b266e556e7b1c369481. The original worktree preserves all 12 uncommitted product paths; the clean reconstruction copy does not discard or modify them.

- Final parent acceptance: the complete 12-file patch SHA-256 f3777ed492dd8bbe743c1a96e139de7829f2166cc5d6f2e26ee87376bb34fbc7 received one independent read-only review with no findings and was committed unchanged as 6c7671047207762ae7f085c7eb4032211a96ec1e.
- Focused validation passed: referent-contract tests (18), hook tests (43), Copier template alignment, and Git whitespace checks. Authoritative scripts/lint-project-workflow.sh and tests/smoke.sh passed on independent copies of that exact patch with REQUIRE_COPIER=1. Host execution was required for Unix-socket tests; optional actionlint was unavailable.
- The three owner-identified local contracts now record ended_without_review with active false, exact prior contracts, and hashed structured evidence. Their acceptance checks correctly fail; pending reports no active records. The unrelated Plan 268 contract was already closed_advisory and was not modified.
- Main-session evidence and missing transcript/hook source declarations are retained under .agent-artifacts/referent-resolution-271/ in the original worktree. Original unaccepted product bytes remain backed up before final fast-forward integration.
- The baseline-only ledger check was invoked after the product commit and correctly rejected the advanced HEAD. Parent acceptance separately verified the ledger remains active, the commit is exactly one descendant of its baseline, its complete patch equals the independently reviewed patch, and the worktree is clean; no ledger or review budget was reset.
