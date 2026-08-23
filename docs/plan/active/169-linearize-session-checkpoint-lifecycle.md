# Linearize session checkpoint lifecycle

status: in_progress
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
primary_invariant: one predecessor execution boundary issues one checkpoint identity that exactly one different observed root session may consume
write_scope:
  - scripts/plan-execution-state.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - tests/test-plan-execution-state.py
  - tests/test-sandboxed-plan-worker.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/168-verify-runtime-session-resource-evidence.md
  - docs/plan/replanned/2026/08/16-31/132-checkpoint-plan-session-resources.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-sandboxed-plan-worker.py
  - git diff --check
validation:
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - At checked, replanned, repair-required, replan-required, and authoritative-failure boundaries, emit and verify one bounded digest-linked session checkpoint before another numbered plan or reviewer context continues; keep final authority in the parent and never treat a resource checkpoint as a semantic failure.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:7ed675c8fc9df790c90252aa2b4ee1afd1063270c97e9adc9a204b62a7442bfa","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
replan_source: docs/plan/active/132-checkpoint-plan-session-resources.md
replan_contract: docs/plan/replanned/contracts/132-checkpoint-plan-session-resources.json
integration_gates:
  - Plan 168 must be checked and its exact checked archive must replace the active context path before implementation
  - issue and consume checkpoint identities through the predecessor ledger rather than mutable checkpoint-file state
  - Plan 170 must start in a different directly observed root session after this plan is checked
successor_plans:
  - docs/plan/active/168-verify-runtime-session-resource-evidence.md
  - docs/plan/active/169-linearize-session-checkpoint-lifecycle.md
  - docs/plan/active/170-bind-review-context-to-candidate-lifecycle.md
  - docs/plan/active/171-integrate-session-resource-boundaries.md
inherited_acceptance_digests:
  - sha256:7ed675c8fc9df790c90252aa2b4ee1afd1063270c97e9adc9a204b62a7442bfa
checked_summary_ja: checkpointの発行と消費を先行実行台帳へ一度だけ記録する。

## Decisions

- Keep the checkpoint file immutable and make the predecessor execution ledger authoritative for issuance and consumption.
- Bind issuance to the exact pre-issuance event-chain digest and consumption to one successor genesis identity.
- Require verified runtime evidence from Plan 168 for both predecessor and successor root-session identities.
- Keep missing identity as a staged-path stop without changing semantic plan state.

## Tasks

- [ ] Define ledger events and replay-safe checkpoint identity.
- [ ] Enforce one issuance and one successor claim across copied checkpoint files.
- [ ] Gate candidate and parent-direct successor starts on verified distinct root sessions.
- [ ] Add terminal-boundary, crash-recovery, copy-replay, same-session, and not-observed tests.
- [ ] Run focused validation, independent review, authoritative validation once, archive, and commit.

## Validation Notes

- Plan 132 rereview proved that mutable per-file claims do not prevent copied checkpoints from being consumed twice.
