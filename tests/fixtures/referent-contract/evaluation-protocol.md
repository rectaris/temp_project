# Referent-First Evaluation Protocol

Use `scenarios.json` as the fixed scenario set.

Do not edit a scenario while comparing baseline and referent-first behavior.

Do not use the hold-out scenario to tune the skill, policy, or evaluator prompt.

## Independent evaluator input

Give each evaluator a fresh context containing only:

1. the target policy or skill path;
2. one scenario task and source;
3. that scenario's requirements;
4. the report format below.

Do not provide the author's referent contract, suspected failure, intended fix, or results from another evaluator before the evaluator produces its artifact.

## Report format

```text
- Artifact:
- Requirement Results: pass, fail, or partial for every requirement with evidence
- Referent Collisions:
- Kind Collisions:
- Lost Ordering:
- Unsupported Certainty:
- Undefined Controlled Terms:
- Unclear Points:
- Discretionary Assumptions:
- Retry Count:
- Tool/Time Notes:
```

## Passing threshold

Every requirement marked `critical` must pass.

The negative scenario must not create a referent contract.

The hold-out scenario must not regress relative to the median and edge scenarios.

Record baseline and referent-first results separately so added workflow time and false-trigger cost remain visible.

Independent empirical results are pending until a fresh evaluator session is explicitly authorized.
