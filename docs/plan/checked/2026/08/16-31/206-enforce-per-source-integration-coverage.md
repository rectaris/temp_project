# Enforce per-source integration coverage

status: checked
primary_invariant: every durable schema-3 source is accepted only when its one designated integration successor maps that source's complete ordered acceptance set
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
  - docs/plan/active/201-reconstruct-shell-parser-lineage.md
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
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 -m py_compile scripts/restructure-plan.py template/.project-agent-workflow/scripts/restructure-plan.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Require every durable schema-3 integration successor to map every acceptance item for each source it designates, preserving source order and rejecting aggregate-only coverage.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:3528df57ef599549f66efcf1bae357bb8a2324b7f81a7977b60546532b57d1a0","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/199-admit-decomposed-shell-validation.md
integration_gates:
  - use commit 96f6645c84d5e1c4b043ac938df51d5d08e736d8 as the exact unaccepted implementation baseline
  - do not reopen, complete, archive, or accept the stopped Plan 200 execution run
  - keep root and generated restructure commands byte-identical
  - keep the coupled reconstruction policy semantically aligned between root and generated specifications
  - Plan 207 remains deferred until this plan is checked and its exact checked archive replaces the active predecessor
checked_summary_ja: sourceごとのintegration successorが全acceptanceを保持するdurable verificationを確定する。

## Decisions

- Per-source integration coverage means that the one integration successor designated for a source maps every acceptance digest of that source in source order.
- Enforce this condition during specification validation and durable contract verification; aggregate coverage across several successors is insufficient.
- Keep the existing rule that each source has exactly one designated integration successor and one integration successor may cover several sources.
- Reject missing, duplicated, reordered, foreign, or partial acceptance mappings on a designated integration successor.
- Add a hold-out contract mutation in which non-integration successors collectively cover the missing digest while the designated integration successor remains partial.
- Preserve every schema-1, schema-2, rebind, activation, lifecycle, and recovery behavior outside this acceptance check.
- Use bounded parent implementation and fresh independent review because this plan changes durable acceptance authority.

## Tasks

- [x] Add exact per-source coverage checks to schema-3 construction and durable verification.
- [x] Add positive multi-source coverage and negative partial-integration, aggregate-only, reordered, duplicate, and foreign-digest tests.
- [x] Align the root and generated Plan Workflow policy with the enforced condition.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, archive, commit, and activate Plan 207 with this plan's exact checked archive as predecessor.

## Validation Notes

- The baseline commit is preservation evidence only; it does not make Plan 200 checked or accepted.
- This plan owns only the per-source integration coverage finding from the final Plan 200 rereview.
- Focused validation passed with `python3 tests/test-plan-restructure.py`, `python3 scripts/restructure-plan.py --verify`, and `git diff --check`.
- Independent review reported no unresolved High or Medium findings.
- The authoritative validation suite completed successfully once.
