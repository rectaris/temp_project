# AGENTS.md

Agent entrypoint for `project-agent-workflow`.

## Scope

This repository packages reusable coding-agent project management, file routing, validation, and file-management templates.

## Rules

- Keep `SKILL.md` concise; move detailed guidance into `references/`.
- Keep installable repo files under `assets/templates/`.
- Keep deterministic checks in `scripts/` or `tests/`.
- Do not add project-specific `supportcard-status` facts to generic templates.
- Validate with `scripts/lint-project-workflow.sh` and `tests/smoke.sh` before completion.
- Use Git for all changes.

## Reports

- State touched repository: `temp_project`.
- State link changes.
- Report validation and commit status.

