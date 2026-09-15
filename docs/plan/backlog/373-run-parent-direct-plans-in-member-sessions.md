# Run and hand off parent-direct implementation in each member session

status: backlog
primary_invariant: Each member changes only its scope under the same logical execution budget and hands off independently derived Git evidence without acceptance or publication.
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
  - {"evidence":"plan-execution-state.py has parent_direct preparation, scope-bound review identities, reviewer/continuation registries and stop gates, but no grouped session binding.","kind":"existing_mechanism"}
  - {"evidence":"dispatch invokes the sandboxed worker; assembly expects its manifest. Parent-direct authorship needs separate evidence and must not fabricate a worker receipt.","kind":"existing_mechanism"}
completion_conditions:
  - Member start/resume/ready operations bind the exact session/worktree to a parent-direct handoff containing its plan, owner generation, baseline and full Git diff; stale or foreign handoffs refuse.
  - Group/ledger bindings preserve budgets and stops across restart: members use at most one formal review, reserve the second for final-base integration and share one correction/adjustment allowance; duplicate preparation and reviewer reuse refuse.
  - Ready submission freezes exact bytes and closes member writing; duplicate ledgers, post-handoff edits and member publication refuse with matching root/generated instructions.
completion_witness_map:
  - {"condition_sha256":"sha256:fac9a7e51f434eb98a3c761f205c8625d31080808f536603edc102f03588c7ef","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:fa4ce009e24182f76dea672e9a6d437a6fa398b6db2c2d072209510a0c34ae4a","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:d3984292ad76f289cf0acda9e4f69697f868e7730a8cf096723bcb5fc701e164","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/run-parallel-plans.py
  - template/.project-agent-workflow/scripts/run-parallel-plans.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - tests/test-sandboxed-plan-worker.py
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - scripts/parallel-plan-state.py
  - template/.project-agent-workflow/scripts/parallel-plan-state.py
  - tests/test-plan-execution-state.py
  - scripts/manage-plan-worktrees.py
  - template/.project-agent-workflow/scripts/manage-plan-worktrees.py
  - scripts/project_workflow/worktree_guard.py
  - template/.project-agent-workflow/scripts/worktree_guard.py
  - AGENTS.md
  - template/AGENTS.md.jinja
  - template/.project-agent-workflow/AGENTS.md.jinja
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - tests/validation_tools/worktrees.py
  - scripts/check-copier-template.py
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/agent/spec-index.yaml
  - scripts/plan_validation_commands.py
  - docs/plan/backlog/372-bind-parallel-plans-to-separate-session-owners.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-validation-tools.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Member start/resume/ready operations bind the exact session/worktree to a parent-direct handoff containing its plan, owner generation, baseline and full Git diff; stale or foreign handoffs refuse.
  - Group/ledger bindings preserve budgets and stops across restart: members use at most one formal review, reserve the second for final-base integration and share one correction/adjustment allowance; duplicate preparation and reviewer reuse refuse.
  - Ready submission freezes exact bytes and closes member writing; duplicate ledgers, post-handoff edits and member publication refuse with matching root/generated instructions.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:fac9a7e51f434eb98a3c761f205c8625d31080808f536603edc102f03588c7ef","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:fa4ce009e24182f76dea672e9a6d437a6fa398b6db2c2d072209510a0c34ae4a","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:d3984292ad76f289cf0acda9e4f69697f868e7730a8cf096723bcb5fc701e164","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - Start only after docs/plan/backlog/372-bind-parallel-plans-to-separate-session-owners.md is checked; resolve it to the exact checked archive before promotion.
  - Start only after the session-ownership predecessor is checked and its exact archive reference is resolved.
  - Implement this execution-control change through the existing serial parent-direct workflow.
checked_summary_ja: 各セッションで実装と修正を進め、実行記録を保って取り込み担当へ渡す。

## Decisions

- Use the approved one-plan, one-session, one-task-worktree design with exactly two independent members and one integration session. Member implementation, correction and review requests may overlap; final review acceptance, validation, publication, archive and retirement are serialized.
- Implement this prerequisite serially through bounded parent-direct execution with an external execution ledger and independent review. Do not use the new parallel path to implement or accept itself. Preserve stopped-state gates and correction/review limits.
- Member sessions are user-started agents responsible for their own plans. Their sandbox workers keep existing restrictions. Add no terminal automation, credentials, model routing, external writes or leader election.
- Add member start/resume/ready operations to run-parallel-plans.py. Return the exact worktree for an operator-started interactive session; retain Orca as optional existing candidate transport.
- Members implement, request independent review and perform the permitted correction. Integration owns review acceptance, final-base validation and publication; earlier formal reviews remain counted and preliminary checks are not acceptance.
- Compose parent-direct setup with one-use group claim, execution genesis and external reviewer/continuation registries. Retain partial setup and refuse second initialization; new sessions, run names or checkouts cannot replenish a member budget.
- Use a mode-discriminated parent-direct handoff with independently derived Git paths, modes and patch digest, including staged, unstaged, new and deleted product paths. Refuse out-of-scope bytes or false worker claims.
- Map the permitted member substantive correction and the group adjustment slot to the same logical allowance; never spend them independently. Preserve existing epoch/cumulative review and continuation limits and stopped-state semantics.
- Freeze the submission and close its writing claim before handoff. Never edit a live member checkout; retain original commits/evidence across target movement.
- Until integration is installed, retain readiness artifacts without accepting or completing the member.
- Allow at most one formal review before handoff, and reserve the epoch second review for integration at the final base. After member correction, freeze and hand off without a member rereview. Zero early reviews is permitted. A current-base review needs its exact adversarial preflight; remaining High/Medium findings stop when the existing review or correction allowance is exhausted.

## Tasks

- [ ] Implement member entrypoints with exact owner/worktree/group checks before effects.
- [ ] Cross-bind execution and review registries with crash-safe one-use group claims.
- [ ] Implement full-Git-diff parent-direct handoff while preserving worker-manifest processing.
- [ ] Close member writing and test duplicate initialization, post-handoff mutation, forged evidence, spent budgets and stopped runs.
- [ ] Align instructions, obtain independent review, run focused tests and unchanged lint/smoke before serial publication.
- [ ] Test one early formal review plus member correction and a reserved current-base integration review; refuse a member rereview that would consume the reserved slot and refuse separate correction/adjustment spending.

## Validation Notes

- Owner authorization: 「提案の方針でプランを作成せよ。」 The accepted proposal assigns one plan to each separate session/worktree, initially two independent members, one integration owner and real-session acceptance. This turn authors plans only.
- Planning baseline: 6dfb0167b26906a0d47bbf9f621c47cb8b19d4ba in temp_project. Plan 360 occupies the runnable slot. Queue this work without changing that task or reopening a stopped run.
- Tier 2 and class C apply because execution ownership and lifecycle authority change. Recheck scope and specifications before promotion. These are new plans, not reconstruction successors.
- Local evidence: .agent-artifacts/parallel-session-planning/. The disposable Git prototype and prior 16 passing GroupedExecutionAdapterTests prove bounded mechanics only; actual two-session runtime acceptance is not yet established.
- Independent plan review identified review-slot exhaustion and an optional-live-report bypass. The plans reserve integration review capacity and bind live evidence before implementation; primary runtime transcript evidence remains required. Parent accepted these bounded corrections without changing the user outcome.
- A bounded independent rereview confirmed all three document findings closed. The main session owns final scope, dependency checks, validation and publication; helpers held no write scope.
