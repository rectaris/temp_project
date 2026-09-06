# Require a task worktree before every repository write

status: checked
primary_invariant: Every repository-changing task performs its writes in one exact task-bound linked worktree; a success response requires its accepted commit published to the exact source branch and its task worktree and temporary local branch absent.
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
  - {"evidence":"At the time of the owner's clarification, Plan 103 was committed on its task branch but absent from dev, and the prior completion report had left that authoring worktree registered instead of publishing and retiring it.","kind":"reproduced_defect"}
  - {"evidence":"plan_authoring.py scans active, backlog, shelved, recursive checked and replanned files plus checked.md, but its lifecycle lock is worktree-local and cannot serialize allocations across linked checkouts.","kind":"existing_mechanism"}
completion_conditions:
  - One idempotent prepare-or-resume operation creates a task-bound linked checkout before the first write for either one committed numbered plan or a disjoint direct task, including plan authoring before a plan identifier exists.
  - The binding fixes repository, common Git directory, task identity, start commit, source ref and checkout, task branch, directory identity, and owner lease while preserving every pre-existing checkout byte and index entry.
  - Supported pre-tool and completion hooks reject an original, missing, foreign, stale, expired, or replaced binding before writes and reject success while publication or exact task-worktree and temporary-branch retirement remains incomplete.
  - Plan authoring reserves the smallest identifier against the published lifecycle files and live cross-worktree reservations; lifecycle writes stay in the task worktree, and only a source-reachable committed active plan may authorize implementation.
  - A recoverable parent-only transaction fast-forwards the clean expected source checkout to the exact accepted commit, preserves local evidence, removes the exact task worktree and temporary branch, and only then permits a success response.
  - A single-plan implementation automatically creates or resumes its plan-bound parent worktree and keeps sandboxed candidate generation and validation in separate no-hardlinks clones without applying into the original checkout.
  - Each simultaneously writable execution-group member uses a distinct live plan-bound worktree, and grouped candidate generation retains current member permits, budgets, serial review, validation, and publication ownership.
  - Root and generated policy, security boundaries, skills, hooks, commands, modes, tests, and Copier inventory stay aligned; exact successful-task retirement is automatic while unrelated and stopped-task retirement remains explicit.
completion_witness_map:
  - {"condition_sha256":"sha256:abd73b8cb40002cb7fb2f8f486fe56ec6eb7c52e8bbd9dfae4aaa7cbc1b974b8","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:0520d6fe4a526d0a885168004964f5f8d3beb68e0001bb5dae0bb05197f008bb","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:601fe8a517f60ca30c9a73ef3cf28ab60547e831190ebd6c624e7f4e9587f284","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:d08e6d9638f3f79b2e0b5f31f2e561dbbe60a52d17d4298c2372d30e48f102fa","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:dfaa2bdb9539da5900a8b14a6457627378fee9e9decb281c4a41e78ea3dea1cd","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:8b8d0d88825413f78a852756b96a2ba6f7420ac94ede6c3dce50e51db3d7ec69","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:de1ab10c92f0f72e67d6139e556e20ef7a7cf7486d190b0e10526c20f028ab6e","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:ba2511d002a2fdc361424290b156ee0d941972f19e11948067145446455528bf","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/project_workflow/worktree_guard.py
  - template/.project-agent-workflow/scripts/worktree_guard.py
  - scripts/manage-plan-worktrees.py
  - template/.project-agent-workflow/scripts/manage-plan-worktrees.py
  - tests/validation_tools/worktrees.py
  - scripts/project_workflow/plan_authoring.py
  - template/.project-agent-workflow/scripts/plan_authoring.py
  - tests/validation_tools/plan_authoring.py
  - tests/fixtures/plan-authoring/cases.json
  - tests/fixtures/plan-authoring/holdout.json
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
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - template/.project-agent-workflow/docs/agent/SPEC_GIT_RETIREMENT.md
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
  - Prepare or resume one separate linked worktree without another owner prompt before Tier 0, plan authoring, single-plan, or grouped-plan writes, and allocate a plan identifier without treating another worktree's unintegrated draft as active.
  - Keep the pre-existing checkout outside hook-controlled task editing and completion effects, and fail closed on missing or invalid task bindings without claiming protection against an unrestricted same-user bypass.
  - Publish only the exact accepted commit through a checked recoverable fast-forward, preserve dirty or drifted source state, retain blocked work, and withhold success until the task worktree and temporary local branch are absent.
  - Run a single numbered plan from its managed parent worktree while retaining exact worker-clone isolation, candidate admission, review, validation, apply, and execution-ledger limits.
  - Run each concurrently writable group member from a distinct managed worktree without weakening membership, permit, baseline-transfer, review-budget, serial-integration, or stop-state rules.
  - Keep root and generated worktree policy, skills, scripts, hooks, tests, modes, shared plan-id allocation, automatic successful-task retirement, and explicit unrelated-retirement behavior mechanically aligned.
  - Preserve project-owned product code, policy, configuration, plan history, validation behavior, and task worktree controls through one real non-destructive Copier update.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:d34fdbe3615acca0aa21a52801499f1e8a6a6ab8b1ce1deff6d1e24309b3e75d","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:d5271055a3f89a674ab9c11318a753826dd8305082cd8fca73c985926361985e","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:a858d6be9ce93ceb61431ec35c227cbb5e7038148f80a913471cc8231b9d421c","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:76b46f0cbf5279f1147fdab6d3f1713f6dd8cf999a1ac166269462663a0a702f","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:e639b11ebb94be98a69614a50e9c5bba677e88df259a01c5a098011749cf6bcc","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:28b46d4c371ad962b66ae82cd1e743ef070b05e2a64d56b70f63b511f82ebb1f","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:96b39fe5a3b8d0aa786e1f6eec094569ae1448c1b143c767ffb6204571cdfb08","authoritative_only_reason":"Only the real isolated Copier transaction executes before-update migration, template application, conflict checks, and after-update preservation together.","stage":"authoritative","witness":"tests/copier-update.sh --require-copier"}
integration_gates:
  - Implement this Tier 2 validation- and lifecycle-authority change through bounded parent-direct work in the dedicated linked checkout created for this plan; do not run a writable worker against protected policy, hook, runner, or validation paths.
  - The planning checkout was created manually from clean commit f5ab608 before Plan 103 existed because the current manager requires an already committed active plan. Treat this direct-task bootstrap and the plan's current absence from dev as defect evidence, not as a future exemption or implementation authority.
  - Use the operating-system account home rather than caller-controlled HOME for automatic worktree placement and external records; reject symlinked, registered, replaced, shared, or unsafe path ancestry before Git mutation.
  - The plan files and active index reachable from the exact source-branch commit selected for publication.
  - A plan file and active-index update that exist only in the direct-task branch and linked checkout before publication.
  - The condition that the plan file and matching active-index row are committed and reachable from the exact source branch.
  - An external record bound to the common Git directory, source commit, direct-task identity, chosen three-digit identifier, owner lease, and allocation state.
  - The condition that the exact accepted commit is reachable from the source branch, its registered checkout reflects that commit, and the task worktree registration, directory, and temporary local branch are absent.
  - The relation in which a direct-task worktree authors and publishes a plan before a separate plan-bound worktree may implement it.
  - Keep plan and direct-task identities as exact disjoint variants. A direct task may create and publish a plan, but it never acquires that plan's implementation authority without a new plan-bound preparation from the published source commit.
  - Do not infer that a worker clone or alternate current working directory is a valid task worktree. Reproduce the live external record, common Git directory, registration, branch, start ancestry, directory identity, and owner lease at each governed boundary.
  - Preserve the current explicit execution-group admission rules. This plan binds member worktrees but does not authorize automatic independence inference, automatic group creation, or a wider concurrent member count.
  - Keep deterministic claims within supported agent and repository entrypoints. State the git commit --no-verify and unrestricted same-user process boundaries instead of weakening the required default workflow.
  - Never scan another worktree's uncommitted plan file to allocate an id, hold a repository-wide lock for an entire authoring session, or make an unintegrated plan executable; reserve briefly, recheck at publication, and stop for a conflicting unsupported write.
  - Do not report success until publication and exact successful-task retirement are both reproduced. A stopped task remains non-successful and retains recoverable state unless the owner separately authorizes its retirement.
checked_summary_ja: すべての書き込み作業を専用 worktree 上で実行する。

## Decisions

- Treat every task-specific product, policy, configuration, test, plan, lifecycle, index, staging, validation, and commit write as requiring a linked worktree; read-only inspection may remain in the pre-existing checkout.
- Accept exactly one of a committed numbered-plan identity or a bounded parent-created direct-task identity. Keep their schemas and external ownership records disjoint so a direct task cannot impersonate a plan.
- Bind one worktree and local branch to one task identity. Never share a writable checkout between concurrent plans or carry retained task bytes into an unrelated task.
- Make prepare-or-resume idempotent and automatic before the first supported write. A documented optional command, a disposable worker clone, or a clean original checkout does not satisfy the boundary.
- Keep plan authoring and plan implementation as separate tasks unless the owner requests both; author a plan under a direct-task identity, publish it first, and create a new plan-bound worktree only from the committed active plan on the source branch.
- Allocate the smallest unused three-digit plan identifier under a common-Git-directory lock after scanning active, backlog, checked, replanned, shelved, and checked.md in the exact source commit plus live external reservations; never scan arbitrary worktree drafts as authority.
- Enforce the boundary in supported agent hooks, lifecycle and runner commands, staging, completion, and publication without claiming to intercept an unrestricted same-user process that bypasses every entrypoint.
- Publish only a reviewed and validated task commit through a parent-owned journalled expected-target fast-forward. Reproduce the updated source checkout, relocate required ignored evidence, then remove the exact clean task worktree and temporary branch before a success response.
- Authorize automatic retirement only for the exact successfully published task owned by the current completion transaction. Keep unrelated, ambiguous, dirty, drifted, and stopped-task retirement in the existing explicit workflow without reset, stash, force removal, or data loss.

## Tasks

- [x] Add disposable plan-authoring, direct-task, single-plan, grouped-plan, allocation-race, stale-binding, original-checkout, dirty-target, publication-recovery, successful-retirement, stopped-retention, and bypass-boundary fixtures before changing production behavior.
- [x] Extract one aligned worktree assertion module and extend the manager with automatic default placement, mutually exclusive plan/direct task identities, idempotent prepare-or-resume, inspection, and bounded ownership records.
- [x] Move plan-id allocation under one common-Git-directory-bound lock and lease record that scans only the exact published source state and live reservations, binds the checked authoring input to its reserved id, and consumes it only after publication.
- [x] Gate plan authoring and every governed root/generated lifecycle mutation before its first repository effect, keep an unintegrated plan non-executable, and make pre-tool, pre-commit, and Stop surfaces report the exact worktree or publication action needed.
- [x] Require the sequential orchestrator and sandboxed runner to start from the bound plan worktree while retaining disposable clone isolation, exact candidate review, focused validation, authoritative validation, apply, and ledger rules.
- [x] Bind every grouped member to its own managed worktree and preserve existing group membership, permits, baseline transfer, counters, stop states, serial integration, and publication authority.
- [x] Implement one checked completion transaction for direct and plan work that journals intent, rechecks the source ref and clean registered checkout, fast-forwards only to the accepted commit, relocates required ignored evidence, retires only its exact task worktree and temporary branch, and recovers without replay.
- [x] Update root/generated plan, retirement, security, orchestration, skill, hook, inventory, and Copier policy while retaining explicit retirement for every worktree not proven to be the exact successfully published current task.
- [x] Run referent-contract checks, exact-target adversarial preflight, independent review within the execution epoch, every focused command, and the authoritative validation suite once for the otherwise acceptable implementation.

## Validation Notes

- Owner requirement: 「こちらで明示してワークツリーの使用を求めなくても、１つのプラン実装であっても２つ以上のプラン実装であってもワークツリー上で作業を行ってほしい」.
- Owner authorization: 「提案の方針でプランを作成せよ。」 This authorizes this implementation plan and its accepted worktree boundary; it does not authorize implementation in this planning turn.
- Owner completion requirement: 「AIエージェントが作業を終了してこちらにボールを渡したとき、ワークツリーは統合されて存在していないようにしたい」. This plan interprets that as the successful completion boundary and never uses it to publish or discard blocked work.
- Owner clarification recorded the then-current state: Plan 103 existed on its authoring branch but not on dev. The plan therefore explains that worktree-local authoring is provisional until publication and that plan implementation starts later from the published active plan.
- Owner update instruction: 「これらの説明もドキュメントに含めるようにプランを更新せよ。」
- Decision audit selected all-write coverage, separate direct-authoring and plan-implementation identities, shared plan-id reservation, checked source publication, automatic exact successful-task retirement, and explicit unrelated or stopped-task retirement. The full comparison remains outside docs/plan.
- Planning baseline is f5ab608 in temp_project. The allocator selected Plan 103; its dedicated branch is plan/103-require-worktree-for-all-writes and its linked checkout is outside the pre-existing checkout.
- Feasibility evidence is bounded source inspection and the reproduced absence of a task worktree for Plan 272. It is not a claim that the future implementation or completion witnesses already pass.
- The parent owns design interpretation, scope admission, independent-review acceptance, validation, lifecycle transitions, publication, commit, and final reporting. No helper is authorized by this planning turn.

### Execution record

- Implementation ran from 43331d2 and published 16 commits to dev, ending at a77a3dc. Every increment was written in the bound plan/103-require-worktree-for-all-writes worktree and published through the delivered transaction; the publication that proved retirement ran from inside the task worktree it removed.
- The delivered boundary was reproduced live after publication: `git worktree list` showed only the pre-existing checkout, the temporary local branch was absent, `outstanding` reported an empty list under `"enforced": true`, and the pre-existing checkout itself now refuses `git commit` through `worktree_guard.py require`.
- No plan execution ledger was initialized for this run, so `scripts/plan-execution-state.py` never bound the run identifier, plan digest, source baseline, primary-invariant digest, or implementation mode, and no ledger-recorded preflight, review, attempt, or continuation event exists. The one-correction and two-review-per-epoch budgets were honored by parent reading and explicit owner decision rather than by mechanical enforcement. This is a recorded deviation, not a satisfied condition; the missing receipts are not reconstructed after the fact.

### Adversarial preflight

- The exact-target adversarial preflight required by the last task ran after implementation and publication rather than before the first independent review. It is recorded here as a late parent-owned probe of the delivered code, and it does not retroactively supply the ordering the task text requires.
- Seven bounded probes ran against the published `worktree_guard.py` and `manage-plan-worktrees.py` in a disposable repository. A write from the pre-existing checkout was refused; a write from the bound task worktree was allowed; a write from an unrelated linked worktree of the same repository was refused; a record whose fields were edited without recomputing its content digest was refused; an expired owner lease refused the write while `outstanding` still reported the binding as outstanding with an expired lease; a record naming a foreign repository identity refused the write and was not reported against this repository; and a record naming a different worktree directory refused the write while remaining reported as outstanding.
- The probes also confirmed two properties the design depends on. Ownership records resolve under the operating-system account home rather than a caller-supplied `HOME`, and a repository identity carries the common Git directory device and inode, so a stale record from a removed disposable repository cannot name or block a live one.

### Independent review

- Four independent reviews ran across two execution epochs and exhausted the cumulative four-review maximum. Epoch 0 produced a six-finding round and a re-review that raised two new defects, including a High regression the parent had introduced where a nonzero `outstanding` exit without a canonical origin would have locked the Stop gate permanently.
- The parent stopped at `parent_remediation_budget_exhausted` rather than opening a third epoch-0 round. The owner authorized one continuation with 「承認する。」, and the continuation epoch ran two further reviews; the last reported no new defect and closed every prior finding.
- The final commit a77a3dc carries no independent review because the budget was already exhausted when its defect was reported. The owner chose to fix and publish it. The reviewer had specified that fix and its impact, so its design was reviewed and only its implementation was not.
- Every regression test added during remediation was negative-tested: the corresponding fix was reverted in isolation and the test was observed failing with the reported symptom. That practice caught one test that passed for the wrong reason and one revert that silently did not apply.
- Helpers were read-only and advisory. One exploration helper and the review helpers held no write scope, and every acceptance, validation, lifecycle, publication, and reporting decision stayed in the main session.
