---
name: plan-archive
description: Use when completing an active plan by moving docs/plan/active work into docs/plan/checked, updating plan indexes, and preserving validation notes through the generated plan lifecycle scripts.
---

# Plan Archive

Use this skill when active work tracked in `docs/plan/active/*.md` is complete.

## Workflow

1. Confirm the active plan exists under `docs/plan/active/`.
2. Confirm the plan has a non-empty `checked_summary_ja`.
3. Record validation results, unresolved risks, and deferred work in the plan before archiving.
4. Run `.project-agent-workflow/scripts/complete-plan.sh <active-plan>` to mark the validated plan `ready_to_archive`.
5. Run `.project-agent-workflow/scripts/finalize-active-plan.sh <active-plan>` to move the plan into `docs/plan/checked/` with `status: checked`.
6. Stop and follow `.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md` if either lifecycle script is unavailable; do not substitute a manual move.
7. Review the checked file, the `docs/plan/plan.md` update, and the `docs/plan/checked.md` index entry.
8. Run the repository's normal completion validation or report the concrete blocker.

## Rules

- Keep raw logs and large command output outside `docs/plan`; store short summaries or manifest paths.
- Do not use deferred-completion fields for work that is actually complete.
- If the project has external issue sync, follow `.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md` before any external status update.
- Do not manually rewrite checked archives except for a deliberate correction.
