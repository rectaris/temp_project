# Plan Workflow

## Files

- `docs/plan/plan.md`: short active-work index.
- `docs/plan/active/*.md`: active executable tasks.
- `docs/plan/backlog/*.md`: future or condition-waiting work.
- `docs/plan/checked.md`: completed-work index.
- `docs/plan/checked/*.md`: durable completion records.
- `docs/plan/handoffs/`: temporary transfer queue.

## README Boundary

- Keep README files human-facing.
- Keep agent-facing operational policy in `docs/agent/SPEC_*.md`.
- If a reusable operational rule appears only in a README, move or mirror it into `docs/agent/` before relying on it.

## Rules

- Create or update an active plan before non-trivial edits.
- Keep `plan.md` short.
- Archive completed work to `checked/`.
- Use handoff files only for real staged transfer.
- Use a single numeric namespace across active, backlog, and checked files.
- Treat checked archives as historical completion records, not current implementation guidance.
- Search `docs/plan/checked.md` or use `scripts/search-plan-archive.py` before opening full checked archives.
- Preserve durable decisions, validation outcomes, and fallback impact in active or checked records before deleting handoff files.

## Manifest Contract

Recommended active/backlog fields:

- `status`
- `review_class`
- `target_files`
- `required_specs`
- `validation`
- `acceptance`
- `completion_deferred_reason`

Rules:

- `review_class` is `A`, `B`, or `C`.
- Class C work requires explicit human approval before implementation.
- `target_files` should list planned edit or context paths.
- `validation` should list commands needed for completion.
- `completion_deferred_reason` is only for intentionally incomplete work or concrete external blockers.

## Lifecycle Commands

- Next plan id: `python3 scripts/lint-plan-docs.py --next-id`
- Create plan: `scripts/create-plan.sh active <slug>`
- Promote backlog: `scripts/promote-plan.sh docs/plan/backlog/NNN-slug.md`
- Complete plan: `scripts/complete-plan.sh docs/plan/active/NNN-slug.md`
- Finalize before final report: `scripts/finalize-active-plan.sh docs/plan/active/NNN-slug.md`
- Completion gate: `scripts/check-agent-completion.sh`

These scripts are local-only. External service sync belongs to `SPEC_EXTERNAL_SERVICES.md`.
