# Enforce canonical lifecycle verification

status: in_progress
implementation_tier: 2
primary_invariant: lifecycle verification removes only syntactically parsed lifecycle field bytes, preserves every other byte, and admits replan_required only with canonical stopped metadata that every durable contract reproduces exactly
replan_sources:
  - docs/plan/active/207-preserve-canonical-lifecycle-bytes.md
  - docs/plan/active/208-bind-journal-replacement-identity.md
replan_contract: docs/plan/replanned/contracts/207-preserve-canonical-lifecycle-bytes.json
integration_gates:
  - combined successors must satisfy every source acceptance item
  - activate only after Plan 213 is checked and its exact checked archive replaces both the active predecessor and the active context reference
  - implement fresh from the checked Plan 209 commit and the archived Plan 207 requirement baseline
  - keep root and generated restructure commands byte-identical
  - preserve every existing schema, acceptance, overlay, prerequisite, journal, and historical-byte check
  - Plan 216 remains deferred until this plan is checked and its exact checked archive replaces its active predecessor
successor_plans:
  - docs/plan/active/215-enforce-canonical-lifecycle-verification.md
  - docs/plan/active/216-bind-journal-replacement-identity.md
inherited_acceptance_digests:
  - sha256:d6486ed4fe2f32f744fd53df526284ab3151fd6bb9fed42e2318cf89855de837
integration_source_ids:
  - 207
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/206-enforce-per-source-integration-coverage.md
  - docs/plan/checked/2026/08/16-31/209-enable-direct-active-source-reconstruction.md
  - docs/plan/replanned/2026/08/16-31/207-preserve-canonical-lifecycle-bytes.md
  - docs/plan/checked/2026/08/16-31/213-reconstruct-stopped-lifecycle-chain.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 -m py_compile scripts/restructure-plan.py template/.project-agent-workflow/scripts/restructure-plan.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Compare lifecycle evolution by removing only parsed lifecycle field bytes and reject every noncanonical replan_required state, including legacy nested-replan compatibility paths.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:d6486ed4fe2f32f744fd53df526284ab3151fd6bb9fed42e2318cf89855de837","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/213-reconstruct-stopped-lifecycle-chain.md
checked_summary_ja: lifecycle field以外のbyteを保持し、canonical stopped metadataをlive manifestとdurable contractの両方で必須化する。

## Decisions

- Canonical lifecycle projection means a lifecycle comparison that removes only parsed lifecycle field bytes, preserves every other byte, and accepts `replan_required` only with canonical stopped metadata.
- Replace range removal that extends to the next top-level field with a projection over the exact scalar line or the exact list field header and its parsed list-item lines.
- Treat comments, blank-line placement, unknown instructions, and every unparsed byte between lifecycle fields as protected bytes.
- Apply one canonical stopped-state validator before schema-1 preflight, before every historical source verification path, and before any legacy nested-replan compatibility decision.
- A canonical stopped plan has bounded `replan_reason_codes` and no `completion_deferred_reason`; the compatibility route may relax lineage shape only, never stopped metadata.
- Require every durable schema-1, schema-2, and schema-3 contract `reason_codes` list to be bounded and to equal its canonical source manifest `replan_reason_codes` exactly.
- Reject a missing, duplicate, unknown, or non-string reason value with a bounded lifecycle error instead of an uncaught type error.
- Apply the same bounded checks to nested historical contracts and to schema-3 prerequisite plans.
- Preserve allowed status transitions, task checkbox completion, and append-only final Validation Notes behavior.
- Implement fresh from the checked Plan 209 commit and the archived Plan 207 requirement baseline; the locally stored rejected Plan 207 candidate is advisory evidence only and grants no implementation, validation, staging, commit, or acceptance authority.
- Use bounded parent implementation and fresh independent review because this plan protects plan identity and historical compatibility.

## Tasks

- [ ] Implement exact lifecycle-field projection over the scalar line or list field without swallowing intervening bytes.
- [ ] Centralize canonical stopped-state validation and invoke it before schema-1 preflight, every historical source verification path, and every legacy compatibility exemption.
- [ ] Bind durable contract reason codes to the canonical source manifest for schema-1, schema-2, schema-3, nested historical contracts, and prerequisite plans.
- [ ] Reject missing, duplicate, unknown, and non-string reason values with bounded lifecycle errors.
- [ ] Add comment-between-fields, blank-line-placement, unknown-instruction, and stale-deferred-reason tests.
- [ ] Add missing, duplicate, unknown, and non-string reason-value tests plus schema-1, schema-2, schema-3, and nested historical verification tests.
- [ ] Align the root and generated Plan Workflow policy with the enforced byte and stopped-state rules.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 216 with this plan's exact checked archive as predecessor.

## Validation Notes

- This successor owns final acceptance of the original Plan 207 requirement.
- It must not broaden the legacy compatibility route or reinterpret historical contract bytes.
- The rejected Plan 207 candidate is local advisory evidence and may be absent in another session without blocking implementation.
