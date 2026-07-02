---
name: implementation-guidelines
description: Use when writing, reviewing, or refactoring code to keep changes scoped, assumptions explicit, abstractions justified, and validation tied to repository policy without importing project-specific facts.
---

# Implementation Guidelines

Use this skill as auxiliary behavior guidance while implementing, reviewing, or refactoring.

## Priority

1. Follow `AGENTS.md`, parent workspace rules, and project-local `docs/agent/spec-index.yaml`.
2. Read routed project specs before editing.
3. Apply this skill only where it does not conflict with project-specific rules.

## Before Implementation

- State assumptions when the request has multiple plausible meanings.
- Ask or challenge briefly when ambiguity affects data semantics, user-visible behavior, validation scope, security, or project invariants.
- Define success criteria through tests, scripts, builds, screenshots, or other deterministic validation when practical.

## During Implementation

- Make the smallest coherent change that satisfies the task.
- Match existing project patterns before adding new abstractions.
- Add abstractions only when they reduce real complexity, duplication, or risk.
- Avoid drive-by formatting, comment rewrites, dependency churn, and unrelated cleanup.
- Keep public contracts, generated artifacts, data schemas, and integration boundaries explicit.
- Prefer enforceable checks over prose-only rules when a rule can be tested or linted.

## Verification

- Prefer reproduce-first fixes when a bug can be captured by a test.
- Run validation required by project specs and the active plan.
- If validation cannot run, record the concrete blocker and residual risk.
- Every changed line should trace to the user request, active plan, or required validation.
