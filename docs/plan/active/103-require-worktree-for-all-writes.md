# Require a task worktree before every repository write

status: in_progress
primary_invariant: Every repository-changing task performs its edits, staging, validation, commit, and plan lifecycle writes in one exact task-bound linked worktree prepared before the first write; the pre-existing checkout is never the implementation workspace.
task_types:
  - planning_docs
  - template_workflow
  - security
  - skill_authoring
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"At commit f5ab608, git worktree list showed only the pre-existing dev checkout after Plan 272 had been implemented and archived there; the optional manager and guidance did not establish the owner's required worktree boundary.","kind":"reproduced_defect"}
  - {"evidence":"manage-plan-worktrees.py already creates, inspects, and resumes plan-bound linked checkouts with repository, branch, start-commit, directory-identity, owner-lease, and retained-state verification.","kind":"existing_mechanism"}
  - {"evidence":"The Codex PreToolUse gate, Stop adapter, staged-tree pre-commit hook, lifecycle commands, and generated copies already provide deterministic supported-workflow boundaries where one shared worktree assertion can fail closed.","kind":"existing_mechanism"}
  - {"evidence":"run-parallel-plans.py already binds each member dispatch to an exact worktree and journals checked fast-forward publication, while run-sandboxed-plan-worker.py already resolves linked parent checkouts and retains disposable no-hardlinks clones.","kind":"existing_mechanism"}
completion_conditions:
  - One idempotent prepare-or-resume operation creates a task-bound linked checkout before the first repository write for either one committed numbered plan or one disjoint bounded direct-task identity.
  - The binding fixes repository, common Git directory, task kind and identity, start commit, target ref, branch, worktree directory identity, and owner lease while preserving every pre-existing checkout byte and index entry.
  - Supported agent pre-tool and completion hook boundaries reject an original, missing, foreign, stale, expired, or replaced task-worktree binding before their governed repository effect.
  - Plan authoring, activation, completion, finalization, shelving, restructuring, and generated equivalents, together with supported staging and commit boundaries, mutate only from the verified task worktree and preserve their existing atomicity, lineage, and validation authority.
  - Parent-only publication advances only the exact reviewed and validated task commit by a journalled expected-target fast-forward and stops without discarding state when the target ref or checkout is dirty, missing, or changed.
  - A single-plan implementation automatically creates or resumes its plan-bound parent worktree and keeps sandboxed candidate generation and validation in separate no-hardlinks clones without applying into the original checkout.
  - Each simultaneously writable execution-group member uses a distinct live plan-bound worktree, and grouped candidate generation retains current member permits, budgets, serial review, validation, and publication ownership.
  - Root and generated policy, security boundaries, skills, hooks, commands, modes, tests, and Copier inventory stay aligned; completion never removes a worktree or local branch outside the explicit retirement workflow.
completion_witness_map:
  - {"condition_sha256":"sha256:52f0a038ad51a696b358ab88eac4f7a302c15008e3d7a95407710274d399f160","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:eabdc2f040fee404941d8ff12ba1cb46ee23d654d01eee74d01f4ef9a7bfd4e4","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:a978285a61d66f173b6d4af284818c2de99b5b242a7bc8f7230efef105ccc91e","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:1ed7def98800d15a81ebc653d9fa27431ef61a96168ea5fb15ab4984fb22f6cf","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:05ebaebcb84356cb26e741767b742cba558d4a0bf2c3016053ab48abcf645dc0","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:8b8d0d88825413f78a852756b96a2ba6f7420ac94ede6c3dce50e51db3d7ec69","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:de1ab10c92f0f72e67d6139e556e20ef7a7cf7486d190b0e10526c20f028ab6e","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:ba3d940ebf2a92512d9a7ce3575e5ec2f60683a4d3e9632cfeab52bb538dbe4e","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/project_workflow/worktree_guard.py
  - template/.project-agent-workflow/scripts/worktree_guard.py
  - scripts/manage-plan-worktrees.py
  - template/.project-agent-workflow/scripts/manage-plan-worktrees.py
  - tests/validation_tools/worktrees.py
  - scripts/project_workflow/plan_authoring.py
  - template/.project-agent-workflow/scripts/plan_authoring.py
  - template/.project-agent-workflow/scripts/create-plan.sh
  - template/.project-agent-workflow/scripts/planlib.py
  - scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - scripts/shelve-plan.sh
  - template/.project-agent-workflow/scripts/shelve-plan.sh
  - template/.project-agent-workflow/scripts/promote-plan.sh
  - .project-agent-workflow/hooks/pre_tool_hardening_gate.py
  - template/.project-agent-workflow/hooks/pre_tool_hardening_gate.py
  - .project-agent-workflow/hooks/stop_review_gate.py
  - template/.project-agent-workflow/hooks/stop_review_gate.py
  - .githooks/pre-commit
  - template/.githooks/pre-commit
  - tests/hooks/gates.py
  - tests/root-plan-lifecycle.sh
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - scripts/run-parallel-plans.py
  - template/.project-agent-workflow/scripts/run-parallel-plans.py
  - tests/test-sandboxed-plan-worker.py
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - .codex/skills/sequential-plan-orchestrator/agents/openai.yaml
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/agents/openai.yaml
  - template/.agents/skills/sequential-plan-orchestrator/SKILL.md
  - AGENTS.md
  - template/AGENTS.md.jinja
  - template/.project-agent-workflow/AGENTS.md.jinja
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - template/.project-agent-workflow/docs/agent/SPEC_SECURITY.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - scripts/check-root-agent-policy.py
  - scripts/check-copier-template.py
  - scripts/project_workflow/copier_inventory.py
  - tests/smoke.sh
  - tests/copier-update.sh
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/git-retirement.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/plan/checked/2026/09/01-15/284-bind-parallel-plan-execution-to-shared-authority.md
  - docs/plan/checked/2026/09/01-15/285-integrate-parallel-plan-candidates-in-order.md
  - docs/plan/checked/2026/09/01-15/287-complete-resumable-parent-worktrees.md
  - scripts/retire-merged-worktrees.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 tests/test-hooks.py
  - tests/root-plan-lifecycle.sh
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
acceptance:
  - Prepare or resume one separate linked worktree without another owner prompt before any supported repository-changing task, including Tier 0, plan authoring, one numbered plan, and grouped numbered plans.
  - Keep the pre-existing checkout outside hook-controlled task editing and completion effects, and fail closed on missing or invalid task bindings without claiming protection against an unrestricted same-user bypass.
  - Publish only an exact accepted commit through a checked recoverable fast-forward, preserve dirty or drifted target state, and require verified publication before plan completion or archival.
  - Run a single numbered plan from its managed parent worktree while retaining exact worker-clone isolation, candidate admission, review, validation, apply, and execution-ledger limits.
  - Run each concurrently writable group member from a distinct managed worktree without weakening membership, permit, baseline-transfer, review-budget, serial-integration, or stop-state rules.
  - Keep root and installable generated worktree policy, skills, scripts, hooks, tests, modes, and explicit retirement behavior mechanically aligned.
  - Preserve project-owned product code, policy, configuration, plan history, validation behavior, and task worktree controls through one real non-destructive Copier update.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:8d3336a8dd4fd90fdd63ecf2cd65c2b6b6157ff751185f875863edbf52c1405d","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:d5271055a3f89a674ab9c11318a753826dd8305082cd8fca73c985926361985e","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:f9087b092b34bc8663b7c1be9e87e4804d62380e9dc778adc1d83e2c146abd02","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:76b46f0cbf5279f1147fdab6d3f1713f6dd8cf999a1ac166269462663a0a702f","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:e639b11ebb94be98a69614a50e9c5bba677e88df259a01c5a098011749cf6bcc","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:7dc63b7f45d31bf345b10043168170bfb0b73fc8559c2e5a981a063414ad2907","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:96b39fe5a3b8d0aa786e1f6eec094569ae1448c1b143c767ffb6204571cdfb08","authoritative_only_reason":"Only the real isolated Copier transaction executes before-update migration, template application, conflict checks, and after-update preservation together.","stage":"authoritative","witness":"tests/copier-update.sh --require-copier"}
integration_gates:
  - Implement this Tier 2 validation- and lifecycle-authority change through bounded parent-direct work in the dedicated linked checkout created for this plan; do not run a writable worker against protected policy, hook, runner, or validation paths.
  - The planning checkout was created manually from clean commit f5ab608 before the first repository write because the current manager requires an already committed active plan. Treat that bootstrap as defect evidence, not as a future exemption.
  - Use the operating-system account home rather than caller-controlled HOME for automatic worktree placement and external records; reject symlinked, registered, replaced, shared, or unsafe path ancestry before Git mutation.
  - Keep plan and direct-task identities as exact disjoint variants. A direct task may create a plan, but it never acquires that plan's lifecycle or execution authority without a new plan-bound preparation.
  - Do not infer that a worker clone or alternate current working directory is a valid task worktree. Reproduce the live external record, common Git directory, registration, branch, start ancestry, directory identity, and owner lease at each governed boundary.
  - Preserve the current explicit execution-group admission rules. This plan binds member worktrees but does not authorize automatic independence inference, automatic group creation, or a wider concurrent member count.
  - Keep deterministic claims within supported agent and repository entrypoints. State the git commit --no-verify and unrestricted same-user process boundaries instead of weakening the required default workflow.
  - Do not remove or prune any worktree, branch, ownership record, retained edit, or ignored local file during preparation, publication, completion, Copier update, or recovery.
checked_summary_ja: すべての書き込み作業を専用 worktree 上で実行する。

## Decisions

- Treat every task-specific product, policy, configuration, test, plan, lifecycle, index, staging, validation, and commit write as requiring a linked worktree; read-only inspection may remain in the pre-existing checkout.
- Accept exactly one of a committed numbered-plan identity or a bounded parent-created direct-task identity. Keep their schemas and external ownership records disjoint so a direct task cannot impersonate a plan.
- Bind one worktree and local branch to one task identity. Never share a writable checkout between concurrent plans or carry retained task bytes into an unrelated task.
- Make prepare-or-resume idempotent and automatic before the first supported write. A documented optional command, a disposable worker clone, or a clean original checkout does not satisfy the boundary.
- Enforce the boundary in supported agent hooks, lifecycle and runner commands, staging, completion, and publication without claiming to intercept an unrestricted same-user process that bypasses every entrypoint.
- Publish only a reviewed and validated task commit through a parent-owned journalled expected-target fast-forward. Stop on target drift or dirty state and never reset, stash, or discard it.
- Keep worktree and local-branch removal exclusively in the existing explicit Git retirement workflow; completion and publication perform no automatic cleanup.

## Operational referents

- The registered checkout that existed before the task-specific linked checkout was created.
- The first operation in a task that changes repository files, the index, plan lifecycle files, or a task commit.
- A linked Git checkout outside the original checkout, bound to the repository, task identity, branch, starting commit, owner lease, and retained state.
- The disposable no-hardlinks clone created by the sandboxed worker for candidate generation or validation.
- The predicate that the current checkout is the live task-bound linked checkout for the exact repository, task identity, branch, starting commit, and owner.
- The relation in which each simultaneously executing numbered plan owns a distinct task-specific linked checkout.

## Tasks

- [ ] Add disposable direct-task, single-plan, grouped-plan, stale-binding, original-checkout, dirty-target, recovery, bypass-boundary, and explicit-retirement fixtures before changing production behavior.
- [ ] Extract one aligned worktree assertion module and extend the manager with automatic default placement, mutually exclusive plan/direct task identities, idempotent prepare-or-resume, inspection, and bounded ownership records.
- [ ] Gate plan authoring and every governed root/generated lifecycle mutation before its first repository effect, and make pre-tool, pre-commit, and Stop surfaces report the exact worktree action needed.
- [ ] Require the sequential orchestrator and sandboxed runner to start from the bound plan worktree while retaining disposable clone isolation, exact candidate review, focused validation, authoritative validation, apply, and ledger rules.
- [ ] Bind every grouped member to its own managed worktree and preserve existing group membership, permits, baseline transfer, counters, stop states, serial integration, and publication authority.
- [ ] Implement or reuse one checked publication transaction for direct and sequential work that journals intent, rechecks the expected target and clean checkout, advances only the exact accepted commit, and recovers without replay.
- [ ] Update root/generated policies, skills, metadata, hooks, inventory, and Copier preservation coverage without enabling automatic worktree deletion or automatic multi-plan selection.
- [ ] Run referent-contract checks, exact-target adversarial preflight, independent review within the execution epoch, every focused command, and the authoritative validation suite once for the otherwise acceptable implementation.

## Validation Notes

- Owner requirement: 「こちらで明示してワークツリーの使用を求めなくても、１つのプラン実装であっても２つ以上のプラン実装であってもワークツリー上で作業を行ってほしい」.
- Owner authorization: 「提案の方針でプランを作成せよ。」 This authorizes this implementation plan and its accepted worktree boundary; it does not authorize implementation in this planning turn.
- Decision audit selected all-repository-write coverage, disjoint direct/plan identities, one worktree per task, supported-entrypoint enforcement, checked publication, and explicit-only retirement. The full comparison remains outside docs/plan.
- Planning baseline is f5ab608 in temp_project. The allocator selected Plan 103; its dedicated branch is plan/103-require-worktree-for-all-writes and its linked checkout is outside the pre-existing checkout.
- Feasibility evidence is bounded source inspection and the reproduced absence of a task worktree for Plan 272. It is not a claim that the future implementation or completion witnesses already pass.
- The parent owns design interpretation, scope admission, independent-review acceptance, validation, lifecycle transitions, publication, commit, and final reporting. No helper is authorized by this planning turn.
