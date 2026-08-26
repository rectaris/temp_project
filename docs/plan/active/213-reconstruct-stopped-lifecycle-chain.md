# Reconstruct the stopped lifecycle chain

status: in_progress
primary_invariant: one plan-only direct-active schema-3 transaction archives exact stopped Plan 207 and dependent Plan 208, creates one unchanged-acceptance successor for each source, and leaves product bytes and unrelated active-plan bytes unchanged
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
  - docs/plan/active/207-preserve-canonical-lifecycle-bytes.md
  - docs/plan/active/208-bind-journal-replacement-identity.md
  - docs/plan/checked/2026/08/16-31/209-enable-direct-active-source-reconstruction.md
  - docs/plan/active/210-reconstruct-coupled-capability-lineage.md
  - docs/plan/checked/2026/08/16-31/206-enforce-per-source-integration-coverage.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-root-agent-policy.py
  - git diff --check
validation:
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-root-agent-policy.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - After direct-active source reconstruction is checked, atomically archive exact stopped Plans 207 and 208 and create separately mapped Plans 215 and 216 without changing either source acceptance, unrelated active-plan bytes, or product files.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:6975b08797db1f7e209a794b9bc6071af1fb96586d225e593ad1bf15dd6a118c","stage":"focused","witness":"python3 scripts/restructure-plan.py --verify"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/209-enable-direct-active-source-reconstruction.md
integration_gates:
  - execute only after Plan 209 is checked and its exact checked archive replaces both the active predecessor and active context reference
  - require a clean worktree and index after the rejected Plan 207 candidate is retained only as local advisory evidence
  - preserve Plan 207 status and parent_remediation_budget_exhausted reason exactly
  - derive Plan 208 stopped bytes only through the checked direct-active lifecycle transformation with reason spec_drift
  - map the complete ordered Plan 207 acceptance only to Plan 215 and the complete ordered Plan 208 acceptance only to Plan 216
  - keep root and generated restructure commands byte-identical
  - create no product files, no preservation entries, no prerequisite plans, and no rebind overlay records
  - before this plan completes, bind Plan 210 to active Plan 216 and replace its Plan 207/208 context with exact replanned archives and active successor paths
checked_summary_ja: 停止中のPlans 207/208を別々のacceptance successorへ単一transactionで再構築する。

## Decisions

- Stopped lifecycle chain reconstruction means the plan-only transaction that archives exact Plans 207 and 208 together after direct-active source reconstruction is checked and creates one unchanged-acceptance successor for each source.
- Use ordered direct active sources Plan 207 then Plan 208; Plan 208 must retain its exact direct predecessor path to Plan 207 in the bound original bytes.
- Preserve Plan 207's existing `parent_remediation_budget_exhausted` stop reason and derive Plan 208's stopped bytes with `spec_drift`.
- Create `docs/plan/active/215-enforce-canonical-lifecycle-verification.md` as the sole integration successor for source Plan 207.
- Canonical lifecycle verification successor means the sole Plan 207 acceptance successor that enforces exact parser-consumed lifecycle byte projection and canonical stopped metadata across live and historical contracts.
- Plan 215 must retain Plan 207's exact acceptance text, digest, authoritative validation suite, and five write-scope paths.
- Plan 215 must start `deferred` behind active Plan 213 and must be activated only after Plan 213 is checked.
- Plan 215 must implement fresh from the checked Plan 209 commit and the exact archived Plan 207 requirement baseline; the local rejected-candidate patch is advisory evidence only and grants no implementation, validation, staging, commit, or acceptance authority.
- Plan 215 must cover scalar and list byte projection, comments, blank-line placement, unknown instructions, stale deferred reasons, missing, duplicate, unknown, and non-string reason values, exact contract-to-manifest reason equality, schema-1/schema-2/schema-3 durable verification, nested historical verification, prerequisites, and legacy compatibility exemptions.
- Create `docs/plan/active/216-bind-journal-replacement-identity.md` as the sole integration successor for source Plan 208.
- Journal replacement identity successor means the sole Plan 208 acceptance successor that binds each journaled replacement to target mode and transaction-created file identity throughout recovery.
- Plan 216 must retain Plan 208's exact acceptance text, digest, authoritative validation suite, five write-scope paths, security boundary, and same-user threat-model limit.
- Plan 216 must start `deferred` behind active Plan 215.
- Use no created prerequisite plans, product-path preservation entries, or live dependent rebindings in the schema-3 transaction.
- Map every Plan 207 acceptance digest only to Plan 215 with `integration_source_ids` containing `207`; map every Plan 208 acceptance digest only to Plan 216 with `integration_source_ids` containing `208`.
- Archive both source plans in the current replanned partition under one schema-3 contract named for source Plan 207 and append both exact rows to the replanned index.
- After the transaction, update Plan 210 while Plan 213 still owns `docs/plan/`: replace its predecessor from active Plan 213 to active Plan 216; replace active Plan 209 with its exact checked archive; replace Plan 207 and Plan 208 with their exact replanned archives; add active Plans 213, 215, and 216 as context; and preserve Plan 210 acceptance and all unrelated bytes.
- After Plan 213 is checked, perform a separate lifecycle update that replaces Plan 215's active Plan 213 predecessor and context with the exact checked Plan 213 archive, changes Plan 215 to `in_progress`, and replaces Plan 210's active Plan 213 context with the same checked archive.
- After Plan 215 is checked, replace Plan 216's active Plan 215 predecessor and context with the exact checked Plan 215 archive, activate Plan 216, and replace Plan 210's active Plan 215 context with the same checked archive.
- After Plan 216 is checked, replace Plan 210's active Plan 216 predecessor and context with the exact checked Plan 216 archive and activate Plan 210.
- Use bounded parent execution and fresh independent review because this plan changes durable active-plan lineage.

## Tasks

- [ ] Verify checked Plan 209, exact active source bytes, source acceptance, source ordering, active index state, and a clean product worktree.
- [ ] Build one schema-3 direct-active specification with ordered sources Plans 207 and 208 and separately mapped successor Plans 215 and 216.
- [ ] Execute the transaction and verify both source archives, the shared contract, both successor manifests, both indexes, and every unaffected active predecessor edge.
- [ ] Update deferred Plan 210 to depend on active Plan 216 and to reference exact Plan 207/208 replanned archives plus active Plans 215 and 216.
- [ ] Confirm Plan 215 retains Plan 207 validation authority and Plan 216 retains Plan 208 recovery and threat-model boundaries.
- [ ] Complete focused validation and independent review of the plan-only diff with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive and commit Plan 213, then activate Plan 215 through a separate exact activation record.

## Validation Notes

- This plan creates no product implementation and does not run either source plan's authoritative validation.
- The rejected Plan 207 candidate is stored locally at `/home/rectaris/.copilot/session-state/b03dfa28-bd50-474b-aa5f-2acf4794258a/files/plan-207/unaccepted-candidate.patch` with SHA-256 `60a8d1fbb0765310dffa74675557764f4b0f38d55a33a8d69a2fd8f8fd34c0c6`.
- The local patch is not a durable repository dependency and may be absent in another session without blocking implementation.
- Plan 215 owns final acceptance of Plan 207, and Plan 216 owns final acceptance of Plan 208.
