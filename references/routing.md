# Task-Scoped File Routing

Use a route table so agents do not load every project document for every task.

## Pattern

- `default_reads`: always read before edits.
- `task_types.<name>.summary`: short matching hint.
- `task_types.<name>.required`: read before editing when the route matches.
- `task_types.<name>.conditional`: read only when the task or touched paths match.
- `usually_unneeded`: files that should not be startup context.

## Route Design Rules

- Route by decision surface, not by directory alone.
- Keep validation and Git workflow in `default_reads`.
- Keep product, UI, data, environment, and orchestration concerns separate.
- Add conditional docs for expensive or rarely needed context.
- Never use route selection as permission to ignore parent security or Git rules.

## Minimum Routes

- `planning_docs`: plan indexes, active task files, checked archives, handoff docs.
- `product_logic`: runtime behavior, calculations, business rules, data contracts.
- `ui_layout`: visible text, layout, interaction, accessibility.
- `japanese_prose`: Japanese README text, documentation, plans, specs, prompts, issue text, review comments, or UI copy.
- `environment_data_flow`: build/runtime paths, generated data, deployment assumptions.
- `orchestration_meta`: helper agents, handoff policy, hooks, execution workflow.

## Japanese Prose

Route Japanese prose work to `docs/agent/SPEC_JAPANESE_TECH_WRITING.md`.
Keep the rule as a generated repository document rather than an installed external skill so Copier updates can carry it to downstream repositories.
