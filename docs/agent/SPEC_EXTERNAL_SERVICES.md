# Root External Services

The active root policy is `docs/agent/external-services.yaml`.
It uses schema version 2 with `access_profile: task_scoped_default_allow` and currently declares GitHub as the configured-provider record.

Provider configuration and authorization are separate facts.
The active environment must confirm that the exact provider is configured and authenticated, and the current user request must require the exact provider operation, target, and complete effect set.
Configuration or authentication alone never authorizes a provider call.
The policy contains no credential material.

## Per-call gate

Run the root entrypoint before each exact provider call:

```text
python3 scripts/check-external-service-policy.py check
python3 scripts/check-external-service-policy.py authorize <service> <read|write> <operation> --provider-configured --task-authorized --target <target> --effect <effect>
```

The authorization check is fresh only for the exact provider, operation, target, complete effect set, payload, and current user request that will be used by the provider call.
Run it again immediately before the call whenever any of those facts changes.
Do not call the provider when policy, provider configuration, task relevance, target, effect classification, payload, or required confirmation is missing, ambiguous, stale, or mismatched.

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
