# Root External Services

The active root policy is `docs/agent/external-services.yaml`.
It uses schema version 2 with `access_profile: task_scoped_default_allow` and currently declares GitHub as the configured-provider record.

Provider configuration and authorization are separate facts.
The provider-call execution context is the provider, command execution boundary, and credential source used for one exact external call.
The active environment must confirm that the exact provider is configured and authenticated through the provider-call execution context that will make the call, and the current user request must require the exact provider operation, target, and complete effect set.
Configuration or authentication alone never authorizes a provider call.
The policy contains no credential material.

For `runtime_configured`, configuration and authentication evidence is valid only for the provider-call execution context that produced it.
Changing the provider, authenticated account, credential source, or command boundary invalidates the evidence and requires a new non-mutating preflight and fresh authorization check.
Schema version 2 and project-owned schema version 1 policies remain unchanged; host sandbox settings and credential-store details do not belong in either policy.

## Per-call gate

Run the root entrypoint before each exact provider call:

```text
python3 scripts/check-external-service-policy.py check
python3 scripts/check-external-service-policy.py authorize <service> <read|write> <operation> --provider-configured --task-authorized --target <target> --effect <effect>
```

The authorization check is fresh only for the exact provider, operation, target, complete effect set, payload, and current user request that will be used by the provider call.
Run it again immediately before the call whenever any of those facts changes.
Do not call the provider when policy, provider configuration, task relevance, target, effect classification, payload, or required confirmation is missing, ambiguous, stale, or mismatched.

Check whether the exact selected credential source is locally available without reading credential material; diagnostics may expose only its credential-source class.
When a provider identity preflight contacts the provider, treat it as a separate exact external read.
Before that read, establish project authorization for its exact provider, operation, target, payload, current-task relevance, and `ordinary` effect without asserting that authentication already succeeded.
Obtain host execution approval separately when the selected command boundary requires it; this approval grants no provider operation, target, payload, or effect.
Both independent conditions are required when both apply, and a saved command-prefix approval is never external-write authorization.

For schema version 1, the identity read must pass the normal configured-state and `allowed_reads` checks.
For schema version 2, do not run the normal `authorize` command for the identity read that establishes authentication: `--provider-configured` would make that check circular.
Instead, evaluate only that non-mutating read's project authorization facts directly against the unchanged version 2 policy: the current request must require the exact read tuple, `ordinary` must be its only effect, and no denied effect may apply.
This narrow prerequisite is not `runtime_configured`, does not authorize a write or the intended call, and creates no reusable or persisted authorization state.
After the read succeeds, keep its evidence process-local or otherwise ephemeral and bind it to the exact provider, account, command boundary, and credential source.
Then establish `runtime_configured` from that evidence and authorize the intended operation separately and freshly with the normal command.

If a local check of the exact credential source fails only in the current sandbox while the user reports a valid login elsewhere, one project-authorized non-mutating provider read may run through the intended provider-call execution context after separately obtaining any required host execution approval and before requesting reauthentication.
If that check is unavailable or inconclusive, fail closed and report the exact missing provider, credential source, or command capability.

Distinguish a process that cannot obtain credentials, a provider that recognizes an authenticated account but rejects its permission, and the absence of a configured backend.
Do not describe all three as a login failure, and do not reuse authentication evidence between connectors, command-line providers, or browser sessions.

Reads and ordinary writes require the `ordinary` effect alone.
An ordinary effect cannot be combined with another effect.
Remote deletion, public communication, financial commitment, production change, and access-control change require current-user confirmation whose target and complete effect set exactly match the proposed write.
An unclassified write also requires that exact confirmation.
Credential-material transfer, secret persistence, and making write credentials available to untrusted code are denied before the provider call, even when the task requires the operation and confirmation is present.
Denied effects take precedence over confirmation.

## GitHub release operations

The root entrypoint applies the provider-specific effect mapping before delegating to the maintained version 2 checker.
For `git.push`, a branch or tag push is an ordinary write.
For `pull_request.publish` and `release.publish`, the write effect is `public_communication` and exact current-user confirmation is required.

These three operations are authorized only for provider `github`, repository `rectaris/temp_project`, and the following exact target forms:

- `git.push`: `rectaris/temp_project:refs/heads/<branch>` or `rectaris/temp_project:refs/tags/<tag>`.
- `pull_request.publish`: `rectaris/temp_project:refs/heads/<head>->refs/heads/<base>`.
- `release.publish`: `rectaris/temp_project:release:<tag>`.

Branch and tag components are validated with the local Git `check-ref-format` implementation.
Both pull-request endpoints use `git check-ref-format --branch`; tag targets use the `refs/tags/<tag>` form.
The caller cannot replace the fixed root policy with an alternate `--policy` argument, and help or unknown options are parsing failures rather than authorization results.

## Fallback and payload boundary

When GitHub is unavailable, continue with local repository files, plans, validation output, and Git history, and report the deferral when it changes scope, confidence, validation, or completion.
Never place credentials, tokens, private keys, secret values, or private configuration in a policy, target, confirmation, or provider payload.

Keep retries non-mutating until the provider-call execution context is selected and its preflight and authorization pass.
After an uncertain write, read the exact remote state before retrying when the operation supports that check, and do not duplicate a write whose intended state already exists.
Never retry a protected write through another provider without current-task authorization and any required exact confirmation for the new provider, target, and effect.

Diagnostics may report only sanitized provider availability, safely exposed account identity, credential-source class, command-boundary class, and error classification; they must not expose the exact credential-source binding.
They must not read, print, persist, or log token values or credential material.
