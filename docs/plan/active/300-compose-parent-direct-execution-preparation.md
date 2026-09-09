# Compose existing parent-direct execution preparation

status: in_progress
primary_invariant: One parent-direct preparation operation composes existing registry and ledger initialization, reports readiness only after exact bindings verify, and grants no implementation, review, continuation or publication authority.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The execution-state CLI exposes registry-init, continuation-registry-init and init. Existing read_state, read_reviewer_registry and read_continuation_registry validate their respective records; there is no general bootstrap-verification CLI.","kind":"existing_mechanism"}
  - {"evidence":"Plan 103 records omitted ledger initialization. The existing review-budget policy already specifies fresh epoch-zero setup, so composing functions needs no new schema.","kind":"existing_mechanism"}
  - {"evidence":"Existing state tests cover path safety, registry identity, replay, stopped state and legacy checkpoints. Reuse these validators and initialize the ledger last.","kind":"existing_mechanism"}
completion_conditions:
  - Fresh parent-direct epoch-zero preparation checks the selected committed active plan, baseline and all explicit external destinations before the first registry write, then composes existing reviewer and continuation registry initialization and ledger initialization.
  - Existing constructors and schemas bind both registries and required adversarial preflight; readiness requires read_state, read_reviewer_registry and read_continuation_registry to validate the resulting records and their exact cross-references.
  - Partial failure identifies created records, retains them without deletion or fabricated success, and refuses occupied destinations; existing, stopped, legacy and foreign state are never replaced.
  - Root and generated orchestration and skill instructions remain aligned and replace the three fresh-start setup calls with the composed operation.
completion_witness_map:
  - {"condition_sha256":"sha256:d73004529f306c01e00885f2809d8431c215db76b61e6484d9511a846f790fe6","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:6b1fb9e174bdd087dcef2f41dfa82c1730edc21754da83d91fc4663e69b0886d","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:56ce7c68dd7ec2b247fd5da23f44886f6f6e45606e7f0009260c28387768364d","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:ff8e9fd1242273a4091fabdf802ec003b4ce259b8c3e4fcbb2bd720af910fe95","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/plan/checked/2026/09/01-15/103-require-worktree-for-all-writes.md
  - docs/plan/checked/2026/09/01-15/286-install-same-plan-continuation-epochs.md
  - docs/plan/checked/2026/09/01-15/296-permit-one-or-two-review-continuation.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Fresh parent-direct epoch-zero preparation checks the selected committed active plan, baseline and all explicit external destinations before the first registry write, then composes existing reviewer and continuation registry initialization and ledger initialization.
  - Existing constructors and schemas bind both registries and required adversarial preflight; readiness requires read_state, read_reviewer_registry and read_continuation_registry to validate the resulting records and their exact cross-references.
  - Partial failure identifies created records, retains them without deletion or fabricated success, and refuses occupied destinations; existing, stopped, legacy and foreign state are never replaced.
  - Root and generated orchestration and skill instructions remain aligned and replace the three fresh-start setup calls with the composed operation.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:d73004529f306c01e00885f2809d8431c215db76b61e6484d9511a846f790fe6","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:6b1fb9e174bdd087dcef2f41dfa82c1730edc21754da83d91fc4663e69b0886d","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:56ce7c68dd7ec2b247fd5da23f44886f6f6e45606e7f0009260c28387768364d","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:ff8e9fd1242273a4091fabdf802ec003b4ce259b8c3e4fcbb2bd720af910fe95","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Start only after this backlog plan is selected for implementation and published as active; use its exact bound task worktree.
  - Use bounded parent implementation and independent read-only review. Keep existing correction and review limits, mandatory validation, Copier preservation and external-effect authority.
  - Use checked 286 and 296 behavior unchanged; this command cannot continue stopped runs or reset review counts.
  - If the skill-consolidation plan is also selected, implement it first to avoid overlapping edits to the sequential skill. This is scheduling, not immutable replan lineage.
  - Do not change worktree publication, generic completion gates, external authorization or live reviewer-session evidence.
checked_summary_ja: 親による実装の開始準備を一つにまとめ、台帳とレビュー登録の準備漏れを減らす。

## Decisions

- Add one fresh-start subcommand inside the existing execution-state CLI by composing current functions, not a second CLI or a new service.
- Limit it to fresh ungrouped parent-direct epoch-zero execution with explicit external paths and the exact committed active plan; worker, grouped, continuation and checkpoint paths stay unchanged.
- Require absent, nonoverlapping, safe destinations. Validate source and plan before creating registries; create and verify the ledger last.
- On partial failure, retain created existing-format records and name them; return nonzero without readiness. Never delete, imply rollback, overwrite occupied paths or silently retry.
- Keep registry lifecycle locking and replay checks; reject concurrent creators. This is not an atomic all-files transaction.
- Replace three setup calls with one. This reduces omission opportunities but does not claim to intercept unrestricted parent writes or satisfy later review and completion evidence.
- Add a bounded read-only preflight within this CLI for every destination, the active-plan committed bytes and source HEAD before any constructor writes; constructors repeat their own checks to handle races. Bound-worktree admission remains the existing parent prerequisite, not a new verification claim by this subcommand.

## Tasks

- [ ] Add fresh parent-direct setup tests and injected failures at each existing initialization boundary.
- [ ] Extract minimal shared preflight helpers and compose existing registry/state initialization functions.
- [ ] Test that any initially occupied or unsafe later destination fails before the first record is created; test races separately as retained partial failure. Verify resulting records with the three named readers and explicit identity comparisons.
- [ ] Test path identity, nonoverlap, concurrent creation, retained partial state and refusal of occupied or stopped state.
- [ ] Update aligned orchestration and existing sequential skill guidance for fresh parent-direct setup only.
- [ ] Run focused tests, independent review and one authoritative suite for the reviewed patch.

## Validation Notes

- Planning baseline: b3e300888412f7e9c2fb243435da4cb4082f5135 in temp_project.
- Owner instruction: 提案の方針でプランを作成せよ。変更点が多い場合は複数のプランとして作成せよ。手続きとして削減するべき部分をまとめたり、スキル化、関数化するべき部分など、改善できる部分をまとめよ。
- This instruction authorizes plan authoring, not implementation or reopening a stopped run. This is ordinary backlog work, not a reconstruction successor.
- See docs/plan/backlog/README.md for procedure reductions, existing-plan reuse and implementation order. Full decision audit stays in local development-process-planning evidence.
- The shared authoring checker derives correspondence and digests; the parent reviews witness semantics. No measured productivity saving is claimed.

- 2026-09-09 activation: Owner instruction 「@docs/plan/backlog/ にあるそれぞれのプランついて、実装作業をせよ。」 selected this backlog plan for implementation.
- 2026-09-09 approval gate: `review_class: B` with `human_approval_status: not_required`, so no separate owner design approval is required.
- 2026-09-09 ordering gate: The gate "If the skill-consolidation plan is also selected, implement it first" is satisfied. Plan 299 is checked at `docs/plan/checked/2026/09/01-15/299-route-shared-implementation-preflight.md`, so the sequential skill edits it owns are already published.
- 2026-09-09 predecessor references: Plans 103, 286 and 296 are checked under `docs/plan/checked/2026/09/01-15/`.
- 2026-09-09 implementation mode: `implementation_risk: high` requires bounded parent implementation with independent read-only review; no writable worker is started for this plan.
- 2026-09-09 activation baseline: `0f78a68` in `temp_project`.
- 2026-09-09 review round 1: An independent read-only review reported three High and two Medium findings, each with a reproduction. Addressed in candidate commit `974505a`: every preparation destination and the plan path now refuse `.` and `..`; the first execution-state publication claims its final name exclusively and the candidate lifecycle destination is rechecked before readiness; a partial failure probes the destinations instead of trusting which constructors returned; and any declared `implementation_mode` must be exactly `parent_direct`. The remaining High finding, that the command establishes no global uniqueness for a plan or run identity, was disputed as an inherited property of the composed `init` call whose remedy the plan's Decisions forbid; the report, docstring and policy text were corrected to state the limit.
- 2026-09-09 review round 2, final of the epoch: The reviewer withdrew the disputed High finding and confirmed the other four resolved, then reported one new Medium finding: reserving the final state pathname publishes an empty placeholder, so a later serialization or synchronization failure leaves an invalid record that blocks every retry, including for existing `init` callers. The finding is accepted. The epoch's two-review budget is spent, so accepted closure is unavailable and the run stopped for an owner decision with the candidate retained unpublished.
- 2026-09-09 owner continuation authorization: Presented the stop, the accepted Medium finding and the intended no-replace publication, and asked the owner to choose between continuation and stopping. The owner answered `authorize_continuation`, quoted as 「プラン300の実装を後続エポックで継続してよい。」, under the standing instruction 「@docs/plan/backlog/ にあるそれぞれのプランついて、実装作業をせよ。」. This authorizes one further execution epoch on the unchanged plan, source baseline, invariant, acceptance items, validation authority and write scope. No requirement or safety condition changes and the owner did not waive review.
