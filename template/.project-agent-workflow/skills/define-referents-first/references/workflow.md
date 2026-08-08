# Referent-First Workflow

## Select a task view

Use the smallest view that preserves the task's meaning:

| Task | Relations to preserve |
|---|---|
| Investigation | unknown, hypothesis, test, observed record, inference, next decision |
| State design | condition, event, prior state, next state, invariant |
| API design | actor, operation, input, output, failure, postcondition |
| Data design | entity, attribute, value, record, identifier, relation |
| Naming | referent, kind, scope, lifetime, label, definition |
| Causal summary | premise, evidence, inference, decision, execution order |

## Create and seal a contract

Create the local contract before the target:

```text
python3 .project-agent-workflow/scripts/referent-contract.py init .agent-artifacts/referent-contracts/<slug>/contract.json --slug <slug> --task-kind <kind> --source <source> --target <target> --mode advisory
```

Use `add-unknown` and `review-unknowns` before adding referents.

Use `add-referent` without a candidate label.

Run `seal-referents` only after concrete targets, kinds, reasoning roles, relations, evidence, and certainty are accurate.

## Decide labels

After sealing, use `assign-label` for a controlled term or `use-concrete-text` when no new term is justified.

Run `finalize-labels` only when every `confirmed` or `inferred` referent has one of those decisions.

An `unknown` or `disputed` referent remains blocked from naming.

## Draft and review

Write the target only after labels are finalized.

Run `record-draft`, `check`, and `semantic-diff` after writing it.

For required mode, give an independent reviewer the source and target before showing the contract.

Record a passing independent-agent or human report with `record-review`.

Use `close-advisory` only when an advisory contract intentionally ends without independent review.

Use `reopen` when a referent, certainty, or relation must change.
