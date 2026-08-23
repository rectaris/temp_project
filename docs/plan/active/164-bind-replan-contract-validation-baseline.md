# Bind replan contracts to authoritative validation baselines

status: deferred
completion_deferred_reason: Plan 189 must be checked and its exact checked archive path must replace the active predecessor before implementation.
primary_invariant: every newly restructured integration successor carries immutable contract evidence of its complete authoritative validation command sequence and witness schema
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
preservation_scope:
  - scripts/check-copier-template.py
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/189-enforce-active-plan-predecessors.md
  - docs/plan/replanned/2026/08/16-31/130-map-acceptance-validation-witnesses.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/active/189-enforce-active-plan-predecessors.md
replan_source: docs/plan/active/130-map-acceptance-validation-witnesses.md
replan_contract: docs/plan/replanned/contracts/130-map-acceptance-validation-witnesses.json
integration_gates:
  - Plan 189 must be checked and its exact checked archive path must replace this active predecessor before implementation
  - preserve scripts/check-copier-template.py and tests/copier-update.sh without editing, staging, or committing them
  - Plan 105 must admit the reconstructed command set after this plan is checked; Plan 190 then creates the current companion baseline and Plan 165 consumes only that accepted evidence
successor_plans:
  - docs/plan/active/163-capture-validation-witness-migration-provenance.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - docs/plan/active/165-enforce-validation-witness-maps.md
  - docs/plan/active/166-unify-copier-update-source-inventory.md
  - docs/plan/active/167-integrate-validation-witness-enforcement.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: 再計画契約へ最終検証command列とwitness schemaを改変不能な証拠として保存する。

## Decisions

- contracted-validation-baseline means the authoritative validation sequence preserved in one immutable replan-contract successor record.
- Introduce a backward-compatible replan-contract schema revision that preserves schema-1 history and records the normalized authoritative validation sequence and its digest for every new successor.
- Do not rewrite existing schema-1 contracts; Plan 190 will bind their exact digests to one separate current-lineage companion baseline.
- Define the companion as `docs/plan/replanned/baselines/live-validation-successors-v1.json` with `schema_version: 1` and one source-ordered record per contract containing its path and SHA-256 digest plus each live successor path, source-ordered acceptance digests, normalized authoritative validation sequence and digest, witness schema, and witness-map digest.
- Make `restructure-plan.py --verify` reject extra, duplicate, reordered, stale, or digest-mismatched companion records. Before publication, permit absence only while exact Plan 190 is the sole unfinished publisher in `deferred` or `in_progress`, no consumer context references the companion path, and no publication event is recorded; this covers the checked Plan 164 and Plan 105 interval through Plan 190 activation. After Plan 190 publishes, validates, and commits the companion, treat that publication as terminal and permanently reject missing or stale evidence.
- Require every new in-progress integration successor to declare schema-1 witness coverage before the restructuring transaction writes any destination.
- Reject validation removal, reordering, duplication, unsupported commands, digest mismatch, and contract/live identity mismatch.
- Keep root and generated restructuring scripts byte-aligned.

## Tasks

- [ ] Extend the contract schema and verifier without rewriting historical schema-1 contracts.
- [ ] Implement the exact companion schema and the bounded pre-publication absence transition that Plan 190 will consume without changing verifier code.
- [ ] Validate every new successor witness map and authoritative command baseline before atomic replacement.
- [ ] Add positive, compatibility, tampering, ordering, and rollback tests.
- [ ] Complete focused validation and independent review, archive, commit, and activate Plan 105 with this exact checked predecessor.

## Validation Notes

- The existing contract already stores successor content, but an explicit versioned validation projection is required for stable runtime consumption and tamper checks.
- `successor_plans` preserves the immutable Plan 130 lineage; this schema producer no longer waits for Plan 179 because Plan 190, not this plan, binds the current live lineage.
