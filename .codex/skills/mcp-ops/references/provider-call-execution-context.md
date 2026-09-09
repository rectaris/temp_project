# Provider-Call Execution Context

The provider-call execution context is the provider, command execution boundary, and credential source used for one exact external call.

## Preflight And Authorization

1. Select the exact provider, command boundary, and credential source that will perform the call. Check only whether that exact selected credential source is locally available without reading credential material; diagnostics may expose only its class.
2. If the preflight contacts the provider, treat it as its own exact external read. Independently establish project authorization for its provider, operation, target, payload, current-task relevance, and `ordinary` effect. This decision excludes host execution approval and any assertion that authentication has already succeeded.
3. Obtain any host execution approval required for the selected command boundary. This condition is independent from project authorization and grants no provider operation, target, payload, or effect.
4. After both conditions pass when both apply, run the smallest non-mutating provider identity read through the exact provider, command boundary, and credential source intended for the later call.
5. Keep process-local or otherwise ephemeral evidence bound to the provider, safely exposed account identity, command boundary, and exact credential source. Diagnostics may report only provider availability, account identity, credential-source class, command-boundary class, and error classification.
6. Apply a fresh project authorization gate to the intended operation, target, payload, and complete effect set immediately before that call.

For schema version 1, the identity read must pass the normal configured-state and `allowed_reads` checks; otherwise fail closed.
For schema version 2, the identity read that establishes authentication cannot pass the normal `authorize` command because that command requires `--provider-configured`.
Evaluate only that read's project authorization facts directly against the unchanged policy: the current request must require the exact read tuple, its only effect must be `ordinary`, and no denied effect may apply.
Do not use this narrow prerequisite for the intended call or any write, and do not treat it as `runtime_configured` evidence.
After the identity read succeeds, use its exact-context evidence to establish `runtime_configured` and run the normal authorization command for the intended call.

Host approval and project authorization are independent gates.
Host approval, including a saved command-prefix approval, does not authorize an external read or write.

Configuration and authentication evidence is valid only for the context that produced it.
Changing the provider, authenticated account, exact credential source, or command boundary invalidates the evidence and requires a new non-mutating preflight and fresh authorization.

Connector evidence does not establish GitHub CLI authentication, GitHub CLI evidence does not establish connector authentication, and a browser session establishes neither.
Switching providers requires that provider's own preflight and a fresh authorization for the exact target and effect.

## Failure Routing

- If one process environment cannot obtain credentials, report credential-source unavailability for that process. Do not infer that the user is logged out.
- If the provider recognizes the account but rejects the requested operation, report a provider-permission denial. Reauthentication or evidence from another provider does not resolve that permission.
- If no backend is configured or reachable for the selected provider, report provider unavailability and use only the configured fallback.
- If a local check of the exact credential source fails only inside the current sandbox while the user reports a valid login elsewhere, require project authorization for one exact non-mutating provider read and request any needed host execution approval as a separate condition before checking through the intended provider-call context. If that check is unavailable or inconclusive, fail closed and name the missing provider, credential source, or command capability.

Do not retry a mutating call while selecting a provider-call context.
Keep retries non-mutating until preflight and authorization both pass.
After an uncertain write, read the exact remote state before retrying when the operation supports that check, and skip the write when the intended state already exists.
Do not retry a protected write through another provider without current-task authorization and any required exact confirmation for that provider, target, and complete effect set.

Never read, print, persist, fixture, log, or send token values, private keys, credential material, or host-specific credential-store configuration.
