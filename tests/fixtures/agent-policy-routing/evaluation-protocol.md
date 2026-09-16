# Agent policy routing evaluation protocol

This protocol separates two kinds of evidence for the relocation of detailed
agent policy out of the always-loaded entrypoints and changes to the routed development guidance.

## Deterministic route checks

`scripts/check-root-agent-policy.py` and `tests/test-validation-tools.py` check
that each relocated requirement still has one canonical normative destination,
that each entrypoint carries a route naming that destination, that the route
stays within its size cap, and that neither entrypoint restates the relocated
rule. These checks are static. Passing them says the obligation is still
reachable; it says nothing about how an agent behaves.

`tests/fixtures/agent-policy-routing/scenarios.json` holds the fixed median and
edge scenarios used while adjusting wording. It contains only those fixed
cases. It never contains the held-out evaluation input.

## Independent scenario evaluation

### Matched Baseline And Candidate

Freeze the baseline instruction revision, candidate instruction bytes, fixed task inputs and scoring criteria before comparison.
Use the same permitted evaluator route, requested model and effort for both sides, with separate fresh sessions and no baseline answer supplied to the candidate session.
Record the evaluator identity, requested settings, runtime-observed settings and exact instruction and task digests; unavailable provider execution details remain unobserved.
Evaluate both the root instructions and generated instructions with only their established path substitutions, preserving identical task facts and criteria.
Keep policy inputs directly readable; do not substitute a compressed policy summary.

For each case, retain the response, the required behavior, the observed action or interpretation, omissions, critical failures and unresolved outcomes.
Include unchanged small work, tool lookup and output effects, incomplete system ownership, a review that invalidates an assumption, uncertain feedback attribution and exhausted execution authority.
Score whether material assumptions are connected to evidence, normal and counterexample probes test the intended property, unnecessary investigation is avoided, and existing stop and authorization rules are preserved.
Separate a reader's proposed action from an actually executed probe; neither static checks nor a plausible proposal establishes observed tool behavior.
Keep raw responses and comparison evidence local under the existing logging policy, never in the fixed fixture.

### Independently Sealed Holdout

The held-out case is prepared by an independent evaluator, not by the
implementer. The evaluator writes it to a parent-owned local artifact outside
this repository and outside the plan's `write_scope`, seals it with SHA-256,
and withholds its content until the final frozen candidate is evaluated.

Only the digest is recorded in the plan. This file names the boundary; it never
embeds the case.

The evaluation is invalid if any of the following happens.

- The sealed digest changes between sealing and evaluation.
- The case content reaches the implementer before the candidate is frozen.
- The outcome of the held-out evaluation is used to tune the candidate further.

A critical failure is a missing requirement, a compressed summary standing in
for the governing policy, an authority overstep, or an ignored stop. Any
critical failure stops the work under the existing owner-decision policy
instead of being answered by weakening the requirement or by repeated tuning.

Apply those critical-failure stops to candidate fixed-case and holdout evaluation as well as formal implementation review.
Record a baseline failure as comparison evidence, never as authority to reproduce it or as a reason to relax the candidate criterion.
Complete fixed-case wording work and formal correction before freezing the final candidate; after holdout evaluation, report a failure or inconclusive result rather than tune on it.
Guidance evaluation is separate from formal implementation review and grants no extra review or continuation allowance.

### Effects And Added Effort

Report matched per-case baseline and candidate observations, including unchanged, worse and inconclusive results rather than only improvements.
Record measured extra reading, probes, model starts and elapsed time with their measurement boundaries and source coverage; leave unavailable values unobserved.
Report confounders such as different runtime settings, missing tool access, session ordering or policy exposure.
If the comparison does not demonstrate improvement, report no demonstrated improvement.
No productivity or universal future-reliability claim follows from static success, a reader evaluation or a small scenario sample.

## What the evidence does not mean

Byte reduction is recorded in UTF-8 bytes. It is not a token count, a latency
measurement, or a productivity claim. Static route success is not evidence of
empirical semantic success.
