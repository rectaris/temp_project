# Compare model and instruction changes using paired local evidence

status: checked
primary_invariant: A harness comparison reports only comparable, provenance-bound observations and never turns missing evidence, synthetic examples or a critical failure into adoption evidence.
task_types:
  - template_workflow
  - test_coverage
review_class: C
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"scripts/natural-japanese-evaluation.py already checks fixed scenarios, digests, independent evaluation and candidate freeze before holdout; adapt its pattern without changing its Japanese-specific schema.","kind":"existing_mechanism"}
  - {"evidence":"scripts/summarize-agent-run.py delegates to the template implementation, which bounds explicit local inputs, verifies evidence digests and preserves not_observed values and metric provenance.","kind":"existing_mechanism"}
  - {"evidence":"scripts/check-copier-template.py and scripts/project_workflow/copier_inventory.py check managed-file installation and alignment; lint-project-workflow.sh and tests/smoke.sh register and exercise root/generated tools.","kind":"existing_mechanism"}
completion_conditions:
  - The offline command rejects mismatched task, acceptance, baseline, invariant or uncontrolled runtime inputs and distinguishes old-model/current-instructions from new-model/current-instructions and new-model/candidate-instructions comparisons.
  - Reports retain observed quality, elapsed time, cost and intervention coverage; missing evidence, failed or timed-out runs, critical failures, unpaired runs and synthetic fixtures cannot produce an adoption recommendation.
  - Reports distinguish declared limits and holdout status from independently reviewed ordering evidence, withhold empirical recommendations when that evidence is absent, and separate declared instruction identity from runtime-observed loading.
  - The root wrapper and a rendered generated-project command produce equivalent reports for the same portable fixtures, and new specification routing applies only to harness comparison work.
completion_witness_map:
  - {"condition_sha256":"sha256:fafeb308cb546ef82060665480accf1e16e1ea05514c95bdfcca73fb2159822b","witness":"python3 tests/test-harness-comparison.py"}
  - {"condition_sha256":"sha256:ff3c1718bcaadc4d1eadc162b208ac0a5e79c8eb0d550024b749dfe60f7eb3d9","witness":"python3 tests/test-harness-comparison.py"}
  - {"condition_sha256":"sha256:c86f3b5572b190b73a47da7edcb80385593b78f0935c59f06b6a21f259756c1f","witness":"python3 tests/test-harness-comparison.py"}
  - {"condition_sha256":"sha256:ae2e4941196a98d0fd329b25280798a625749f36a12428b5fe93ac9b99fb8576","witness":"python3 tests/test-harness-comparison.py --generated"}
write_scope:
  - scripts/compare-harness-runs.py
  - template/.project-agent-workflow/scripts/compare-harness-runs.py
  - tests/test-harness-comparison.py
  - tests/fixtures/harness-comparison/cases.json
  - tests/fixtures/harness-comparison/evaluation-protocol.md
  - docs/agent/SPEC_HARNESS_EVALUATION.md
  - template/.project-agent-workflow/docs/agent/SPEC_HARNESS_EVALUATION.md
  - docs/agent/spec-index.yaml
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/natural-japanese-evaluation.py
  - scripts/summarize-agent-run.py
  - template/.project-agent-workflow/scripts/summarize-agent-run.py
  - template/.project-agent-workflow/scripts/agent_log_manifest.py
  - tests/fixtures/agent-policy-routing/evaluation-protocol.md
  - docs/plan/checked/2026/09/01-15/277-summarize-observed-run-resources-locally.md
  - docs/plan/checked/2026/09/01-15/302-complete-routed-agent-policy.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - references/validation.md
focused_validation:
  - python3 tests/test-harness-comparison.py
  - python3 tests/test-harness-comparison.py --generated
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Users can assess a model or instruction change from comparable local records while uncertainty and critical regressions remain visible and no provider, policy or lifecycle effect occurs.
  - Root and generated projects receive the same bounded comparison command and protocol, covered by registered focused and generated smoke checks.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:3afc4e066bb4461fd20eabbcad22abefcfc76a5159f2a072b07c56515a046522","stage":"focused","witness":"python3 tests/test-harness-comparison.py"}
  - {"acceptance_sha256":"sha256:0ca108dab500d6680a2375d8f45e8d87a7155b12fff13394bd1510059d7b9f9a","stage":"focused","witness":"python3 tests/test-harness-comparison.py --generated"}
checked_summary_ja: 同じ課題の実行記録から、モデル変更と指示変更の影響を分けて比較できるようにする。

## Decisions

- Implement a standard-library CLI over explicit local JSON inputs and stdout JSON/Markdown reports. No model launch, network, price lookup, home-directory discovery, automatic promotion or changes to existing log/ledger schemas. Use a thin root wrapper over the template-owned implementation.
- A comparison protocol is one frozen record of task/input and acceptance digests, repository baseline, invariant/authority digests, permitted comparison axis, complete case roster, repetitions, budget, metric boundaries and predeclared decision limits. A run observation is one evidence-linked outcome for a case and repetition. Neither record grants execution authority.
- A file digest proves content consistency, not historical preregistration or holdout independence. Treat freeze time, ordering and independence as declared unless explicit independently reviewed evidence binds the protocol/candidate before run outcomes and holdout use. Verify those supplied links and record their reviewer/source provenance, while stating that the CLI cannot authenticate the real-world truth of local attestations. Missing or disputed ordering evidence withholds empirical recommendations.
- Support three configuration slots: old model/current instructions, new model/current instructions, and new model/candidate instructions. Compare the first two with only the model axis changed, and the last two with only the declared instruction axis changed. Require matching reasoning settings where supported; otherwise report a configuration comparison rather than a model-only effect. Reject other uncontrolled differences.
- Bind actual model identity, requested/resolved snapshot when observed, reasoning settings, CLI/runtime and tool versions, task and acceptance digests, effective instruction asset digests, configuration digest and explicit evidence-file digests. Do not equate caller-declared configuration with observed execution. Unknown host/system instructions or unavailable loading evidence prevent an instruction-attributed adoption recommendation.
- Record observed completion outcomes, critical violations, total task elapsed seconds through terminal outcome, directly recorded cost with currency, and human interventions under one frozen counting rule. Reuse explicit run-manifest references; keep absent values not_observed. Preserve observed zero. Do not derive tokens from byte counts or infer billed cost from public prices.
- Every quality or critical-violation judgment must bind the fixed acceptance item and rubric to an explicit deterministic test result or identified independent evaluator, its source evidence and reviewer/session provenance. Agent self-reports and unreviewed or missing judgment evidence cannot support empirical recommendations. The CLI verifies the declared links and reports who judged what; it does not prove the truth of external reports or substitute for independent assessment.
- Enumerate all expected case/repetition/configuration cells before evaluation. Retain errors, timeouts and unavailable-model outcomes in coverage and quality totals; never compare only successful survivors. Summaries may show successful-run timing separately with its denominator and cannot hide failure rates. Incomplete pairs or insufficient repetitions yield inconclusive, not pass.
- A report may recommend a candidate only when all critical requirements pass, observed evidence covers required metrics/cells, and the predeclared quality and cost/time/intervention limits pass. Equal acceptable results may recommend keeping the current configuration. Never compensate a critical violation with speed or cost. No universal percentage target or automatic switch is introduced.
- Keep tuning cases and historical failure cases in versioned fixtures as clearly synthetic examples. Document independent holdout creation outside implementation scope, frozen candidate/protocol digests before evaluation, and invalidation if holdout results are used to retune. Do not claim independent holdout execution from unit tests or fabricate observations.
- Ship an operator recipe using small fixes, cross-file changes, preserved dirty user edits, ambiguous requests and previous verification failures. Operators choose bounded representative workloads and budgets before authorized real runs. Missing provider access or runtime observations leave performance unmeasured without blocking offline tool completion.
- Bound input files, number of records and output size; reject duplicate keys, nonfinite/negative measurements where invalid, duplicate cells, malformed digests, symlinks and nonregular files using the existing summary-tool pattern. Read only supplied evidence and never include credentials, environment values or raw transcripts in reports.
- Register every new template path in the existing inventory and add mechanical root/template policy alignment. Implement --generated in the focused test driver as a real isolated rendered-command comparison, then keep required lint and smoke suites unchanged except additive coverage.

## Tasks

- [x] Define the portable comparison protocol, run-observation schema, outcomes and operator recipe with one focused test for each completion condition.
- [x] Implement explicit-input parsing, evidence binding, paired comparison, failure accounting and coverage-aware reports in the template implementation and root wrapper.
- [x] Add fixed positive, negative and boundary cases for altered acceptance, stale evidence, missing/duplicate pairs, timeout omission, unknown instruction loading, hidden runtime differences, synthetic data and holdout leakage.
- [x] Add root/generated parity and installation coverage, narrow spec routing and required validation registration.
- [x] Review the exact diff and invariant, obtain the required independent review, run focused commands then the authoritative suite, commit and publish. State separately whether any real model comparison was performed.

## Validation Notes

- Owner instruction: 提案の方針でプランを作成せよ。 This authorizes these plans; this authoring task does not execute their implementation or call models.
- Reuse the accepted direction: preserve project requirements and authority, compare bounded instruction changes, retain failure cases, and pin adoption with a rollback path.
- Implementation validation passed: `python3 tests/test-harness-comparison.py` (56 tests), `python3 tests/test-harness-comparison.py --generated` (8 tests), then `scripts/lint-project-workflow.sh` and `tests/smoke.sh` once each.
- No real model comparison was performed. No model was launched, no provider was called, and no run outcome was observed. Every fixture in this scope is synthetic and establishes tool behavior only; it is not observed model performance.
- Independent read-only review ran on the exact diff and reported four confirmed High findings: unverified declared evidence, partial metric coverage, unconfirmed runtime, and ignored observed reasoning and effective instruction identity. All four are fixed, each with a regression test, and the review confirmed the remediation clean.
- Use bounded parent implementation with the existing external execution ledger and independent read-only review because specification and validation registration paths are part of this scope. Preserve all existing execution and review budgets.
