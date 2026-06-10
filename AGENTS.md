# AGENTS.md

Agent entrypoint for `project-agent-workflow`.

## Scope

This repository packages reusable coding-agent project management, file routing, validation, and file-management templates.

## Rules

- Keep `SKILL.md` concise; move detailed guidance into `references/`.
- Keep installable repo files under `template/`.
- Keep `copier.yml` as the long-term generation/update interface.
- Keep deterministic checks in `scripts/` or `tests/`.
- Do not add project-specific `supportcard-status` facts to generic templates.
- Validate with `scripts/lint-project-workflow.sh` and `tests/smoke.sh` before completion.
- Use Git for all changes.
- Keep commits granular and scoped to one meaningful work unit.
- Do not stage unrelated files.
- Do not rewrite history unless explicitly requested.
- Preserve user changes you did not make.
- Commit after successful validation unless the user requested otherwise or a concrete dirty-worktree blocker prevents it.
- Do not push unless the user explicitly requests it.

## Reports

- State touched repository: `temp_project`.
- State link changes.
- Report validation and the commit hash, or the exact dirty-worktree blocker when a commit cannot be made.
