---
name: linear-ops
description: Use when reading, drafting, syncing, or completing Linear-backed planning tasks. Requires project-local external-service policy for workspace, team, credentials, allowed operations, and write authorization.
---

# Linear Operations

Use this skill for Linear-backed plan, issue, status, comment, label, or sync work.

## Policy Gate

1. Apply `.agents/skills/mcp-ops/SKILL.md` as the common external-service gate.
2. Use `external_services.linear_sync` and classify the exact Linear operation as a read or write.
3. If the common gate denies the call, do not read or write Linear. Keep the local plan workflow active and record sync deferral only when it affects completion.
4. Apply the Linear-specific rules below only after the common gate passes.

Do not assume workspace, team, status, label, or project identifiers. They must come from the project-local policy or a linked project spec.

## Local Source Of Truth

- Repository plan files are the execution manifest and offline fallback.
- Linear is a human-facing planning or review surface when configured.
- GitHub, CI, local validation, and repository files remain authoritative for implementation state.
- Preserve file paths, commands, symbols, issue keys, commit hashes, and technical identifiers verbatim.

## Write Guardrails

- Require the common write-authorization check to pass for the exact issue, project, comment, label, assignee, or status change.
- Preserve human-authored issue content outside managed regions.
- Use deterministic source markers or unique local plan IDs for duplicate prevention.
- Fail closed when credentials, target team/status, labels, permissions, managed-region markers, or duplicate-prevention checks cannot be confirmed.
- Do not create, update, comment, assign, label, or close issues unless that exact side effect is authorized.
