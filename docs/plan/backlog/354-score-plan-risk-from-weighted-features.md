# Predict plan implementation risk from weighted structured feature scores and report its measured limits

status: backlog
primary_invariant: Feature dimensions and weights are fitted only on the tuning partition, the held-out partition is scored exactly once against predeclared limits, and every reported accuracy is paired with its majority-class baseline and its own denominator so a class below the declared minimum is reported as not measurable instead of scored.
task_types:
  - planning_docs
  - test_coverage
  - external_services
review_class: C
human_design_required: yes
human_approval_status: pending
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: high
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Plan 317 emits implementation_risk questions from committed plan records with point-in-time inputs, named exclusions, per-class counts with the majority-class share, and lineage-aware time-split tuning and holdout partitions. This plan consumes that output and adds no new dataset source.","kind":"existing_mechanism"}
  - {"evidence":"A bounded scan of 365 committed plan files at dev tip 8f5cbcc read implementation_risk from 295: high 157, ordinary 108, low 28, and 2 out-of-policy medium. A constant high prediction therefore scores about 53 percent, which fixes the baseline any model must beat.","kind":"bounded_prototype"}
  - {"evidence":"SPEC_HARNESS_EVALUATION.md already requires predeclared decision limits, coverage that retains failures and timeouts in the denominator, metrics reported with their own denominators, and insufficient_evidence whenever evidence is missing or unverified. This plan reuses those rules for a per-class report.","kind":"existing_mechanism"}
  - {"evidence":"scripts/natural-japanese-evaluation.py already validates an offline evaluation packet whose event sequence forces scenarios frozen, non-holdout compared, candidate fixed, holdout revealed, then holdout compared. That ordering is the shape this plan applies to weight fitting.","kind":"existing_mechanism"}
completion_conditions:
  - Feature dimensions and weights are fitted only on the tuning partition, and the command refuses to fit, refit, or tune on any record belonging to the held-out partition.
  - The held-out partition is scored exactly once per frozen dimension set and weight vector, and a second scoring attempt against the same holdout is refused rather than reported.
  - Every reported accuracy is paired with the majority-class baseline computed on the same records, and a report that omits the baseline is refused.
  - Per-class results carry their own denominators, and a class whose record count falls below the declared minimum is reported as not measurable instead of receiving an accuracy value.
  - The report states record counts and accuracy for the high-confidence, middle, and low-confidence bands separately, using thresholds declared before any holdout record is scored.
  - Scoring, fitting, and reporting run offline from recorded provider responses, contact no provider, need no network, and write no file into the repository.
completion_witness_map:
  - {"condition_sha256":"sha256:fc0e03338c3ef46430ea302601a2475a262607078471abe2570d950cc797c0cf","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:be3a983010a8f87a7e27cfdb36b28dcbe621c19d42737a42db468ea61418aa28","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:2ecfd3876c8975cfbb4a9a49c15f251ca687987c5961c36453830a51c4e21c72","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:feb38910075fecb0f3673a2c6a52b01e33a29e7c8ce79b914bf3e840e7eebc56","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:61938cbbca084b94e3d69166283f3933c3e1df14a608bd9e43c0cba96022cfb2","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:8717663a742a53b828047aab9024db546b4e43969d6fe3c6891cbdb4ba9cdfa1","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/score-plan-features.py
  - tests/validation_tools/feature_scoring.py
  - tests/test-validation-tools.py
  - scripts/project_workflow/copier_inventory.py
  - tests/fixtures/feature-scoring/evaluation-protocol.md
  - tests/fixtures/feature-scoring/cases.json
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/agent/SPEC_HARNESS_EVALUATION.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_HARNESS_EVALUATION.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
focused_validation:
  - python3 tests/test-validation-tools.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Weighted feature scores predict implementation risk with tuning-only fitting and a single holdout scoring, reported beside the majority-class baseline with per-class denominators and not-measurable classes named.
  - Confidence-band counts and accuracies are reported from predeclared thresholds, and the whole evaluation path runs offline from recorded responses without writing into the repository.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:89d6929e5705c84c5e3af0d4d540d7cca8fc1944299fa04c82879044c714be95","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:49f8c2c8a829d2ec3e97af59ed97a297c1ed247836acdfaa1dc23ca5f3800e37","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - Start only after plan 317 is checked, because this plan consumes its emitted question set and its tuning and holdout partitions.
  - Start provider-backed scoring only after the TypeSafe provider registration plan is checked, because obtaining recorded responses requires an authorized read.
checked_summary_ja: 重み付き特徴量スコアから計画の実装リスクを予測し、測定限界を報告する。

## Decisions

- Do not ask the provider for the label directly. Ask it for scores on named feature dimensions, then combine those scores with fitted weights, because a direct classification discards the evidence that makes a wrong answer reviewable.
- Let a language model propose the candidate dimensions and keep every proposed dimension named and recorded, so a later reader can see which signals the prediction rests on.
- Fit weights only on the tuning partition from plan 317. Refuse fitting on any held-out record rather than trusting the caller to keep them apart.
- Score the holdout exactly once per frozen dimension set and weight vector. A second attempt against the same holdout is refused, because a retried holdout stops being held out.
- Declare the confidence band thresholds before scoring any holdout record, and report the three bands separately instead of a single accuracy.
- Pair every accuracy with the majority-class baseline on the same records. With high at about 53 percent of labeled records, an unpaired accuracy is unreadable.
- Report a class below the declared minimum count as not measurable. Ambiguity high has 9 records and review class A has 10, so thin classes are a real and recurring case.
- Split the provider call from the evaluation. The command evaluates recorded responses offline; obtaining those responses is a separate authorized step under the registered provider.
- Record the protocol beside the fixtures and commit only tuning cases, marked as used for tuning, following the existing harness comparison and natural-japanese evaluation shapes.
- Report insufficient evidence rather than a recommendation whenever coverage, baselines, or band counts are incomplete, keeping the existing harness evaluation default.

## Tasks

- [ ] Define the recorded score record: its dimensions, per-dimension scores, confidence, source question identity, and partition membership.
- [ ] Implement tuning-only weight fitting that refuses any held-out record as a fitting input.
- [ ] Implement single-use holdout scoring with an explicit refusal when the same holdout is scored again for an unchanged dimension set and weight vector.
- [ ] Implement the report: overall and per-class accuracy with denominators, the majority-class baseline, not-measurable classes, and the three confidence bands.
- [ ] Implement offline operation with no provider contact, no network, and no repository write, and assert each of those in the tests.
- [ ] Write the evaluation protocol document and the committed tuning cases, marked as used for tuning.
- [ ] Register the command in the source inventory and the tests in tests/test-validation-tools.py.
- [ ] Run the focused check, then the full validation suite, and commit through the ordinary lifecycle.

## Validation Notes
