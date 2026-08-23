# Integrate session resource boundaries

status: checked
task_types:
  - planning_docs
  - security
  - skill_authoring
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
primary_invariant: the combined runtime evidence checkpoint and reviewer lifecycle preserves all Plan 132 acceptance without unresolved High or Medium findings
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
  - template/.project-agent-workflow/hooks/agent_log_event.py
  - template/.project-agent-workflow/scripts/agent_log_manifest.py
  - template/.project-agent-workflow/scripts/check-agent-log-manifest.py
  - template/.project-agent-workflow/scripts/import-codex-transcript.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
  - tests/hooks/logging.py
  - tests/smoke.sh
  - tests/test-plan-execution-state.py
  - tests/test-sandboxed-plan-worker.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/168-verify-runtime-session-resource-evidence.md
  - docs/plan/checked/2026/08/16-31/169-linearize-session-checkpoint-lifecycle.md
  - docs/plan/checked/2026/08/16-31/174-linearize-reviewer-session-registry.md
  - docs/plan/replanned/2026/08/16-31/132-checkpoint-plan-session-resources.md
required_specs:
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-hooks.py
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - python3 tests/test-hooks.py
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
  - {"acceptance_sha256":"sha256:cf0c0eaf1b20d2e1a87a62c8c9b82f72b208c16e7ed984058ce9f596df8d15a7","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
replan_source: docs/plan/active/132-checkpoint-plan-session-resources.md
replan_contract: docs/plan/replanned/contracts/132-checkpoint-plan-session-resources.json
integration_gates:
  - Plan 174 is checked and consumed through its exact archive path
  - run the complete parent-owned focused suite before one fresh independent review and the authoritative suite exactly once
  - update Plan 133 to consume only checked Plan 168 through 171 evidence
successor_plans:
  - docs/plan/active/168-verify-runtime-session-resource-evidence.md
  - docs/plan/active/169-linearize-session-checkpoint-lifecycle.md
  - docs/plan/active/170-bind-review-context-to-candidate-lifecycle.md
  - docs/plan/active/171-integrate-session-resource-boundaries.md
inherited_acceptance_digests:
  - sha256:7ed675c8fc9df790c90252aa2b4ee1afd1063270c97e9adc9a204b62a7442bfa
  - sha256:cf0c0eaf1b20d2e1a87a62c8c9b82f72b208c16e7ed984058ce9f596df8d15a7
  - sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc
checked_summary_ja: runtime証拠、checkpoint lifecycle、review lifecycleを統合し、全受入条件を検証する。

## Decisions

- runtime-session-resource-evidence means a bounded runtime-produced transcript or hook artifact whose bytes and digest are verified before identity, inheritance, or usage facts are consumed.
- session-checkpoint-lifecycle means the predecessor-ledger issuance and single-successor consumption records for one checkpoint identity.
- candidate-review-lifecycle means the admitted-candidate records that bind review target, runtime-proven reviewer identity, the external reviewer-session registry, and the one-initial-plus-one-rereview budget.
- session-resource-boundary-integration means the final acceptance condition over checked runtime evidence, checkpoint lifecycle, and candidate review lifecycle outputs.
- Integrate only checked outputs from Plans 168, 169, and 174.
- Reject staged promotion when runtime identity or reviewer inheritance remains `not_observed`.
- Preserve existing default behavior until Plan 133 completes paired evaluation.
- Keep final acceptance, authoritative validation, archive, and commit in the parent session.

## Tasks

- [x] Replace the active Plan 174 context path with its exact checked archive.
- [x] Reconcile root and generated policy, scripts, tests, and Copier inventories.
- [x] Run the complete focused suite and obtain one fresh independent review.
- [x] Run the authoritative suite exactly once.
- [x] Update Plan 133 dependency evidence, archive this plan, and commit.

## Validation Notes

- This integration plan preserves all three Plan 132 acceptance items exactly.
- The Hook validation entry was corrected from the non-collecting `python3 -m pytest tests/hooks` path to the repository aggregate `python3 tests/test-hooks.py` without changing its acceptance witness.
- Focused validation passed with 42 Hook tests, 66 execution-state tests, 96 sandboxed-worker tests, root policy checks, Copier template checks, and `git diff --check`.
- One fresh independent review found no High or Medium findings in the combined integration diff.
- Authoritative validation passed exactly once with validation tools, Hook tests, execution-state tests, sandboxed-worker tests, worker self-test, root policy including holdout, Copier checks, all-change validation, lint, smoke, Copier update, and `git diff --check`.
