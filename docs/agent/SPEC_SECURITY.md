# Security Policy

This repository keeps template security controls explicit and fail-closed at write boundaries.

## Secrets And Private Data

- Do not commit, print, or persist credentials, tokens, private keys, `.env` contents, or deployment secrets.
- Treat automatic redaction as pending review unless a deterministic check establishes that the stored data class is safe.
- Prefer allowlisted log fields over recording complete external or hook payloads.

## Generated Automation

- Default generated automation to read-only or artifact-only behavior.
- Require explicit project configuration before generated automation writes to branches, issues, services, or durable external memory.
- An explicitly selected task-scoped external-access profile may authorize ordinary writes required by the current user request, but it does not override credential denials or exact-confirmation requirements for consequential effects.
- Validate generated patches against protected paths and required checks before any automated write.

## Task Worktree Boundary

- Perform every repository-changing task in its bound task worktree, so an accepted change reaches the pre-existing checkout only through one checked publication that fast-forwards the expected source ref to the exact accepted commit.
- Bind an ownership record to the repository's credential-free origin identity and its canonical common Git directory, and store it under the operating-system account home rather than a caller-controlled `HOME`.
- Treat a repository that ships the guard as fail-closed: a guard that refuses or fails blocks the write. A repository that ships no guard, or that no canonical `remote.origin.url` can name, stays outside enforcement rather than refusing every write.
- Treat `git commit --no-verify`, a changed `core.hooksPath`, and any other bypass of every supported entrypoint as outside this boundary. It governs the supported paths; it is not a sandbox against an unrestricted local process.

## Dependencies And External Code

- Treat pull-request code, dependency installers, external skills, and downloaded scripts as untrusted until reviewed.
- Do not expose write tokens or secrets to untrusted code execution.
- Pin or verify external actions and dependencies when the repository adopts a concrete supply-chain policy.

## Validation

- Keep deterministic security checks in scripts or tests.
- Fail when a configured security or validation check cannot run.
- Record environment-only blockers without weakening the check.
