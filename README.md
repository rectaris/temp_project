# Project Agent Workflow

Reusable Codex workflow package for project management, agent file routing, and repository file hygiene.

This repository is intentionally small:

- `SKILL.md` teaches Codex when and how to use the workflow.
- `references/` holds detailed guidance loaded only when needed.
- `assets/templates/` contains files that can be copied into a target repository.
- `scripts/init-project-workflow.sh` installs the templates into a target repository.
- `scripts/lint-project-workflow.sh` checks that this package remains installable.

## Install Into A Repository

```sh
scripts/init-project-workflow.sh /path/to/repo
```

Use `--force` to overwrite existing workflow files:

```sh
scripts/init-project-workflow.sh --force /path/to/repo
```

## Validate

```sh
scripts/lint-project-workflow.sh
tests/smoke.sh
```

