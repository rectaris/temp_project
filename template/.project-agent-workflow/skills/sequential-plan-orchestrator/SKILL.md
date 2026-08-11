---
name: sequential-plan-orchestrator
description: Execute numbered files in docs/plan/active sequentially by delegating one bounded plan at a time to the generated sequential_plan_worker agent, then reviewing, accepting, and updating dependent plans. Use when a project needs parent-controlled orchestration of multiple active implementation plans.
---

# Sequential Plan Orchestrator

Process active plans as a parent-owned sequence. Keep implementation in the worker, keep acceptance and lifecycle decisions in the parent, and stop when a plan cannot be safely accepted.

## Workflow

1. Enumerate `docs/plan/active/<number>-<name>.md` files and sort by the integer prefix.
   Stop on malformed names, duplicate numbers, ambiguous or blocked plans, or missing required inputs.
2. Read the selected plan, every required spec, and the active-plan index before delegation.
3. Verify `.project-agent-workflow/scripts/run-sandboxed-plan-worker.py` is available and keep the built-in `sequential_plan_worker` profile read-only.
   Stop if the sandboxed runner is unavailable.
4. Run `.project-agent-workflow/scripts/run-sandboxed-plan-worker.py run <plan>` to create a candidate patch and manifest from an isolated clone. The runner mounts the clone read-only and over-mounts writable shadows only for normalized `write_scope` entries; temporary artifacts belong under the worker scratch directory.
   Pass the selected plan path and keep the plan's `context_files` read-only.
5. Inspect the candidate patch, manifest, and worker result.
   Treat them as advisory until the parent validates the repository.
6. Reject and stop on a blocker, missing input, an out-of-scope path, an unrelated change, or failed required validation.
   Do not retry automatically, fall back to direct writable delegation, or continue to the next plan.
7. On acceptance, apply the candidate with `.project-agent-workflow/scripts/run-sandboxed-plan-worker.py apply <manifest>`, then update only the assigned plan's concise validation notes and affected later plans' decisions, targets, dependencies, or validation conditions.
   Keep detailed logs and large evidence under `.agent-logs/` or `.agent-artifacts/`.
8. Repeat for the next numeric plan only after acceptance.
   Finish with consolidated validation and remaining-risk reporting.

## Boundaries

- The worker may modify only the assigned plan's explicit write scope: unlisted clone paths, including `.git`, are read-only during execution, and the parent independently admits only an in-scope candidate patch.
- The parent may modify orchestration metadata, affected active-plan instructions, concise validation notes, and local evidence references.
- The parent must not implement product or code changes directly.
- Do not process the next plan, spawn descendants, perform external-service writes, weaken tests, commit unrelated changes, or bypass `.project-agent-workflow/scripts/run-sandboxed-plan-worker.py`.
- Do not copy full decision audits, raw logs, or large artifacts into `docs/plan/active`.
