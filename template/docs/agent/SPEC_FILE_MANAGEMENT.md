# File Management

## Read Before Edit

- Read the target file and nearby conventions before changing it.
- Prefer `rg` and targeted reads over broad directory sweeps.
- Do not sweep all `docs/agent/` files for normal startup; use `spec-index.yaml`.

## Edit Policy

- Keep changes scoped to the task.
- Do not revert user changes unless explicitly asked.
- Avoid destructive operations.
- Use Git to inspect changes before cleanup.
- Keep generated, cache, build, dependency, and local tool folders out of commits.

## Backup And Generated Files

- Inspect backup files such as `*.backup`, `*.orig`, and `*.pre-*` before deleting them.
- Preserve or report useful prior state before cleanup.
- Do not create ad hoc backup files beside runtime artifacts unless a repository rule explicitly permits it.

## Secrets

- Do not read or print likely secret-bearing files without explicit need.
- Never commit credentials, tokens, private keys, `.env` contents, or local environment files.
- Keep external service credentials in environment variables or platform secret stores.
