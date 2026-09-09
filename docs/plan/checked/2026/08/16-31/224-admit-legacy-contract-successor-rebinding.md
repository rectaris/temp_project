# Admit rebinding for legacy-contract live successors

status: checked
implementation_tier: 2
primary_invariant: a live successor whose owning contract records no preservation baseline can carry one exact rebind or activation projection, while every contract that does record a preservation baseline keeps its unchanged contract-identity comparison
task_types:
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/211-verify-coupled-lineage-acceptance.md
  - docs/plan/replanned/contracts/183-build-bounded-copier-transition-fixture.json
  - docs/plan/replanned/contracts/130-map-acceptance-validation-witnesses.json
required_specs:
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
  - python3 scripts/check-root-agent-policy.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Permit one exact rebind or activation projection over a live successor whose owning contract records no preservation baseline, and keep the unchanged contract-identity comparison for every contract that records one.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:5870f706aa155ee1615158e82d5fa833377e46f433dc8366a98f0bd52c446d5a","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/211-verify-coupled-lineage-acceptance.md
checked_summary_ja: preservation基準を持たない旧contractのlive successorに対しても、正確なrebindとactivation projectionを一度だけ許可する。

## Decisions

- legacy_contract_live_successor means one live contract successor whose owning replan contract records no `preservation_scope` for that successor, so the repository holds no authoritative preservation baseline for it.
- The observed defect is exact: `verify_rebind_records` compares the first rebind record's original bytes against the owning contract's created bytes through `compare_contract_identity`, and that comparison includes `preservation_scope` even when the contract records no preservation baseline at all.
- Plans 166, 185, and 186 each gained one `preservation_scope` entry after creation under schema-1 contracts, so every rebind and every future activation rebind for them is rejected before any reference rule runs.
- Repair only the unfounded comparison: ignore `preservation_scope` in the first-record contract-identity comparison exactly when the owning contract records no preservation baseline for that successor.
- Keep every other rebind rule unchanged, including reference authorization, protected plan identity between the record's own before and after bytes, validation-authority transition, and the final lifecycle projection.
- Keep the root and generated `restructure-plan.py` byte-identical.
- Use bounded parent implementation and independent review because this path is validation-authority code.

## Tasks

- [x] Reproduce the rejection through a real coupled specification over Plans 197 and 198 with rebindings for Plans 185, 186, and 166.
- [x] Add the bounded `ignore_fields` parameter to `compare_contract_identity` and pass it only when the owning contract records no preservation baseline.
- [x] Mirror the exact change into the generated template script.
- [x] Add a regression test that rebinds a legacy-contract live successor whose live `preservation_scope` differs from its contract bytes, and keep a negative test that a contract-recorded preservation baseline still rejects drift.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, archive, and commit.

## Validation Notes

- This plan is the bounded independent repair prerequisite recorded while stopping the Plan 223 execution run; it copies no Plan 223 acceptance text and creates no replan contract.
- Plan 223 waits in the backlog because `status: deferred` is an invalid lifecycle transition for a schema-3 contract successor that is already `in_progress`.
- The repair changes no requirement, no safety condition, no external-effect authority, and no source acceptance.
- The defect was reproduced end to end: without the repair the coupled Plan 197 and 198 specification failed with `rebind baseline docs/plan/active/166-unify-copier-update-source-inventory.md/0 original content already drifted in: preservation_scope`, and both added tests fail against the unrepaired script.
- Focused validation passed `python3 tests/test-plan-restructure.py` with 142 tests, `python3 scripts/restructure-plan.py --verify`, and `git diff --check`.
- The authoritative suite passed once: `python3 tests/test-plan-restructure.py`, `python3 scripts/restructure-plan.py --verify`, `python3 scripts/check-root-agent-policy.py`, `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, and `git diff --check`.
- Independent review reported zero High and zero Medium findings and confirmed that `expected_preservation is None` holds exactly when the owning contract records no `preservation_scope`, that schema-3 successors and prerequisites can never reach the ignore branch, that `preservation_scope` stays outside `REBIND_FIELDS` and inside `manifest_identity_values`, and that both scripts stay byte-identical.
