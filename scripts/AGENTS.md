# Script Sources

This file adds directory-local guidance to the repository root `AGENTS.md`.

## Layout

- Keep directly executed commands and stable documented paths in `scripts/`.
- Put Python modules imported by those commands under `scripts/project_workflow/`.
- Group imported modules by responsibility when more than one module shares the same change reason.
- Do not move a directly executed command without updating every documented, CI, and validation reference.

## Routing

- Change Copier source inventories and generation rules in `project_workflow/copier_inventory.py`.
- Change Copier validation behavior and CLI dispatch in `check-copier-template.py`.
- Keep plan lifecycle, migration, and validation commands at the directory root while they remain independently executable.
- Add new Python sources to the deterministic inventory used by `check-copier-template.py`.

## Validation

- Run `python3 scripts/check-copier-template.py` for inventory or checker changes.
- Run the focused tests for the changed command before the repository-required lint and smoke suites.
- Preserve import-time purity for inventory modules.
