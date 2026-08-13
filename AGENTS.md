# AGENTS.md

Agent entrypoint for `project-agent-workflow`.

## Scope

This repository packages reusable coding-agent project management, file routing, validation, and file-management templates.

## Rules

- Keep `SKILL.md` concise; move detailed guidance into `references/`.
- Keep installable repo files under `template/`.
- Keep `copier.yml` as the long-term generation/update interface.
- Treat non-destructive Copier evolution as a repository invariant: supported copy and update paths must preserve project-owned product code, policy, configuration, plan history, and validation behavior, and must stop on unresolved conflicts, rejection files, or unclassified tracked-file deletion.
- Keep deterministic checks in `scripts/` or `tests/`.
- Use `references/orchestration.md` for bounded delegation triggers, final ownership, and safety boundaries.
- Do not add project-specific `supportcard-status` facts to generic templates.
- When writing or editing Japanese prose in this repository, follow `docs/agent/SPEC_JAPANESE_TECH_WRITING.md`.
- When changing Japanese writing policy for generated projects, keep `docs/agent/SPEC_JAPANESE_TECH_WRITING.md` and `template/.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md` semantically aligned, or state the intentional difference in the change.
- Use `docs/agent/spec-index.yaml` to route root-level agent policy when the task concerns planning, logging, compression, decision audit, user-facing communication, or Japanese prose.
- Keep raw agent logs and large agent artifacts local under `.agent-logs/` and `.agent-artifacts/`; do not commit them.
- Treat external transcript logs as primary full-turn evidence when available, and repo-local hook event logs as best-effort corroborating evidence.
- Record missing transcript or hook sources explicitly in run manifests.
- Use `.codex/hooks/agent_log_event.py` as the root best-effort Codex lifecycle event logger when Codex hooks are active; keep raw outputs under `.agent-logs/`.
- Use run manifests, search, excerpts, and optional context compression before loading large raw logs.
- Read `AGENTS.md`, `docs/agent/`, validation policy, and security policy directly; do not route normative instructions through compression.
- Run decision audit before creating or materially updating active plans when meaningful design, storage, validation, lifecycle, security, or artifact-boundary choices remain open; keep the full audit out of `docs/plan/active`.
- Keep active plans as executable agent instructions. Record final accepted decisions only, not recommendation matrices or debate transcripts.
- Use the repo-local `.codex/skills/decision-audit` skill when available; keep `docs/agent/SPEC_DECISION_AUDIT.md` as the normative root policy.
- Before introducing a new domain or workflow label in design, investigation, remediation, causal-summary, or naming work, fix its concrete referent and preserve unresolved facts according to `docs/agent/SPEC_REFERENT_FIRST.md`; use `.codex/skills/define-referents-first` for the operational workflow. In chat naming work, show an unnamed referent and uncertainty stage before any candidate or controlled term.
- Use repo-local generic Codex skills such as `.codex/skills/implementation-guidelines`, `.codex/skills/mcp-ops`, `.codex/skills/linear-ops`, `.codex/skills/graph-memory`, and `.codex/skills/plan-archive` only as auxiliary workflow guidance; keep project-specific values in `docs/agent/` policy files.
- Use `scripts/run-sandboxed-plan-worker.py` for writable sequential-plan implementation; keep `.codex/agents/sequential_plan_worker.toml` read-only and apply only parent-admitted candidate patches.
- Review an admitted candidate diff and critical invariants before parent-authorized focused validation, then run the authoritative validation suite exactly once for an otherwise acceptable candidate. After one initial generation and two rejected isolated corrections, require a strategy change; bounded parent implementation is permitted for inseparable high-judgment work or exhausted correction budget with explicit scope, independent review, and unchanged acceptance gates.
- Route the writable runner from the plan's separate `implementation_risk` and `implementation_ambiguity` fields: GPT-5.3-Codex-Spark medium only for low/low, GPT-5.6-Terra medium when neither is high and at least one is ordinary, and refuse either high. Reserve Sol for independent review. Allow exactly one fresh isolated GPT-5.6-Luna max attempt only when the Codex CLI itself reports a bounded usage limit, rate limit, unavailable-model, or denied-model-access error; do not fall back for other failures.
- Before submitting a substantive progress update, proposal, explanation, blocking report, or final summary, follow `docs/agent/SPEC_USER_COMMUNICATION.md` and use `.codex/skills/write-for-reader` for its operational workflow.
- When creating or updating Codex skills, follow `docs/agent/SPEC_SKILL_AUTHORING.md`.
- Validate with `scripts/lint-project-workflow.sh` and `tests/smoke.sh` before completion.
- Use Git for all changes.
- Keep commits granular and scoped to one meaningful work unit.
- Do not stage unrelated files.
- Do not rewrite history unless explicitly requested.
- Preserve user changes you did not make.
- Before deleting generated backup files such as `*.backup`, `*.orig`, or `*.pre-*`, inspect and preserve or report useful prior state.
- Commit after successful validation unless the user requested otherwise or a concrete dirty-worktree blocker prevents it.
- Do not push unless the user explicitly requests it.

## CI Autofix Rules

- Codex must make minimal changes when repairing CI failures.
- Codex must not change unrelated behavior.
- Codex must not weaken tests to make CI pass.
- Codex must not delete failing tests unless the user explicitly requests it.
- Codex must not modify secrets, deployment credentials, or production settings.
- Codex must prefer fixing root causes over skipping checks.
- Codex must stop and report when the failure is due to missing secrets, external service outages, or environment-only issues.

## Delegation Safety and Ownership

- Delegate proactively without requiring a separate per-task user instruction only when a bounded helper can return independently useful output and expected context reduction, parallelism, or review value exceeds coordination cost; repository breadth alone is insufficient.
- Keep final ownership in the main agent for interpretation, final integration, validation acceptance, planning updates, commits, and the final report/completion reporting.
- Do not delegate short deterministic commands (including pass/fail commands), direct user clarification, final policy judgment, authorization decisions, external writes, secret handling, or destructive changes unless an explicit external policy grants that authority.
- Keep helper delegation bounded by `write_scope`, keep context files read-only, and keep final acceptance and reporting in the main session.
- Final report must state whether helpers were used; if used, include role, write scope, and the main-session acceptance decision path.
- Treat helper output as advisory until validated in the main session.

## Reports

- State touched repository: `temp_project`.
- State link changes.
- Report validation and the commit hash, or the exact dirty-worktree blocker when a commit cannot be made.
