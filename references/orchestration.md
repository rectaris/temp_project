# Orchestration

The main agent owns interpretation, final integration, validation acceptance, planning updates, and commits.

## Helper Roles

- `repo_explorer`: read-only file discovery and impact analysis.
- evidence_synthesizer means a read-only helper that compares multiple repositories, logs, specifications, implementation alternatives, or cause hypotheses and reports agreements, contradictions, impact boundaries, unresolved questions, confidence, and source evidence for parent verification.
- `fast_scoped_worker`: fast, low-ambiguity code changes with explicit write scope and predetermined validation.
- `scoped_worker`: bounded implementation with explicit write scope.
- `change_reviewer`: read-only correctness, regression, validation, and security review.
- `docs_researcher`: read-only external or version-specific research.
- `sequential_plan_worker`: implementation of exactly one assigned active plan without descendant delegation.

## Delegation Rules

- Delegate only concrete, bounded, independently useful work.
- Assign non-overlapping write scopes.
- Use `evidence_synthesizer` only for bounded comparison of multiple evidence sources, alternatives, or hypotheses whose result the parent can verify.
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
- Use `gpt-5.6-luna` with xhigh reasoning for `evidence_synthesizer`.
- Use `gpt-5.3-codex-spark` with medium reasoning for fast scoped coding and one-plan sequential implementation.
- Use `gpt-5.6-terra` with medium reasoning for bounded implementation that includes ordinary judgment.
- Use `gpt-5.6-sol` with high reasoning for correctness, regression, security-sensitive, and policy-conflict review.
- Use a higher one-off effort only when the delegated task remains bounded and the prompt states why the default is insufficient.
- Reserve Sol with xhigh reasoning for exceptional final review of security, ownership, migration, or release risk.

## Luna Effort Selection

- Use low for targeted repository searches and existing-pattern lookup.
- Use medium for current documentation research and extraction of facts from several files.
- Use high as a one-off override when bounded read-only work must reconcile conflicting evidence or analyze a long context and the prompt states the expected quality gain.
- Use xhigh through `evidence_synthesizer` when the task compares multiple repositories, logs, specifications, implementation alternatives, or cause hypotheses and must report agreements, contradictions, impact boundaries, and unresolved questions.
- Do not use Luna for deterministic pass-or-fail commands, code edits, or final security, ownership, migration, release, or policy judgment.
- Do not define Luna max as a default helper profile. Move the hardest final judgment to Terra or Sol unless a representative evaluation demonstrates a measurable Luna max benefit.

## Optional External Services

MCP, Linear, graph memory, and external CLIs should be modeled as opt-in modules. For each workflow, document whether operations are dry-run, read-capable, or write-capable. External writes require explicit user intent or a documented lifecycle command.

Generated repositories should use `docs/agent/SPEC_EXTERNAL_SERVICES.md` as the integration guide. It should name the credential source, connection metadata, write-capable commands, local fallback, and review boundary for each enabled service. Disabled services should still explain what must be added before the service can become required.
