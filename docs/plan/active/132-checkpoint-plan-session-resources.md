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
primary_invariant: continue another numbered plan only in a different verified root session and start each reviewer with zero inherited turns from one bounded checkpoint with directly observed resource evidence
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
  - docs/plan/checked/2026/08/16-31/136-integrate-plan-bound-worker-contract.md
  - docs/plan/checked/2026/08/16-31/162-integrate-structured-worker-completion-receipt.md
  - docs/plan/checked/2026/08/16-31/115-classify-review-outcomes-and-sequence-writes.md
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
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:7ed675c8fc9df790c90252aa2b4ee1afd1063270c97e9adc9a204b62a7442bfa","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:cf0c0eaf1b20d2e1a87a62c8c9b82f72b208c16e7ed984058ce9f596df8d15a7","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
replan_source: docs/plan/active/116-evaluate-plan-worker-orchestration.md
replan_contract: docs/plan/replanned/contracts/116-evaluate-plan-worker-orchestration.json
integration_gates:
  - plan 136 as the accepted successor for plan 113, plan 162 as the checked replacement successor for plan 155 and plan 114, and plan 115 must be checked before implementation starts
  - Do not implement this plan in the session that creates or materially updates it.
  - Start the next numbered plan only in a root session whose directly observed runtime session identity differs from the session that emitted the prior terminal checkpoint.
  - Treat compaction or a summary injected into the same conversation as continued context, not a fresh root session.
  - When either session identity is unavailable, record freshness as `not_observed` and stop before staged execution without blocking the current default path.
  - Start each independent reviewer with zero inherited conversation turns and an explicit bounded packet containing only the unchanged plan, admitted diff, bounded receipts, and applicable specifications.
  - Use compaction, helper-turn, and tool-call counts only as diagnostic proxies; require directly comparable provider-observed token values for a token-reduction claim.
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
- Require a verified checkpoint after terminal, deferred, replan, repair, or authoritative-failure boundaries, then stop the root session before another numbered plan starts.
- Require different directly observed root-session identities across numbered-plan boundaries; a compaction, summary, new orchestration run id, or elapsed-time gap cannot satisfy this condition.
- Keep missing root-session identity as `not_observed`; do not infer freshness or promote the staged path from a manual claim.
- Store only provider-observed numeric usage with explicit observed or not_observed provenance; keep deterministic proxy counters separate and never estimate tokens.
- Start each independent review from zero inherited turns and bounded plan, diff, receipt, and specification inputs; permit one initial review and one bounded rereview per candidate.
- Verify reviewer inheritance from outer transcript evidence when available; keep it `not_observed` and block staged promotion when the runtime does not expose the spawn configuration.
- Treat resource thresholds as session-rollover conditions only; determine numeric promotion thresholds through Plan 133 paired evidence.
- Use bounded parent implementation and independent review because this plan changes logging, ledger, runner, and reviewer scheduling boundaries.

## Tasks

- [ ] Define and validate the checkpoint schema, root-session identity, lifecycle boundaries, and replay protections without treating an orchestration run id as proof of a fresh model context.
- [ ] Preserve bounded provider usage and deterministic proxy counts through transcript manifests and execution telemetry.
- [ ] End the current root session at every numbered-plan terminal boundary and gate the next numbered-plan start on a verified checkpoint plus a different directly observed root-session identity without changing semantic plan states.
- [ ] Enforce zero-inheritance reviewer starts, exact bounded review packets, transcript-backed fork-mode evidence when available, and the one-review-plus-one-rereview budget.
- [ ] Add deterministic rejection cases for same-session successor starts, compaction presented as freshness, full-history reviewer forks, reused general-purpose reviewers, missing required identity evidence, and proxy counts presented as token savings.
- [ ] Align root and generated policy, logging, runner, ledger, Skill, fixtures, and Copier behavior.
- [ ] Review the bounded parent diff, run focused validation, obtain independent review, run the authoritative suite once, and archive the accepted plan.

## Validation Notes

- The user approved the session-resource checkpoint boundary on 2026-08-21.
- On 2026-08-21, the user requested this plan-only refinement after a second implementation sequence remained in one root session, compacted four times, and started three reviewers with full inherited history.
- This plan update intentionally ends without implementation; continuing implementation in this root session violates its bootstrap gate.
- The source Plan 116 acceptance text is preserved exactly.
