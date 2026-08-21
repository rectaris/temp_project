# Checkpoint plan-session resources at lifecycle boundaries

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
primary_invariant: continue another numbered plan or reviewer context only from a verified bounded checkpoint with directly observed resource evidence
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - docs/plan/
  - references/orchestration.md
  - scripts/agent-log-event.py
  - scripts/check-agent-log-manifest.py
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/import-codex-transcript.py
  - scripts/plan-execution-state.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/hooks/agent_log_manifest.py
  - template/.project-agent-workflow/scripts/agent_log_manifest.py
  - template/.project-agent-workflow/scripts/import-codex-transcript.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
  - tests/smoke.sh
  - tests/test-agent-log-event.py
  - tests/test-agent-log-manifest.py
  - tests/test-import-codex-transcript.py
  - tests/test-plan-execution-state.py
  - tests/test-sandboxed-plan-worker.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/136-integrate-plan-bound-worker-contract.md
  - docs/plan/active/114-validate-structured-worker-completion.md
  - docs/plan/active/115-classify-review-outcomes-and-sequence-writes.md
  - docs/plan/replanned/2026/08/16-31/116-evaluate-plan-worker-orchestration.md
  - docs/plan/checked/2026/08/01-15/078-plan-execution-budget-ledger.md
required_specs:
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - At checked, replanned, repair-required, replan-required, and authoritative-failure boundaries, emit and verify one bounded digest-linked session checkpoint before another numbered plan or reviewer context continues; keep final authority in the parent and never treat a resource checkpoint as a semantic failure.
  - Record provider-observed input, cached input, output, reasoning, model-response, compaction, helper-turn, and tool-call measurements only when directly available, keep unavailable values as not_observed, store no prompts or output bodies, and use deterministic proxy counts without estimating tokens.
  - Give an independent reviewer only the unchanged plan, admitted diff, bounded receipts, and applicable specifications after the candidate is otherwise review-ready; permit one initial review and one bounded rereview per candidate before the existing strategy-change path, and do not reuse an accumulated general-purpose reviewer history across numbered plans.
replan_source: docs/plan/active/116-evaluate-plan-worker-orchestration.md
replan_contract: docs/plan/replanned/contracts/116-evaluate-plan-worker-orchestration.json
integration_gates:
  - plan 136 as the accepted successor for plan 113, plus plans 114 and 115, must be checked before implementation starts
  - plan 133 must compare the checkpointed path with the unchanged baseline under the same provider observations
successor_plans:
  - docs/plan/active/130-map-acceptance-validation-witnesses.md
  - docs/plan/active/131-require-confirmed-failure-diagnosis.md
  - docs/plan/active/132-checkpoint-plan-session-resources.md
  - docs/plan/active/133-evaluate-resource-bounded-orchestration.md
inherited_acceptance_digests:
  - sha256:7ed675c8fc9df790c90252aa2b4ee1afd1063270c97e9adc9a204b62a7442bfa
  - sha256:cf0c0eaf1b20d2e1a87a62c8c9b82f72b208c16e7ed984058ce9f596df8d15a7
  - sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc
checked_summary_ja: plan境界で限定的な引継記録を作り、利用量を観測して新しい文脈から次の実行とreviewを始める。

## Decisions

- Define `session_checkpoint` as a bounded record that transfers plan and execution identity, not raw conversation content or new authority.
- Require a verified checkpoint after terminal, deferred, replan, repair, or authoritative-failure boundaries before another numbered plan or reviewer context continues.
- Store only provider-observed numeric usage with explicit observed or not_observed provenance; keep deterministic proxy counters separate and never estimate tokens.
- Start each independent review from bounded plan, diff, receipt, and specification inputs; permit one initial review and one bounded rereview per candidate.
- Treat resource thresholds as session-rollover conditions only; determine numeric promotion thresholds through Plan 133 paired evidence.
- Use bounded parent implementation and independent review because this plan changes logging, ledger, runner, and reviewer scheduling boundaries.

## Tasks

- [ ] Define and validate the checkpoint schema, identity, lifecycle boundaries, and replay protections.
- [ ] Preserve bounded provider usage and deterministic proxy counts through transcript manifests and execution telemetry.
- [ ] Gate subsequent numbered-plan and reviewer starts on a verified checkpoint without changing semantic plan states.
- [ ] Enforce fresh bounded reviewer context and the one-review-plus-one-rereview budget.
- [ ] Align root and generated policy, logging, runner, ledger, Skill, fixtures, and Copier behavior.
- [ ] Review the bounded parent diff, run focused validation, obtain independent review, run the authoritative suite once, and archive the accepted plan.

## Validation Notes

- The user approved the session-resource checkpoint boundary on 2026-08-21.
- The source Plan 116 acceptance text is preserved exactly.
