# Enforce plan id reservations

status: deferred
completion_deferred_reason: Plan 213 must be checked and replace the active predecessor, and Plans 215 and 216 must be checked, before this plan may write the shared restructure tool, the shared specification, or plan files.
implementation_tier: 2
primary_invariant: a plan id that a live plan reserves is never assigned to any other plan
task_types:
  - planning_docs
  - template_workflow
  - referent_first
review_class: C
human_design_required: yes
human_approval_status: pending
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/active/201-reconstruct-shell-parser-lineage.md
  - docs/plan/active/210-reconstruct-coupled-capability-lineage.md
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/plan/active/213-reconstruct-stopped-lifecycle-chain.md
  - docs/plan/plan.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
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
  - Reject a plan id reserved by a live plan for every other plan at repository verification and at restructuring plan creation, and record the existing Plan 201 and Plan 210 reservations without changing any other plan's acceptance, acceptance digest, validation authority, or write scope.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:6c504e801d619ed94566699d8c33c4d33d5908e666cd50617844787d24c2a021","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/active/213-reconstruct-stopped-lifecycle-chain.md
integration_gates:
  - activate only after Plan 213 is checked and its exact checked archive replaces both the active predecessor and the active context reference
  - execute only after Plans 215 and 216 are checked, because both own this plan's restructure tool and specification write scope
  - keep root and generated restructure commands byte-identical
  - record reservations only for plans that are still live when this plan executes
  - create no plan file and consume no reserved plan id
  - preserve every existing schema, acceptance, lifecycle, overlay, and historical-byte check
checked_summary_ja: 予約済みplan idを他プランが消費できないよう、リポジトリ検証と作成時検査の両方で拒否する。

## Decisions

- Plan id reservation means one three-digit plan id that a live plan declares it will create later and that no plan file uses yet.
- A plan is live when its id appears in `docs/plan/plan.md` or when its file resides in `docs/plan/backlog/`.
- Add the optional manifest list field `reserved_plan_ids`; each entry is exactly three digits, entries are unique and ascending, and no entry equals the declaring plan's own id.
- Add the optional manifest scalar field `reserved_by`; its value is the three-digit id of the plan that reserved this plan's id.
- Reject a repository state in which two live plans reserve the same id.
- Reject a repository state in which any plan file uses an id reserved by a live plan unless that file declares `reserved_by` with the reserving plan's id.
- Reject a restructuring transaction that creates a plan id reserved by a live plan unless the created manifest declares the matching `reserved_by`.
- Keep the existing rejection of a created plan id that already exists unchanged, and keep a manifest without either field valid.
- Treat `reserved_by` as historical lineage text once the named plan is no longer live, so an archived reserving plan releases its ids automatically.
- Enforce every reservation rule inside `scripts/restructure-plan.py` at repository verification and at schema-1 and schema-3 plan creation, then mirror the root file into the generated template byte-identically.
- Execute this plan only after Plans 215 and 216 are checked, because those successors own the same restructure tool, test, and specification paths.
- Record `reserved_plan_ids` 202, 203, 204, and 205 in active Plan 201, and 211 and 212 in active Plan 210.
- Record no reservation for Plan 213, whose reserved ids are already consumed when this plan executes.
- Keep reservation-aware id allocation in `template/.project-agent-workflow/scripts/planlib.py` out of scope, because fail-closed verification already rejects the incident and allocation ergonomics is a separate invariant.
- Change no other plan's acceptance text, acceptance digest, validation command, write scope, or lifecycle state.

## Tasks

- [ ] Verify checked Plans 213, 215, and 216, the current live plan set, the current reserved ids, and a clean worktree.
- [ ] Document `reserved_plan_ids` and `reserved_by` semantics in the root plan workflow specification and mirror the generated specification.
- [ ] Implement manifest parsing and the repository verification rejections in `scripts/restructure-plan.py`.
- [ ] Implement the created-plan-id reservation rejection for schema-1 and schema-3 transactions.
- [ ] Mirror `scripts/restructure-plan.py` into the generated template byte-identically.
- [ ] Add positive and negative behavior tests to `tests/test-plan-restructure.py` for every new rejection, for legitimate consumption, and for a historical manifest carrying neither field.
- [ ] Record the existing Plan 201 and Plan 210 reservations.
- [ ] Complete focused validation and independent review of the diff with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, then archive and commit this plan.

## Validation Notes

- This plan changes no product runtime behavior outside plan lifecycle verification.
- The decision audit for this plan is stored locally at `.agent-artifacts/decision-audits/20260826-plan-id-reservation.md` and is not a durable repository dependency.
- The motivating defect is recorded in commit d058559, which shifted Plan 213's reserved successor ids from 214 and 215 to 215 and 216 after id 214 was consumed by checked Plan 214.
- Plan 213 consumes ids 215 and 216 before this plan executes, so this plan closes the remaining exposure of ids 202 through 205 and 211 and 212.
