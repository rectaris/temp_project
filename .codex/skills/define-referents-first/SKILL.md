---
name: define-referents-first
description: Use before drafting design documents, investigation reports, remediation proposals, causal summaries, or new public, domain, state, condition, event, value, record, type, method, or boolean names when a new or compressed label could hide multiple concrete referents. Preserve unknowns, seal referents before labels, and validate the target against a referent contract. Do not use for quotations, mechanical edits, boilerplate, or established project terms used with their established meaning.
---

# Define Referents First

1. Read `AGENTS.md`, `docs/agent/spec-index.yaml`, and `docs/agent/SPEC_REFERENT_FIRST.md`.
2. Select the task-specific model described in [references/workflow.md](references/workflow.md).
3. For file-based work, create a contract with `python3 scripts/referent-contract.py init` before drafting the target.
4. Record unknowns explicitly, then add concrete referents without labels.
5. Seal referents before assigning labels or choosing concrete-text decisions.
6. Never label an `unknown` or `disputed` referent.
7. Finalize naming decisions before drafting the target.
8. Record and check the draft, then obtain an independent or human review when the contract mode is `required`.

If a sealed referent is wrong, reopen and correct the contract before regenerating affected text.

Do not preserve a wrong row and compensate with extra prose.

For chat-only work without a writable filesystem, show the referent and uncertainty stage before the target prose and state that artifact-order validation is unavailable.
