# Copier Template Development

## Source Of Truth

- `copier.yml` defines questions, rendering settings, and update metadata.
- `template/` is the generated repository source of truth.
- `references/` explains agent behavior and template maintenance.
- `scripts/` and `tests/` provide deterministic validation.

## Update-Safe Design

- Keep `.copier-answers.yml` generated and committed in downstream repositories.
- Version this template repo with Git tags before recommending `copier update`.
- Keep project-owned files small and clearly marked.
- Put domain-specific content in generated repo specs, not in this template.
- Avoid `_skip_if_exists` for managed files because skipped files do not receive template updates.
- Treat `*.rej` files from `copier update` as manual review blockers.

## Managed Boundaries

Copier-managed:

- `AGENTS.md`
- generic `docs/agent/SPEC_*.md`
- `docs/agent/spec-index.yaml`
- `docs/plan/` skeleton
- human-facing plan README files
- optional helper prompt templates under `docs/plan/sub-agents/`
- reusable `.codex/agents/` definitions
- deterministic hook templates
- workflow utility scripts
- generic plan lifecycle scripts
- change-aware validation, static security, and structure scanner scripts
- optional external-service policy stubs

Codex helper agents are installed by default and recorded in generated docs/config.

`codex_hooks_mode` separates installed hook scripts from active `.codex/hooks.json` wiring.

External-service modules use generated policy states in `docs/agent/external-services.yaml`; template answers do not authorize MCP, Linear, or graph-memory reads or writes by themselves.

Repository-owned:

- product specs
- UI wording
- domain data contracts
- local validation commands
- external integration settings

## Release Flow

1. Change `copier.yml`, `template/`, references, or tests.
2. Run `UV_CACHE_DIR=.uv-cache uv sync`.
3. Run `UV_CACHE_DIR=.uv-cache uv run copier --version`.
4. Run `scripts/lint-project-workflow.sh`.
5. Run `tests/smoke.sh`.
6. Run `tests/test-hooks.py`.
7. Run `tests/copier-update.sh`.
8. Generate at least one sample project with Copier when the CLI is available.
9. Commit the change.
10. Tag stable template versions for downstream `copier update`.
11. Push `main` and tags to GitHub.

## CI Expectations

- Use `uv sync` before running generated-project checks.
- Run smoke and update tests with `REQUIRE_COPIER=1`.
- Treat generated `*.rej` files as release blockers.
- Keep `git diff --check` as the final whitespace gate.
