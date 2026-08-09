# Orchestration

The main agent owns interpretation, final integration, validation acceptance, planning updates, and commits.

## Helper Roles

- `repo_explorer`: read-only file discovery and impact analysis.
- `fast_scoped_worker`: fast, low-ambiguity code changes with explicit write scope and predetermined validation.
- `scoped_worker`: bounded implementation with explicit write scope.
- `change_reviewer`: read-only correctness, regression, validation, and security review.
- `docs_researcher`: read-only external or version-specific research.
- `sequential_plan_worker`: implementation of exactly one assigned active plan without descendant delegation.

## Delegation Rules

- Delegate only concrete, bounded, independently useful work.
- Assign non-overlapping write scopes.
- Use `fast_scoped_worker` only when the expected edit and validation are known before delegation.
- Stop a fast worker when it encounters architecture, policy, security, authorization, destructive-operation, external-write, or scope-expansion decisions.
- Keep final judgment in the main session.
- Treat helper output as advisory until accepted through validation.
- Use durable handoff files only for cross-session transfer or staged work.
- Keep repeated helper prompt templates under `docs/plan/sub-agents/` when a project needs them.
- Use deterministic Stop hooks only as review prompts; they do not replace validation.

## Cost Gate

Use local execution for short deterministic commands, direct user clarification, final integration, validation acceptance, commits, tags, pushes, releases, and high-risk decisions.
Use helpers when context pressure, file size, semantic risk, or review value outweighs coordination cost.

## Model Defaults

- Use `gpt-5.6-luna` with low reasoning for targeted repository exploration.
- Use `gpt-5.6-luna` with medium reasoning for current documentation research.
- Use `gpt-5.3-codex-spark` with medium reasoning for fast scoped coding and one-plan sequential implementation.
- Use `gpt-5.6-terra` with medium reasoning for bounded implementation that includes ordinary judgment.
- Use `gpt-5.6-sol` with high reasoning for correctness, regression, security-sensitive, and policy-conflict review.
- Use a higher one-off effort only when the delegated task remains bounded and the prompt states why the default is insufficient.
- Reserve Sol with xhigh reasoning for exceptional final review of security, ownership, migration, or release risk.

## Optional External Services

MCP, Linear, graph memory, and external CLIs should be modeled as opt-in modules. For each workflow, document whether operations are dry-run, read-capable, or write-capable. External writes require explicit user intent or a documented lifecycle command.

Generated repositories should use `docs/agent/SPEC_EXTERNAL_SERVICES.md` as the integration guide. It should name the credential source, connection metadata, write-capable commands, local fallback, and review boundary for each enabled service. Disabled services should still explain what must be added before the service can become required.
