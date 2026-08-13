---
name: mcp-ops
description: Use before reading from or writing to MCP servers or other external tool providers. Applies the versioned project-local external-service gate, task authorization, and effect boundaries while preserving repository evidence as the implementation source of truth.
---

# MCP Operations

Use this skill before every MCP or external-provider read or write.

## Common External-Service Gate

1. Read `docs/agent/SPEC_EXTERNAL_SERVICES.md` and `docs/agent/external-services.yaml`.
2. Run `python3 scripts/check-external-service-policy.py check`.
3. Identify policy schema version 1 or 2 before authorizing the exact provider operation.
4. Confirm the active environment has configured and authenticated the requested provider; provider availability does not authorize an operation.
5. Classify the exact operation as a read or write; version 1 requires the current user request or documented lifecycle command to authorize it, while version 2 requires the current user request itself.
6. For version 1, require the configured service state, operation allowlist, and write-authorization rule.
7. For version 2, apply the task-scoped default, identify the exact target and every applicable effect for each provider call, require exact target-and-effect confirmation where configured, and give every denied effect precedence before reads as well as writes.
8. Run the version-appropriate `authorize` command immediately before the provider call.

If any fact is missing, ambiguous, stale, or mismatched, do not call the provider.
Use the configured local fallback and report it only when it affects scope, confidence, validation, or completion.

## Version 2 Provider-Call Check

A version 2 read passes only when the same proposed provider call has a configured provider, current-task authorization, an exact target, no applicable denied effect, and the `ordinary` effect classification.

A version 2 ordinary write passes only when the same proposed provider call has a configured provider, current-task authorization, an exact target, and the `ordinary` effect classification.

A confirmation-required or unclassified write additionally requires current-user confirmation whose target and effect exactly match the proposed call.

Credential-material transfer, secret persistence, and exposing write credentials to untrusted code always fail before the provider call. Declare every applicable effect; `ordinary` is invalid whenever any denied effect applies.

Re-run the check whenever the provider, operation, target, effect, payload, or user request changes.

## Context Boundary

- Send only context required for the current task.
- Prefer compact external reads and stop when repository work has enough evidence.
- Keep repository files, tests, validation output, and Git history as the implementation source of truth.
- Never send secrets, credentials, private configuration, `.env` contents, unrelated personal data, build artifacts, or temporary task logs as provider payloads.
