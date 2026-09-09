# Bind journal replacement identity

status: checked
implementation_tier: 2
primary_invariant: recovery accepts a replacement only when its content, target mode, and transaction-created file identity match the journaled operation at every apply, rollback, roll-forward, and completion boundary
replan_sources:
  - docs/plan/active/207-preserve-canonical-lifecycle-bytes.md
  - docs/plan/active/208-bind-journal-replacement-identity.md
replan_contract: docs/plan/replanned/contracts/207-preserve-canonical-lifecycle-bytes.json
integration_gates:
  - combined successors must satisfy every source acceptance item
  - activate only after Plan 215 is checked and its exact checked archive replaces both the active predecessor and the active context reference
  - preserve the source recovery boundary and the same-user threat-model limit without widening either claim
  - preserve all checked schema, acceptance, lifecycle, overlay, and historical-byte checks
  - keep root and generated restructure commands byte-identical
  - Plan 210 remains deferred until this plan is checked and its exact checked archive is bound
successor_plans:
  - docs/plan/active/215-enforce-canonical-lifecycle-verification.md
  - docs/plan/active/216-bind-journal-replacement-identity.md
inherited_acceptance_digests:
  - sha256:497235095714aaf76aa07e63f8c77582f7c0ad51c815a88836b01c99a1417383
integration_source_ids:
  - 208
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/209-enable-direct-active-source-reconstruction.md
  - docs/plan/replanned/2026/08/16-31/208-bind-journal-replacement-identity.md
  - docs/plan/checked/2026/08/16-31/215-enforce-canonical-lifecycle-verification.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 -m py_compile scripts/restructure-plan.py template/.project-agent-workflow/scripts/restructure-plan.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Bind every journaled replacement to its target mode and transaction-created file identity through apply, rollback, roll-forward, and durable completion.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:497235095714aaf76aa07e63f8c77582f7c0ad51c815a88836b01c99a1417383","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/215-enforce-canonical-lifecycle-verification.md
checked_summary_ja: journal replacementのtarget modeとtransaction生成file identityをrecoveryの全段階へ拘束する。

## Decisions

- Journal replacement identity means the target mode and the transaction-created temporary and renamed-file identity bound to each journal operation and reverified throughout recovery.
- Bind the exact target mode before temp creation and reject any operation or recovered target with a different mode.
- After each transaction temp is created, record its regular-file type, device, inode, mode, link count, and content digest before it can be renamed.
- After rename, require the target to retain the recorded temp identity; same-content replacement by another inode is not idempotent completion.
- Record and verify separately any transaction-created rollback replacement identity rather than accepting content equality as proof of restoration ownership.
- Make roll-forward, rollback resumption, commit-point verification, and final durable verification reject missing, stale, impossible, or externally replaced identities.
- Preserve confinement, symlink, hard-link, stale-HEAD, dirty snapshot, fsync, phase monotonicity, and exact journal-path checks.
- Keep the guarantee bounded to transaction-created file identity and the repository's existing same-user threat model.
- Build on the canonical lifecycle verification accepted by Plan 215 without replacing or weakening it.
- Use bounded parent implementation and fresh independent review because this plan changes crash recovery and filesystem identity handling.

## Tasks

- [x] Extend the operation and journal state with target-mode and transaction-created identity evidence.
- [x] Enforce identity transitions during temp preparation, rename, rollback restoration, replay, and completion verification.
- [x] Add same-content inode swap, mode drift, temp replacement, post-rename replacement, interrupted rollback, and interrupted roll-forward tests.
- [x] Align the root and generated Plan Workflow policy with the enforced recovery identity.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, then archive and commit this plan.

## Validation Notes

- This successor owns final acceptance of the original Plan 208 requirement.
- The guarantee must not claim protection against an actor that can replace every local process and file.
- Plan 210 depends on this plan and stays deferred until this plan's exact checked archive is bound.
- Independent review returned zero High and zero Medium findings across an initial review and two rereviews.
- The reviewer probed twenty-one crash windows plus three injected crash points the harness does not simulate.
- Every new guard was mutation-verified; redundant guards were mutated as a set because removing one alone leaves the suite green.
- A producer-side unsafe target mode check rejects setuid, setgid, sticky, and world-writable modes before any journal exists, closing a producer and reader asymmetry that could otherwise strand an unrecoverable journal.
- Rejecting an unsafe mode is preferred over masking because the rollback path derives its mode from the original mode, so masking only the target mode would relocate the same defect to rollback.
- The interrupted roll-forward case required by the test task also asserts that recovery rejects before the journal advances, because five downstream guards emit the same message and would otherwise mask the replaying guard.
- The recorded temporary identity is protected by three redundant guards, kept deliberately as defence in depth.
