# Root External Services

The active root policy is `docs/agent/external-services.yaml`.
It uses schema version 2 with `access_profile: task_scoped_default_allow` and declares GitHub, OpenCode Go, and TypeSafe as its configured-provider records.

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

## OpenCode Go inference

Service `opencode_go` covers delegated inference through the OpenCode Go plan at `https://opencode.ai/zen/go/v1/chat/completions`.
Its only operation is `inference.chat_completions`, its only access class is `read`, and its only admissible effect is `ordinary`.

The plan credential is a denied payload, not a task input.
Never place it in a prompt, a delegated task description, a sandbox environment, a repository file, a plan, a log, or a provider payload, and never hand it to delegated code that the current session does not control.
`scripts/project_workflow/opencode_go_transport.py` is the only route that satisfies this boundary: the parent process keeps the credential in memory, serves a Unix-domain socket that the sandbox mounts, attaches the credential itself, and lets the delegated process see only a loopback address and a placeholder key.

The transport enforces the boundary rather than trusting the caller.
It refuses a destination other than the fixed upstream, discards downstream authentication headers, refuses routing and forwarding headers, rejects a request body that names a destination, credential, provider, or protocol, and stops the relay on a redirect, an authentication failure, an authorization failure, a rate limit, an upstream server error, an exhausted request or byte budget, a passed deadline, a cancellation, and a truncated response.

Authorize each relayed request separately before it reaches the provider.
The target is the exact upstream URL with the exact requested model, so a model the request did not declare is a different target and a different authorization.
A failed, ambiguous, or erroring authorization denies the request.

## TypeSafe structured decisions

Service `typesafe` covers structured decisions from the TypeSafe System One endpoint.
Its only operation is `decision.evaluate`, its only access class is `read`, and its only admissible effect is `ordinary`.
Its only target form is `https://api.typesafe.ai/v1/systemone#model=jev-<MAJOR>.<MINOR>.<PATCH>`, where each version component is a decimal integer without a leading zero.

The root entrypoint applies this tuple before it delegates to the maintained version 2 checker.
It routes a request through the tuple check when the target's URL authority names a TypeSafe host, or when the service or operation name folds to `typesafe` or `decision.evaluate`.

For every service, the entrypoint first refuses a target that contains a tab, line feed, or carriage return, or that begins or ends with a control or space character, because a URL parser may strip those characters.
It then finds the URL authority the way a client would connect to it.
A scheme follows the RFC 3986 grammar.
The special network schemes `http`, `https`, `ws`, `wss`, and `ftp`, and a scheme-relative target that begins with two slashes or backslashes, skip every leading slash and backslash and require a host.
A `file` target has an authority only after two leading slashes or backslashes, and another libcurl protocol scheme, such as `gopher`, `dict`, `imap`, `ldap`, `sftp`, or `telnet`, followed by at least one slash or backslash skips all of them, because libcurl reads `gopher:/host` and `gopher:///host` as `gopher://host`.
Every other scheme has an authority only after `//`, as RFC 3986 and the WHATWG URL parser read it, so `foo:/a_b` has none.
The authority ends at the first `/`, `?`, or `#`.
When a target has an authority, it must be canonical ASCII: at most one `@`, a userinfo of unreserved and sub-delimiter ASCII characters and colons without a percent escape, an LDH host without a trailing dot or a bracketed literal that parses as an IPv6 address, and an optional decimal port.
Only a `file` target or the authority of another non-special scheme may have an empty host.
Any other authority, including a percent escape, a backslash, or a non-ASCII character, is refused with one fixed diagnostic, so a noncanonical spelling of a TypeSafe host cannot reach the maintained checker.
Every target is also read the way a command-line client such as curl reads it, because `api.example.com:/v1` is a URL with a dotted scheme to one parser and a host with an empty port to another.
When the leading token before the first `/`, `?`, or `#` contains no whitespace, the text after its last `@` and before the following first `:` is a guessed host if its name fold, described below, contains a dot, so `x:secret@host` and `host:443/v1` both name `host` and an ideographic, full-width, or percent-encoded dot still counts.
A guessed host must be an LDH host without a trailing dot; a guessed host with any other character, including a non-ASCII character, is refused as a noncanonical host.
Every host either reading finds must be canonical, and the target names TypeSafe when a canonical host or guessed host is equal to or under `typesafe.ai`, compared case-insensitively.
A target with neither a URL authority nor a guessed host, such as a GitHub-form target or an opaque URI without a dotted leading name, keeps its existing result, and so does every canonical target of another host.

The service and operation names are folded instead, because the maintained checker accepts any operation text.
The name fold percent-decodes until the text is stable, applies Unicode compatibility normalization, case folding, and compatibility normalization again, maps the ideographic full stop to a dot, and drops control, format, surrogate, private-use, unassigned, mark, separator, and Hangul filler characters together with every character that IDNA2003 nameprep maps to nothing (RFC 3454 table B.1).
A wider fold can only route more requests into the tuple check.

The entrypoint cannot recognize TypeSafe reached through another gateway, an IP address, an alias host, or client-side expansion such as curl URL globbing, because the maintained version 2 checker still authorizes other services without consulting the service map; that separate defect is outside this registration.
A caller must therefore authorize every call that reaches TypeSafe as service `typesafe` against the direct endpoint, and must not reach TypeSafe through another service or gateway.

The tuple check refuses any other access class, operation, effect, host, path, query, or model, and it refuses the moving aliases `jev-latest` and `jev-preview`.
An alias moves when the provider ships a release, so it can change the decisions that a later evaluation depends on without any change on this side; each call pins one versioned model id instead.
An authorization rule and a confirmation argument are not accepted for this service.
A repeated `--target`, `--confirmed-target`, or `--authorization-rule` is refused for every service instead of keeping only its last value.
The host and path come only from the authorized target, so the caller must not honor a base-URL override such as `TYPESAFE_BASE_URL`.
A request without `--provider-configured` or `--task-authorized` is refused before delegation.

Authorize each request separately immediately before it is sent.
The exact operation, target, payload, and current user request must match, and a changed model id is a different target and a different authorization.
The entrypoint cannot observe whether the current user request still requires the call, so keeping that fact fresh remains the caller's duty.

The TypeSafe API key is a denied payload, not a task input.
The only admissible caller is a process that the parent session starts and controls, reading `TYPESAFE_API_KEY` from its own runtime environment.
Never pass the key on a command line, in a prompt, a delegated task, a sandbox environment, a repository file, a plan, a log, a fixture, or a provider payload, and never make it available to a delegated process.
This registration installs no relay and no SDK.
The entrypoint runs the maintained checker with an environment that omits every variable whose name starts with `TYPESAFE_`, so no TypeSafe credential reaches that subprocess.
Every refusal of a TypeSafe request exits nonzero.
The tuple check's diagnostics use fixed wording that echoes no caller-supplied value and names no credential value or credential-source binding.
An argument-parsing failure reports the same fixed invalid-arguments diagnostic for every service instead of echoing the rejected argument.

A returned decision is advisory.
It never relaxes, replaces, or satisfies a deterministic validation, review, authorization, or stop condition, and no returned score, probability, or confidence value substitutes for one.

When GitHub is unavailable, continue with local repository files, plans, validation output, and Git history, and report the deferral when it changes scope, confidence, validation, or completion.
Never place credentials, tokens, private keys, secret values, or private configuration in a policy, target, confirmation, or provider payload.

Keep retries non-mutating until the provider-call execution context is selected and its preflight and authorization pass.
After an uncertain write, read the exact remote state before retrying when the operation supports that check, and do not duplicate a write whose intended state already exists.
Never retry a protected write through another provider without current-task authorization and any required exact confirmation for the new provider, target, and effect.

Diagnostics may report only sanitized provider availability, safely exposed account identity, credential-source class, command-boundary class, and error classification; they must not expose the exact credential-source binding.
They must not read, print, persist, or log token values or credential material.
