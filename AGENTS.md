# AGENTS.md

Agent entrypoint for `project-agent-workflow`.

## Scope

This repository packages reusable coding-agent project management, file routing, validation, and file-management templates.

## Rules

- Keep `SKILL.md` concise; move detailed guidance into `references/`.
- Keep installable repo files under `template/`.
- Keep `copier.yml` as the long-term generation/update interface.
- Keep deterministic checks in `scripts/` or `tests/`.
- Do not add project-specific `supportcard-status` facts to generic templates.
- When writing or editing Japanese prose in this repository, follow `docs/agent/SPEC_JAPANESE_TECH_WRITING.md`.
- When changing Japanese writing policy for generated projects, keep `docs/agent/SPEC_JAPANESE_TECH_WRITING.md` and `template/docs/agent/SPEC_JAPANESE_TECH_WRITING.md` semantically aligned, or state the intentional difference in the change.
- Use `docs/agent/spec-index.yaml` to route root-level agent policy when the task concerns planning, logging, compression, decision audit, or Japanese prose.
- Keep raw agent logs and large agent artifacts local under `.agent-logs/` and `.agent-artifacts/`; do not commit them.
- Treat external transcript logs as primary full-turn evidence when available, and repo-local hook event logs as best-effort corroborating evidence.
- Record missing transcript or hook sources explicitly in run manifests.
- Use `.codex/hooks/agent_log_event.py` as the root best-effort Codex lifecycle event logger when Codex hooks are active; keep raw outputs under `.agent-logs/`.
- Use run manifests, search, excerpts, and optional context compression before loading large raw logs.
- Read `AGENTS.md`, `docs/agent/`, validation policy, and security policy directly; do not route normative instructions through compression.
- Run decision audit before creating or materially updating active plans when meaningful design, storage, validation, lifecycle, security, or artifact-boundary choices remain open; keep the full audit out of `docs/plan/active`.
- Keep active plans as executable agent instructions. Record final accepted decisions only, not recommendation matrices or debate transcripts.
- Use the repo-local `.codex/skills/decision-audit` skill when available; keep `docs/agent/SPEC_DECISION_AUDIT.md` as the normative root policy.
- Validate with `scripts/lint-project-workflow.sh` and `tests/smoke.sh` before completion.
- Use Git for all changes.
- Keep commits granular and scoped to one meaningful work unit.
- Do not stage unrelated files.
- Do not rewrite history unless explicitly requested.
- Preserve user changes you did not make.
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

## Reports

- State touched repository: `temp_project`.
- State link changes.
- Report validation and the commit hash, or the exact dirty-worktree blocker when a commit cannot be made.
