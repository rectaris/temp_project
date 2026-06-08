# File Management Guardrails

## Read Before Edit

- Read the target file and nearby conventions before changing it.
- Prefer `rg` and targeted reads over broad directory sweeps.
- Keep generated, cache, build, and dependency folders out of commits.

## Edit Policy

- Keep changes scoped to the task.
- Do not revert user changes unless explicitly asked.
- Avoid destructive operations. Use Git to inspect changes before cleanup.
- Inspect backup files before deleting them.
- Preserve public paths and external links unless the task explicitly changes them.

## Secrets

- Do not read or print likely secret-bearing files without explicit need.
- Never commit credentials, tokens, private keys, or local environment files.
- Treat hook gates as guardrails, not substitutes for judgment.

