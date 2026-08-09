# Copier Template Development

## Source Of Truth

- `copier.yml` defines questions, rendering settings, and update metadata.
- `template/` is the generated repository source of truth.
- `references/` explains agent behavior and template maintenance.
- `scripts/` and `tests/` provide deterministic validation.

## Update-Safe Design

- Treat preservation of downstream product code, repository policy, configuration, plan history, and validation viability as a template-development invariant for every supported copy and update path.
- Keep `.copier-answers.yml` generated and committed in downstream repositories.
- Version this template repo with Git tags before recommending `copier update`.
- Keep replaceable workflow content under `.project-agent-workflow/`.
- Use `_skip_if_exists` for root entrypoints and mutable repository state that Copier seeds but does not own after creation.
- Put domain-specific content under generated `docs/agent/` or another declared project extension, not in the managed core.
- Keep host-discovered bridge files small and route them to the managed core.
- Treat `*.rej` files from `copier update` as manual review blockers.
- Reject an update fixture that leaves unresolved conflicts, unclassified tracked-file deletion, or broken repository-specific validation even when Copier exits successfully.
- Use a versioned pre-update guard and a separate adoption command when a breaking layout change would otherwise delete or conflict with legacy same-path files.
- Keep adoption commands narrow, recoverable, and covered by fixtures from supported tags.
- Require `--trust` for every documented copy and update command because the template always runs the post-render agent-profile normalization task.
- Explain that `--trust` authorizes template tasks but does not establish that an update is safe to commit.

## Managed Boundaries

Copier-managed:

- `.project-agent-workflow/` policy, Skills, hooks, and scripts
- generated generic `.agents/skills/*/SKILL.md` discovery bridges
- legacy `.codex/hooks/*.py` compatibility bridges
- `.github/workflows/project-agent-workflow.yml`
- optional CI autofix workflow and prompt

Codex helper agents are installed by default and recorded in generated docs/config.

`codex_hooks_mode` separates installed hook scripts from active `.codex/hooks.json` wiring.

External-service modules use generated policy states in `docs/agent/external-services.yaml`; template answers do not authorize MCP, Linear, or graph-memory reads or writes by themselves.

Repository-owned:

- root `AGENTS.md`, `README.md`, `.gitignore`, `.codex/config.toml`, and `.codex/hooks.json`
- seeded `.codex/agents/*.toml` helper-agent definitions, except for the template-fixed `model` and `model_reasoning_effort` fields
- `.agents/skills/` entries whose names do not collide with generated generic skills
- `docs/agent/` project policy and external-service settings
- `docs/plan/` active state and history
- product specs, UI wording, domain data contracts, and local validation adapters

The post-render profile task may replace only `model` and `model_reasoning_effort` in seeded helper-agent definitions.

It must preserve instructions and every unrelated project-owned field.

## Release Flow

1. Change `copier.yml`, `template/`, references, or tests.
2. Run `UV_CACHE_DIR=.uv-cache uv sync`.
3. Run `UV_CACHE_DIR=.uv-cache uv run copier --version`.
4. Run `scripts/lint-project-workflow.sh`.
5. Run `tests/smoke.sh`.
6. Run `tests/test-hooks.py`.
7. Run `tests/copier-update.sh`, including the direct-update guard and recopy-based pre-v1 adoption lanes.
8. Generate at least one sample project with Copier when the CLI is available.
9. Commit the change.
10. Tag stable template versions for downstream `copier update`.
11. Push `main` and tags to GitHub.

## CI Expectations

- Use `uv sync` before running generated-project checks.
- Run smoke and update tests with `REQUIRE_COPIER=1`.
- Treat generated `*.rej` files as release blockers.
- Keep `git diff --check` as the final whitespace gate.
