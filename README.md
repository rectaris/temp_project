# Project Agent Workflow

Reusable Codex workflow package for project management, agent file routing, and repository file hygiene.

This repository is intentionally small:

- `SKILL.md` teaches Codex when and how to use the workflow.
- `references/` holds detailed guidance loaded only when needed.
- `copier.yml` defines the long-term template interface.
- `template/` contains files rendered into a target repository.
- `scripts/init-project-workflow.sh` wraps Copier for simple installs.
- `scripts/lint-project-workflow.sh` checks that this package remains installable.

## Install Into A Repository

Preferred:

```sh
copier copy /path/to/project-agent-workflow /path/to/repo
```

Wrapper:

```sh
scripts/init-project-workflow.sh /path/to/repo
```

Use force/default answers for non-interactive generation:

```sh
copier copy -f /path/to/project-agent-workflow /path/to/repo
```

Commit the generated `.copier-answers.yml` file so `copier update` can work later.

## Update A Generated Repository

From the generated repository:

```sh
copier update
```

Review any `*.rej` files manually before committing. Stable template releases should be tagged so downstream updates can resolve versions predictably.

## Validate

```sh
scripts/lint-project-workflow.sh
tests/smoke.sh
```
