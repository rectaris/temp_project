# Maintain the companion baseline inside the reconstruction transaction

status: in_progress
implementation_tier: 2
primary_invariant: a reconstruction transaction that archives a live schema-1 contract successor publishes the exact derived live validation successor companion records in the same all-or-nothing transaction, and changes no record or successor it does not archive
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: high
write_scope:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/190-migrate-live-plan-contracts.md
  - docs/plan/checked/2026/08/16-31/225-repair-live-successor-rebind-baseline.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Maintain the live validation successor companion baseline inside the reconstruction transaction so archiving a schema-1 contract successor keeps the derived and published records identical without editing any committed contract or archive.
  - Reject a companion projection that removes, reorders, or alters any record or successor the transaction does not archive, and keep the transaction fail-closed when the published baseline already disagrees with the derived records.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:023a2506800bce585adaea943ae69ed1d011573cac6f8e788c450dd0863f0a49","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:67668adf08e0109d3193e6d3762b37d6496dd45425da37e3e0563da4c8d5155d","stage":"focused","witness":"python3 scripts/restructure-plan.py --verify"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/225-repair-live-successor-rebind-baseline.md
integration_gates:
  - do not edit any committed contract under docs/plan/replanned/contracts/ or any archive under docs/plan/checked/ or docs/plan/replanned/
  - the Plan 185 restructuring may start only after this plan is checked and repository lineage verification still succeeds
checked_summary_ja: reconstruction取引がcompanion baselineを同一取引内で正しく更新し、archive対象以外を変更しないことを保証する。

## Decisions

- `docs/plan/replanned/baselines/live-validation-successors-v1.json` records the live successors of every schema-1 contract that declares `validation_witness_schema: 1`. `verify_companion_baseline` compares the published records against records derived from the current repository, and `verify_repository_contracts` runs that comparison on the prospective repository state as well.
- Archiving a live schema-1 contract successor removes it from the derived records, but no restructuring operation writes the companion baseline. Every reconstruction of such a successor therefore fails in prospective verification with `live validation successor companion baseline mismatch`, so the stopped Plan 185 cannot be restructured at all.
- The defect predates this plan. Plan 190 published the baseline and is already checked, so `companion_absence_allowed` no longer applies and the file cannot be left behind.
- Repair by projecting the companion baseline inside the transaction instead of relaxing the check. The transaction already knows exactly which plan paths it archives, so the projection removes only those successors, removes a record only when it keeps no live successor, and preserves every other record, successor, and field byte for byte.
- Publish the projection as one ordinary transaction write with its own expected original bytes, so it is covered by the same journal, rollback, roll-forward, and prospective verification as every other write.
- Keep the transaction fail-closed. If the published baseline already disagrees with the derived records before the transaction, the existing verification still rejects, because the projection is derived from the published bytes and never repairs an unrelated disagreement.
- Mirror both the policy text and the tool into `template/` in the same change, because root and template must stay in the same state.
- Use bounded parent implementation with independent review. Both `implementation_risk` and `implementation_ambiguity` are high, so the writable sandboxed runner is refused.

## Tasks

- [ ] Reproduce the prospective `live validation successor companion baseline mismatch` for a reconstruction that archives a live schema-1 contract successor.
- [ ] Extend `docs/agent/SPEC_PLAN_WORKFLOW.md` with the in-transaction companion baseline projection and its bounded change rule.
- [ ] Implement the projection in `scripts/restructure-plan.py` and publish it as one journaled transaction write.
- [ ] Extend `tests/test-plan-restructure.py` with coverage for the archived successor, an untouched record, an emptied record, and a pre-existing published disagreement.
- [ ] Mirror the policy and tool changes into `template/` and confirm the alignment checks pass.
- [ ] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Pending. Reproduced at HEAD `fac6aa6` as `plan restructuring failed: prospective repository verification failed: plan restructuring failed: live validation successor companion baseline mismatch` for both a schema-1 and a schema-3 reconstruction of `docs/plan/active/185-complete-bounded-copier-fixture-runtime.md`.
