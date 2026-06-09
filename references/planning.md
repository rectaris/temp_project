# Planning Files

Use lightweight planning files to make agent work resumable without turning every task into process overhead.

## Files

- `docs/plan/plan.md`: short active-work index.
- `docs/plan/active/*.md`: current executable work with scope, target files, validation, and acceptance.
- `docs/plan/backlog/*.md`: future or condition-waiting work.
- `docs/plan/checked.md`: machine-readable index of completed work.
- `docs/plan/checked/*.md`: durable completion records.
- `docs/plan/handoffs/`: temporary queue for real cross-agent or cross-session transfers.

## Rules

- Create or update an active plan before non-trivial edits.
- Keep `plan.md` short; move details into active task files.
- Move completed active work to `checked/` and update `checked.md`.
- Use handoff records only when direct prompt results are not enough.
- Keep README files human-facing; keep operational rules in `docs/agent/`.

## Active Plan Fields

Recommended fields:

- `status`
- `review_class`
- `target_files`
- `required_specs`
- `validation`
- `acceptance`
- `notes`

Review classes:

- `A`: local/mechanical work.
- `B`: semantic implementation work.
- `C`: architecture, product direction, story, frame, or philosophy. Requires explicit human approval.

## Lifecycle Scripts

Generated repositories may include local-only plan lifecycle helpers:

- `scripts/create-plan.sh active <slug>`
- `scripts/create-plan.sh backlog <slug>`
- `scripts/promote-plan.sh docs/plan/backlog/NNN-slug.md`
- `scripts/complete-plan.sh docs/plan/active/NNN-slug.md`
- `scripts/finalize-active-plan.sh docs/plan/active/NNN-slug.md`
- `scripts/check-agent-completion.sh`
- `scripts/lint-plan-docs.py`
- `scripts/format-plan-docs.py`
- `scripts/search-plan-archive.py --text <term>`

These helpers must remain local-only. External issue or memory sync belongs in an optional module.
