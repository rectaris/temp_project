# Evaluate one-plan worker orchestration before default rollout

status: in_progress
task_types:
  - planning_docs
  - referent_first
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: ordinary
primary_invariant: change the default orchestration path only when reproducible paired evidence meets existing quality and efficiency thresholds without weakening safety gates
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
  - tests/smoke.sh
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/113-generate-plan-bound-worker-contract.md
  - docs/plan/active/114-validate-structured-worker-completion.md
  - docs/plan/active/115-classify-review-outcomes-and-sequence-writes.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
  - docs/plan/checked/2026/08/01-15/078-plan-execution-budget-ledger.md
  - references/orchestration.md
  - references/validation.md
  - tests/fixtures/orchestration/staged-acceptance.json
  - tests/fixtures/orchestration/staged-baseline-events.json
  - tests/fixtures/orchestration/staged-holdout-events.json
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - git diff --check
acceptance:
  - Require plans 113, 114, and 115 to be accepted and archived before any paired evaluation or default-policy change begins; if evaluation exposes a design, scope, specification, security, or artifact-boundary change in those implementations, mark this plan `replan_required` instead of repairing them inside this write scope.
  - After plans 113, 114, and 115 are archived, replace their active `context_files` entries with the exact checked archive paths before evaluation; treat these as dependency-path refreshes only, rerun plan checks, and do not change accepted requirements or broaden scope.
  - Produce orchestration comparison evidence as a repository-local reproducible record of paired baseline and staged executions over fixed median, edge, negative, and untuned holdout cases.
  - Run each pair from the same source commit and workload bytes with recorded case identity, workload digest, runner revision, configuration, model route, plan and primary-invariant digest, execution-contract schema, completion-receipt schema, review-reason schema, and ledger schema.
  - Keep holdout cases physically outside reusable implementation prompts and configuration tuning, and fail evaluation when any required scenario class or pair is missing, reordered without a version change, or not backed by raw runner and ledger evidence.
  - Measure accepted-patch outcome, unresolved independent-review severity, parent rejection count by review outcome reason, correction rounds, model starts, elapsed time to accepted patch, out-of-scope changes, and token usage only when the worker provider exposes it directly and comparably.
  - For baseline runs, classify parent review evidence under the same fixed reason vocabulary only after each run and never use that retrospective classification to change baseline control flow, correction eligibility, or acceptance.
  - Mark unavailable token usage as `not_observed` with provider and attempt identity; do not estimate, normalize from text length, or make token reduction a mandatory pass criterion without comparable direct measurements.
  - Require zero unresolved High or Medium independent-review findings, no safety-gate regression, at least 30 percent lower median model starts and median time to accepted patch than the paired baseline, and p95 time to accepted patch no more than 10 percent worse than the paired baseline.
  - Reject a measured pass when either side uses different requirements, source state, validation authority, correction budget, model availability treatment, external access, credentials, or manual intervention not represented in the paired evidence.
  - Keep the current path as the default and record `measurement_pending` or `measured_fail` when evidence is unavailable, incomplete, noncomparable, or below any threshold; do not claim improvement from historical unpaired runs.
  - Promote the staged path to the documented default only after the checker validates every evidence digest and threshold; preserve an explicit, tested rollback to the prior default without deleting evidence or rewriting prior outcomes.
  - Add deterministic tampering and holdout checks for side swapping, digest mismatch, missing raw evidence, synthetic summary promotion, absent scenario class, hidden manual restart, unobserved token inference, quality regression, threshold boundary, p95 regression, and attempted safety-gate weakening.
  - Keep root and generated policy and Skill semantics aligned after path normalization, preserve supported non-destructive Copier updates, record the measured outcome under Unreleased without overstating causality, run the authoritative suite exactly once, and finish with zero unresolved High or Medium independent-review findings.
checked_summary_ja: 一plan一workerの段階導入を同一条件の比較証拠で評価し、品質と効率の既存基準を満たす場合だけ既定経路へ昇格する。

## Context

Smaller worker context and structured handoffs can reduce ambiguity, but extra orchestration can also increase token use, latency, and failure surfaces. Repository breadth alone does not establish value.

The orchestration comparison evidence is the reproducible paired baseline-versus-staged execution record used to decide whether the staged path may become the repository default.

Existing orchestration policy already defines quality, median improvement, and p95 regression thresholds. Historical observations are not paired evidence for equivalent workloads.

## Decisions

- Evaluate the combined accepted outputs of plans 113 through 115 instead of evaluating each mechanism against different workloads.
- Use fixed paired median, edge, negative, and untuned holdout cases with exact source and configuration identity.
- Treat directly observed token use as an optional metric until comparable provider evidence exists.
- Retain the current default on missing, incomparable, or failing evidence and promote only a checker-verified measured pass.
- Stop for replanning when evaluation requires an implementation design change outside this plan's evidence and policy scope.

## Tasks

- [ ] Freeze versioned paired workloads, schemas, source identity, thresholds, raw evidence requirements, and separated holdout cases.
- [ ] Execute or ingest comparable baseline and staged runs and generate digest-linked orchestration comparison evidence.
- [ ] Extend deterministic checks for evidence completeness, comparability, thresholds, tampering, rollback, and default selection.
- [ ] Align root and generated policy, Skill, inventories, changelog, and non-destructive Copier behavior for the measured outcome.
- [ ] Review the complete plans 113 through 116 acceptance chain, obtain independent review, run the authoritative suite once, and archive the accepted plan.

## Validation Notes

- Decision audit selected measured rollout rather than immediate default adoption.
- The advisory referent contract preserves the actual benefit and token observability as unresolved until paired execution evidence exists.
- This plan is an evidence and policy gate. It must not absorb implementation corrections for plans 113 through 115.
- The parent must refresh all predecessor context paths after archival before starting paired evaluation.
