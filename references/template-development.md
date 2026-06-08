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
- reusable `.codex/agents/` definitions
- deterministic hook templates
- workflow utility scripts

Current `use_codex_agents` and `use_hooks` answers are recorded in generated docs/config. They do not remove files from the rendered tree because conditional file exclusion in `copier.yml` would make update behavior harder to reason about.

Repository-owned:

- product specs
- UI wording
- domain data contracts
- local validation commands
- external integration settings

## Release Flow

1. Change `copier.yml`, `template/`, references, or tests.
2. Run `scripts/lint-project-workflow.sh`.
3. Run `tests/smoke.sh`.
4. Run `tests/test-hooks.py`.
5. Run `tests/copier-update.sh`.
6. Generate at least one sample project with Copier when the CLI is available.
7. Commit the change.
8. Tag stable template versions for downstream `copier update`.
9. Push `main` and tags to GitHub.

## CI Expectations

- Install Copier before running generated-project checks.
- Run smoke and update tests with `REQUIRE_COPIER=1`.
- Treat generated `*.rej` files as release blockers.
- Keep `git diff --check` as the final whitespace gate.
