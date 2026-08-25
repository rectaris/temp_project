# Preserve canonical lifecycle bytes

status: in_progress
primary_invariant: lifecycle verification removes only syntactically parsed lifecycle field bytes, preserves every other byte, and admits replan_required only with canonical stopped metadata
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
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/200-enable-coupled-lineage-reconstruction.md
  - docs/plan/checked/2026/08/16-31/206-enforce-per-source-integration-coverage.md
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
  - docs/plan/checked/2026/08/16-31/206-enforce-per-source-integration-coverage.md
integration_gates:
  - begin only from the exact checked Plan 206 archive and a clean worktree
  - preserve the Plan 206 acceptance check and all unrelated manifest and body bytes
  - keep root and generated restructure commands byte-identical
  - Plan 208 remains deferred until this plan is checked and its exact checked archive replaces the active predecessor
checked_summary_ja: lifecycle field以外のbyteを保持しcanonical stopped metadataを必須化する。

## Decisions

- Canonical lifecycle projection means a lifecycle comparison that removes only parsed lifecycle field bytes, preserves every other byte, and accepts `replan_required` only with canonical stopped metadata.
- Replace range removal that extends to the next top-level field with a projection over the exact scalar line or exact list field and its parsed list-item lines.
- Treat comments, blank-line placement, unknown instructions, and any unparsed bytes between lifecycle fields as protected bytes.
- Apply the same canonical stopped-state validator before schema-1 preflight, historical source verification, and any legacy nested-replan compatibility decision.
- A canonical stopped plan has bounded `replan_reason_codes` and no `completion_deferred_reason`; the compatibility route may relax lineage shape only, never stopped metadata.
- Preserve allowed status transitions, task checkbox completion, and append-only final Validation Notes behavior.
- Use bounded parent implementation and fresh independent review because this plan protects plan identity and historical compatibility.

## Tasks

- [ ] Implement exact lifecycle-field projection without swallowing intervening bytes.
- [ ] Centralize canonical stopped-state validation and invoke it before every compatibility exemption.
- [ ] Add comment-between-fields, unknown-instruction, stale-deferred-reason, missing-reason, duplicate-reason, schema-1, and historical nested-replan tests.
- [ ] Align the root and generated Plan Workflow policy with the enforced byte and stopped-state rules.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 208 with this plan's exact checked archive as predecessor.

## Validation Notes

- This plan owns both lifecycle findings because they are two violations of one canonical lifecycle projection invariant.
- It must not broaden the legacy compatibility route or reinterpret historical contract bytes.
