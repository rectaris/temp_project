# Planning Files

Use lightweight planning files to make agent work resumable without turning every task into process overhead.

## Files

- `docs/plan/plan.md`: short active-work index.
- `docs/plan/active/*.md`: current executable work with scope, target files, validation, and acceptance.
- `docs/plan/backlog/*.md`: future or condition-waiting work.
- `docs/plan/checked.md`: machine-readable index of completed work.
- `docs/plan/checked/*.md`: durable completion records.
- `docs/plan/handoffs/`: temporary queue for real cross-agent or cross-session transfers.
- `docs/plan/README.md`, `backlog/README.md`, and `handoffs/README.md`: human-facing Japanese overviews.
- `docs/plan/sub-agents/`: optional helper prompt and custom-agent notes for repeated workflows.

## Rules

- Create or update an active plan before non-trivial edits.
- Keep `plan.md` short; move details into active task files.
- Move completed active work to `checked/` and update `checked.md`.
- Use handoff records only when direct prompt results are not enough.
- Keep README files human-facing; keep operational rules in `docs/agent/`.

## Active Plan Fields

Recommended fields:

- `status`
- `task_type`
- `review_class`
- `human_design_required`
- `human_approval_status`
- `target_files`
- `target_json`
- `required_specs`
- `validation`
- `acceptance`
- `acceptance_focus`
- `expected_output`
- `checked_summary_ja`
- `completion_deferred_reason`

Review classes:

- `A`: local/mechanical work.
- `B`: semantic implementation work.
- `C`: architecture, product direction, story, frame, or philosophy. Requires explicit human approval.

Prefer English for manifest values and operational detail so agents can parse plans consistently. Japanese is expected for human-facing summaries, domain terms, and `checked_summary_ja`.

## Lifecycle Scripts

Generated repositories may include local-only plan lifecycle helpers:

- `scripts/create-plan.sh active <slug>`
- `scripts/create-plan.sh backlog <slug>`
- `scripts/promote-plan.sh docs/plan/backlog/NNN-slug.md`
- `scripts/complete-plan.sh docs/plan/active/NNN-slug.md`
- `scripts/finalize-active-plan.sh docs/plan/active/NNN-slug.md`
- `scripts/check-agent-completion.sh`
- `scripts/select-task-context.sh docs/plan/active/NNN-slug.md`
- `scripts/clean-handoffs.sh --dry-run`
- `scripts/lint-plan-docs.py`
- `scripts/lint-plan-docs.sh`
- `scripts/format-plan-docs.py`
- `scripts/format-plan-docs.sh --check`
- `scripts/search-plan-archive.py --text <term>`

These helpers must remain local-only. External issue or memory sync belongs in an optional module.
