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
4. Prefer `scripts/finalize-active-plan.sh <active-plan>` when available.
5. Otherwise use `scripts/complete-plan.sh <active-plan>` when available.
6. Review the move to `docs/plan/checked/`, the `docs/plan/plan.md` update, and the `docs/plan/checked.md` index entry.
7. Run the repository's normal completion validation or report the concrete blocker.

## Rules

- Keep raw logs and large command output outside `docs/plan`; store short summaries or manifest paths.
- Do not use deferred-completion fields for work that is actually complete.
- If the project has external issue sync, follow `docs/agent/SPEC_EXTERNAL_SERVICES.md` before any external status update.
- Do not manually rewrite checked archives except for a deliberate correction.
