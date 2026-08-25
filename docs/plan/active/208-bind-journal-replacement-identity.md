# Bind journal replacement identity

status: deferred
completion_deferred_reason: Plan 207 must be checked and its exact checked archive path must replace the active predecessor before implementation.
primary_invariant: recovery accepts a replacement only when its content, target mode, and transaction-created file identity match the journaled operation at every apply, rollback, roll-forward, and completion boundary
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
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/200-enable-coupled-lineage-reconstruction.md
  - docs/plan/active/207-preserve-canonical-lifecycle-bytes.md
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
  - docs/plan/active/207-preserve-canonical-lifecycle-bytes.md
integration_gates:
  - begin only from the exact checked Plan 207 archive and a clean worktree
  - preserve all checked schema, acceptance, lifecycle, overlay, and historical-byte checks
  - keep root and generated restructure commands byte-identical
  - Plan 209 remains deferred until this plan is checked and its exact checked archive replaces the active predecessor
checked_summary_ja: journal replacementのmodeとtransaction生成file identityをrecovery全段階へ拘束する。

## Decisions

- Journal replacement identity means the target mode and transaction-created temporary and renamed-file identity bound to each journal operation and reverified throughout recovery.
- Bind the exact target mode before temp creation and reject any operation or recovered target with a different mode.
- After each transaction temp is created, record its regular-file type, device, inode, mode, link count, and content digest before it can be renamed.
- After rename, require the target to retain the recorded temp identity; same-content replacement by another inode is not idempotent completion.
- Record and verify separately any transaction-created rollback replacement identity rather than accepting content equality as proof of restoration ownership.
- Make roll-forward, rollback resumption, commit-point verification, and final durable verification reject missing, stale, impossible, or externally replaced identities.
- Preserve confinement, symlink, hard-link, stale-HEAD, dirty snapshot, fsync, phase monotonicity, and exact journal-path checks.
- Use bounded parent implementation and fresh independent review because this plan changes crash recovery and filesystem identity handling.

## Tasks

- [ ] Extend the operation and journal state with target-mode and transaction-created identity evidence.
- [ ] Enforce identity transitions during temp preparation, rename, rollback restoration, replay, and completion verification.
- [ ] Add same-content inode swap, mode drift, temp replacement, post-rename replacement, interrupted rollback, and interrupted roll-forward tests.
- [ ] Align the root and generated Plan Workflow policy with the enforced recovery identity.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 209 with this plan's exact checked archive as predecessor.

## Validation Notes

- The guarantee is bounded to transaction-created file identity and the repository's existing same-user threat model.
- This plan must not claim protection against an actor that can replace every local process and file.
