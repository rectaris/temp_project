# Integrate separate-session results in order and verify real-session completion

status: in_progress
primary_invariant: Only the exact current-base result accepted by integration is published and completed; preserve both member changes and require real two-session evidence.
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
  - {"evidence":"A disposable two-worktree Git prototype produced A fast-forward exit 0, original B fast-forward exit 128, and successful B diff assembly at the A-containing base, retaining both files.","kind":"bounded_prototype"}
  - {"evidence":"The adapter has assembly records, one-use baseline transfer, leases and publication journals. Managed task publish independently requires a descendant tip and retires its task; these boundaries need one verified connection.","kind":"existing_mechanism"}
  - {"evidence":"GroupedExecutionAdapterTests passed 16 cases at the planning baseline using mock manifests and Git fixtures; no live session acceptance is established.","kind":"existing_mechanism"}
  - {"evidence":"The command parser admits tests/root-plan-lifecycle.sh, which can invoke a shipped read-only private-report verifier without starting agents in ordinary CI.","kind":"existing_mechanism"}
completion_conditions:
  - Integration assembles either handoff mode at the current target with original evidence retained and one review slot reserved from member execution; incompatible scope, stale evidence, target drift and spent review/correction allowances refuse.
  - Checked publication and serialized lifecycle updates retire only exact completed-member worktrees/branches; interruptions, dirty state or failed B retain accepted A and recoverable B without duplicate publication or false completion.
  - Two real sessions overlap implementation in distinct task worktrees and publish A then B with both changes retained and completed tasks retired; a pre-implementation plan/acceptance-bound required-evidence record and verified live report gate completion even without the environment variable.
  - Root/generated commands and guidance expose matching start, handoff, integration and retirement behavior and register preservation fixtures for project plans, groups, configuration and history.
completion_witness_map:
  - {"condition_sha256":"sha256:fa8fd07e674da2c9bc560061a17191a7336705b5f4da25a281060af350aff6e4","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:4f7453fc0e59e3ccda836275d66739d8568b487ff2def2db542e550e784841cd","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:78d5a40ddf9da07975330961711334ee747e8bdf119961e1373ab28b57c42411","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:405a824fe0f24376c2ce7a8275ef41575cc19ddb95b3d66029a3600aba97a1d2","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/run-parallel-plans.py
  - template/.project-agent-workflow/scripts/run-parallel-plans.py
  - scripts/parallel-plan-state.py
  - template/.project-agent-workflow/scripts/parallel-plan-state.py
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-sandboxed-plan-worker.py
  - tests/test-plan-execution-state.py
  - scripts/manage-plan-worktrees.py
  - template/.project-agent-workflow/scripts/manage-plan-worktrees.py
  - scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - scripts/project_workflow/worktree_guard.py
  - template/.project-agent-workflow/scripts/worktree_guard.py
  - template/.project-agent-workflow/scripts/planlib.py
  - tests/validation_tools/worktrees.py
  - tests/validation_tools/plan.py
  - scripts/verify-parallel-plan-sessions.py
  - template/.project-agent-workflow/scripts/verify-parallel-plan-sessions.py
  - scripts/check-agent-completion.sh
  - template/.project-agent-workflow/scripts/check-agent-completion.sh
  - tests/root-plan-lifecycle.sh
  - scripts/check-root-agent-policy.py
  - tests/validation_tools/generated.py
  - AGENTS.md
  - template/AGENTS.md.jinja
  - template/.project-agent-workflow/AGENTS.md.jinja
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - template/.project-agent-workflow/docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/smoke.sh
  - tests/copier-update.sh
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/agent/spec-index.yaml
  - scripts/plan_validation_commands.py
  - docs/plan/checked/2026/09/01-15/108-orchestrate-supervised-orca-workers.md
  - docs/plan/checked/2026/09/16-31/372-bind-parallel-plans-to-separate-session-owners.md
  - docs/plan/checked/2026/09/16-31/373-run-parent-direct-plans-in-member-sessions.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-validation-tools.py
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
acceptance:
  - Integration assembles either handoff mode at the current target with original evidence retained and one review slot reserved from member execution; incompatible scope, stale evidence, target drift and spent review/correction allowances refuse.
  - Checked publication and serialized lifecycle updates retire only exact completed-member worktrees/branches; interruptions, dirty state or failed B retain accepted A and recoverable B without duplicate publication or false completion.
  - Two real sessions overlap implementation in distinct task worktrees and publish A then B with both changes retained and completed tasks retired; a pre-implementation plan/acceptance-bound required-evidence record and verified live report gate completion even without the environment variable.
  - Root/generated commands and guidance expose matching start, handoff, integration and retirement behavior and register preservation fixtures for project plans, groups, configuration and history.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:fa8fd07e674da2c9bc560061a17191a7336705b5f4da25a281060af350aff6e4","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:4f7453fc0e59e3ccda836275d66739d8568b487ff2def2db542e550e784841cd","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:78d5a40ddf9da07975330961711334ee747e8bdf119961e1373ab28b57c42411","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:405a824fe0f24376c2ce7a8275ef41575cc19ddb95b3d66029a3600aba97a1d2","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
live_evidence_contract: parallel_sessions_v1
live_evidence_acceptance_sha256: sha256:78d5a40ddf9da07975330961711334ee747e8bdf119961e1373ab28b57c42411
integration_gates:
  - Start only after docs/plan/checked/2026/09/16-31/373-run-parent-direct-plans-in-member-sessions.md is checked; that archive is the exact resolved predecessor.
  - Start only after docs/plan/checked/2026/09/16-31/372-bind-parallel-plans-to-separate-session-owners.md is checked; that archive is the exact resolved predecessor.
  - Implement this integration serially.
  - Demonstration plans change bounded product files, not the governing controls; candidate-only or mock sessions cannot substitute for independent parent-direct sessions.
  - Live evidence is additional acceptance, not a replacement for focused/authoritative/Copy update checks. Bind its report path/digest before focused verification and completion.
checked_summary_ja: 別セッションの変更を順番に取り込み、実セッションで完了と後片付けを確認する。

## Decisions

- Use the approved one-plan, one-session, one-task-worktree design with exactly two independent members and one integration session. Member implementation, correction and review requests may overlap; final review acceptance, validation, publication, archive and retirement are serialized.
- Implement this prerequisite serially through bounded parent-direct execution with an external execution ledger and independent review. Do not use the new parallel path to implement or accept itself. Preserve stopped-state gates and correction/review limits.
- Member sessions are user-started agents responsible for their own plans. Their sandbox workers keep existing restrictions. Add no terminal automation, credentials, model routing, external writes or leader election.
- Integration owns assembly, review acceptance, focused/authoritative validation, publication, lifecycle/index updates and retirement. Members report readiness until publication and retirement are verified.
- After A publishes, transfer B once and assemble at the current target in a fresh disposable checkout. Retain original B commits/handoff as provenance. Reserve the existing adjustment slot before substantive edits; mechanical replay creates no generation or review budget.
- Never import dirty/live work wholesale, rewrite commits or force-update refs. Preserve both requirements; incompatible requirements, scope/authority drift or exhausted transfer stop under existing owner/diagnosis rules.
- Review/validate the exact final diff at a frozen current base using admitted authority. Early formal reviews remain counted and cannot prove a changed target. Record diagnosis_required immediately after authoritative failure.
- Connect publication and retirement using verified original task tip, handoff, assembled diff and published descendant. Publish only the admitted product diff, serialize lifecycle commits afterwards, and retire only when every owned change is accounted for without dirty/unaccounted work. Never rewrite history merely to make obsolete member commits ancestors.
- Journal publication, group acceptance, lifecycle and retirement with bounded exact recovery. Preserve work on dirty targets or ambiguous state; failed B leaves accepted A and an incomplete group.
- Add a bounded read-only live-report verifier and a procedure in an isolated generated project with two useful bounded product implementation plans. Use two real operator-started agent sessions and one integration owner; prove overlapping implementation intervals, not just terminal lifetimes.
- Keep raw runtime/transcript evidence local and state unavailable sources. Bind the private report to installed revision, plans/group, distinct sessions, worktrees, diffs, review/validation evidence, publication order and retirement. Derive Git facts independently and reject missing, fake, altered or replayed evidence.
- Require PROJECT_AGENT_WORKFLOW_PARALLEL_LIVE_REPORT for this plan focused execution; tests/root-plan-lifecycle.sh invokes the verifier read-only. Ordinary CI fixtures never establish live acceptance. Bind the report digest to this plan completion evidence so unsetting the variable cannot waive the requirement.
- Do not check this plan until real-session acceptance passes. Unavailable runtime is a reported blocker with retained evidence, not permission to substitute mock tests. Introduce no new external automation.
- Inherit the reserved integration review: at most one formal member review precedes handoff. Review the final assembled target after its exact adversarial preflight using the remaining epoch slot. Never reset counts at transfer; if the final round leaves High/Medium findings, retain the result and take the existing stopped-owner path.
- Before implementation begins, initialize one private structured required-evidence record bound to this plan digest, its exact live acceptance digest and execution genesis; reserve the demonstration group identity there and later append its exact group and report digests. Bind the record identity into parent execution evidence. Missing, replaced or mismatched required records refuse finalization; no prose-keyword inference or environment flag can create or remove the obligation.
- The explicit report environment locates bytes for tests/root-plan-lifecycle.sh only. check-agent-completion.sh and every complete/finalize/publication path independently resolve the fixed required-evidence record and verified report digest through parent execution evidence; unsetting or redirecting the environment variable cannot waive this plan acceptance.
- Use runtime-provided external transcript bytes as primary evidence of distinct session identities and overlapping implementation tool events, with hook logs only as corroboration. Bind exact reviewed source digests and independently cross-check Git effects and runtime provenance. A self-authored summary or synthetic event fixture is not live proof; unavailable primary evidence leaves this plan incomplete.

## Tasks

- [x] Extend assembly for mode-discriminated handoffs and original-versus-final evidence.
- [ ] Bind inherited accounting and one-use transfer to exact final validation/publication.
- [ ] Connect checked publication, lifecycle and task retirement with full-change preservation and crash recovery.
- [ ] Implement bounded private-report verification and completion binding, rejecting fake sessions, missing evidence, non-overlap, stale revision or incomplete retirement.
- [ ] Add deterministic concurrent-member, conflict, target-race, dirty-source, replay, partial-failure and crash-boundary tests.
- [ ] Align policies, inventory, generated smoke and actual Copier update fixtures.
- [ ] After static review/preflight run real member sessions in an isolated generated project, retain and independently verify evidence, then run focused checks with the required report and unchanged authoritative suites.
- [ ] Complete and publish only after independent review clears High/Medium findings and deterministic plus real-session acceptance pass.
- [x] Initialize and preserve the plan/acceptance-bound required-evidence record before implementation; test absent/replaced records, unset report environment and direct completion bypasses. Obtain primary transcript evidence for the real-session run or report the acceptance blocker.

## Validation Notes

- Integration path implemented: `assemble` is mode-discriminated (`--manifest` with `--permit`, or `--handoff` with no permit), `publish` selects its mode from the assembly record's own `handoff_mode`, the group authority records a parent-direct publication against the exact submitted handoff record digest instead of an open candidate permit, and publication now invokes the integration-authorized retirement of the member worktree. `ParentDirectMemberSessionTests` covers the full assemble, review, publish and retire path plus the assembly and retirement refusals; `tests/test-sandboxed-plan-worker.py` passes 209 tests.
- Member retirement authority: the member session owns its worktree and never releases it, so the authorization written by `scripts/run-parallel-plans.py publish` replaces both the owner lease and ordinary cleanliness. `scripts/manage-plan-worktrees.py retire --integration-authorization` rechecks repository identity, group, plan, worktree, branch, frozen member head, frozen result tree and target reachability, and preserves any worktree that changed after the freeze.
- Live-evidence gate: `scripts/verify-parallel-plan-sessions.py` owns the required-evidence record at a fixed private path keyed by repository identity, plan path and record type. The obligation comes from the committed `live_evidence_contract` and `live_evidence_acceptance_sha256` manifest fields, so dropping the acceptance item or the contract makes the gate refuse rather than pass. `complete-plan.sh`, `finalize-active-plan.sh` and `check-agent-completion.sh` all refuse this plan while the demonstration is reserved.
- Outstanding at this commit: acceptance item 3 (the live two-session demonstration) and the remaining alignment work for `references/orchestration.md`, `SPEC_AGENT_LOGGING.md`, `tests/smoke.sh`, `tests/validation_tools/generated.py` and a `tests/copier-update.sh` preservation fixture. This plan stays `in_progress`.
- Independent review of the first candidate returned five High and three Medium findings, and the owner directed remediation. The first remediation round closed four authority findings, and a second independent review reported that the closures were incomplete. The findings this plan now treats as closed are: publication and the exclusive lease authenticate the integration session that admitted the group by its recorded identity and exact process incarnation; the authority itself, not its caller, requires one recorded review of the exact assembled result, and that reserved post-handoff review is itself authenticated; the adapter authenticates integration before it advances the target; publication frees the lease and `group-complete` accepts a schema-2 group, so a published first member no longer locks the second one out; retirement resolves the parent-owned group state and requires the recorded publication, commit, handoff digest and a result tree that reproduces the recorded handoff patch, so a well-formed self-digest written by a member is refused and post-publication work is never approved for removal; and every lifecycle gate consults the live-evidence verifier for each plan, so a plan that drops its contract after reserving a record is refused instead of released.
- Still open after this remediation round, as the rereview reported: the boot-only process comparison still admits any member-owned ancestor process from the same boot, `record-review` is still unauthenticated so a member can record the reserved integration review itself, `command_publish` advances the target before integration is authenticated, retirement still trusts an authorization-supplied `member_result_tree`, and the three shell gates still call the verifier only when the manifest fields are present, so removing both fields still bypasses them. The earlier deferral claim in this plan was also wrong: this plan has four acceptance items, and the retention, recovery and forced-removal findings belong to acceptance item 2, not to an unclaimed later item. The publication and retirement task is therefore unchecked again and acceptance item 2 is not claimed.
- Owner continuation instruction: 「1 で進める。」 The owner chose to continue remediation rather than restructure or stop. This round closes the four authority findings the rereview left open. The integration process check now requires the exact recorded incarnation, not merely the same boot, so a member-owned ancestor process is refused. The reserved post-handoff review requires the authenticated integration session, so a member can no longer record the review its own publication would consume. The adapter authenticates integration before it advances the target, so a refused publication leaves the target unmoved. Retirement requires the authorization's named result tree to reproduce the authority-recorded handoff patch against the admitted baseline, so work frozen after publication is never approved for removal. All three lifecycle gates now consult the verifier for every plan, so deleting the manifest fields no longer skips them. `tests/test-sandboxed-plan-worker.py` passes 220 tests, `scripts/check-copier-template.py` and `scripts/lint-project-workflow.sh` pass.
- Execution ledger accounting: the two independent reviews of this plan were bounded read-only sub-agent reviews, and they were not recorded as formal reviews in `/home/rectaris/.local/state/project-agent-workflow/plan-374/execution.json`. `plan-execution-state.py review` admits a reviewer only against runtime-proven evidence — one `ReviewPacketStart` hook record or a `review_packet_start` transcript record carrying the reviewer's real session identifier, the packet digest and inherited turn zero — and this runtime emits neither. Producing that evidence by hand would be exactly the synthetic-evidence defect this plan exists to refuse, so it was not produced. The ledger therefore remains at epoch 0 `active` with its reserved required-evidence binding, no formal review is recorded, and the epoch-1 continuation path is neither claimed nor consumed. The reviews are recorded here as advisory evidence instead.
- Still open, and belonging to acceptance item 2: change retention is still proved only by a path differing between base and tip rather than by the exact published patch, publication recovery still has no supported path once the journal is `completed` and retirement failed, and forced worktree removal is neither atomic with its cleanliness checks nor proof that the member process stopped. Acceptance item 3 additionally needs the verifier to cross-check a live report against primary transcript bytes and schema-2 authority state. Neither item 2 nor item 3 is claimed.

- Implementation authorization: 「@docs/plan/backlog/373-run-parent-direct-plans-in-member-sessions.md @docs/plan/backlog/374-publish-and-verify-separate-session-plan-results.md の実装作業をせよ。本セッションはオーケストレーターとして動き、作業はサブエージェントを用意して作業させよ。」 After plan 373 reached its checked archive the owner reviewed a corrected assessment of this plan and chose to run activation, implementation and validation now, stopping before the live two-session demonstration.
- Activation baseline: 7fa0c91aa5104ab0353554641a6e7c5918363b21 on dev in temp_project. The active index was empty and predecessor 373 resolves to docs/plan/checked/2026/09/16-31/373-run-parent-direct-plans-in-member-sessions.md, so both integration gates now name exact checked archives. Promotion changes no approved scope, decision or acceptance text.
- Corrected start assessment: an earlier report treated this plan as unstartable because the required-evidence record binds "its exact live acceptance digest" before implementation begins. That digest is the SHA-256 of the third acceptance item text, sha256:78d5a40ddf9da07975330961711334ee747e8bdf119961e1373ab28b57c42411, which the plan already fixes and which the completion witness map already cites. It is therefore available at activation. The group and report digests are the values the same decision defers to a later append. Implementation is not blocked; completion is.
- Live acceptance remains outstanding. Deterministic work covers acceptance items 1, 2 and 4 and the read-only verifier that item 3 needs, but item 3 also requires two real operator-started sessions with overlapping implementation intervals and runtime-provided transcript bytes. This plan stays in_progress after the implementation commit and is not checked until that demonstration passes.
- Writable delegation stays refused because `implementation_risk` is `high`. Implement through bounded parent-direct execution with an external execution ledger and independent review, exactly as this plan's Decisions require. Read-only helpers may reduce context; they hold no write scope.

- Owner authorization: 「提案の方針でプランを作成せよ。」 The accepted proposal assigns one plan to each separate session/worktree, initially two independent members, one integration owner and real-session acceptance. This turn authors plans only.
- Planning baseline: 6dfb0167b26906a0d47bbf9f621c47cb8b19d4ba in temp_project. Plan 360 occupies the runnable slot. Queue this work without changing that task or reopening a stopped run.
- Tier 2 and class C apply because execution ownership and lifecycle authority change. Recheck scope and specifications before promotion. These are new plans, not reconstruction successors.
- Local evidence: .agent-artifacts/parallel-session-planning/. The disposable Git prototype and prior 16 passing GroupedExecutionAdapterTests prove bounded mechanics only; actual two-session runtime acceptance is not yet established.
- Independent plan review identified review-slot exhaustion and an optional-live-report bypass. The plans reserve integration review capacity and bind live evidence before implementation; primary runtime transcript evidence remains required. Parent accepted these bounded corrections without changing the user outcome.
- A bounded independent rereview confirmed all three document findings closed. The main session owns final scope, dependency checks, validation and publication; helpers held no write scope.
