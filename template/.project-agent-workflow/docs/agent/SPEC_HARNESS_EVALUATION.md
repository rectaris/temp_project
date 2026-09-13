# Harness Evaluation

This specification governs how a model change or an instruction change is assessed from paired local run records. It applies only to harness comparison work. It does not change plan lifecycle, validation authority, security policy, or any other routed specification.

`.project-agent-workflow/scripts/compare-harness-runs.py` reports paired observations from explicitly supplied local records. It is advisory derived information, never acceptance, review, or validation evidence, and it never authorizes adopting a configuration by itself.

## Boundaries

- Supply every record on the command line. The command discovers no run, reads no home directory, launches no model, calls no provider, needs no network, looks up no price, writes no file, and changes no plan lifecycle state.
- The report is written to stdout only. Save it yourself under `.agent-logs/` or `.agent-artifacts/` when a comparison needs a durable copy.
- At most 64 explicit input files of at most 8 MiB each and at most 256 run observations are accepted, and the report is bounded at 256 KiB. A symlinked, nonregular, oversized, duplicated, or structurally invalid input rejects the whole report with a nonzero exit.
- Reports carry digests, declared identities, and counts. They never carry credentials, environment values, prompts, response bodies, or raw transcripts.
- The command verifies structure, digests, and declared links. It cannot authenticate the real-world truth of a local record, so `fixture_kind`, an ordering-evidence `independently_reviewed` status, and a declared reviewer identity remain operator claims that the report restates rather than confirms. Treat a report as evidence about the supplied records only.

## Comparison Protocol

A comparison protocol is one frozen record. It does not grant execution authority.

- It fixes `protocol_id`, `repository_baseline`, `invariant_digest`, `authority_digest`, the complete case roster, `repetitions`, the run `budget`, the metric boundaries, and the predeclared `decision_limits`.
- Each case fixes `task_digest`, `acceptance_digest`, `rubric_digest`, and `fixture_kind`. A `synthetic` case demonstrates tool behavior only.
- Metric boundaries are fixed: elapsed time is `task_start_to_terminal_outcome`, cost is a `directly_recorded_billed_amount`, and human interventions are counted under one frozen counting rule whose digest every observation must repeat.
- `decision_limits` must require every critical requirement to pass. The remaining limits set the minimum quality-pass delta and the maximum elapsed ratio, cost ratio, and additional interventions.

## Configuration Slots

Three slots are supported: `old_model_current_instructions`, `new_model_current_instructions`, and `new_model_candidate_instructions`. Each slot fixes a declared model, reasoning settings, instruction asset digests, runtime versions, and one `configuration_digest`.

- The `model_effect` comparison pairs the first two slots and may change only the declared model.
- The `instruction_effect` comparison pairs the last two slots and may change only the declared instruction assets.
- Every other declared difference between a pair, including runtime versions, is an uncontrolled input and rejects the report.
- When reasoning settings differ or one side does not expose them, the pair is reported as a `configuration_comparison` rather than a single-axis effect, and no empirical recommendation follows from it.

## Run Observations

A run observation is one evidence-linked outcome for one slot, case, and repetition. It does not grant execution authority.

- Each observation repeats the task, acceptance, repository baseline, invariant, authority, and configuration digests. A mismatch against the frozen protocol rejects the report.
- Declared configuration is never treated as observed execution. `observed_model`, `observed_reasoning_settings`, `observed_runtime`, and `instruction_loading` are reported separately and stay `not_observed` when the run did not record them.
- `outcome` is `completed`, `failed`, `timed_out`, or `model_unavailable`. A timed-out run must still record its elapsed seconds.
- Every quality judgment binds the fixed acceptance item and rubric to one `deterministic_test` or one identified `independent_evaluator`, with its source evidence digest and reviewer provenance. An `agent_self_report` judgment is recorded and reported, and it never supports an empirical recommendation.
- Billed cost, human interventions, and elapsed seconds stay `not_observed` unless the record observes them directly. An observed zero remains a measurement. Tokens are never derived from byte counts and billed cost is never inferred from public prices.

## Evidence And Provenance

- Every observation binds at least one evidence digest. Pass the raw file with `--evidence` to verify that a declared digest names those bytes. A supplied file matching no declared digest rejects the report.
- A declared evidence digest that no supplied file matches stays unverified, and any unverified digest on either compared side withholds the empirical recommendation. Supply every observation transcript and every quality-judgment source before reading a recommendation.
- A verified digest proves content consistency. It never proves preregistration, freeze ordering, holdout independence, or the truth of a local attestation.
- Freeze time, holdout status, and predeclared limits are reported as declared. Ordering evidence is reported separately and reaches `independently_reviewed_link_verified` only when the protocol declares an independently reviewed attestation and `--ordering-evidence` supplies bytes matching its digest.
- Without independently reviewed ordering evidence, the report withholds every empirical recommendation and says so.

## Coverage And Failure Accounting

- The report enumerates every expected slot, case, and repetition cell before evaluating anything. Missing cells, duplicate cells, and unpaired runs are named.
- Errors, timeouts, and unavailable-model outcomes stay in coverage and in the quality denominator. Successful runs are never compared alone.
- Elapsed time over successful runs is reported separately from elapsed time over all runs, and each carries its own denominator. A summary never hides the failure rate.
- Incomplete pairs or fewer than two repetitions yield an inconclusive result, never a pass.
- A metric is comparable only when every run on both compared sides measured it. Partial elapsed, cost, or intervention coverage is still reported with its own denominator, but it withholds the recommendation instead of standing in for the runs that recorded nothing.
- Declared model, runtime, and reasoning settings count as confirmed only when a run observed them and the observation matches the frozen declaration. An unobserved field is never read as agreement.

## Outcomes

The report states one outcome per comparison.

- `adopt_candidate` requires every critical requirement to pass, complete paired coverage, observed values for every compared metric, admissible quality judgments, verified independently reviewed ordering evidence, an operational case roster, and every predeclared limit satisfied. An instruction-attributed recommendation additionally requires observed instruction loading, known host instructions, effective instruction digests matching the frozen assets on both sides, and an observed difference between the two sides' effective instructions.
- `keep_current` is a legitimate result when the candidate is merely equal or a predeclared limit fails.
- `insufficient_evidence` is reported whenever evidence is missing, unpaired, inadmissible, synthetic, or unverified. A candidate run that did not reach a completed outcome is missing candidate evidence and withholds the recommendation, while baseline failures stay in the totals because they are what the change is judged against.
- `blocked_critical_failure` is reported when the candidate records a critical violation. A critical violation is never offset by lower cost, shorter elapsed time, or fewer interventions.
- A critical violation observed on the baseline side withholds the empirical recommendation as `insufficient_evidence`, because the compared evidence set contains a critical failure. Both sides report their critical violation counts.

No universal percentage target, automatic promotion, or automatic configuration switch is defined here.

## Operator Recipe

1. Choose a bounded representative workload before any authorized real run. Include small fixes, cross-file changes, preserved dirty user edits, ambiguous requests, and previously failed verifications.
2. Freeze the protocol and the candidate instructions, record their digests, and have an independent reviewer attest the ordering before the runs start.
3. Set the budget and the predeclared limits before observing any outcome.
4. Run the authorized workload yourself. This command never runs it.
5. Record one observation per cell, including failures and timeouts, and keep the raw evidence files.
6. Compare with `--observation`, `--evidence`, and `--ordering-evidence`, then read the blockers before the recommendation.
7. Keep any holdout outside tuning. A holdout result used to retune the candidate invalidates the evaluation, and the protocol must record that as `used_for_tuning`.

Missing provider access or unrecorded runtime observations leave performance unmeasured. They do not block this offline command, and they do not become adoption evidence.
