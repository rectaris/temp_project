# AGENTS.md

Agent entrypoint for this repository.

## Priority

1. Follow this file first for repository-local behavior.
2. Use parent workspace rules only for cross-repository coordination, security, or Git policy.
3. Open `docs/agent/spec-index.yaml`.
4. Read only `default_reads` plus the matched route's `required` docs before editing.
5. Add `conditional` docs only when the task or touched files match.

## Operating Rules

- Keep project-specific implementation rules in `docs/agent/SPEC_*.md`.
- Track non-trivial implementation work in `docs/plan/plan.md`.
- Use Git for every coherent work unit.
- Preserve user changes you did not make.
- Prefer deterministic checks over prose-only rules.
- Ask before high-impact or ambiguous changes.

## Reports

- State touched repositories.
- State link or public-path changes.
- Report validation run and commit status.

