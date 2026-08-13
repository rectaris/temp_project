# Orchestration

The main agent owns interpretation, final integration, validation acceptance, planning updates, commits, and completion reporting.

## Proactive bounded delegation

- Delegate repository-wide work proactively without waiting for a per-task user instruction only when bounded, independent helper work produces independently useful output and its expected context reduction, parallelism, or review value exceeds coordination cost; repository breadth alone is insufficient.
- Trigger proactive delegation when at least one applies:
  - multiple independent code or documentation areas are affected,
  - cross-specification reconciliation is required,
  - validation, security, or orchestration review crosses several policy areas,
  - large or dense sources benefit from parallel bounded context reduction and expected return justifies the overhead.
- Keep delegation bounded:
  - use explicit `write_scope` per helper,
  - keep helper write scopes non-overlapping,
  - keep context files read-only,
  - require an explicit acceptance note before the main session integrates results.
- Keep non-delegation as the default for short deterministic commands, direct user clarification, and local tasks where coordination cost exceeds expected benefit.
- Keep authorization decisions and final high-risk judgment in the main session.
- Keep secrets, external writes, destructive operations, and authorization actions outside delegated authority unless a separate explicit policy grants that authority.

## Non-delegation boundaries

- Do not delegate short deterministic commands, direct user clarification, final interpretation, final validation acceptance, commit/release decisions, or final report generation.
- Do not delegate work involving external writes, secrets, secret handling, destructive operations, authorization decisions, or final high-risk policy or architectural judgment.
- The main session must reconcile findings and decide what is accepted before planning updates and commits.
- Final report transparency is mandatory: state whether helpers were used, and when used, each helper's role and write scope plus the main-session acceptance rationale.

## Helper Roles

- `repo_explorer`: read-only file discovery and impact analysis.
- evidence_synthesizer means a read-only helper that compares multiple repositories, logs, specifications, implementation alternatives, or cause hypotheses and reports agreements, contradictions, impact boundaries, unresolved questions, confidence, and source evidence for parent verification.
- `fast_scoped_worker`: fast, low-ambiguity code changes with explicit write scope and predetermined validation.
- `scoped_worker`: bounded implementation with explicit write scope.
- `change_reviewer`: read-only correctness, regression, validation, and security review.
- `docs_researcher`: read-only external or version-specific research.
- `sequential_plan_worker`: read-only implementation contract for exactly one assigned active plan; writable execution must route through `scripts/run-sandboxed-plan-worker.py`.

## Delegation Rules

- Delegate only concrete, bounded, independently useful work.
- Assign non-overlapping write scopes.
- For writable sequential active-plan implementation, use `scripts/run-sandboxed-plan-worker.py run` and `scripts/run-sandboxed-plan-worker.py apply`; the worker sees a read-only clone with writable shadow mounts only for normalized `write_scope` entries. Do not grant direct repository write access to the built-in `sequential_plan_worker` profile.
- Admit one writable candidate only as an admissible implementation slice: one invariant that is independently reviewable and validatable and has an explicit later integration gate. Split a broad active plan before delegation rather than using its breadth as a candidate boundary.
- Read optional scalar `implementation_risk` and `implementation_ambiguity` as `low`, `ordinary`, or `high`. Only an absent field defaults to `ordinary`; a present blank, whitespace-only, list-valued, or unknown value fails closed.
- Use Spark medium only when both inputs are `low`; use Terra medium when neither is `high` and at least one is `ordinary`; refuse writable delegation when either input is `high`.
- Preserve explicit nonblank preferred-model, preferred-reasoning, fallback-model, and fallback-reasoning overrides, but reject Sol as both a preferred and fallback writable model. Sol remains reserved for independent security and regression review.
- The sandboxed sequential runner prefers `gpt-5.3-codex-spark` with medium reasoning. Only a bounded Codex CLI error line for a usage limit, rate limit, unavailable model, or denied model access may trigger one fallback to `gpt-5.6-luna` with max reasoning.
- A fallback attempt must use the same committed source HEAD in a new isolated clone, scratch directory, writable-shadow set, staged authentication copy, and ephemeral Codex session. Do not reuse worker changes, Git configuration, caches, or output files from the preferred attempt.
- Authentication, network, refusal, implementation, validation, sandbox, custom-worker, and unclassified failures stop without model fallback. Keep every attempt's raw output local and record only bounded provenance and digests in the successful manifest.
- Reuse availability knowledge only through an explicit state path outside the repository paired with one nonblank orchestration run identifier. The runner accepts only its exact bounded schema, rejects symlinked targets or ancestors, and uses directory-file-descriptor reads and atomic replacement so target or parent swaps are not followed.
- Availability state stores only one allowlisted reason code per bounded model name. Once a preferred or fallback model is recorded unavailable, skip another start of that model in the same run; never reinterpret remembered unavailability as an implementation, semantic, or validation result.
- Initial candidate manifests contain parent-produced bounded telemetry: attempt and total runner durations, actual model starts, current availability failures, skipped known-unavailable starts, candidate generations, full-validation count, and the selected risk and ambiguity. Durations are finite and nonnegative; custom workers record one attempt duration and zero model starts. Never place prompts, raw output, environment values, or credentials in availability state or telemetry.
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
Use helpers only when they return independently useful output and expected context reduction, parallelism, or review value outweighs coordination cost.
When helper output is used, include role, scope, and acceptance summary in the final report.

## Model Defaults

- Use `gpt-5.6-luna` with low reasoning for targeted repository exploration.
- Use `gpt-5.6-luna` with medium reasoning for current documentation research.
- Use `gpt-5.6-luna` with xhigh reasoning for `evidence_synthesizer`.
- Use `gpt-5.3-codex-spark` with medium reasoning for fast scoped coding and one-plan sequential implementation.
- For one-plan sequential implementation only, use `gpt-5.6-luna` with max reasoning as the single isolated availability fallback defined above; it is not the default helper profile.
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
- Do not define Luna max as a default helper profile. Its bounded sequential-worker availability fallback does not authorize final judgment; otherwise move the hardest final judgment to Terra or Sol unless a representative evaluation demonstrates a measurable Luna max benefit.

## Optional External Services

MCP, Linear, graph memory, and external CLIs should be modeled as opt-in modules. For each workflow, document whether operations are dry-run, read-capable, or write-capable. External writes require explicit user intent or a documented lifecycle command.

Generated repositories should use `docs/agent/SPEC_EXTERNAL_SERVICES.md` as the integration guide. It should name the credential source, connection metadata, write-capable commands, local fallback, and review boundary for each enabled service. Disabled services should still explain what must be added before the service can become required.
