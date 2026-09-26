# Register TypeSafe with canonical host detection at the root entrypoint

status: in_progress
implementation_mode: parent_direct
primary_invariant: Every TypeSafe call is authorized per request as a read with the ordinary effect against the unchanged root policy, its credential never reaches a repository file, plan, log, fixture, provider payload, or delegated process, and no advisory score can relax an existing deterministic check.
replan_sources:
  - docs/plan/active/345-register-typesafe-structured-decision-provider.md
replan_contract: docs/plan/replanned/contracts/345-register-typesafe-structured-decision-provider.json
integration_gates:
  - This plan proves both acceptance items of plan 345 together, because the TypeSafe registration and the root-only boundary are one root entrypoint change and cannot be witnessed separately.
  - Continue from the promoted epoch-3 candidate in the retained task worktree of plan 345; do not restart from the committed baseline, and do not reuse any plan 345 review, preflight or validation evidence.
successor_plans:
  - docs/plan/active/400-register-typesafe-with-canonical-host-detection.md
inherited_acceptance_digests:
  - sha256:7f4bb3333d4719ecf5c9c2b0a52295a0123a736d482e6e4880d6009561396770
  - sha256:126774b069c3fce41025e5a10e7e550052570c5a58d21b8d6a537e41c4131d22
integration_source_ids:
  - 345
task_types:
  - security
  - external_services
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"At 258558b `python3 scripts/check-external-service-policy.py authorize opencode_go read inference.chat_completions --target 'https://api.typesafe.ai./v1/systemone#model=jev-latest' --effect ordinary --provider-configured --task-authorized` exits 0 on the committed wrapper, because version-2 authorization never consults the service map and the committed wrapper has no TypeSafe check.","kind":"reproduced_defect"}
  - {"evidence":"The promoted plan 345 candidate (patch sha256:e793f2d5a45e20726505e3fec3a4566e8d20acbb31cf582b99f253281c666fc0) registers typesafe, fixes the tuple in the root wrapper and passes the three focused commands; its fourth review left four findings, which this plan closes.","kind":"bounded_prototype"}
  - {"evidence":"The root wrapper scripts/check-external-service-policy.py already fixes one provider tuple before delegating: GITHUB_WRITE_EFFECTS and validate_github_target pin github operations, effects and exact target forms, and the maintained template checker stays unchanged.","kind":"existing_mechanism"}
  - {"evidence":"tests/validation_tools/external.py RootExternalServicePolicyTest, registered in tests/test-validation-tools.py, drives the root wrapper as a subprocess over the real root policy, and tests/validation_tools/support.py load_module loads a script for direct function checks.","kind":"existing_mechanism"}
completion_conditions:
  - The root policy registers service typesafe, and the root entrypoint admits only access read, operation decision.evaluate, effect ordinary and the exact target https://api.typesafe.ai/v1/systemone#model=jev-<MAJOR>.<MINOR>.<PATCH>, refusing any other access, operation, effect, host, path, repeated target option or moving model alias before delegation.
  - For every service, the root entrypoint refuses a target whose URL authority is not a canonical ASCII host and routes a canonical host equal to or under typesafe.ai through the TypeSafe tuple check, while GitHub-form targets, the fixed OpenCode Go target and other canonical targets keep their existing results.
  - A TypeSafe request without --provider-configured or --task-authorized is refused, every refusal exits nonzero with a fixed diagnostic that echoes no caller-supplied value and names no credential value or credential-source binding, and the maintained checker subprocess receives no TYPESAFE_ environment variable.
  - The root specification carries a TypeSafe section that states the fixed tuple, the canonical host rule, the denied-payload credential boundary, the parent-only caller, and that a returned decision is advisory and never relaxes, replaces or satisfies a deterministic validation, review, authorization or stop condition, and the root policy check asserts each statement.
  - The template checker refuses any typesafe marker in template/docs/agent/external-services.yaml.jinja and the generated SPEC_EXTERNAL_SERVICES template, and every existing template external-service check still passes.
completion_witness_map:
  - {"condition_sha256":"sha256:763de3523c01cdaea439181dac5f0ff2b503deaa842da3ee114497f2132f8f82","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:8917a950a028b0fb50e0011e633a51efb64f55b0dd4d19a6cdc947ffcefa1315","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:2d4cfe6eae156531781d731c42170a9aa60186cc4235a7a3431464ae0600dff7","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:e1f86470c5c40297aa19d6a72c18cfe36799d257e837ad5868ec10806cad9ff4","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:ac3a81864afef8bfa133912b7fdce277138389f743b33ee73d2f89126021f135","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - docs/agent/external-services.yaml
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - scripts/check-external-service-policy.py
  - scripts/check-root-agent-policy.py
  - scripts/check-copier-template.py
  - tests/validation_tools/external.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - template/.project-agent-workflow/scripts/check-external-service-policy.py
required_specs:
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - TypeSafe is registered as a root read-only external service with a fixed operation and target form, per-call authorization, and a denied-payload credential boundary.
  - The change stays root-only: the generic template gains no TypeSafe fact and existing template checks pass unchanged.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:7f4bb3333d4719ecf5c9c2b0a52295a0123a736d482e6e4880d6009561396770","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:126774b069c3fce41025e5a10e7e550052570c5a58d21b8d6a537e41c4131d22","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: TypeSafeの構造化判断をルート外部サービスとして登録し、ルートの入口で正規のASCIIホスト表記を要求して操作と対象を固定する。

## Decisions

- The owner approved registering TypeSafe on 2026-09-26 with 「@docs/plan/backlog/345-register-typesafe-structured-decision-provider.md について実装作業をせよ。」. The approval covers the provider choice only; the tuple below is fixed by this plan.
- Register TypeSafe only in the root policy and root specification. The Copier template stays generic, because a downstream project must not inherit this repository's provider choice.
- Use service typesafe, operation decision.evaluate, access read and effect ordinary. The target is the direct endpoint https://api.typesafe.ai/v1/systemone followed by #model= and one pinned jev-<MAJOR>.<MINOR>.<PATCH> model id with decimal components and no leading zero. Refuse jev-latest, jev-preview, any other host or path, and any base-URL override, because a moving alias silently changes the decisions a later evaluation depends on.
- Enforce every rule in the root wrapper scripts/check-external-service-policy.py before delegating to the maintained checker. Do not change the maintained template checker, its v2 service-entry schema, or `access_profile: task_scoped_default_allow`: unregistered services stay authorized per task as before. The owner chose this canonical host rule over refusing unregistered services.
- Detect a TypeSafe target from its URL authority, not from its whole text. Refuse, for every service, a target that contains an ASCII tab, line feed or carriage return, or that begins or ends with a C0 control or space. Find the authority after a recognized scheme without a dot, skipping every leading slash and backslash for the special schemes http, https, ws, wss, ftp and file; after `//` for other schemes and scheme-relative targets; and, for a schemeless target, in its leading token when that token contains a dot and no whitespace. The authority ends at the first `/`, `?` or `#`.
- Require that authority to be canonical ASCII: at most one `@`, an ASCII userinfo, an LDH host with no trailing dot or a bracketed IPv6 literal, and an optional decimal port. Refuse any other authority, including a percent escape, backslash or non-ASCII character in the host, with one fixed diagnostic. Treat a canonical host equal to or under typesafe.ai, compared case-insensitively, as a TypeSafe request.
- Keep folding only for the service and operation names, so a name spelled like typesafe or decision.evaluate under another provider still reaches the tuple check; document the exact folding steps.
- Refuse a repeated --target, --confirmed-target or --authorization-rule instead of keeping the last value, and keep every argument-parsing failure on one fixed diagnostic.
- Run the maintained checker with an environment that omits every variable whose name starts with TYPESAFE_, so no TypeSafe credential reaches that subprocess.
- Do not add opencode_go tuple enforcement here. Its missing entrypoint enforcement is a separate defect; it needs its own owner-approved plan.
- Keep the credential parent-held. The only admissible caller is a process the parent session starts and controls, reading TYPESAFE_API_KEY from its runtime environment. Never pass the key on a command line, in a prompt, a delegated task, a sandbox environment, a repository file, a plan, a log, a fixture or a provider payload. No relay or SDK installation is part of this plan.
- State that a returned decision is advisory. It can never relax, replace or satisfy a deterministic validation, review, authorization or stop condition.
- Authorize each request separately. The exact operation, target and current user request must match; a changed model id is a different target and a different authorization. Freshness of the user request stays the caller's duty, which the specification states and the entrypoint cannot observe.
- Document the limits: the entrypoint cannot recognize TypeSafe reached through another gateway, an IP address or an alias host, so a caller must authorize every call that reaches TypeSafe as service typesafe against the direct endpoint.
- Put statement checks in check-root-agent-policy.py and the template absence check in check-copier-template.py. Behavioral refusals are tested in RootExternalServicePolicyTest; do not add a validation command.

## Tasks

- [ ] Before product edits, prepare a fresh parent-direct execution ledger with a new reviewer registry and continuation registry, record its review-route check, and confirm the promoted candidate bytes match the recorded plan 345 patch digest.
- [ ] Replace whole-target folding with the canonical authority rule, keep name folding for service and operation, and remove the GitHub-form exemption that the authority rule makes unnecessary.
- [ ] Refuse repeated single-value options and run the maintained checker without TYPESAFE_ environment variables.
- [ ] Update the TypeSafe section of docs/agent/SPEC_EXTERNAL_SERVICES.md with the canonical host rule, the name folding steps, the option and environment rules, and the documented limits.
- [ ] Extend RootExternalServicePolicyTest with the canonical host acceptances and refusals, every non-ASCII host character, repeated options, the scrubbed subprocess environment, and the unchanged GitHub and OpenCode Go results.
- [ ] Update the policy, specification and entrypoint markers in check-root-agent-policy.py; keep the template absence check in check-copier-template.py.
- [ ] Obtain independent review through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, run the focused checks, then the full validation suite once, and publish through the ordinary lifecycle.

## Validation Notes

- This plan reconstructs plan 345, which the owner stopped at replan_required after its cumulative four independent reviews, with 「再構成して実装を続ける（許可リスト方式）」 and then 「正規表記方式に切り替える」. Its fourth review found that the maintained-checker subprocess inherits a TypeSafe credential, that a repeated --target hides the checked value, that whole-target folding refuses legitimate targets, and that the specification misstated the fold; its earlier reviews found host spellings that the folding approach kept missing.
- The promoted candidate is advisory until this plan's own review and validation pass. Implementation has not started under this plan; its focused and authoritative commands are required future witnesses.
