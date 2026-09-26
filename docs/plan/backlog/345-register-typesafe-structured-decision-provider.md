# Register TypeSafe structured decisions as a root external service with a parent-held credential

status: backlog
primary_invariant: Every TypeSafe call is authorized per request as a read with the ordinary effect against the unchanged root policy, its credential never reaches a repository file, plan, log, fixture, provider payload, or delegated process, and no advisory score can relax an existing deterministic check.
task_types:
  - security
  - external_services
review_class: C
human_design_required: yes
human_approval_status: pending
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"At d61b41e `python3 scripts/check-external-service-policy.py authorize typesafe read decision.evaluate --target https://api.typesafe.ai/v1/systemone --effect ordinary --provider-configured --task-authorized` exits 0 although no typesafe entry exists, and `authorize opencode_go write ...` also exits 0: version-2 authorization never consults the service map.","kind":"reproduced_defect"}
  - {"evidence":"The root wrapper scripts/check-external-service-policy.py already fixes one provider tuple before delegating: GITHUB_WRITE_EFFECTS and validate_github_target pin github operations, effects and exact target forms. A TypeSafe block of that shape leaves the maintained template checker, whose v2 service entries admit only unavailable_fallback, unchanged.","kind":"existing_mechanism"}
  - {"evidence":"check-root-agent-policy.py already asserts root policy, specification and entrypoint markers, and check-copier-template.py already refuses forbidden credential markers in template external-service files, so a TypeSafe statement check and a template absence check extend existing loops.","kind":"existing_mechanism"}
  - {"evidence":"tests/validation_tools/external.py RootExternalServicePolicyTest, registered in tests/test-validation-tools.py, already drives the root wrapper as a subprocess over the real root policy for github and opencode_go refusals.","kind":"existing_mechanism"}
completion_conditions:
  - The root policy registers service typesafe, and the root entrypoint admits only access read, operation decision.evaluate, effect ordinary and the exact target https://api.typesafe.ai/v1/systemone#model=jev-<MAJOR>.<MINOR>.<PATCH>, refusing any other access, operation, effect, host, path or moving model alias before delegation.
  - A TypeSafe request without --provider-configured or --task-authorized is refused, and every refusal exits nonzero with a sanitized diagnostic that names no credential value or credential-source binding.
  - The root specification carries a TypeSafe section that states the fixed tuple, the denied-payload credential boundary, the parent-only caller, and that a returned decision is advisory and never relaxes, replaces or satisfies a deterministic validation, review, authorization or stop condition, and the root policy check asserts each statement.
  - The template checker refuses any typesafe marker in template/docs/agent/external-services.yaml.jinja and the generated SPEC_EXTERNAL_SERVICES template, and every existing template external-service check still passes.
completion_witness_map:
  - {"condition_sha256":"sha256:93cd9604a8f086c9ee120d540328894d9e60be68825dd3f55464054583954a77","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:0c47b1c9ea22c36b2082feaf8ceb017ae4686815ac87c8205a15ee96e8f73105","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:38fc577efb4f9da6a17bb2c478206bda2ca34fa453402f1e497c2616217136b1","witness":"python3 scripts/check-root-agent-policy.py"}
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
checked_summary_ja: TypeSafeの構造化判断をルート外部サービスとして登録し、ルートの入口で操作と対象を固定する。

## Decisions

- Keep human_approval_status pending until the owner approves registering TypeSafe. The approval covers the provider choice only; the tuple below is fixed by this plan.
- Register TypeSafe only in the root policy and root specification. The Copier template stays generic, because a downstream project must not inherit this repository's provider choice.
- Use service typesafe, operation decision.evaluate, access read and effect ordinary. The target is the direct endpoint https://api.typesafe.ai/v1/systemone followed by #model= and one pinned jev-<MAJOR>.<MINOR>.<PATCH> model id. Refuse jev-latest, jev-preview, any other host or path, and any base-URL override, because a moving alias silently changes the decisions a later evaluation depends on.
- Enforce the tuple in the root wrapper scripts/check-external-service-policy.py, following the github block: validate service, access, operation, effect and target before delegating to the maintained checker. Do not change the maintained template checker or its v2 service-entry schema.
- Do not add opencode_go tuple enforcement here. Its missing entrypoint enforcement is a separate defect recorded in this plan's Validation Notes; it needs its own owner-approved plan.
- Keep the credential parent-held. The only admissible caller is a process the parent session starts and controls, reading TYPESAFE_API_KEY from its runtime environment. Never pass the key on a command line, in a prompt, a delegated task, a sandbox environment, a repository file, a plan, a log, a fixture or a provider payload. No relay or SDK installation is part of this plan.
- State that a returned decision is advisory. It can never relax, replace or satisfy a deterministic validation, review, authorization or stop condition.
- Authorize each request separately. The exact operation, target and current user request must match; a changed model id is a different target and a different authorization. Freshness of the user request stays the caller's duty, which the specification states and the entrypoint cannot observe.
- Put statement checks in check-root-agent-policy.py and the template absence check in check-copier-template.py. Behavioral refusals are tested in RootExternalServicePolicyTest; do not add a validation command.

## Tasks

- [ ] Before edits, rerun the reproduced authorize probes from feasibility evidence against the current HEAD and record the observed exits in Validation Notes.
- [ ] Add the typesafe entry with its unavailable_fallback to docs/agent/external-services.yaml, preserving schema version, access profile and effect lists.
- [ ] Add the TypeSafe tuple block to scripts/check-external-service-policy.py and route every typesafe authorize request through it before delegation.
- [ ] Add the TypeSafe section to docs/agent/SPEC_EXTERNAL_SERVICES.md, update its provider list line, and state the tuple, target grammar, credential boundary, parent-only caller, per-request authorization and advisory-only result.
- [ ] Extend RootExternalServicePolicyTest with the accepted tuple and refusals for write access, non-ordinary effects, other operations, other hosts and paths, jev-latest and jev-preview, missing flags, and diagnostics that expose no credential binding.
- [ ] Add the policy and specification markers to check-root-agent-policy.py and the typesafe absence check over the two template files to check-copier-template.py.
- [ ] Obtain independent review, run the focused checks, then the full validation suite once, and publish through the ordinary lifecycle.

## Validation Notes

- Pre-activation review at d61b41e: the version-2 checker ignores the service map, so the original plan's claim that opencode_go already fixes its tuple at the entrypoint was documentation only. The TypeSafe endpoint and model naming come from public TypeSafe documentation and integrations; confirm them against the provider's own documentation before implementation.
