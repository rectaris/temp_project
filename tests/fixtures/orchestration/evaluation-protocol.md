# Bounded Proactive Subagent Evaluation Protocol

Use `proactive-bounded-subagents.json` as the fixed scenario set.

Required classes are `median`, `edge`, `negative`, and `holdout`.

`holdout` must never be used for tuning and must remain outside any prompt updates.

Do not use another evaluator's result or intended fix before artifact generation is complete.

## Independent evaluator input

Provide only the following:

1. The target policy path.
2. One scenario's `id`, `class`, `task`, and `source`.
3. The full requirements block from the fixture.
4. This protocol text.

The evaluator must work in blank-context mode: do not add repository-specific context beyond this payload.

## Report format

```text
- Artifact:
- Requirement Results:
  - R1: pass|fail|partial — reason
  - R2: pass|fail|partial — reason
  - ...
- Unclear Points:
- Discretionary Assumptions:
- Retry Count:
- Tool/Time Notes:
```

- Requirement Results must include all requirements with pass/fail/partial and rationale.

The negative scenario must not delegate.

The holdout scenario must be evaluated without prompt tuning.

If all critical requirements do not pass, the scenario set is not considered a pass.
