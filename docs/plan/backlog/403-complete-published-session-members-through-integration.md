# Let the bound integration session complete exactly published and retired member plans

status: backlog
primary_invariant: Only the bound integration session may complete and archive a schema-2 member after its exact accepted result is published and its task worktree and branch are retired; missing live evidence or an unfinished partner never becomes false completion.
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: pending
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"require_group_permit routes every schema-2 operation into require_session_member_operation, which unconditionally refuses completion, finalization and archive. complete-plan.sh and finalize-active-plan.sh both invoke that gate even after publication.","kind":"existing_mechanism"}
  - {"evidence":"run-parallel-plans.py publish already records publication and retires the member worktree. It does not complete or archive the numbered plan; group-status computes group_complete from publication flags alone.","kind":"existing_mechanism"}
  - {"evidence":"manage-plan-worktrees.py verify_integration_authorization already binds publication to the frozen result and refuses retirement until the recorded member process incarnation exits.","kind":"existing_mechanism"}
  - {"evidence":"The existing completion scripts parse the active index and check live evidence. The task-worktree manager can prepare a separate direct authoring/lifecycle checkout, so integration need not reuse an already retired member checkout.","kind":"existing_mechanism"}
completion_conditions:
  - The bound integration session can run the supported completion and finalization path for a published and retired schema-2 member; the member session, an unrelated integration session and an unpublished or unretired member refuse before lifecycle writes.
  - Completion retains the existing live-evidence requirement and plan evidence checks, archives one exact member and updates shared indexes serially without invalidating the partner enrollment or discarding either result.
  - Group completion is false while any member retirement or lifecycle transition remains unfinished; interruption after publication preserves the accepted commit and supports an exact recovery without deleting unrelated work.
  - The parent task-worktree guard remains enforced for integration lifecycle writes and the successful lifecycle task is published and retired through the existing task manager.
  - Root and generated lifecycle entrypoints and guidance stay aligned.
completion_witness_map:
  - {"condition_sha256":"sha256:26f30e52cca69d4ddaf07bd456d148cded3d59908ba288f0b2501e628e57f384","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:37fb855539ad00a4067ab40328a8bac11ef61681ca63a53978f0ccc58141aa4b","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:699f2d39d6decc05824eb43111c5306ca2372f9ea9d70b77fb422829d74f0a8c","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:6f66b67d67914edad693e54ea918aa48aa5c2b58942304f37d83cc47e2372c46","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:a5ec92d1a9446b2f829a1084704949db548482167a80af2a8b620ba0ee6be2ed","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/parallel-plan-state.py
  - template/.project-agent-workflow/scripts/parallel-plan-state.py
  - scripts/run-parallel-plans.py
  - template/.project-agent-workflow/scripts/run-parallel-plans.py
  - scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - scripts/project_workflow/worktree_guard.py
  - template/.project-agent-workflow/scripts/worktree_guard.py
  - scripts/manage-plan-worktrees.py
  - template/.project-agent-workflow/scripts/manage-plan-worktrees.py
  - scripts/check-agent-completion.sh
  - template/.project-agent-workflow/scripts/check-agent-completion.sh
  - tests/test-sandboxed-plan-worker.py
  - tests/test-plan-execution-state.py
  - tests/root-plan-lifecycle.sh
  - tests/validation_tools/worktrees.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - template/.project-agent-workflow/docs/agent/SPEC_GIT_RETIREMENT.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
preservation_scope:
  - none
context_files:
  - docs/plan/checked/2026/09/16-31/373-run-parent-direct-plans-in-member-sessions.md
  - docs/plan/checked/2026/09/16-31/384-derive-review-outcome-from-reviewer-evidence.md
  - docs/plan/parallel-session-development-20260926.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - tests/root-plan-lifecycle.sh
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The bound integration session can complete and archive each exactly published and retired schema-2 member through supported commands while live-evidence gates, plan evidence and task-worktree ownership remain enforced; members, stale authority and incomplete results refuse without lifecycle mutation.
  - A then B completion retains both changes and the partner enrollment, unfinished retirement or lifecycle work is never group completion, and replay or interruption preserves the accepted result and recoverable work.
  - Root and generated lifecycle entrypoints and guidance stay aligned.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:61c2bc69742f2407ffc4fd30e8d771fc2fd7a53b1091e2929dd7341f732744b4","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:04235e5f069e2ee5dd9404012bb093abc72df9a7b0d538266d48db08c338dfb4","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:a5ec92d1a9446b2f829a1084704949db548482167a80af2a8b620ba0ee6be2ed","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Begin implementation only after the integration-review plan named in the operational roadmap is checked and published; keep this plan in backlog until then.
  - Plan 380 remains shelved. This plan does not inherit its broad ledger-obligation and authority claims; its scope is the independently verifiable legitimate integration completion route.
  - Use the completed transcript verifier before the real-session demonstration. Synthetic lifecycle fixtures are regression evidence only, never proof that two agent sessions ran.
checked_summary_ja: 反映と作業場所の削除を確認して、統合担当がメンバープランを完了する

## Decisions

- Keep the member prohibition intact. Add a separate integration-owned route using the group-bound integration session identity and exact process incarnation; no broad bypass flag, caller assertion or filename grants authority.
- Reuse published commit reachability, frozen result and retirement facts. Distinguish publication from retirement and numbered-plan completion, and make the reported group completion depend on the required final states.
- Route lifecycle writes through a separate task-bound integration checkout, never the source checkout or a retired member checkout. Serialize each index update and publish that lifecycle task through manage-plan-worktrees.py.
- Keep live-evidence verification before completion. A member carrying the whole-group demonstration waits for both results and the bound report; another member may complete only after its own obligations are met.
- Retain original group plan digests and immutable handoffs. Resolve published members across active and checked locations using existing lifecycle rules, so archiving A does not strand B or relax the partner write scope.
- Keep stopped execution ledgers stopped. This plan supplies the missing legitimate completion route; it does not restart plan379 or reintroduce same-user unforgeability.
- Use the existing journal and retirement mechanisms for bounded exact recovery. Do not force-delete a live process, ignored work or an unpublished branch and do not turn a publication flag into completion.
- Run this shared-control change serially after the evidence-backed integration-review prerequisite in the operational roadmap. Keep the root and generated public entrypoints consistent.

## Tasks

- [ ] Reproduce the current schema-2 lifecycle refusal using a published isolated member and the actual completion command; preserve the member-session refusal as a negative case.
- [ ] Add the integration-owned lifecycle route and propagate its exact group/session evidence through the adapter, completion/finalization commands and existing task guard.
- [ ] Require exact publication and retirement before lifecycle mutation, preserve the live-evidence and plan-completion gates, and define truthful group completion from those recorded outcomes.
- [ ] Run the lifecycle changes from a dedicated bound integration task checkout; archive A, retain B enrollment, then complete B without modifying committed group digests or member outcomes.
- [ ] Exercise live member processes, missing/stale identity, unretired worktrees or branches, missing live evidence, publication interruptions and exact retry, plus unchanged ungrouped/schema-1 behavior.
- [ ] Mirror code and policies, run the focused commands and an actual isolated A/B completion and archive smoke, then the unchanged authoritative suite once on the accepted candidate.

## Validation Notes

- Planning request 2026-09-26: 「並列実装をするためのプランを作成せよ。」 This task authors backlog plans only; implementation and design approval remain separate.
- Planning baseline: c704d857e1e5826dcc96dba6a2fc5513e953aa97. Parent inspected the actual command path after bounded read-only review; no new live-session run or defect regression was executed during authoring.
- Do not reopen the exhausted plan-379 ledgers, apply its unaccepted retained patch, or claim same-user evidence unforgeability. Preserve existing stopped runs and budgets. This plan changes the supported command path, not the operating-system trust model.
- Use bounded parent-direct implementation because the scope includes workflow and validation authority. Before implementation, obtain design approval, publish the active plan, initialize its own permitted ledger and review route, and retain ordinary review and stop limits.
