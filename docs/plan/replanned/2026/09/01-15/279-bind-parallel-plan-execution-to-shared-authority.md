# Bind independent parallel plan execution to parent-owned authority

status: replanned
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
  - {"kind":"existing_mechanism","evidence":"plan-execution-state.py require_repository_baseline binds HEAD, plan and invariant digests; successor claims, attempt locks, reviewer registry and bounded event validation already provide the serial authority primitives."}
  - {"kind":"existing_mechanism","evidence":"check-root-agent-policy.py rejects multiple in_progress index rows, and the sequential orchestrator selects exactly one runnable row. Parallel admission therefore needs an explicit additional path, not a relaxed legacy selector."}
  - {"kind":"existing_mechanism","evidence":"Worker contracts and candidate manifests already bind repository, plan, source HEAD and attempt identity; their current exact schemas have no parallel-member or baseline-transfer authority and can be preserved under versioned dispatch."}
completion_conditions:
  - Only a committed, parent-admitted group description naming exact numbered member plans permits grouped execution; ungrouped or ambiguous multiple runnable rows, unsatisfied predecessors and known overlapping write scopes remain rejected.
  - A parent-owned external record binds repository, target and member identities, preserves one upstream claim and one publication owner across worktrees, and refuses duplicate or replayed member and final-successor claims with bounded crash recovery.
  - A logical member keeps at most one initial generation, one correction and two independent reviews across every workspace, baseline transfer, session and availability fallback; other independent members have their own bounded budgets.
  - A source-baseline transfer consumes an exact prior member state, carries its counters, stop state and canonical reviewer-registry proof, and binds a fresh candidate identity without rewriting old evidence or reopening a stopped run.
  - Direct root and generated completion or finalization of an enrolled member is refused before the grouped adapter exists and before that adapter can prove verified publication; ungrouped lifecycle behavior is unchanged.
  - Legacy ledger, checkpoint and review-receipt formats retain their exact historical interpretation and all existing stop, review and successor-claim protections.
  - Ungrouped plan manifests and default sequential selection retain their existing validation and single-runnable behavior.
  - Root and generated authority commands, group parsing and policy remain mechanically aligned in the install inventory.
completion_witness_map:
  - {"condition_sha256":"sha256:21f5c3a49ba1abf199454173a967e3c5879face34e0f6dae7062c2b8b47bf703","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:0374647130d04cb6b11b7724f2a7d99a0f3504d152164f5ea141721d56484474","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:0f14e5ebfd1caac4fe80cf060f274db40f8583089a15821b867d8ab2079e7f67","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:6ff1f8a98d626bff8e517ad5731d04e26c7fa518de97d6af6f36c310bb57ec66","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:5b3aee30e8f3cba928d28d41bea282ded1860211b5406e5a6328cc88fd5e8cbf","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:d8661ba1d35739749e3363d4684931871571df2ea00c2892fdadfc9bb4827902","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:2238bc264e7b8edc0b364074efa0fe88963b3fc233a00f233d4ae647ddafd39b","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:f753af3f887aa1373324eeee9ff260588db180e2d855e48769f72c4c8fd43951","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/parallel-plan-state.py
  - template/.project-agent-workflow/scripts/parallel-plan-state.py
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - scripts/check-root-agent-policy.py
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - tests/test-plan-execution-state.py
  - tests/validation_tools/plan.py
  - tests/validation_tools/generated.py
  - AGENTS.md
  - template/AGENTS.md.jinja
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/smoke.sh
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - tests/test-sandboxed-plan-worker.py
  - scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - tests/root-plan-lifecycle.sh
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - scripts/plan_validation_commands.py
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/plan/active/278-create-resumable-parent-worktrees.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/plan/backlog/276-run-bounded-parent-owned-candidate-preflight.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_AGENT_LOGGING.md
predecessor_plans:
  - docs/plan/active/278-create-resumable-parent-worktrees.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-validation-tools.py
  - python3 tests/test-sandboxed-plan-worker.py
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-copier-template.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Admit parallel members only through exact committed membership and parent authorization, preserving numbered-plan admission, independent scopes, resolved predecessors and the unchanged single-plan default.
  - Enforce exclusive upstream/member/publication claims and bounded state recovery across linked worktrees without allowing another clone, group, session or ledger to reuse those claims.
  - Carry each member's correction and review limits, registry admissions and every stop condition across candidate replacement and baseline transfer without resetting counters or reinterpreting historical evidence.
  - Until the versioned grouped runner is installed, legacy run, correction, validation and apply refuse an enrolled member before effects; later grouped operation requires the verified group/member permit.
  - Root and generated complete/finalize commands refuse enrolled members before the grouped adapter exists and require its verified publication evidence afterward, while preserving ungrouped completion behavior.
  - Keep existing serial schemas, checkpoints, review receipts and stopped-state interpretation unchanged for all legacy executions.
  - Keep ungrouped manifest validation and default single-runnable sequential selection unchanged.
  - Register mechanically aligned root and generated group authority commands, parsing and policy in the deterministic install inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:832f81d26c7deace802c9de03926f046dd198216ca68dcf89a853c5e56b74865","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:879b71f3e6dd97ddd2b2d989369e528f02384d28937938ff0fe63a846e0dbb14","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:0f9c0d014b019f32448829e374205ebb62c893f6e22b90e7da80c7e539b21972","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:98f5395f4ad3c77ef5f71dd8a6c0d508dd95a6579ea15b86212980fb98bc80a1","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:e20a416e2433ddeac43db7cd1ed6128c9c53c6952ed1c481491c214274d0405a","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:93c6691b05bc22afc3dc72b7601b5aeb5d67743787ab01c42d59eb915e1ac374","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:1bdd1dc3f6afb721ed95cfe35e24d4c8432051244e671db4d72ae17bdefe6f5c","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:e7329dac215ccc9c5fc2738f35b522e2c261781e34b1a8264fc938e22d68b5a0","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
primary_invariant: preserve the complete coupled source acceptance baseline
replan_sources:
  - docs/plan/active/278-create-resumable-parent-worktrees.md
  - docs/plan/active/279-bind-parallel-plan-execution-to-shared-authority.md
  - docs/plan/active/280-integrate-parallel-plan-candidates-in-order.md
replan_contract: docs/plan/replanned/contracts/278-complete-resumable-parent-worktrees.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/283-complete-resumable-parent-worktrees.md
  - docs/plan/active/284-bind-parallel-plan-execution-to-shared-authority.md
  - docs/plan/active/285-integrate-parallel-plan-candidates-in-order.md
inherited_acceptance_digests:
  - sha256:832f81d26c7deace802c9de03926f046dd198216ca68dcf89a853c5e56b74865
  - sha256:879b71f3e6dd97ddd2b2d989369e528f02384d28937938ff0fe63a846e0dbb14
  - sha256:0f9c0d014b019f32448829e374205ebb62c893f6e22b90e7da80c7e539b21972
  - sha256:98f5395f4ad3c77ef5f71dd8a6c0d508dd95a6579ea15b86212980fb98bc80a1
  - sha256:e20a416e2433ddeac43db7cd1ed6128c9c53c6952ed1c481491c214274d0405a
  - sha256:93c6691b05bc22afc3dc72b7601b5aeb5d67743787ab01c42d59eb915e1ac374
  - sha256:1bdd1dc3f6afb721ed95cfe35e24d4c8432051244e671db4d72ae17bdefe6f5c
  - sha256:e7329dac215ccc9c5fc2738f35b522e2c261781e34b1a8264fc938e22d68b5a0
checked_summary_ja: 独立した二つのプランの実行権限を親が管理し、開始コミットを変更しても各プランの回数制限と停止状態を維持する。

## Decisions

- A parent-owned durable record outside the repository binding an admitted independent plan set, member attempts, baseline changes, cumulative per-plan limits, stop states and one integration owner.
- Add explicit grouped execution instead of weakening the legacy sequential selector. A frozen committed description declares membership; the external parent record owns mutable runtime authority.
- Use separate member permits for speculative candidate generation and one parent publication lease for source effects. Candidate readiness is not formal plan completion.
- Carry limits per logical numbered member across new baseline identities. A has its own limits and B has its own; recomposing B cannot replenish B limits.
- Keep root/generated lifecycle policy aligned and keep the full audit outside active plans. Newly written group formats are versioned; existing serial and migration formats are unchanged.

## Tasks

- [ ] Add exact-shape group-description and runtime-record fixtures, including default serial behavior, duplicate/foreign members, dirty or replaced policy inputs, unresolved predecessors and known scope overlap.
- [ ] Implement bounded member enrollment, one upstream claim, exclusive member permits, canonical repository identity and one publication lease with lock order and crash recovery.
- [ ] Implement and test the single-slot parent-adjustment transition, mutual exclusion with worker correction, failure/crash retention and unchanged review counters.
- [ ] Implement an atomic baseline-transfer record that consumes the prior member authority and preserves counters, frozen requirements, registry proof and terminal states.
- [ ] Add direct legacy runner and root/generated completion refusal fixtures for an enrolled member, including completed checkboxes and forged or missing group permits.
- [ ] Extend root/generated manifest parsing and static checks for the explicit optional group-description reference while leaving ungrouped selection strict.
- [ ] Reject self-containing commit claims, changed or uncommitted group/member bytes, and source HEAD drift after admission; prove both member checkouts use the recorded containing commit.
- [ ] Test fork/replay/cross-clone/cross-worktree races, old-epoch use, event budget exhaustion, per-member review accounting, stopped transfer and exact recovery after each persistence boundary.
- [ ] Update aligned policies and Copier inventory/parity and test project-owned group-description preservation without manufacturing any live execution group in this repository.
- [ ] Run focused validation and independent review, then the authoritative suite; leave parallel runner invocation unavailable until plan 280 is checked.

## Validation Notes

- Planning baseline: `56dd79a2461acd9880f27cf7c75f62a1dad877a5` in `temp_project`.
- Owner authorization: 「この方針でプランを docs/plan/active に作成せよ。」 The owner selected the preceding proposal and A/B conflict-resolution explanation; the accepted design is approved for this bounded plan. This turn creates plans only and does not execute their product changes.
- These are new plans, not a reconstruction of a stopped source, so no historical restructuring contract, acceptance set or owner-continuation record is fabricated or changed.
- Feasibility is bounded source inspection and, where named, a disposable Git prototype run during planning. It is not a claim that the new runtime behavior or future completion witnesses already pass.
- Full decision audit and planning prototype are local evidence under `.agent-artifacts/decision-audits/parallel-plan-worktrees/`; final decisions needed for execution are stated here.
- Plan-authoring validation passed: scripts/lint-project-workflow.sh and tests/smoke.sh (exit 0). Smoke ran the generated-project scenarios; its optional GitHub Actions lint was skipped because actionlint was unavailable. These results validate plan creation and the existing repository, not the future implementation tasks.
- Parent checks passed for numbered-plan admission, actual TSV index/status/dependency mapping, exact condition/acceptance digests, declared command grammar, context existence and diff whitespace. After the final witness-only clarification, the parent reran the affected policy/manifest checks.
- Two read-only document-review rounds found authority bypass, completion-scope, accounting, baseline-self-reference and witness-boundary issues. The parent incorporated the bounded corrections and verified the final mechanical witness split; no product execution ledger was opened and no runtime implementation review is claimed.
- Implementation task checkboxes remain open, and implementation completion witnesses have not yet been established.
- Recheck the current committed baseline and exact scope before implementation; read applicable directory AGENTS.md and required specifications directly. Preserve any intervening owner changes.
- The parent owns scope admission, validation acceptance, independent-review acceptance, lifecycle, commits and reporting. Read-only helpers may supply bounded evidence; no writable helper is authorized by this planning turn.
- No measured speedup or resource saving is claimed. Root plan files describe this repository's implementation work and are not copied as product-specific plans into the reusable template.
