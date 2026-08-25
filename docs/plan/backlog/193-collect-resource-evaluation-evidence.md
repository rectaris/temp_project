# Collect comparable resource-bounded orchestration evidence

status: backlog
primary_invariant: paired baseline and staged executions produce digest-linked comparable evidence without changing control flow, policy defaults, or missing measurements into estimates
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - tests/fixtures/orchestration/paired-artifacts/resource-evaluation-baseline-v1.json
  - tests/fixtures/orchestration/paired-artifacts/resource-evaluation-staged-v1.json
  - tests/fixtures/orchestration/resource-evaluation-result-v1.json
preservation_scope:
  - scripts/check-copier-template.py
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/192-freeze-resource-evaluation-contract.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - git diff --check
validation:
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - git diff --check
acceptance:
  - Produce orchestration comparison evidence as a repository-local reproducible record of paired baseline and staged executions over fixed median, edge, negative, and untuned holdout cases.
  - Run each pair from the same source commit and workload bytes with recorded case identity, workload digest, runner revision, configuration, model route, plan and primary-invariant digest, execution-contract schema, completion-receipt schema, review-reason schema, and ledger schema.
  - Keep holdout cases physically outside reusable implementation prompts and configuration tuning, and fail evaluation when any required scenario class or pair is missing, reordered without a version change, or not backed by raw runner and ledger evidence.
  - Measure accepted-patch outcome, unresolved independent-review severity, parent rejection count by review outcome reason, correction rounds, model starts, elapsed time to accepted patch, out-of-scope changes, and token usage only when the worker provider exposes it directly and comparably.
  - For baseline runs, classify parent review evidence under the same fixed reason vocabulary only after each run and never use that retrospective classification to change baseline control flow, correction eligibility, or acceptance.
  - Mark unavailable token usage as `not_observed` with provider and attempt identity; do not estimate, normalize from text length, or make token reduction a mandatory pass criterion without comparable direct measurements.
  - Record provider-observed input, cached input, output, reasoning, model-response, compaction, helper-turn, and tool-call measurements only when directly available, keep unavailable values as not_observed, store no prompts or output bodies, and use deterministic proxy counts without estimating tokens.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:fab81555f698b828c50e01aee3e0a5baf7a01c6c57f26cd4f5ef8b147ddcb7b5","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
  - {"acceptance_sha256":"sha256:7701247ddfbb9b6067289f4ec871bd2a2f971aa22354784e2657da5e44a6b4ed","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
  - {"acceptance_sha256":"sha256:fbc1c1c96eb6501b3b5d9f0216dbca4b9c9effaba938fef770699862afeeaa07","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
  - {"acceptance_sha256":"sha256:df74e7bc01e4446fee1049705e130abc21bd8a2176ce9dbd1d059ea0e971a525","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
  - {"acceptance_sha256":"sha256:250ec4c459a592ae9ba133ac4cac3a21cc59e23a01d086c925f2deb4510e644b","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
  - {"acceptance_sha256":"sha256:a7185b3b664461a636b4c2e17332ede1886308498304364dbccc95fc2d3ebddb","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
  - {"acceptance_sha256":"sha256:cf0c0eaf1b20d2e1a87a62c8c9b82f72b208c16e7ed984058ce9f596df8d15a7","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
replan_source: docs/plan/active/133-evaluate-resource-bounded-orchestration.md
replan_contract: docs/plan/replanned/contracts/133-evaluate-resource-bounded-orchestration.json
predecessor_plans:
  - docs/plan/active/192-freeze-resource-evaluation-contract.md
integration_gates:
  - Plan 192 must be checked and its exact checked archive path must replace this active predecessor before evidence collection
  - in the same parent-owned activation update, add the frozen checker, evaluation schema, and session-regression fixture emitted by checked Plan 192 as exact read-only context
  - keep raw runner and ledger evidence local under .agent-logs and .agent-artifacts and commit only bounded digest-linked summaries
  - Plan 194 remains deferred until this plan is checked and its exact checked archive path replaces its active predecessor
successor_plans:
  - docs/plan/active/192-freeze-resource-evaluation-contract.md
  - docs/plan/active/193-collect-resource-evaluation-evidence.md
  - docs/plan/active/194-apply-resource-evaluation-outcome.md
  - docs/plan/active/195-verify-plan133-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:fab81555f698b828c50e01aee3e0a5baf7a01c6c57f26cd4f5ef8b147ddcb7b5
  - sha256:7701247ddfbb9b6067289f4ec871bd2a2f971aa22354784e2657da5e44a6b4ed
  - sha256:fbc1c1c96eb6501b3b5d9f0216dbca4b9c9effaba938fef770699862afeeaa07
  - sha256:df74e7bc01e4446fee1049705e130abc21bd8a2176ce9dbd1d059ea0e971a525
  - sha256:250ec4c459a592ae9ba133ac4cac3a21cc59e23a01d086c925f2deb4510e644b
  - sha256:a7185b3b664461a636b4c2e17332ede1886308498304364dbccc95fc2d3ebddb
  - sha256:cf0c0eaf1b20d2e1a87a62c8c9b82f72b208c16e7ed984058ce9f596df8d15a7
checked_summary_ja: 固定済みcaseを同一条件で実行し、推定を含まないdigest付き比較証拠を記録する。

## Decisions

- Run each baseline and staged pair from the same source commit and workload bytes with no hidden restart or manual intervention.
- Record provider-observed usage only when directly available and store unavailable values as not_observed.
- Classify baseline review reasons only after each run without changing baseline control flow.
- Emit measurement_pending or measured_fail for incomplete, noncomparable, unsafe, or below-threshold evidence; do not change the default.
- Use bounded parent execution because evidence collection owns runtime and review identity.

## Tasks

- [ ] Execute or ingest every fixed paired case and preserve raw local evidence manifests.
- [ ] Generate bounded baseline, staged, and comparison records with exact digests and observed fields.
- [ ] Run comparability and tampering checks and obtain independent evidence review.
- [ ] Archive, commit the bounded records, and activate Plan 194.

## Validation Notes

- No prompt or output body and no estimated token value belongs in committed evidence.
