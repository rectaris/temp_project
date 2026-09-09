# Agent policy routing evaluation protocol

This protocol separates two kinds of evidence for the relocation of detailed
agent policy out of the always-loaded entrypoints.

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

## What the evidence does not mean

Byte reduction is recorded in UTF-8 bytes. It is not a token count, a latency
measurement, or a productivity claim. Static route success is not evidence of
empirical semantic success.
