---
name: project-agent-workflow
description: Use when a repository needs reusable AI-agent project management through a Copier template, task-scoped file routing, planning docs, handoff queues, validation selection, Git discipline, or deterministic file-management guardrails.
---

# Project Agent Workflow

Use this skill to set up or operate a repository that needs predictable coding-agent behavior across project management, file routing, and file hygiene.

## Core Workflow

1. Start from the target repo's `AGENTS.md`.
2. Open `docs/agent/spec-index.yaml`.
3. Select the smallest matching task route.
4. Read only `default_reads` plus the route's `required` docs.
5. Add `conditional` docs only when the task statement or touched files match.
6. Track implementation work in `docs/plan/plan.md` and durable task files.
7. Validate with the smallest complete command set for the changed files.
8. Commit each coherent work unit.

When generated lifecycle scripts are present, prefer them for plan creation, promotion, completion, archive search, plan linting, handoff cleanup, task-context selection, and change-aware validation. Keep external-service workflows optional unless the target repository enables them in `SPEC_EXTERNAL_SERVICES.md`.

## Install Templates

Preferred:

```sh
copier copy /path/to/project-agent-workflow /path/to/repo
```

For non-interactive defaults:

```sh
copier copy -f /path/to/project-agent-workflow /path/to/repo
```

The wrapper `scripts/init-project-workflow.sh` is available for local convenience, but Copier is the long-term interface. Commit the generated `.copier-answers.yml` so future `copier update` runs can reuse answers and apply template changes.

## Reference Selection

- For file routing and `spec-index.yaml`: read `references/routing.md`.
- For planning, active/backlog/checked files, and handoffs: read `references/planning.md`.
- For validation matrices and completion checks: read `references/validation.md`.
- For safe file edits and cleanup policy: read `references/file-management.md`.
- For helper agents and delegation boundaries: read `references/orchestration.md`.
- For Copier template maintenance and release flow: read `references/template-development.md`.

## Non-Negotiables

- Keep project-specific facts out of this skill; put them in the target repo's specs.
- Prefer deterministic scripts for rules that can be checked.
- Do not manually edit generated `.copier-answers.yml`; use `copier update`.
- Keep `AGENTS.md` short; detailed policy belongs under `docs/agent/`.
- Keep MCP, Linear, and graph-memory workflows opt-in and side-effect classified.
