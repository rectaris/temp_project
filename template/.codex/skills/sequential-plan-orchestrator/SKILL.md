---
name: sequential-plan-orchestrator
description: Execute numbered files in docs/plan/active sequentially by delegating one bounded plan at a time to a configurable worker, then reviewing, accepting, and updating dependent plans. Use when a project needs parent-controlled orchestration of multiple active implementation plans.
---

# Sequential Plan Orchestrator

Process active plans as a parent-owned sequence. Keep implementation in the worker, keep acceptance and lifecycle decisions in the parent, and stop when a plan cannot be safely accepted.

## Workflow

1. Enumerate `docs/plan/active/<number>-<name>.md` files and sort by the integer prefix.
   Stop on malformed names, duplicate numbers, ambiguous or blocked plans, or missing required inputs.
2. Read the selected plan, every required spec, and the active-plan index before delegation.
3. Resolve the configured worker agent name, defaulting to `sequential_plan_worker`.
   Stop if that agent is unavailable.
4. Delegate exactly one plan with its path, explicit read scope, explicit write scope, required validation commands, and this return contract: changed paths, implementation summary, validation results, blockers, cross-plan impacts, and remaining risks.
5. Wait for the worker result.
   Treat it as advisory until the parent inspects the diff and validates the repository.
6. Reject and stop on a blocker, missing input, unrelated change, or failed required validation.
   Do not retry automatically, fall back to another worker, or continue to the next plan.
7. On acceptance, update only the assigned plan's concise validation notes and affected later plans' decisions, targets, dependencies, or validation conditions.
   Keep detailed logs and large evidence under `.agent-logs/` or `.agent-artifacts/`.
8. Repeat for the next numeric plan only after acceptance.
   Finish with consolidated validation and remaining-risk reporting.

## Boundaries

- The worker may modify only the assigned plan's explicit write scope.
- The parent may modify orchestration metadata, affected active-plan instructions, concise validation notes, and local evidence references.
- The parent must not implement product or code changes directly.
- Do not process the next plan, spawn descendants, perform external-service writes, weaken tests, or commit unrelated changes.
- Do not copy full decision audits, raw logs, or large artifacts into `docs/plan/active`.
