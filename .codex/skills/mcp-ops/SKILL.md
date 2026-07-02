---
name: mcp-ops
description: Use before reading from or writing to MCP servers or other external tool providers. Checks project-local external-service policy, keeps context bounded, and preserves repository files, validation output, and Git history as the implementation source of truth.
---

# MCP Operations

Use this skill before any MCP or external-provider read/write that is not already covered by a more specific local skill.

## Policy Gate

1. Read `docs/agent/SPEC_EXTERNAL_SERVICES.md` when present.
2. Read `docs/agent/external-services.yaml` when present.
3. Locate the matching service entry, normally `external_services.mcp`.
4. If the state is `disabled` or `documented`, do not call the service. Continue from local files when safe and report the fallback only when it affects scope, confidence, or completion.
5. If the state is `configured_read_only`, use only listed `allowed_reads`.
6. If the state is `configured_write_capable`, writes still require explicit user intent or a documented lifecycle command.

Missing policy means no external read or write is authorized by this skill.

## Read Strategy

- Prefer local repository files, specs, validation output, and Git history when they can answer the question.
- Start with the narrowest query that can answer the current decision.
- Prefer summaries, IDs, statuses, labels, timestamps, and small result sets before full bodies or schemas.
- Stop querying once the retrieved context is enough for the local change or report.
- Summarize relevant external findings before applying them to plans, code, or docs.

## Write Boundary

- Do not perform external writes unless the current user request or documented lifecycle command authorizes that exact side effect.
- Before writing, identify the target service, object ID or key, intended state, local validation or dry-run evidence, and rollback/fallback behavior.
- Never send or store secrets, credentials, private config, `.env` contents, raw personal data, generated dependency artifacts, build artifacts, or temporary task logs unless the project policy explicitly permits that data class.
