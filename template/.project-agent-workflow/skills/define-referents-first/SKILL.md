---
name: define-referents-first
description: Use before drafting design documents, investigation reports, remediation proposals, causal summaries, or new public, domain, state, condition, event, value, record, type, method, or boolean names when a new or compressed label could hide multiple concrete referents. Preserve unknowns, seal referents before labels, and validate the target against a referent contract. Do not use for quotations, mechanical edits, boilerplate, or established project terms used with their established meaning.
---

# Define Referents First

1. Read `AGENTS.md`, `.project-agent-workflow/docs/agent/spec-index.yaml`, and `.project-agent-workflow/docs/agent/SPEC_REFERENT_FIRST.md`.
2. Select the task-specific model described in [references/workflow.md](references/workflow.md).
3. For file-based work, create a contract with `python3 .project-agent-workflow/scripts/referent-contract.py init` before drafting the target.
4. Record unknowns explicitly, then add concrete referents without labels.
5. Classify a referent by its role in the source, not by verb shape: a condition is a truth predicate used for eligibility or triggering, while an event is an occurrence, emission, or recorded boundary. Treat a transition as an event only when the source establishes that occurrence.
6. For a threshold, classify the measurement-versus-limit predicate as a condition. Classify crossing detection, notification, or a recorded transition as an event only when the source establishes that occurrence.
7. Preserve source specificity; do not infer comparison operators, inclusivity, units, causality, timing, or derivation rules that the source does not establish. Record them as unknown when they matter.
8. Run a source-fidelity pass before sealing and before submission. Every operator, boundary, causal, and timing claim must have source evidence; when the source gives only a neutral boundary relation, keep that wording and leave the operator or inclusivity unknown.
9. For a sequence summary, include only source-stated actions and branches. Do not add retries, validation, rollback, documentation, or other workflow steps unless the source requests them; preserve an unresolved outcome instead.
10. Seal referents before assigning labels or choosing concrete-text decisions.
11. Never label an `unknown` or `disputed` referent.
12. When only a property, derivation, or selection rule is unsettled, keep the settled referent separate and mark only that property or rule as `unknown` or `disputed`.
13. Reject any label or first-use definition that changes the sealed semantic kind; read the label and definition as standalone text and confirm they still denote the same referent kind.
14. Finalize naming decisions before drafting the target.
15. Record and check the draft, then obtain an independent or human review when the contract mode is `required`.

If a sealed referent is wrong, reopen and correct the contract before regenerating affected text.

Do not preserve a wrong row and compensate with extra prose.

For a chat deliverable, first show a referent and uncertainty stage containing concrete referents, semantic kinds, boundaries or relations, and certainty without candidate labels or controlled terms.

Only after that stage, assign controlled terms and write the target prose.

Do not add an artifact-order disclaimer to an ordinary answer.

The visible order is required output structure but does not prove hidden reasoning order.
