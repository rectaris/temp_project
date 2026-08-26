# Reconstruct the coupled capability lineage

status: in_progress
primary_invariant: one plan-only transaction archives exact stopped Plans 200 and 201 and creates separately mapped acceptance successors without changing product bytes, reserved shell-plan identities, committed rejected-candidate evidence, or any unaffected active predecessor edge
reserved_plan_ids:
  - 211
  - 212
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - docs/plan/
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - scripts/restructure-plan.py
  - docs/plan/backlog/197-freeze-bounded-shell-structure-parser.md
  - docs/plan/backlog/198-integrate-bounded-copier-fixture-validator.md
  - docs/plan/active/200-enable-coupled-lineage-reconstruction.md
  - docs/plan/active/201-reconstruct-shell-parser-lineage.md
  - docs/plan/checked/2026/08/16-31/206-enforce-per-source-integration-coverage.md
  - docs/plan/replanned/2026/08/16-31/207-preserve-canonical-lifecycle-bytes.md
  - docs/plan/replanned/2026/08/16-31/208-bind-journal-replacement-identity.md
  - docs/plan/checked/2026/08/16-31/209-enable-direct-active-source-reconstruction.md
  - docs/plan/checked/2026/08/16-31/213-reconstruct-stopped-lifecycle-chain.md
  - docs/plan/checked/2026/08/16-31/215-enforce-canonical-lifecycle-verification.md
  - docs/plan/checked/2026/08/16-31/216-bind-journal-replacement-identity.md
  - docs/plan/checked/2026/08/16-31/199-admit-decomposed-shell-validation.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-root-agent-policy.py
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-root-agent-policy.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Atomically archive stopped Plans 200 and 201 and create separately mapped Plans 211 and 212 without changing source acceptance, the active predecessor graph, reserved Plans 202 through 205, or committed rejected-candidate blobs.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:dc406d3c0fa0ac0755912a904d97a8849a5efbbc13dcebd86e0cab48b56b3b89","stage":"focused","witness":"python3 scripts/restructure-plan.py --verify"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/216-bind-journal-replacement-identity.md
integration_gates:
  - execute only after Plans 206, 209, 215, and 216 are checked and their exact checked archives are bound
  - require a clean worktree and index at a HEAD descending from checkpoint commit 96f6645c84d5e1c4b043ac938df51d5d08e736d8
  - keep the blobs for scripts/project_workflow/copier_fixture.py and tests/test-copier-fixture.py byte-identical to commit 3ff2309dc85b4ebbb31904acae1949e12654fa88 and never use them as acceptance authority
  - leave Plans 197, 198, 185, 186, 166, and every unrelated active plan byte-identical
  - Plan 211 remains deferred until this plan is checked and its exact checked archive replaces the active predecessor
  - Plan 212 remains deferred until Plan 211 is checked and its exact checked archive replaces the active predecessor
checked_summary_ja: Plans 200/201を別々のacceptance successorへ単一transactionで再構築する。

## Decisions

- The coupled capability lineage transition means the plan-only transaction that archives Plans 200 and 201 together and creates their separately mapped successors after all prerequisite fixes are checked.
- Before Plan 213 completes, replace this plan's active Plan 213 predecessor with active Plan 216 and replace the Plan 207/208 context paths with their exact replanned archives plus active Plans 215 and 216.
- Use ordered direct active sources Plan 200 then Plan 201; Plan 201 must retain a direct or transitive predecessor path to Plan 200 in the bound original bytes.
- Preserve Plan 200's existing `parent_remediation_budget_exhausted` stop reason and derive Plan 201's stopped bytes with `spec_drift`.
- Create `docs/plan/active/211-verify-coupled-lineage-acceptance.md` as the sole integration successor for source Plan 200.
- Plan 211 must copy Plan 200's exact acceptance text and digest, retain the unchanged authoritative validation suite, own the five coupled-reconstruction implementation and policy paths, and start `deferred` behind active Plan 210.
- Create `docs/plan/active/212-reconstruct-shell-parser-lineage.md` as the sole integration successor for source Plan 201.
- Plan 212 must copy Plan 201's exact acceptance text and digest, retain its valid executable decomposition and reserved Plan IDs 202 through 205, replace the predecessor requirement from checked Plan 200 to checked Plan 211, and start `deferred` behind active Plan 211.
- Replace Plan 201's stale dirty or untracked candidate assertions with an exact invariant that the two blobs committed by `3ff2309dc85b4ebbb31904acae1949e12654fa88` remain byte-identical, non-authoritative evidence.
- Use no created prerequisite plans, no live dependent rebindings, and no product-path preservation entries in this clean transaction.
- Map every Plan 200 acceptance digest only to Plan 211 with `integration_source_ids` containing `200`; map every Plan 201 acceptance digest only to Plan 212 with `integration_source_ids` containing `201`.
- Archive both source plans in the current replanned partition under one schema-3 contract named for source Plan 200 and append both exact rows to the replanned index.
- After this plan is checked, perform a separate activation record that replaces Plan 211's active Plan 210 predecessor with this plan's exact checked archive and changes Plan 211 to `in_progress`.
- After Plan 211 is checked, replace Plan 212's active predecessor with Plan 211's exact checked archive and activate Plan 212.
- Use bounded parent execution and fresh independent review because this plan changes active lineage and durable contract state.

## Tasks

- [ ] Verify the clean checkpoint ancestry, checked Plans 206, 209, 213, 215, and 216, exact replanned archives for Plans 207 and 208, exact source bytes, exact source acceptance, current active index, and committed rejected-candidate blobs.
- [ ] Build one schema-3 specification with ordered direct active sources Plans 200 and 201 and separately mapped successors Plans 211 and 212.
- [ ] Execute the transaction and verify both source archives, the shared contract, both successor manifests, both indexes, and the complete unaffected active graph.
- [ ] Confirm Plan 211 retains Plan 200 validation authority and Plan 212 retains Plan 201 shell plan IDs 202 through 205 without stale dirty-path claims.
- [ ] Complete focused validation and independent review of the plan-only diff with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive and commit Plan 210, then activate Plan 211 through a separate exact activation record.

## Validation Notes

- This plan creates no product implementation and does not run Plan 200 authoritative validation.
- Plan 211, not the prerequisite remediation plans or Plan 210, owns final acceptance of the original Plan 200 requirement.
- Plan 212, not Plan 210, owns the original Plan 201 shell-lineage reconstruction requirement.
- Plan 210 must not activate directly from checked Plan 209; Plan 213 and both acceptance successors created from Plans 207 and 208 are mandatory predecessors.
