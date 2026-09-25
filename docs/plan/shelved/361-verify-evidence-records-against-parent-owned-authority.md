# Verify evidence records against parent-owned authority

status: shelved
shelved_reason: Owner instruction 2026-09-25: 374 以外の関連プランはすべて棚上げして良い. Stopped at replan_required with security_boundary_drift after two epochs; plan 374 is now reconstructed directly and its write scope already covers the mechanism this plan could not reach.
shelved_at: 2026-09-25
implementation_mode: parent_direct
primary_invariant: Every value the required-evidence, transfer and live-evidence gates treat as authority is read from a parent-owned record that the reporting session cannot author, relocate or replay; a reporter-controlled field never decides a gate outcome.
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
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The epoch-3 independent review recorded one High and two Medium findings, all inside scripts/verify-parallel-plan-sessions.py: group execution verification omits the session-state authority check, concurrency spans ignore the session binding digest and generation, and the verify entrypoint accepts a group-state argument without reaching the group authority path.","kind":"reproduced_defect"}
  - {"evidence":"The rejected epoch-3 implementation is preserved outside the repository as a dev-relative patch with digest sha256:b1da3d4d3fe89c2bbfec83562097de94c1ce889ab469786817cf6f910e4f881a; this plan re-applies it onto the published baseline instead of inheriting uncommitted bytes.","kind":"bounded_prototype"}
  - {"evidence":"The session-state authority check, the authoritative group resolver and the group authority verifier already exist in the verifier and are called on the bind path, so the three findings are reached by routing the remaining entrypoints through them rather than by adding a new mechanism.","kind":"existing_mechanism"}
  - {"evidence":"All three focused commands passed on the preserved epoch-3 patch before the review: 277 unit cases, the root plan lifecycle script and the Copier template alignment check.","kind":"existing_mechanism"}
completion_conditions:
  - Group execution verification resolves group state through the canonical parent-owned location and the repository common Git identity before any binding is read, and refuses state assembled anywhere else.
  - Concurrency spans derive only from events that match the final authoritative session binding digest and generation, so a serial stop-and-resume sequence cannot satisfy the overlap requirement.
  - The verify entrypoint reaches the same group authority and group execution checks as bind, so serial publication with fabricated group identifiers refuses instead of passing.
  - Root and generated verifier bytes stay identical, and the restored reservation, binding and inspection entrypoints keep the original private record and stopped ledger unrewritten.
completion_witness_map:
  - {"condition_sha256":"sha256:06c543a4a7f73a0fa2ec8e41bba1971991f8436655ecaa5c2e0838b66af0be2f","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:e26536066d1e72bb9cd0a901f9c6f9ef90d3901d60f4ebf58709ddcd1ed2418a","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:2fa5180a9ae93255433473b60880e590a9cc3e585455465a0d97e73706762517","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:85496e0b95c00c5725a8289d2d292d32086d5cc5d0009a9aeae918d16bb5abbd","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/verify-parallel-plan-sessions.py
  - template/.project-agent-workflow/scripts/verify-parallel-plan-sessions.py
  - tests/test-sandboxed-plan-worker.py
  - tests/root-plan-lifecycle.sh
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - scripts/plan-execution-state.py
  - scripts/project_workflow/worktree_guard.py
  - scripts/complete-plan.sh
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
  - python3 tests/test-sandboxed-plan-worker.py
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Original required-evidence bytes and their execution reservation remain verifiable at their canonical private identity; absence, replacement or a forged reservation refuses rather than being recreated as historical evidence.
  - A single verified owner-authorized acceptance transfer preserves the original record and stopped ledger, accounts for the exact deferred item at one destination and supports only exact idempotent crash recovery.
  - Every source completion path requires either valid live evidence or the verified transfer, and every destination completion path retains the unfulfilled live requirement independently of manifest edits or report environment variables.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:5476865eb4ad67917497ac0a208a8caf86458a028e3a183f4abce8f335898900","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:a64668ab97129eb85cf951c24c8b5e5204b4716b53504f1d02d90c80a2dd6635","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:57272969571ee919aa4c719ccef9344845bd847c61a7af4b9e105c0a50b84d8a","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
integration_gates:
  - Re-apply the preserved epoch-3 patch onto the published baseline as the starting implementation, preserve its external bytes as provenance, and start a fresh parent-direct execution ledger; the reconstruction separates two coupled invariants and does not reopen any stopped plan 370 ledger.
  - Do not execute a transfer against plans 374 or 378, edit those plans, mutate their private evidence or resume their stopped execution. Exercise effects only in isolated fixtures.
  - Leave the lifecycle completion commands, the workflow and logging specifications, the orchestration reference and the Copier fixtures to plan 375; this plan changes only the verifier and its two test files.
  - Treat any remaining entrypoint that accepts a reporter-controlled value as authority as a stop condition, not a finding to defer to plan 375.
checked_summary_ja: 証拠記録と移管の判定を親所有の記録だけに依拠させ、報告者が制御できる値が単独でゲートを通過しないようにする。

## Decisions

- Plan 370 coupled two independently validatable invariants: whether the evidence records themselves can be trusted, and whether every completion path and the generated template consult one verified result. This plan keeps the first; plan 375 keeps the second.
- The rejected plan 370 implementation puts both invariants in one file, so dirty-path promotion would bind the whole reconstruction to a single successor and defeat the split. The owner authorized preserving that work as an external patch instead, so this plan re-applies it and inherits the three open epoch-3 findings, which all sit in that file.
- The recurring defect across four reviews was a gate accepting an input the reporting session controls. That is recorded as acceptance item three rather than as a task, so a candidate that leaves any such entrypoint cannot be accepted.
- Acceptance items one and two keep the substance of source items one and two; source item three and four move to plan 375, which retains the source text and owns integration.

## Tasks

- [ ] Start the successor parent-direct execution ledger at the published baseline and pass the review-route gate before any product write.
- [ ] Route group execution verification through the parent-owned session-state authority check so state assembled outside the canonical location refuses.
- [ ] Derive concurrency spans only from events matching the final authoritative session binding digest and generation.
- [ ] Route the verify entrypoint through the same group authority and group execution checks as bind, and cover the serial-publication case in the lifecycle test.
- [ ] Audit every remaining entrypoint for reporter-controlled values used as authority and close each one before requesting review.
- [ ] Run the three focused commands, then bind an exact-target adversarial preflight and one independent review.
- [ ] Run the authoritative suite once after review clears High and Medium findings, then commit, publish and archive.

## Validation Notes

- Source failure: plan 370 exhausted its four-review maximum at epoch 3 with one High and two Medium findings and stopped at replan_required with reason code multiple_independent_invariants.
- Owner continuation authorization: 「提案の方針で後続プランを作成せよ。」
- The preserved epoch-3 patch already passes all three focused commands; the review rejected it for the three findings above, not for validation failure. Verify its digest before applying and treat any apply conflict as a stop, not a reason to drop source changes.
- Plan 370 recorded four out-of-scope defects in its own Validation Notes. Re-read them before review and route any that fall inside this write scope into this plan rather than deferring them silently.
- Epoch 0 (`plan-361-parent-direct-001`) ran one parent review that returned High, Medium and Low findings. The single parent-direct remediation round was spent, so the run stopped at `descope_pending` with reason code `parent_remediation_budget_exhausted`.
- Epoch 1 (`plan-361-parent-direct-002`) was opened under owner continuation authorization with a cumulative review limit of four. The route gate and the exact-target adversarial preflight passed, and the three focused commands passed on the epoch-1 candidate.
- The epoch-1 independent review did not approve. It returned three High findings and one Medium finding: the supplied candidate hashes to `sha256:1f72df3d5144d27f73096cd111aa9645b84e1da487110b41356f5c542d360d2e` while the review packet and preflight bind `sha256:c8d4bc267fafa106b7cc6cfc46f860955d2b4ce321556c7865ab2a7f01f938cd`; the transfer path records the descope event itself as `owner_authorization_digest` instead of separately authenticated owner authorization; default `verify` still accepts a canonical record that no parent reservation authenticates; and no published command can create the reservation that a transfer now requires.
- The three substantive findings all require a parent-owned reservation and authorization mechanism in `scripts/plan-execution-state.py`, which this plan's `write_scope` does not contain. Acceptance items one and two therefore cannot be satisfied inside the declared boundary, so the run was stopped at `replan_required` with reason code `security_boundary_drift` rather than widening the scope.
- The epoch-1 candidate bytes remain dirty in the bound task worktree and are preserved outside the repository at `plan-361-parent-direct-epoch1/candidate.patch`, whose digest equals the worktree diff. They are rejected work, not accepted implementation.
- Both ledger runs are stopped and must not be reopened. Reconstruction into successors, or shelving, is an owner decision.
