# Bind independent plans to separate session owners and worktrees

status: in_progress
primary_invariant: Each admitted member has one exclusive session/worktree binding, without transferring shared integration or validation authority.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"parallel-plan-state.py binds exact two-member descriptions and private permits under flock; schema-1 members lack session and implementation-mode binding.","kind":"existing_mechanism"}
  - {"evidence":"prepare and worktree_guard.py bind tasks to linked checkouts, but a default owner string parent does not identify a unique live session.","kind":"existing_mechanism"}
  - {"evidence":"GROUP_AUTHORITY_DENY_PATHS rejects specification/validation paths before admission. Parent-direct scope needs an explicit mode, not a relaxation for candidate workers.","kind":"existing_mechanism"}
completion_conditions:
  - Distinct members receive distinct session/worktree bindings; duplicate starts, stale owners, wrong worktrees and ambiguous resume refuse before member effects.
  - Explicit parent-direct members can change approved project tooling, tests or specifications outside partner inputs and shared execution controls; candidate-worker scope denials remain unchanged.
  - Supported pre-tool and commit paths reject grouped writes without the matching session binding, and root/generated enforcement preserves ungrouped behavior.
completion_witness_map:
  - {"condition_sha256":"sha256:34b9d0992cf5d007f5ef4bd7dd085917e63eebf810584a94fef267cef3cab103","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:6b4d18c5db871fd580ed823cb74f26124395add219ea10235341b417f84f137c","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:b645e12746317f8d7d5c544cb546ba90a0de5793af0f6d27b232169ac3f750ae","witness":"python3 tests/test-hooks.py"}
write_scope:
  - scripts/parallel-plan-state.py
  - template/.project-agent-workflow/scripts/parallel-plan-state.py
  - scripts/manage-plan-worktrees.py
  - template/.project-agent-workflow/scripts/manage-plan-worktrees.py
  - scripts/project_workflow/worktree_guard.py
  - template/.project-agent-workflow/scripts/worktree_guard.py
  - tests/test-plan-execution-state.py
  - tests/validation_tools/worktrees.py
  - AGENTS.md
  - template/AGENTS.md.jinja
  - template/.project-agent-workflow/AGENTS.md.jinja
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - docs/agent/SPEC_SECURITY.md
  - template/.project-agent-workflow/docs/agent/SPEC_SECURITY.md
  - scripts/check-root-agent-policy.py
  - template/.project-agent-workflow/scripts/planlib.py
  - tests/validation_tools/plan.py
  - tests/validation_tools/generated.py
  - .project-agent-workflow/hooks/pre_tool_hardening_gate.py
  - template/.project-agent-workflow/hooks/pre_tool_hardening_gate.py
  - .githooks/pre-commit
  - template/.githooks/pre-commit
  - tests/test-hooks.py
  - tests/hooks/gates.py
  - scripts/check-copier-template.py
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/agent/spec-index.yaml
  - scripts/plan_validation_commands.py
  - docs/plan/checked/2026/09/01-15/287-complete-resumable-parent-worktrees.md
  - docs/plan/checked/2026/09/01-15/284-bind-parallel-plan-execution-to-shared-authority.md
  - docs/plan/checked/2026/09/01-15/285-integrate-parallel-plan-candidates-in-order.md
  - docs/plan/checked/2026/09/01-15/103-require-worktree-for-all-writes.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-validation-tools.py
  - python3 tests/test-hooks.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Distinct members receive distinct session/worktree bindings; duplicate starts, stale owners, wrong worktrees and ambiguous resume refuse before member effects.
  - Explicit parent-direct members can change approved project tooling, tests or specifications outside partner inputs and shared execution controls; candidate-worker scope denials remain unchanged.
  - Supported pre-tool and commit paths reject grouped writes without the matching session binding, and root/generated enforcement preserves ungrouped behavior.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:34b9d0992cf5d007f5ef4bd7dd085917e63eebf810584a94fef267cef3cab103","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:6b4d18c5db871fd580ed823cb74f26124395add219ea10235341b417f84f137c","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:b645e12746317f8d7d5c544cb546ba90a0de5793af0f6d27b232169ac3f750ae","stage":"focused","witness":"python3 tests/test-hooks.py"}
integration_gates:
  - Use checked plans 287, 284, 285 and 103. This authoring task enrolls no live group.
  - Registration alone never enables parent-direct execution or publication; require the later execution and integration capabilities.
checked_summary_ja: 独立した2件のプランを別セッションと専用 worktree に結び付ける。

## Decisions

- Use the approved one-plan, one-session, one-task-worktree design with exactly two independent members and one integration session. Member implementation, correction and review requests may overlap; final review acceptance, validation, publication, archive and retirement are serialized.
- Implement this prerequisite serially through bounded parent-direct execution with an external execution ledger and independent review. Do not use the new parallel path to implement or accept itself. Preserve stopped-state gates and correction/review limits.
- Member sessions are user-started agents responsible for their own plans. Their sandbox workers keep existing restrictions. Add no terminal automation, credentials, model routing, external writes or leader election.
- Add an exact versioned parent-direct group schema; verify historical candidate-only records unchanged. Bind common Git identity, plan bytes, baseline, worktree/branch, session identity and ownership generation in private external state.
- Use one lock order for group, worktree and lifecycle records. Recover partial preparation without duplicate owners. Lease expiry or a repeated owner string does not prove quiescence; require exact process-stop evidence or an explicit stopped handoff before resume.
- Keep one integration owner. Members have no source-ref, shared plan-index, acceptance, publication or lifecycle authority. Ownership checks cover supported commands, not arbitrary same-user process replacement.
- Keep candidate deny lists. Admit approved parent-direct tooling/test/spec edits only outside the other member context/validation inputs and immutable integration controls. Shared admission, ledger, guard and publication code remains serial-only while governing the group.
- Check semantic/read dependencies as well as disjoint write paths. Freeze accepted safety and validation obligations separately from editable product specifications. Reject effects on partner required specifications or validation inputs.
- Install binding and guards first, keep member execution/publication gated until later prerequisites, and correct root/template AGENTS pre-adapter wording.

## Tasks

- [ ] Extend exact schemas and private state with member mode, session ownership, integration owner and generations.
- [ ] Compose group admission with managed worktree preparation/resume, lock ordering and crash recovery.
- [ ] Implement mode-specific scope/dependency admission and supported write-entrypoint checks.
- [ ] Add concurrent distinct-member/same-plan races, stale/live owners, wrong worktrees, symlink/common-Git mismatch and partial-creation fixtures.
- [ ] Align policies and generated enforcement, obtain independent review, run focused checks and template alignment, then unchanged lint/smoke before serial publication.

## Validation Notes

- Implementation authorization: 「@docs/plan/backlog/372-bind-parallel-plans-to-separate-session-owners.md @docs/plan/backlog/373-run-parent-direct-plans-in-member-sessions.md @docs/plan/backlog/374-publish-and-verify-separate-session-plan-results.md の実装作業をせよ。」 Activate 372 first and keep 373 and 374 queued until their checked predecessors exist.
- Activation baseline: fc63404dfd7107713694da4c97931da6e15d6058 on dev in temp_project. The active index is empty, and prerequisites 287, 284, 285 and 103 resolve to their exact checked archives. Plan 360 is checked. The approved Tier 2 parent-direct design, scope and acceptance remain unchanged; no new design decision is introduced by promotion.
- Owner authorization: 「提案の方針でプランを作成せよ。」 The accepted proposal assigns one plan to each separate session/worktree, initially two independent members, one integration owner and real-session acceptance. This turn authors plans only.
- Planning baseline: 6dfb0167b26906a0d47bbf9f621c47cb8b19d4ba in temp_project. Plan 360 occupies the runnable slot. Queue this work without changing that task or reopening a stopped run.
- Tier 2 and class C apply because execution ownership and lifecycle authority change. Recheck scope and specifications before promotion. These are new plans, not reconstruction successors.
- Local evidence: .agent-artifacts/parallel-session-planning/. The disposable Git prototype and prior 16 passing GroupedExecutionAdapterTests prove bounded mechanics only; actual two-session runtime acceptance is not yet established.
- Independent plan review identified review-slot exhaustion and an optional-live-report bypass. The plans reserve integration review capacity and bind live evidence before implementation; primary runtime transcript evidence remains required. Parent accepted these bounded corrections without changing the user outcome.
- A bounded independent rereview confirmed all three document findings closed. The main session owns final scope, dependency checks, validation and publication; helpers held no write scope.
