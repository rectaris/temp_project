# Predict plan implementation risk from weighted structured feature scores and report its measured limits

status: backlog
primary_invariant: Feature dimensions and weights are fitted only on the tuning partition, the held-out partition is scored exactly once against predeclared limits, and every reported accuracy is paired with its majority-class baseline and its own denominator so a class below the declared minimum is reported as not measurable instead of scored.
task_types:
  - planning_docs
  - harness_evaluation
review_class: C
human_design_required: yes
human_approval_status: pending
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Checked plan 317 ships scripts/build-plan-question-set.py: a schema-1 plan_record_question_set report whose questions carry question_id, input_sha256, lineage_group and partition tuning or holdout, with per-partition statistics, majority_class and protocol.min_class_count, plus a verify subcommand that regenerates the report from Git.","kind":"existing_mechanism"}
  - {"evidence":"317's recorded run at 4f2727f emitted 250 questions (high 148, ordinary 88, low 14; majority share 0.592); tuning 207 and holdout 43 with holdout low 2 below min_class_count 10. Thin and not-measurable classes are therefore real inputs, and the baseline must come from each report rather than a constant.","kind":"bounded_prototype"}
  - {"evidence":"SPEC_HARNESS_EVALUATION.md already requires predeclared decision limits, denominators that retain failures, insufficient_evidence when evidence is missing, and states that synthetic fixtures demonstrate tool behavior only.","kind":"existing_mechanism"}
  - {"evidence":"317 registered with exactly one script, one tests/validation_tools module imported by tests/test-validation-tools.py, committed fixtures under tests/fixtures/, and SOURCE_REQUIRED entries in scripts/project_workflow/copier_inventory.py; no other file was needed.","kind":"existing_mechanism"}
completion_conditions:
  - fit accepts only a question-set report that passes 317's verify check, joins recorded scores by question_id and input_sha256, and refuses any holdout record, any unjoined or mismatched record, and any score outside 0 to 1 before computing weights.
  - score-holdout requires a ledger path outside the repository worktree, derives one key from the report source commit, the sorted holdout input digests, and the dimension, weight and band-threshold digests, and refuses a second scoring for a recorded key.
  - Every reported accuracy, overall, per class and per band, is paired with the majority-class baseline computed on the same records, and the report writer refuses to emit a report that lacks a paired baseline.
  - Per-class results carry their own denominators, and a class whose count is below the question set's min_class_count is reported as not_measurable with no accuracy value.
  - Band thresholds are read from the committed protocol before any holdout record is scored, and the report states count, accuracy and paired baseline for the high, middle and low bands, marking an empty or thin band not_measurable.
  - fit, score-holdout and report run with socket creation disabled, contact no provider, leave the repository tree byte-identical, and write only to stdout or explicit paths outside the worktree.
  - Fitting is deterministic standard-library multinomial logistic regression with the protocol's fixed learning rate, iteration count and L2 weight, so identical inputs produce identical weight and report digests.
  - The command, its test module and its fixtures are registered in the source inventory and the validation-tool test entrypoint, and the template checker passes.
completion_witness_map:
  - {"condition_sha256":"sha256:0f7d3594e0a958b1676d005d2d5e39b84c395e1617b0e7a68f7ebf25160d61b0","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:d4eff5c0b0fe1777b08c30b01889d9cceb0212070499320633467347e225d44f","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:09a9b33e71df172e37c25fa96c6439234199fd34efcfcb0b25a6da64e0a9aa22","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:3f20d5b55c61e3b247f7e7e1bd7ea42aa889fa918a5deab265d9c4ab1dd4dcc9","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:5bef24c0733a4238597cb1dd34c646c531063a92737ccdbdae6f31567cd48356","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:faa90de335ee6095b597d060f923056e3eae358f1a388aaa2afad40e4d21dfeb","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:675011c336e97c980a38bd17ec9bb4240e00189de80a021c69cda379ba7a23be","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:6563f806cb1ae8d79aeb88ad85bf5bdb9ca1bb812543c44a626968a2e5a50abd","witness":"python3 scripts/check-copier-template.py"}
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
  - scripts/build-plan-question-set.py
  - tests/fixtures/question-set/construction-protocol.md
  - docs/plan/checked/2026/09/16-31/317-build-plan-record-question-set.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_HARNESS_EVALUATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
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
  - docs/plan/checked/2026/09/16-31/317-build-plan-record-question-set.md
checked_summary_ja: 重み付き特徴量スコアから計画の実装リスクを予測し、測定限界を報告するオフライン評価コマンドを作る。

## Decisions

- Build only the offline evaluation command and its synthetic-case tests. Proposing dimensions, obtaining recorded provider responses and the one real holdout measurement are evaluation operations kept outside numbered plans; this plan neither performs them nor depends on plan 345.
- Acceptance is established as tool behavior on synthetic cases and a Git-built question set. A real prediction result is not claimed; SPEC_HARNESS_EVALUATION treats synthetic cases as behavior evidence only.
- Ask for scores on named dimensions rather than the label itself. A dimensions file lists each dimension id and text and is identified by its digest; a scores file binds that digest, the recorder identity and model id, and per-question scores keyed by question_id and input_sha256.
- Take partition membership only from a report that passes 317's verify logic, imported from scripts/build-plan-question-set.py. Never trust a partition field inside a scores file.
- Fit multinomial logistic regression with batch gradient descent: tuning-set standardized features, zero initial weights, learning rate 0.1, 2000 iterations and L2 weight 0.01, all recorded in the protocol. Confidence is the maximum class probability.
- Declare the band thresholds in the committed protocol: high at 0.70 or above, middle from 0.50 up to 0.70, low below 0.50. Reuse the report's protocol.min_class_count as the minimum for classes and bands.
- Guard single holdout use with an append-only mode-0600 ledger file outside the worktree, keyed as the invariant states. The ledger prevents accidental reuse, not an adversary who starts a new ledger; the protocol states that limit.
- Report insufficient_evidence instead of a recommendation whenever coverage, a paired baseline or a band count is incomplete.
- Commit only synthetic tuning cases, marked used_for_tuning, following tests/fixtures/question-set and the harness-comparison fixtures.

## Tasks

- [ ] Define the dimensions, scores, weights and report record shapes in the protocol document, including the fixed fitting parameters and band thresholds.
- [ ] Implement fit with 317 report verification, the question_id and input_sha256 join, and holdout refusal before any computation.
- [ ] Implement score-holdout with the outside-worktree ledger and the second-scoring refusal.
- [ ] Implement report with paired baselines, per-class and per-band denominators and not_measurable classes, and refuse a report without a paired baseline.
- [ ] Add FeatureScoringTest: synthetic cases for every refusal and report field, socket creation disabled in the subprocess, and a repository tree digest compared before and after.
- [ ] Register the command and fixtures in SOURCE_REQUIRED and the test in tests/test-validation-tools.py.
- [ ] Obtain independent review, run the focused checks, then the full validation suite once, and publish through the ordinary lifecycle.

## Validation Notes

- Pre-activation review at d61b41e replaced the stale 8f5cbcc class counts with 317's recorded numbers, removed the dependency on plan 345, and moved response collection and the real measurement out of this plan, because investigation and value evaluation stay outside numbered plans.
