# Evaluate one-plan worker orchestration before default rollout

status: replanned
replan_reason_codes:
  - multiple_independent_invariants
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
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
  - After an authoritative failure, enter a parent-owned no-write condition that permits only bounded read-only reproduction and classification evidence; do not create a numbered repair plan until the exact failed operation and affected invariant are confirmed, then transition only to the existing independent-repair or hard-replan path.
  - At checked, replanned, repair-required, replan-required, and authoritative-failure boundaries, emit and verify one bounded digest-linked session checkpoint before another numbered plan or reviewer context continues; keep final authority in the parent and never treat a resource checkpoint as a semantic failure.
  - Record provider-observed input, cached input, output, reasoning, model-response, compaction, helper-turn, and tool-call measurements only when directly available, keep unavailable values as not_observed, store no prompts or output bodies, and use deterministic proxy counts without estimating tokens.
  - Give an independent reviewer only the unchanged plan, admitted diff, bounded receipts, and applicable specifications after the candidate is otherwise review-ready; permit one initial review and one bounded rereview per candidate before the existing strategy-change path, and do not reuse an accumulated general-purpose reviewer history across numbered plans.
  - Extend paired evaluation with a fixed generic workload structurally equivalent to the Plan 119 late-integration and speculative-repair sequence; require at least 30 percent lower median directly comparable input-token use when both sides expose it, otherwise keep token improvement not_observed and do not claim a usage reduction.
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/116-evaluate-plan-worker-orchestration.md
replan_contract: docs/plan/replanned/contracts/116-evaluate-plan-worker-orchestration.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/130-map-acceptance-validation-witnesses.md
  - docs/plan/active/131-require-confirmed-failure-diagnosis.md
  - docs/plan/active/132-checkpoint-plan-session-resources.md
  - docs/plan/active/133-evaluate-resource-bounded-orchestration.md
inherited_acceptance_digests:
  - sha256:158d415534f8ba707df6e05f303514c377e4286f6f5128ae2f7174cbaf7473fe
  - sha256:1c4d732d6a277114b68e0b6eca7618d03e5c2cc51f84da2abd8b1863c9f8a576
  - sha256:fab81555f698b828c50e01aee3e0a5baf7a01c6c57f26cd4f5ef8b147ddcb7b5
  - sha256:7701247ddfbb9b6067289f4ec871bd2a2f971aa22354784e2657da5e44a6b4ed
  - sha256:fbc1c1c96eb6501b3b5d9f0216dbca4b9c9effaba938fef770699862afeeaa07
  - sha256:df74e7bc01e4446fee1049705e130abc21bd8a2176ce9dbd1d059ea0e971a525
  - sha256:250ec4c459a592ae9ba133ac4cac3a21cc59e23a01d086c925f2deb4510e644b
  - sha256:a7185b3b664461a636b4c2e17332ede1886308498304364dbccc95fc2d3ebddb
  - sha256:74676af1c3fd1ec6c706498604bbe8b3f2cbbcb4dd8a1ffaf172718f73726583
  - sha256:1573727361ca97cecd78c1402e5da1408485636d354b073d41538c0e6f7f1293
  - sha256:93709976edad8b54f41e89a815beb179fcdf85a17ac3a8a7205d89d7e6d91a2a
  - sha256:d5e7d033295d031afe5825359b3d986cea2182dccb3cafbed36972cfff29c735
  - sha256:089ede7f008b392e945178ad74cfb61e714a468f7a74ebb565f44f1343fc45e1
  - sha256:edfc0aeac6285bab001c16d4b35fdf65c2cc81311b1adb3d012d5101aee64f9b
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
  - sha256:f01ccfa44e09342cbfeb4599282afbed2286a3e43524757881dd3163bb3b93e7
  - sha256:7ed675c8fc9df790c90252aa2b4ee1afd1063270c97e9adc9a204b62a7442bfa
  - sha256:cf0c0eaf1b20d2e1a87a62c8c9b82f72b208c16e7ed984058ce9f596df8d15a7
  - sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc
  - sha256:3758070f0f3636a1edf9b06253cc357baabdb1901375edf08c8ab76026e154ba
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
- Preserve plans 113 through 115 unchanged, implement validation witnesses, diagnosis gating, and session-resource checkpoints as separate successors, then evaluate their combined accepted behavior.

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
- On 2026-08-21, the user approved restructuring this plan around early validation witnesses, confirmed diagnosis before repair planning, bounded session checkpoints, directly observed usage telemetry, and isolated review contexts.
- The accepted additions contain multiple independently validatable invariants, so this source plan is `replan_required` before implementation and must be replaced atomically.
