# Orchestrate bounded Orca worker command sessions without transferring repository authority

status: checked
primary_invariant: The user-started coordinator remains the only repository acceptance and publication authority while an optional Orca bridge creates or reuses only one command terminal that runs the existing isolated candidate dispatcher for one exact admitted attempt.
task_types:
  - template_workflow
  - security
  - planning_docs
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The locally installed Orca 1.4.197 CLI exposes machine-readable terminal create, show, list, wait, read, and close operations, and its status command reports the runtime reachable and connected.","kind":"existing_mechanism"}
  - {"evidence":"scripts/run-parallel-plans.py and scripts/parallel-plan-state.py already confine grouped workers to isolated candidate generation while the parent alone assembles, reviews, validates, and publishes.","kind":"existing_mechanism"}
  - {"evidence":"Version-matched local CLI help confirms that terminal create can start one explicit command in an existing path-selected worktree and that terminal show and wait expose bounded process identity and completion observations.","kind":"bounded_prototype"}
completion_conditions:
  - The bridge refuses an unavailable or incompatible Orca runtime, a non-admitted plan attempt, a mismatched repository or worktree binding, unsafe external state paths, and malformed machine-readable replies before creating a terminal.
  - Under one private external lock, the bridge returns the recorded matching live command terminal or creates and records exactly one terminal for the exact plan, permit, worktree, source commit, candidate output, and coordinator terminal binding.
  - Before terminal creation, the bridge records one unpredictable start token; the entry command claims that token and waits, while the coordinator validates the create response with terminal show and binds its handle and incarnation before releasing candidate dispatch, and any lost, missing, or conflicting observation stops without an automatic duplicate.
  - The created terminal command is a shell-safe shlex.join projection of a constant worker-entry argument vector containing only the exact bridge path, validated external state path, and hexadecimal start token; worker-entry invokes the existing isolated candidate dispatcher as an argument vector without a shell, and no unrestricted outer agent or parent-only operation is exposed.
  - The generated project installs the executable bridge and aligned policy through the Copier inventory while preserving existing grouped execution and authoritative validation behavior.
completion_witness_map:
  - {"condition_sha256":"sha256:b84f450c4caa937d8030e2720e11c96483840a4a031ff50025af7942105e5bbb","witness":"python3 tests/test-orca-coordinator.py"}
  - {"condition_sha256":"sha256:64548122e9ceb434f432866c73a7c021fb20e9bc3df007b4628987d85babe700","witness":"python3 tests/test-orca-coordinator.py"}
  - {"condition_sha256":"sha256:0e1155b463f2fb0a8511a3a841fcb4e35c55e3bc9ae779d0766d099fef08b499","witness":"python3 tests/test-orca-coordinator.py"}
  - {"condition_sha256":"sha256:1a5030ac9d8cd3ae8745c43a94b59878d4487f5a82ee8810fb398a122abda94d","witness":"python3 tests/test-orca-coordinator.py"}
  - {"condition_sha256":"sha256:bbffc3bd6f760e5fb5e1b69617d6fc68f90b56f0c1a10591fa03cc9edc5824da","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/orca-coordinator.py
  - template/.project-agent-workflow/scripts/orca-coordinator.py
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/test-orca-coordinator.py
  - tests/smoke.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - scripts/manage-plan-worktrees.py
  - scripts/parallel-plan-state.py
  - scripts/run-parallel-plans.py
  - scripts/run-sandboxed-plan-worker.py
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-orca-coordinator.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A user can start one coordinator session and let it create or reuse bounded Orca command sessions for candidate generation without manually opening every worker and without transferring repository acceptance or publication authority.
  - Concurrent or repeated ensure-worker calls for one exact admitted attempt result in one recorded candidate-dispatch terminal or a fail-closed uncertain state, never duplicate candidate attempts.
  - Root and generated projects expose the same bounded Orca transport semantics and keep Orca identifiers advisory to existing plan, ledger, review, validation, and publication authority.
  - The complete generated-project smoke suite passes with the optional bridge installed and no weakening of the authoritative workflow gates.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:6777f08eea7dd1f2d96270595ba7e60b00a3927b3ba2a3111009674433da2e24","stage":"focused","witness":"python3 tests/test-orca-coordinator.py"}
  - {"acceptance_sha256":"sha256:dcc1ec42596ac03550a4c424f8a792b07232fb7b7c8aae3bb828a8631e757876","stage":"focused","witness":"python3 tests/test-orca-coordinator.py"}
  - {"acceptance_sha256":"sha256:859b9537e5c413ad73dd48c74b806e683cd763736e40ccfe10f5f070a36c5a37","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:63aa9d1bca7216c5c33fe08e1b0ffc1006de1358bb103eaa28ba4f440238c2fe","authoritative_only_reason":"Only the generated-project smoke suite exercises the complete Copier installation and existing lifecycle gates together.","stage":"authoritative","witness":"tests/smoke.sh"}
integration_gates:
  - Do not invoke a real terminal-create mutation during deterministic tests; use a fake CLI and reserve live Orca verification for parent-owned opt-in smoke after implementation.
  - Refuse any plan that is not an admitted execution-group member with a verified open run permit and external group state.
  - Refuse repository-relative mutable bridge state; require a caller-supplied regular mode-0600 state file and lock path outside every repository worktree.
  - Do not scan home directories, discover credentials, retain prompts or raw terminal output, or write Orca runtime identifiers into committed repository files.
  - Build terminal command text only with shlex.join over a constant argument-vector shape after path and token validation; invoke the grouped dispatcher with shell disabled and reject every unexpected field or argument.
  - Do not add automatic leader election, host startup automation, a second unrestricted agent around the isolated runner, worker-owned publication, plan completion, or lifecycle transitions.
checked_summary_ja: リポジトリの権限を移さず、Orca上で候補生成用のコマンドセッションを起動・再利用できるようにする。

## Decisions

- The coordinator session is the one user-started agent process and remains the only owner of repository interpretation, candidate acceptance, validation, commit, publication, lifecycle updates, and final reporting.
- A bounded worker command session is one Orca-managed terminal whose initial process is the bridge's noninteractive entry command and whose only repository operation is one exact existing grouped candidate dispatch.
- The Orca coordinator bridge is optional transport. Its private external record, terminal handle, and incarnation identifier grant no project authority and cannot replace plan, permit, ledger, review, validation, or publication evidence.
- The ensure-worker operation is locked and idempotent for one exact attempt: reuse a provably matching live command terminal, record one start token before creation, and stop without retry when entry claim or terminal identity is uncertain.
- Use task worktrees created by manage-plan-worktrees.py and the existing isolated candidate dispatch. Do not start an unrestricted outer agent, let Orca create a replacement repository authority path, or expose grouped assembly and publication commands in the terminal entry command.
- Use bounded parent implementation with independent review because every changed script, template, policy, inventory, and test path is parent-owned validation authority and cannot be mounted writable for a sandboxed plan worker.
- Keep automatic coordinator election and host-reboot startup outside this plan; the user starts one whole-task session, and that session starts or reuses its workers.

## Tasks

- [x] Implement strict CLI preflight, bounded JSON parsing, private external locking and records, exact attempt binding, pre-created start tokens, and start-or-reuse state transitions in the root bridge.
- [x] Implement a noninteractive terminal entry command that claims the pre-created token, waits for the coordinator to validate and bind the create response handle and incarnation, runs only the existing grouped candidate-dispatch argument vector, records the bounded exit result, and exits.
- [x] Add deterministic fake-Orca tests for success, live reuse, concurrent ensure calls, stale or mismatched bindings, malformed and oversized replies, symlink and hard-link state paths, settled attempts, entry-claim races, lost or ambiguous terminal creation, and shell metacharacters in every interpolated value.
- [x] Mirror the executable bridge and orchestration policy into the generated template, register inventory and alignment checks, and assert installation in the smoke suite.
- [x] Review the complete candidate and critical authority invariant before focused validation, obtain independent review with zero unresolved High or Medium findings, and run the authoritative validation suite exactly once.

## Validation Notes

- Planning baseline: fb6e0bfde634dd8dc83e5058e69d931e74db56e7 in temp_project.
- Owner instruction: 一度やってみたが、対応できているかわからない、実装できる部分については実装作業せよ。
- The local Orca CLI repair is independently verified: status is connected and version-matched orchestration help is available.
- The accepted decision direction is the previously recommended user-started single coordinator topology; arbitrary worker-led leader election remains out of scope.
- Helper findings were read-only and advisory; the parent accepted only the plan-authoring workflow and bounded implementation-surface evidence verified against current repository sources.
- Independent implementation rereview passed with zero High or Medium findings after the bounded remediation round.
- `scripts/lint-project-workflow.sh` failed once in the pre-existing `test_shared_publication_requires_explicit_supersede_and_stops_at_conflicts` assertion because two unchanged publications crossed a UTC-second boundary and produced different `generated_at` values. The parent-owned execution record is stopped at `repair_required`; `tests/smoke.sh` was not run.
- Plan 297 checked and committed the bounded shared-report repair at `16ad1c6b25ec5065d9ac12a2e374c7117465bf49`; this plan resumes with unchanged scope, acceptance, validation authority, safety boundary, and external-effect authority under a fresh execution.
- The resumed implementation added the root and generated bridge, deterministic fake-Orca coverage, inventory and alignment checks, generated-project smoke assertions, and the bounded orchestration policy.
- Independent review found pathname replacement, delayed-entry, output-bounding, bound-state reuse, and reboot-stale deadline defects. The parent corrected each finding; the final independent check reported High 0 and Medium 0.
- Focused validation passed: `python3 tests/test-orca-coordinator.py` ran 15 tests and `python3 scripts/check-copier-template.py` passed.
- Authoritative validation passed exactly once for the final candidate: `scripts/lint-project-workflow.sh` and `tests/smoke.sh`.
