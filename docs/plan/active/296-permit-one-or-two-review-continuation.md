# Permit continuation after one or two prior formal reviews

status: in_progress
primary_invariant: One owner-authorized epoch-1 continuation may consume an otherwise eligible stopped parent-remediation execution after one or two prior formal reviews without changing the stopped ledger, the per-epoch review limit, the cumulative ceiling, or any other eligibility boundary.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The canonical stopped Plan 254 epoch has one formal review and satisfies every continue_state predicate except the exact-two-review check.","kind":"reproduced_defect"}
  - {"evidence":"The existing continuation epoch records predecessor_review_count and already enforces epoch 1, two reviews per epoch, a four-review ceiling, unchanged identities, one registry consumption and replay refusal.","kind":"existing_mechanism"}
  - {"evidence":"The root and generated execution-state scripts are byte-identical and the plan-workflow review-budget sections are checked after the mechanical generated-path rewrite.","kind":"mechanical_transformation"}
completion_conditions:
  - The continue command admits a canonical epoch-enabled parent_remediation_budget_exhausted predecessor with no open attempt and either one or two formal reviews, while zero reviews and every previously ineligible stop or identity remain rejected before a child is admitted.
  - An epoch-1 child records the exact predecessor formal-review count of one or two, still permits at most two reviews in that epoch, retains the encoded cumulative ceiling of four, and cannot create epoch 2.
  - Root and generated execution-state implementations and the enforced review-budget policy sections remain aligned, and authoritative validation remains unchanged.
  - The root policy checker rejects review-budget policy that does not state that exactly one or two prior formal reviews are required for the otherwise eligible continuation.
completion_witness_map:
  - {"condition_sha256":"sha256:9ac15a992b1f2d84bb97013e1906d2332649192713fda3aab391ebf0119bd599","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:1494a0272d9d4afce6be688396fcc48723f73fcf1dcb3c440a7dd99e3d8452e1","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:2903cc768ffbc586d523c81f0c0dddfe1fdb4b0f92afe783787263cf41c6a4a6","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:9c0c12995e22ff9a145b832d870b950496c78dcff7887c695fc1600c625e2a02","witness":"python3 scripts/check-root-agent-policy.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/check-root-agent-policy.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/plan/active/254-preserve-identical-human-report-supersede.md
  - docs/plan/checked/2026/09/01-15/286-install-same-plan-continuation-epochs.md
  - docs/plan/backlog/273-stop-indivisible-tier-one-work-without-descope.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/check-root-agent-policy.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Permit the existing one-time epoch-1 continuation after one or two prior formal reviews only when every other stopped-ledger, identity, registry, plan, source, invariant and implementation-mode predicate is unchanged.
  - Preserve the exact prior review count in the child, two reviews per epoch, the cumulative four-review authorization ceiling, the epoch-1 limit, stopped-ledger immutability and replay resistance.
  - Keep root and generated lifecycle policy and execution-state tooling mechanically aligned without weakening the authoritative validation suite.
  - Make the existing root policy checker enforce the one-or-two prior-review eligibility boundary rather than relying on root/template text equality alone.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:cf2b4736dc36be835e0e7d5857229cc8edf69a39c4d9915b0904e1aca6bba8b0","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:20d464068ceee129a593b71b25abf87ba3e3e64952bc9dda8e1f90e5e6d27e1e","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:b9d6c4e04d99dfb0224a9a8b105fb0ed9eeaa6c81127ec258edcf8c05c7958ef","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:b28e2ee2740e4ae8d62879c64a51d1499cb0062293aeedeedbb329fede011c70","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
integration_gates:
  - Implement this lifecycle prerequisite in its own task worktree and publish it before creating any continuation child for Plan 254.
  - Keep the current stopped Plan 254 ledger and its one-review evidence byte-identical; this plan changes future command eligibility, not historical bytes.
  - Admit only a formal-review count in the closed interval from one through the existing per-epoch limit; do not infer eligibility from an owner quotation alone.
  - Preserve every existing exact plan, source HEAD, primary invariant, implementation mode, stop reason, open-attempt, registry identity, predecessor identity, authorization, replay, and epoch-limit check.
  - Keep CONTINUATION_AUTHORIZATION_SCHEMA_VERSION and the authorization object's cumulative_review_limit value unchanged at four.
  - Store the actual predecessor formal-review count in the epoch-1 event and validate that value as one or two; do not rewrite it to two.
  - A one-review predecessor can therefore reach at most three actual formal reviews because epoch 1 retains its two-review limit and epoch 2 remains unavailable.
  - Use bounded parent-direct implementation because implementation_risk is high; the existing policy cannot authorize its own behavior change through the sandboxed worker.
  - Run an adversarial preflight bound to the exact policy candidate before formal independent review, and run the authoritative validation suite exactly once for an otherwise accepted candidate.
checked_summary_ja: 正式レビューが一回または二回ある停止済み実行を、既存の上限内で一度だけ継続できるようにする。

## Decisions

- A canonical epoch-enabled execution ledger whose state is descope_pending, whose sole reason is parent_remediation_budget_exhausted, whose writable attempt is closed, and whose formal-review count is one or two.
- The epoch-1 execution ledger created from the exact immutable stopped predecessor and bound to the existing registry, unchanged plan and source identities, and actual predecessor formal-review count.
- At most two formal reviews in epoch 1, with the authorization field still capped at four cumulative reviews and no epoch after epoch 1; a one-review predecessor therefore permits at most three actual reviews overall.
- A ledger with zero formal reviews, no execution-epoch record, another stop reason, an open writable attempt, changed plan or source identity, epoch 1 already reached, or a consumed predecessor identity.
- Do not change admission, descope, reconstruction, or other stop-state transitions.

## Tasks

- [ ] Add focused continuation fixtures for one prior review and zero prior reviews while retaining the existing two-review, replay, identity and epoch-limit cases.
- [ ] Generalize only the predecessor formal-review count check and continuation-epoch validation to accept one or two, then mirror the execution-state script exactly.
- [ ] Update the root and generated review-budget policy wording and make the existing root policy checker enforce the new one-or-two boundary without changing authoritative validation or unrelated lifecycle rules.
- [ ] Run exact-target adversarial preflight, independent review, focused validation and the authoritative suite, then archive and publish this prerequisite before resuming Plan 254.

## Validation Notes

- Owner continuation authorization: 「完了させるためにプランを修正し、作業せよ。」
- Full decision audit: .agent-artifacts/decision-audits/early-review-continuation.md.
- Required referent contract: .agent-artifacts/referent-contracts/early-review-continuation.json.
- The current Plan 254 product diff and stopped execution ledger remain untouched while this prerequisite is authored and implemented.
