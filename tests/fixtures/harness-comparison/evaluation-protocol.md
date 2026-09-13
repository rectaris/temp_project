# Harness comparison evaluation protocol

This protocol separates two kinds of evidence for a model change or an
instruction change.

## Deterministic tool checks

`tests/test-harness-comparison.py` checks that `scripts/compare-harness-runs.py`
rejects mismatched task, acceptance, baseline, invariant, authority, and
configuration inputs, that it rejects uncontrolled runtime differences, that it
retains failed, timed-out, and unavailable-model runs in coverage and in the
quality denominator, and that missing, inadmissible, synthetic, unpaired, or
unverified evidence cannot become an adoption recommendation.

`tests/fixtures/harness-comparison/cases.json` holds the fixed tuning cases and
the historical failure cases used while adjusting the command. It contains only
those clearly synthetic cases. It never contains an independent holdout and it
never records an observed model outcome.

These checks are deterministic. Passing them says the command reports what the
supplied records observe. It says nothing about how any model performs.

## Independent evaluation

A real comparison is prepared by the operator, not by this test suite.

- Choose a bounded representative workload before any authorized real run.
  Cover small fixes, cross-file changes, preserved dirty user edits, ambiguous
  requests, and previously failed verifications.
- Freeze the protocol and the candidate instructions first and record their
  SHA-256 digests. Have an independent reviewer attest that the freeze happened
  before any run outcome existed, and store that attestation in a parent-owned
  local artifact outside this repository.
- Prepare any holdout case separately, keep it withheld until the candidate is
  frozen, and never use its result to retune the candidate.
- Set the run budget and the predeclared decision limits before observing any
  outcome.

Only digests and declared identities reach the report. This file names the
boundary; it never embeds a case.

The evaluation is invalid if any of the following happens.

- A frozen digest changes between freezing and evaluation.
- A holdout case reaches the implementer before the candidate is frozen.
- A holdout result is used to tune the candidate further.
- Only successful runs are compared.

A critical failure is a lost requirement, an authority overstep, an ignored
stop, or a falsely reported success. Any critical failure blocks adoption. It is
never offset by lower cost, shorter elapsed time, or fewer interventions.

## What the evidence does not mean

A verified digest proves content consistency. It is not preregistration, not
holdout independence, and not proof that a local attestation is true. A passing
deterministic tool check is not evidence that a model or an instruction change
performs better. Until an authorized real comparison runs, performance remains
unmeasured.
