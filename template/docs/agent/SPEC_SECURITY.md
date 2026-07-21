# Security Policy

This repository keeps security controls explicit and fail-closed at write boundaries.

## Secrets And Private Data

- Do not commit, print, or persist credentials, tokens, private keys, `.env` contents, or deployment secrets.
- Treat automatic redaction as pending review unless a deterministic check establishes that the stored data class is safe.
- Prefer allowlisted log fields over recording complete external or hook payloads.

## Generated Automation

- Default generated automation to read-only or artifact-only behavior.
- Require explicit project configuration before automation writes to branches, issues, services, or durable external memory.
- Validate generated patches against protected paths and required checks before any automated write.

## Dependencies And External Code

- Treat pull-request code, dependency installers, external skills, and downloaded scripts as untrusted until reviewed.
- Do not expose write tokens or secrets to untrusted code execution.
- Pin or verify external actions and dependencies when the repository adopts a concrete supply-chain policy.

## Validation

- Keep deterministic security checks in scripts or tests.
- Fail when a configured security or validation check cannot run.
- Record environment-only blockers without weakening the check.
