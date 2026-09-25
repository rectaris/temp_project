# Align completion paths with one verified obligation result

status: shelved
shelved_reason: Owner instruction 2026-09-25: 374 以外の関連プランはすべて棚上げして良い. Never started; its completion-path and Copier alignment work returns to a plan 374 successor.
shelved_at: 2026-09-25
primary_invariant: Every completion path in the root repository and in the generated template reaches the same verified live-evidence obligation result, and project-owned bytes survive installation and Copier update without any command reading private evidence.
replan_sources:
  - docs/plan/active/370-preserve-live-evidence-obligations-across-descope.md
replan_contract: docs/plan/replanned/contracts/370-preserve-live-evidence-obligations-across-descope.json
successor_plans:
  - docs/plan/active/361-verify-evidence-records-against-parent-owned-authority.md
  - docs/plan/active/375-align-completion-paths-with-one-verified-obligation-result.md
inherited_acceptance_digests:
  - sha256:5476865eb4ad67917497ac0a208a8caf86458a028e3a183f4abce8f335898900
  - sha256:a64668ab97129eb85cf951c24c8b5e5204b4716b53504f1d02d90c80a2dd6635
  - sha256:57272969571ee919aa4c719ccef9344845bd847c61a7af4b9e105c0a50b84d8a
  - sha256:59b81ceb6885ea9ea1fd16a7e251a24f6fe5ef92f7d0d563d3e783e214b61b07
integration_source_ids:
  - 370
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
  - {"evidence":"On the plan 370 branch the difference against dev names only the verifier pair and its two test files, so the lifecycle completion commands, the workflow and logging specifications, the orchestration reference and the Copier fixtures were never changed by any plan 370 epoch and this work remains entirely unstarted.","kind":"reproduced_defect"}
  - {"evidence":"The completion, finalization and agent-completion commands already call the verifier require entrypoint, so the verified obligation result reaches each completion path through an existing call site rather than a new mechanism.","kind":"existing_mechanism"}
  - {"evidence":"The Copier template alignment check already enforces byte alignment between root and generated copies and fails on drift, so the alignment condition has an existing deterministic witness.","kind":"existing_mechanism"}
  - {"evidence":"The four source acceptance items and their digests move to this successor unchanged; only the implementation boundary changes, because the verifier internals move to plan 361.","kind":"mechanical_transformation"}
completion_conditions:
  - Each source completion command refuses while the plan live-evidence obligation is unresolved, and accepts only after either verified real-session evidence or the verified transfer.
  - Each destination completion command keeps the transferred live requirement unmet regardless of manifest edits, removed fields or report environment variables.
  - Root commands, the workflow and logging specifications and the orchestration reference state the same obligation rules as their generated template copies, byte for byte where the template is a copy.
  - Registered Copier fixtures assert that project-owned plan, group, configuration and history bytes survive installation and update, and read no private evidence.
completion_witness_map:
  - {"condition_sha256":"sha256:c39231fa881c3d995d81fb5d9a5b50e8248eed565c38e8f662a87667cb2f9c95","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:01f7566fd3113c7171cb44806d55cc2ae6a01343b892e886d49f1ec19be68fdc","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:f6e6315461759444f448ff3a6c178d149229083eccc8f8616833b486efd7b15d","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:8fae99d702565fe2e3606cf040f00886f3907a8e9f4da707ad3281785d8ae9fe","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - scripts/check-agent-completion.sh
  - template/.project-agent-workflow/scripts/check-agent-completion.sh
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - tests/validation_tools/generated.py
  - tests/smoke.sh
  - tests/copier-update.sh
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - scripts/verify-parallel-plan-sessions.py
  - scripts/plan-execution-state.py
  - docs/plan/active/361-verify-evidence-records-against-parent-owned-authority.md
  - docs/plan/replanned/2026/09/16-31/370-preserve-live-evidence-obligations-across-descope.md
  - docs/plan/replanned/2026/09/16-31/374-publish-and-verify-separate-session-plan-results.md
  - docs/plan/backlog/378-verify-live-parallel-session-results.md
  - docs/agent/spec-index.yaml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
acceptance:
  - Original required-evidence bytes and their execution reservation remain verifiable at their canonical private identity; absence, replacement or a forged reservation refuses rather than being recreated as historical evidence.
  - A single verified owner-authorized acceptance transfer preserves the original record and stopped ledger, accounts for the exact deferred item at one destination and supports only exact idempotent crash recovery.
  - Every source completion path requires either valid live evidence or the verified transfer, and every destination completion path retains the unfulfilled live requirement independently of manifest edits or report environment variables.
  - Root/generated commands and policy remain aligned and register Copier fixtures asserting preservation of project-owned plan, group, configuration and history bytes without touching private evidence.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:5476865eb4ad67917497ac0a208a8caf86458a028e3a183f4abce8f335898900","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:a64668ab97129eb85cf951c24c8b5e5204b4716b53504f1d02d90c80a2dd6635","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:57272969571ee919aa4c719ccef9344845bd847c61a7af4b9e105c0a50b84d8a","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:59b81ceb6885ea9ea1fd16a7e251a24f6fe5ef92f7d0d563d3e783e214b61b07","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Start only after plan 361 is checked and published; this plan reads the verifier as context and must not modify it or its two test files.
  - Retain the four source acceptance items of plan 370 verbatim and prove the combined result of plans 361 and 375 against them; this plan owns integration for plan 370.
  - Do not execute a transfer against plans 374 or 378, edit those plans, mutate their private evidence or resume their stopped execution.
  - Treat a completion path that still accepts a manifest edit or report environment variable as a waiver as a stop condition, not a documentation gap.
checked_summary_ja: すべての完了経路と生成テンプレートが一つの検証済み義務結果を参照するようにし、導入と更新で利用者所有のバイト列が保たれることを検査で保証する。

## Decisions

- This successor retains the four plan 370 acceptance items verbatim and is the single integration successor for that source.
- Its write scope holds only files that no plan 370 epoch ever changed, so it is disjoint from the plan 361 implementation and can be reviewed without re-reading the verifier diff.
- It stays deferred until plan 361 is checked, because its completion-path tests must run against the accepted verifier rather than against rejected bytes.
- No integration-only plan is created; this product-changing successor owns the final integration verification and runs the authoritative suite itself.

## Tasks

- [ ] Confirm plan 361 is checked and published, then start this plan's execution ledger and pass the review-route gate.
- [ ] Make each source completion command refuse while the live-evidence obligation is unresolved and accept only on verified evidence or the verified transfer.
- [ ] Make each destination completion command retain the transferred live requirement against manifest edits, field removal and report environment variables.
- [ ] Align the root commands, the workflow and logging specifications and the orchestration reference with their generated template copies.
- [ ] Register Copier fixtures asserting preservation of project-owned plan, group, configuration and history bytes during installation and update, without reading private evidence.
- [ ] Run the focused commands, bind an exact-target adversarial preflight and one independent review, then run the authoritative suite once.
- [ ] Prove the four retained plan 370 acceptance items against the combined result of plans 361 and 375, then commit, publish and archive.

## Validation Notes

- Source failure: plan 370 exhausted its four-review maximum at epoch 3 and stopped at replan_required with reason code multiple_independent_invariants.
- Owner continuation authorization: 「提案の方針で後続プランを作成せよ。」
- Plan 370 never changed any file in this write scope, so this is unstarted work carried forward rather than a retry of a rejected candidate.
- Plan 370 recorded four out-of-scope defects in its own Validation Notes. Re-read them before review and route any that fall inside this write scope into this plan.
