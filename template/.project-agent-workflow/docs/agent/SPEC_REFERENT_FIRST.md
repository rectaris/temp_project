# Referent-First Semantic Guard

This specification prevents a fluent label from becoming the unexamined basis of design, investigation, remediation, summary, or code naming.

The policy fixes concrete referents, semantic kinds, evidence, unresolved facts, and relevant ordering before assigning controlled terms.

## Scope

Apply this policy when work does any of the following:

- introduces a new public, domain, workflow, state, condition, event, value, record, type, method, or boolean name;
- compresses a multi-step causal or investigative sequence into a short label;
- writes a design, investigation report, remediation proposal, or decision whose central terms are not already established by the project;
- uses one candidate term for referents that may have different semantic kinds.

Do not apply it to quotations, mechanical edits, boilerplate, reuse of an established project term with its established meaning, or short text that introduces no controlled term.

When scope is uncertain, create an advisory contract or keep the concrete description instead of inventing a label.

## Semantic Model

Use a task-specific view over these shared fields:

- source and evidence;
- purpose;
- concrete referent;
- referent kind;
- reasoning role;
- relations or ordering;
- certainty;
- naming decision;
- candidate label and first-use definition.

Use task-specific relations rather than forcing every task into one universal table.

Classify semantic kind from the referent's role in the source, not from whether its wording contains a change verb.

A condition is a truth-valued predicate used for eligibility, gating, or triggering.

An event is an occurrence, emission, or recorded transition boundary.

Treat the transition into a condition as a separate event only when the source establishes that occurrence rather than merely stating the predicate.

For threshold semantics, classify the predicate comparing a measurement with a configured limit as a condition.

Classify detection of a crossing, emission of a notification, or a recorded transition as an event only when the source establishes that occurrence.

Preserve the source's level of specificity when describing the referent.

Do not infer comparison operators, boundary inclusivity, units, causality, timing, or derivation rules that the source does not establish.

Record those details as unknown when they affect design or naming.

Run a source-fidelity pass before sealing referents and again before submitting the target.

Every operator, boundary, causal, and timing claim must point to source evidence.

When the source provides only a neutral natural-language boundary relation, preserve that relation in the referent and definition while leaving the exact operator and inclusivity unknown.

Investigation work should preserve unknown, hypothesis, test, observed record, inference, and next-decision relations.

State design should preserve condition, event, prior state, next state, and invariant relations.

API and data design should preserve actor, operation, input, output, failure, entity, attribute, and identifier relations.

Naming work should preserve referent, kind, scope, lifetime, label, and definition relations.

Causal summaries should preserve premise, evidence, inference, decision, and execution order.

An executable sequence summary must contain only actions and branches established by the source.

Do not add retry loops, validation, rollback, documentation, or other workflow steps merely because they are generally useful.

When the source does not state what happens after an inconclusive result, preserve that outcome as unresolved instead of choosing the next action.

## Uncertainty

Use `confirmed`, `inferred`, `unknown`, or `disputed` as certainty states.

Treat `unknown` and `disputed` as valid outcomes rather than blanks to fill.

Do not assign a label to an `unknown` or `disputed` referent.

Record what evidence would resolve an unknown and which naming or design decision remains blocked.

Do not convert uncertainty into certainty to complete a table or continue prose.

Attach uncertainty to the narrowest concrete referent that is actually unresolved.

When a value, event, condition, or other referent is settled but a property, derivation, or selection rule concerning it is not, represent the settled referent and the unresolved property or rule separately.

Do not merge them into a row such as `value or rule`, and do not lower the settled referent's certainty merely because its derivation is unresolved.

## Controlled Terms

A controlled term is a label newly introduced or redefined by the current work.

Each controlled term must identify exactly one referent in the contract.

A referent stage does not precede naming when its rows or bullets begin with candidate labels or controlled terms.

The assigned label and its first-use definition must preserve the sealed referent's semantic kind when read without the surrounding explanation.

Reject a naming decision that turns an event into a time or boundary, a condition into a value, a record into an observation action, or any other referent into a different kind.

Different semantic kinds require different controlled terms even when they participate in one workflow.

For example, a threshold value, the condition that compares against it, the event that begins work, and the resulting state are separate referents.

Prefer an established project term when it matches the referent.

For a new term, record a first-use definition in the form `X means ...` or an equivalent project-language definition.

If a useful definition cannot be written, use the concrete referent description instead of the term.

## File-Based Workflow

Store local working contracts under `.agent-artifacts/referent-contracts/` unless the user requests a durable deliverable elsewhere.

Use `.project-agent-workflow/scripts/referent-contract.py` to make visible artifact order enforceable:

1. Register the source, target, task kind, and advisory or required mode.
2. Record unknowns, including an explicit review that no unknowns were found when applicable.
3. Add referents without labels.
4. Seal the referent projection and its hash.
5. Assign a label or an explicit concrete-text decision to every label-eligible referent.
6. Finalize labels before creating the target draft.
7. Record the draft hash and run structural validation.
8. Obtain an independent or human semantic review for required contracts.

The sealed projection hash identifies the reviewed referent content.

It does not prove the model's hidden reasoning order.

If a sealed referent is wrong, reopen the contract, correct the referent, reseal it, and regenerate affected target text.

Do not patch explanatory prose around a wrong referent while preserving the wrong contract row.

## Chat-Only Work

Before any candidate label or controlled term appears, submit a visible stage that identifies each concrete referent, semantic kind, boundary or relation, and certainty without naming it.

Assign controlled terms only in a later stage, then write the target prose from those decisions.

This visible order is an output requirement.

It does not prove the model's hidden reasoning order, and ordinary user-facing answers should not add an artifact-order disclaimer unless the user requests audit evidence.

## Review

Self-consistency between a contract and its draft is necessary but not sufficient.

An independent semantic reviewer should first extract referents and ordering from the source without seeing the author's contract.

The reviewer should then compare that extraction with the contract and draft and report merged referents, missing referents, lost ordering, undefined terms, and unsupported certainty.

A required contract passes only after an independent-agent or human review is recorded.

## Enforcement Boundary

Use deterministic validation for contract state, hashes, unique labels, blocked naming, first-use definitions, and controlled-term presence.

Use hooks as advisory restoration and completion reminders unless a target explicitly declares required mode.

Do not parse a Codex transcript as a required validation interface.

Do not block unrelated Markdown files based only on filename or keyword heuristics.

After context compaction or session restoration, reread active contract files instead of relying on a compressed recollection of their definitions.

## Evaluation

Keep median, edge, negative-trigger, and hold-out scenarios outside the skill.

Evaluate at least referent collisions, kind collisions, lost causal order, undefined new terms, unsupported certainty, false triggers, and added workflow cost.

Do not treat same-session self-review as independent empirical validation.
