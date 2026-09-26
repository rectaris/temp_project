# Weighted feature scoring evaluation protocol

This protocol fixes how `scripts/score-plan-features.py` predicts the
`implementation_risk` label of a plan-record question set from recorded scores
on named feature dimensions, and how it reports the measured limits of that
prediction.

The command is root-only and offline. `fit`, `score-holdout`, and `report` read
explicitly supplied local records, the committed history through Git, and this
protocol as committed at `HEAD` of `--repo`. They call no provider, need no
network, and write to stdout only. `score-holdout` additionally appends one
entry to an explicit ledger file that must lie outside every repository
worktree the command can name. Save durable copies of the outputs under
`.agent-artifacts/`, outside the repository index.

Proposing dimensions, obtaining recorded scores from a provider, and the one
real holdout measurement are evaluation operations performed by the operator.
The command never performs them.

## Records

Every digest below is `sha256:` followed by the SHA-256 of the record's
canonical JSON: sorted keys, `,` and `:` separators, UTF-8, and no NaN or
infinity. Every record is a JSON object with exactly the listed keys. An
unknown key, including a `partition` field inside a scores record, rejects the
whole input.

- Question set: a schema-1 `plan_record_question_set` report from
  `scripts/build-plan-question-set.py`. It is accepted only when that command's
  `verify` logic regenerates it unchanged from the recorded commit. Partition
  membership, labels, input digests, and `protocol.min_class_count` are taken
  from it and from nowhere else.
- Dimensions: `schema_version` 1, `kind` `feature_dimensions`, and
  `dimensions`, a list of 1 to 64 objects with `id` (lowercase identifier) and
  `text` (at most 2000 bytes). The record is identified by its digest.
- Scores: `schema_version` 1, `kind` `feature_scores`, `dimensions_sha256`,
  `recorder` with `identity` and `model_id`, and `scores`, a list of objects
  with `question_id`, `input_sha256`, and `values`. `values` holds exactly one
  number from 0 to 1 per dimension id. A record joins a question only when both
  `question_id` and `input_sha256` match.
- Weights: the `feature_weights` record printed by `fit`. It binds the question
  set, protocol, dimensions, and scores digests, the recorder, the tuning
  coverage, the standardization, and per-class bias and dimension weights.
- Holdout scoring: the `feature_holdout_scoring` record printed by
  `score-holdout`. It carries the ledger key and its key material, the band
  thresholds and decision limits read from this protocol, the baseline class,
  and one prediction per holdout question, with unscored questions retained.
- Report: the `feature_scoring_report` record printed by `report`.
- Ledger entry: one canonical JSON line with `schema_version` 1, `kind`
  `feature_scoring_ledger_entry`, `key`, and `scoring_sha256`.

## Fitting

- `fit` accepts tuning questions only. A holdout record, a record naming no
  question, a record whose input digest differs, and a score outside 0 to 1
  reject the input before any weight is computed.
- Records are ordered by `question_id`, so the order of a scores file never
  changes the result.
- Features are standardized by the tuning mean and population standard
  deviation; a constant dimension keeps scale 1.
- Fitting is standard-library multinomial logistic regression by batch gradient
  descent from zero weights, with the learning rate, iteration count, and L2
  weight fixed below. The bias is not penalized. Identical inputs produce
  identical weight and report digests.
- A tuning question without a score is not fitted. It is listed in the tuning
  coverage and makes every later report `insufficient_evidence`.

## Holdout scoring

- `score-holdout` reads this protocol before any holdout record is scored and
  refuses weights fitted under a different protocol, dimensions, or question
  set. It accepts holdout records only.
- The ledger key is the digest of the question set source commit, the sorted
  holdout input digests, and the dimensions, weights, and band-threshold
  digests. A key already recorded in the ledger is refused before any holdout
  record is scored.
- The ledger is created with mode 0600, must stay a regular file owned by the
  caller, is never a symlink, and is only appended to under an exclusive lock.
- The ledger prevents accidental reuse of the holdout. It does not stop an
  operator who starts a new ledger, changes the protocol, or reads the holdout
  labels directly, and a clean ledger never proves that the holdout stayed
  unseen.
- The predicted class is the one with the highest probability, the first in
  label order on a tie. Confidence is that maximum class probability.

## Reporting

- `report` accepts a holdout scoring record only when its digest is recorded in
  the ledger under its own key and its protocol and band thresholds equal this
  protocol.
- Accuracy is reported overall, per class, and per confidence band. Each
  accuracy is paired with the majority-class baseline computed on the same
  records: the fraction of those records whose label is the tuning partition's
  majority class, the first in label order on a tie. Each section states its
  own count, and the baseline repeats that count.
- A holdout question without a score stays in the overall and per-class
  denominators as incorrect and is reported as unscored. It belongs to no band.
- A class, a band, or the overall set whose count is below the question set's
  `protocol.min_class_count` is `not_measurable` and carries no accuracy and no
  baseline.
- The writer refuses to emit a report in which any accuracy lacks a paired
  baseline over the same count.

## Outcomes

- `insufficient_evidence` is reported whenever tuning or holdout coverage is
  incomplete, the overall set is not measurable, or any band is not
  measurable. The blockers are named.
- Otherwise `meets_limits` is reported when the overall accuracy exceeds its
  paired baseline by at least `min_overall_accuracy_gain_over_baseline`, and
  `below_limits` when it does not.
- A per-class result that is not measurable is named but does not by itself
  block the outcome.
- No outcome changes a plan, a routing rule, or a lifecycle state.

## Committed cases

`tests/fixtures/feature-scoring/cases.json` holds synthetic dimensions and
synthetic tuning cases, each marked `used_for_tuning`. They demonstrate tool
behavior only. No holdout question, holdout score, or recorded provider
response is committed, and a result on these cases is not a prediction result.

## What a result does not mean

A declared label is the author's judgment at authoring time, not ground truth
about how hard the work was, and the classes are imbalanced. A result measures
agreement with declared labels on one frozen holdout, read beside the
majority-class baseline of the same records. A holdout result used to change
dimensions, weights, or thresholds invalidates the evaluation, and the rerun
must record that holdout as `used_for_tuning`.

## Parameters

The command reads exactly one JSON block from this file. Changing it is a
protocol change and invalidates every earlier weight and holdout result.

```json
{
  "baseline": "tuning_majority_class",
  "bands": [
    {"band": "high", "lower_inclusive": 0.7},
    {"band": "middle", "lower_inclusive": 0.5},
    {"band": "low", "lower_inclusive": 0.0}
  ],
  "classes": ["low", "ordinary", "high"],
  "confidence": "max_class_probability",
  "decision_limits": {"min_overall_accuracy_gain_over_baseline": 0.05},
  "fit": {
    "feature_scaling": "tuning_mean_population_standard_deviation",
    "initial_weights": "zero",
    "iterations": 2000,
    "l2_weight": 0.01,
    "learning_rate": 0.1,
    "method": "multinomial_logistic_regression",
    "optimizer": "batch_gradient_descent"
  },
  "kind": "feature_scoring_protocol",
  "label_field": "implementation_risk",
  "min_count_source": "question_set_protocol_min_class_count",
  "schema_version": 1
}
```
