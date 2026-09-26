# Register TypeSafe structured decisions as a root external service with a parent-held credential

status: replanned
implementation_mode: parent_direct
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
primary_invariant: preserve the complete coupled source acceptance baseline
replan_sources:
  - docs/plan/active/345-register-typesafe-structured-decision-provider.md
replan_contract: docs/plan/replanned/contracts/345-register-typesafe-structured-decision-provider.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/400-register-typesafe-with-canonical-host-detection.md
inherited_acceptance_digests:
  - sha256:7f4bb3333d4719ecf5c9c2b0a52295a0123a736d482e6e4880d6009561396770
  - sha256:126774b069c3fce41025e5a10e7e550052570c5a58d21b8d6a537e41c4131d22
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
- Owner instruction 2026-09-26, 「@docs/plan/backlog/345-register-typesafe-structured-decision-provider.md について実装作業をせよ。」, approved registering TypeSafe and promoted this plan to active. The approval covers the provider choice only; the tuple stays as the Decisions fix it.
- implementation_risk is high, and the write scope includes validation authority under scripts/ and tests/, so scripts/run-sandboxed-plan-worker.py refuses this plan. It runs parent_direct in its task-bound worktree with a parent-owned execution ledger, review-route check and adversarial preflight before the first product edit.
- Probes rerun at dev 9bcaada before any edit: `authorize typesafe read decision.evaluate --target https://api.typesafe.ai/v1/systemone --effect ordinary --provider-configured --task-authorized` exited 0, and `authorize opencode_go write x --target https://example.invalid --effect ordinary --provider-configured --task-authorized` exited 0. The feasibility defect is unchanged.
- Provider documentation checked 2026-09-26: https://docs.typesafe.ai/api.md states `POST https://api.typesafe.ai/v1/systemone` with `Authorization: Bearer <API_KEY>`; https://docs.typesafe.ai/models.md lists the versioned id `jev-1.13.0` and the moving aliases `jev-latest` and `jev-preview`; https://docs.typesafe.ai/sdk/python/api/constants.md names `TYPESAFE_API_KEY` and a `TYPESAFE_BASE_URL` override. The fixed tuple and the refused aliases match that documentation.
- Execution history, all parent_direct in the task worktree at source head `91e4b67`, reviewers were fresh read-only Codex `gpt-5.6-sol` sessions, and every epoch recorded its review-route check before its first product edit. Epoch 0 (`plan-345-parent-direct`) review 1 reported High, Medium, Medium, Low, Low: trailing-dot and Unicode-dot hosts and a whitespace-padded operation bypassed routing, argparse echoed an invalid access value, tests lacked those cases, an undocumented nine-digit version limit, and no per-request marker. Owner answered 「同一計画で継続する」.
- Epoch 1 (`plan-345-parent-direct-epoch1`) review 2 reported High and Medium: default-ignorable host characters such as a soft hyphen bypassed routing, and whole-target search refused a GitHub ref named `typesafe.ai`. Owner answered 「最終継続を承認する」. Epoch 2 (`plan-345-parent-direct-epoch2`) review 3 reported High: U+1806, which IDNA2003 maps to nothing, bypassed routing. Owner answered 「4回目のレビューまで継続する」.
- Epoch 3 (`plan-345-parent-direct-epoch3`) review 4, the last of the cumulative four, reported: (High) `delegate()` passes the parent environment, so a TypeSafe credential reaches the maintained-checker subprocess; (Medium) argparse keeps only the last repeated `--target`, so a TypeSafe URL followed by a benign target is checked as the benign one; (Medium) whole-target folding refuses legitimate targets such as a GitHub branch `x%2F%2Ftypesafe.ai` or an OpenCode model fragment naming `typesafe.ai`; (Low) the specification says case folding runs twice but the code runs it once. A remaining High makes resolve-owner ineligible.
- The owner stopped this plan at `replan_required` for reconstruction and chose to continue through a successor: 「再構成して実装を続ける（許可リスト方式）」, then, after the parent reported that refusing unregistered services would end `task_scoped_default_allow` and change the root policy, 「正規表記方式に切り替える」. The successor keeps both acceptance items and replaces spelling-folding host detection with a canonical ASCII host requirement.
- The reviewed epoch-3 candidate is not committed. Its exact patch against `91e4b67` for the six `write_scope` files has digest `sha256:e793f2d5a45e20726505e3fec3a4566e8d20acbb31cf582b99f253281c666fc0` and is kept at `.agent-artifacts/plan-345/epoch3-reviewed-candidate.patch` and in the parent-owned review directory `plan-345-parent-direct-epoch3/review-1/target.patch`. The dirty bytes transfer unchanged to the successor through dirty-path promotion. No focused or authoritative validation event was recorded, because review never cleared.
