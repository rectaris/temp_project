# Keep one plan-id reservation per authoring target so rechecking a revised input never skips identifiers

status: backlog
primary_invariant: A task worktree holds at most one unwritten plan-id reservation per target lifecycle and slug, rechecking a revised input for that target keeps its identifier, and publishing the worktree leaves none of its unwritten reservations behind.
task_types:
  - task_worktrees
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"On 2026-09-26 revising four authoring inputs in one direct-task worktree and rerunning create-root-plan.py check reserved 411 to 414 for the first digests and 415 to 418 for the revised ones; 411 to 414 stayed reserved and unwritten after publication until their 24-hour lease.","kind":"reproduced_defect"}
  - {"evidence":"worktree_guard.reserve_plan_id matches an existing unwritten entry by input_digest and worktree_path only, although every entry already records relative_path derived from lifecycle and slug, and manage-plan-worktrees.py publish calls no reservation cleanup.","kind":"existing_mechanism"}
  - {"evidence":"tests/validation_tools/worktrees.py PlanIdentifierReservationTest and tests/validation_tools/plan_authoring.py PlanAuthoringInRepositoryTest already cover allocation, recheck, publication consumption and expiry through tests/test-validation-tools.py.","kind":"existing_mechanism"}
completion_conditions:
  - Checking a revised authoring input for the same lifecycle and slug in the same worktree replaces the digest of that worktree's unwritten reservation and keeps its identifier, so repeated checks of revised drafts allocate no new identifier.
  - Different slugs in one worktree, the same slug in two linked worktrees, and a written reservation still receive distinct identifiers; after check A then check B, writing A is refused with no file or index change and writing B uses the original identifier.
  - Publishing or retiring a task worktree removes that worktree's unwritten reservations under the lifecycle lock, leaves other worktrees' entries unchanged, and a later allocation can reuse the freed identifiers.
  - Both worktree_guard.py copies and both manage-plan-worktrees.py copies stay byte-identical, and both SPEC_PLAN_WORKFLOW.md copies describe per-target reuse and publication cleanup.
completion_witness_map:
  - {"condition_sha256":"sha256:1a62aa918aaa9e8c29d582e0256f03374936f234616b48bc3450e56897935698","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:06715e4605583d935756995625f199e443ebda5e89838ac1b33b68d02646fb41","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:ecba9b1a8438316f7d4a897c1c99e74cb5e3f8f30618d45315fb2b0c049fd8cd","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:1b8ed1afa39923a8615d8847f5adaf4c5cadc4977ef39dc23dcf5f56da39ae58","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/project_workflow/worktree_guard.py
  - template/.project-agent-workflow/scripts/worktree_guard.py
  - scripts/manage-plan-worktrees.py
  - template/.project-agent-workflow/scripts/manage-plan-worktrees.py
  - tests/validation_tools/worktrees.py
  - tests/validation_tools/plan_authoring.py
  - scripts/project_workflow/plan_authoring.py
  - template/.project-agent-workflow/scripts/plan_authoring.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Revising and rechecking a plan draft keeps its reserved identifier, and publishing an authoring task releases every reservation it did not use.
  - Two linked worktrees still never receive the same plan identifier, in the root repository and in generated projects.
  - The root and generated copies of the reservation, authoring and worktree-manager code stay byte-identical and their specifications describe the same reservation lifecycle.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:db8f4bd7c2814c5916f72dff21e98d71377a6113321b7078cdf0e7b0cdb89f97","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:bf88ec6d425f51e50a4f0beb5e000a9e816a65341a9b7148e4761185bb3c8f88","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:b180eb52f4764fc10e88ae977efa209d61c86a4c91450d149f704cd119e90d86","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 作成するプランの行き先ごとに予約を一つに保ち、入力を直して確認し直してもプラン番号が飛ばないようにする。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct.
- Key reuse by worktree and target relative_path. check replaces the digest of the worktree's unwritten reservation for the same lifecycle and slug and keeps its identifier; write only verifies and consumes an existing reservation whose digest equals its input under the lifecycle lock and never replaces a digest, so a superseded draft cannot be written.
- Remove, not re-lease, a worktree's unwritten reservations when manage-plan-worktrees.py publishes or retires that worktree, under the shared lifecycle lock. Written reservations keep their existing consumption through the published state.
- Split plan_authoring.py so check calls the replacing reservation path and write calls a verify-and-consume path; every other allocator keeps calling reserve_plan_id.
- Leave the 411 to 414 leases to expire; this plan adds no manual ledger repair.

## Tasks

- [ ] Record the unchanged reservation test results before product edits.
- [ ] Implement per-target reuse in reserve_plan_id and unwritten-reservation removal in publish and retire, in both copies.
- [ ] Add cases for a revised recheck, distinct slugs, two worktrees, written entries, publication cleanup and identifier reuse after cleanup.
- [ ] Describe the reservation lifecycle in both SPEC_PLAN_WORKFLOW.md copies.
- [ ] Obtain independent review through a fresh read-only reviewer, resolve findings within the existing budget, run the focused checks, then the authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Owner instruction on 2026-09-26 asked to define these environment and workflow changes as rules and to create plans for them: create each task worktree's .venv with uv, let Bubblewrap run the .venv Python, replace the retired gpt-5.3-codex-spark with gpt-5.6-terra medium, fix the check-time plan-id reservations, and approve continuations up to the fourth review once at plan start (option A).
