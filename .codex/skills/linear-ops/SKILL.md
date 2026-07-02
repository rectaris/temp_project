---
name: linear-ops
description: Use when reading, drafting, syncing, or completing Linear-backed planning tasks. Requires project-local external-service policy for workspace, team, credentials, allowed operations, and write authorization.
---

# Linear Operations

Use this skill for Linear-backed plan, issue, status, comment, label, or sync work.

## Policy Gate

1. Use `.codex/skills/mcp-ops/SKILL.md` first when it exists.
2. Read `docs/agent/SPEC_EXTERNAL_SERVICES.md` and `docs/agent/external-services.yaml`.
3. Locate `external_services.linear_sync`.
4. If the state is `disabled` or `documented`, do not read or write Linear. Keep the local plan workflow active and record sync deferral only when it affects completion.
5. If the state is `configured_read_only`, read only listed `allowed_reads`.
6. If the state is `configured_write_capable`, writes still require explicit user intent or a documented lifecycle command.

Do not assume workspace, team, status, label, or project identifiers. They must come from the project-local policy or a linked project spec.

## Local Source Of Truth

- Repository plan files are the execution manifest and offline fallback.
- Linear is a human-facing planning or review surface when configured.
- GitHub, CI, local validation, and repository files remain authoritative for implementation state.
- Preserve file paths, commands, symbols, issue keys, commit hashes, and technical identifiers verbatim.

## Write Guardrails

- Use dry-run or local payload validation before any write-capable flow.
- Preserve human-authored issue content outside managed regions.
- Use deterministic source markers or unique local plan IDs for duplicate prevention.
- Fail closed when credentials, target team/status, labels, permissions, managed-region markers, or duplicate-prevention checks cannot be confirmed.
- Do not create, update, comment, assign, label, or close issues unless that exact side effect is authorized.
