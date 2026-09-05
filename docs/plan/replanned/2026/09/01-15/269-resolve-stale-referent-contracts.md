# Resolve stale referent contracts without claiming unperformed review

status: replanned
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
review_class: B
human_design_required: no
human_approval_status: approved
plan_purpose: implementation
task_types:
  - template_workflow
  - planning_docs
  - security
  - referent_first
feasibility_evidence:
  - {"kind": "reproduced_defect", "evidence": "The 265 and 266 contract checks report missing backlog targets; plan-243 reports missing required review; the hook repeats all three active records."}
  - {"kind": "existing_mechanism", "evidence": "referent-contract.py already seals target identity, hashes drafts, validates transitions, and closes advisory records; complete-plan.sh and finalize-active-plan.sh provide bounded reminder insertion points."}
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
primary_invariant: preserve the complete coupled source acceptance baseline
replan_sources:
  - docs/plan/active/269-resolve-stale-referent-contracts.md
replan_contract: docs/plan/replanned/contracts/269-complete-referent-contract-resolution.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/271-complete-referent-contract-resolution.md
inherited_acceptance_digests:
  - sha256:2cb05261df94708d4babddb2029c366cb71ab24978c8d66b31b0d54bddb22b35
checked_summary_ja: 用語の記録に下書きの参照先変更と適用終了の手続きを追加し、未完了の記録に必要な対応を通知する。

## Decisions

- Preserve sealed source and target identity. Record identical-draft relocation separately; reject changed bytes.
- Record ended applicability separately from acceptance with a preserved prior contract and a hashed evidence report. This operation does not shelve a plan or waive a requirement.
- Keep reminders read-only and advisory. Check exact source and target references during completion and archival, and keep session-wide reminders for restoration.
- Resolve only the three owner-identified local records after reviewing their history. Preserve the independent Plan 268 record.

## Tasks

- [ ] Implement and mirror the lifecycle commands, diagnostics, and policy.
- [ ] Add regression coverage for preserved evidence, refused false acceptance, and lifecycle reminders.
- [ ] Review and validate the change, then reconcile the three local records with evidence.
- [ ] Archive this plan and restore the pre-existing active plan.

## Validation Notes

- Focused validation passed: referent contracts 17 tests; hooks 43 tests; Copier template alignment; git diff --check.
- Initial independent review found three Medium issues; one bounded parent correction addressed evidence shape and retention, relocation history, and the mapped hook witness.
- The final independent rereview still found two Medium issues: filtered reminders omit the effective relocated path after reopen, and relocation permits a non-regular replacement at the previous target. The parent accepts both findings.
- The two-review budget is exhausted. The external ledger /tmp/referent-269-state.json is stopped at descope_pending with parent_remediation_budget_exhausted. No further correction, successor creation, authoritative validation, local-record ending, completion, or archive is authorized without an owner continuation decision.
- The plan remains live at replan_required. Review receipts, original contract backups, and history evidence are preserved under .agent-artifacts/referent-resolution-269/. The reviewed implementation patch is preserved at /tmp/referent-269-final.patch and remains uncommitted in the declared write scope.
- Authoritative lint and smoke were not started; the 243, 265, and 266 local records remain unchanged. Plan 268 remains deferred while the owner decides how to continue this repair.
