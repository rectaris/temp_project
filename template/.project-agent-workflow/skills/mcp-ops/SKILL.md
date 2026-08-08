---
name: mcp-ops
description: Use before reading from or writing to MCP servers or other external tool providers. Applies the common project-local external-service gate, keeps context bounded, and preserves repository files, validation output, and Git history as the implementation source of truth.
---

# MCP Operations

Use this skill before every MCP or external-provider read or write.

## Common External-Service Gate

1. Read `.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md` when present.
2. Read `docs/agent/external-services.yaml` when present.
3. Run `python3 .project-agent-workflow/scripts/check-external-service-policy.py check`.
4. Locate the exact service entry, normally `external_services.mcp`.
5. Deny the call when policy or the service entry is missing, or when `state` is `disabled` or `documented`.
6. Require a non-empty `connection`.
7. Validate `authentication` and `credential_reference` as one pair:
   - `none` requires an empty `credential_reference`.
   - `environment` requires a non-empty environment-variable name.
   - `platform` requires `binding:`, `secret:`, or `vault:` followed by a non-secret platform identifier.
   - Any other value or credential material stored in `credential_reference` fails the gate.
8. Classify the exact requested operation as a read or write and require it in `allowed_reads` or `allowed_writes`.
9. Run `python3 .project-agent-workflow/scripts/check-external-service-policy.py authorize <service> read <operation>` before a read.
10. For a write, run the write-authorization check below and then run `python3 .project-agent-workflow/scripts/check-external-service-policy.py authorize <service> write <operation> --authorization-rule "<exact configured rule>"`.

The external-service gate means this common pre-call procedure.
If any check is missing, ambiguous, stale, or mismatched, do not call the provider.
Continue from local files when safe and report the fallback only when it affects scope, confidence, or completion.

## Write-Authorization Check

The write-authorization check passes only when all of these facts are confirmed for the same proposed provider call:

- `state` is `configured_write_capable`.
- The exact operation is listed in `allowed_writes`.
- The authentication pair passes the common gate.
- `write_authorization_rule` is non-empty.
- The current user request or the lifecycle command named by `write_authorization_rule` authorizes the exact service, target, and side effect.
- `dry_run_or_local_validation` is non-empty and its documented check succeeded for the same target and payload.
- The target identifier, intended state, and unavailable fallback are known.

Fail closed when any fact cannot be confirmed.
Do not treat a previous user request, a broad project goal, read authorization, or a dry-run result as write authorization.

## Read Strategy

- Prefer local repository files, specs, validation output, and Git history when they can answer the question.
- Start with the narrowest query that can answer the current decision.
- Prefer summaries, IDs, statuses, labels, timestamps, and small result sets before full bodies or schemas.
- Stop querying once the retrieved context is enough for the local change or report.
- Summarize relevant external findings before applying them to plans, code, or docs.

## Write Boundary

- Apply specialized service rules only after this common gate passes.
- Re-run the write-authorization check when the target, payload, operation, user request, or lifecycle state changes.
- Never send or store secrets, credentials, private config, `.env` contents, raw personal data, generated dependency artifacts, build artifacts, or temporary task logs unless the project policy explicitly permits that data class.
