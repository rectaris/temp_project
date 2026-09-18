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
  - {"evidence":"docs/agent/external-services.yaml is schema version 2 with access_profile task_scoped_default_allow and already registers two providers, github and opencode_go, each as a mapping entry carrying unavailable_fallback. Adding a third provider is an entry of the same shape.","kind":"existing_mechanism"}
  - {"evidence":"SPEC_EXTERNAL_SERVICES.md already carries a provider-specific section for opencode_go that fixes its single operation, its read access class, its ordinary-only effect, and its credential boundary. That section is the precedent this plan follows for a provider whose only operation is a read.","kind":"existing_mechanism"}
  - {"evidence":"At dev tip 8f5cbcc the root specification is 9239 bytes and the template counterpart is 14667 bytes and they already differ. check-copier-template.py asserts SPEC_EXTERNAL_SERVICES only through markers, not the root/template equality it applies to SPEC_HARNESS_PROFILES and SPEC_TEMPLATE_FEEDBACK, so a root-only provider section is admissible.","kind":"bounded_prototype"}
  - {"evidence":"check-copier-template.py requires the string opencode_go: in both the root policy and template/docs/agent/external-services.yaml.jinja by presence, not by equality, so a root-only provider entry does not break the template check.","kind":"existing_mechanism"}
  - {"evidence":"tests/validation_tools/external.py already drives scripts/check-external-service-policy.py over the real root policy for opencode_go and over a seeded temporary policy, so a new provider is testable through the registered RootExternalServicePolicyTest without a new validation command.","kind":"existing_mechanism"}
completion_conditions:
  - The root policy registers one TypeSafe provider whose only access class is read, whose only admissible effect is ordinary, and whose operation and target forms are fixed, and the entrypoint refuses any other access class, effect, operation, or target.
  - The TypeSafe credential is declared a denied payload: the specification forbids placing it in a repository file, plan, log, fixture, prompt, delegated task description, sandbox environment, or provider payload, and no added file contains credential material.
  - Authorization is required per request and is fresh for the exact operation, target, payload, and current user request, and a failed, ambiguous, or erroring authorization denies the call.
  - The specification states that a TypeSafe score is advisory only and can never relax, replace, or satisfy a deterministic validation, review, authorization, or stop condition.
  - The generic Copier template records no TypeSafe-specific provider fact, and the existing template external-service and alignment checks continue to pass unchanged.
completion_witness_map:
  - {"condition_sha256":"sha256:5b9d02813ab28fd7e588ea286aaea491fdee8def90eb4c9d2b737b97fd26e6c3","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:d14a6fbc530026d1659ad370e1ad39af76b032cb236ba3d2958cd687937ad3a3","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:4304be440292c00aebbea73df6e688989bc007a6ac0e412800e3175794e54637","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:bf9cc4d174314fb9e293b6133f3beb7530f5d7d0c0c0ea1b01d5e0986fcb9457","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:be0a71c17cf6f4db5ab2f0c45af877af24c27f47382674d1dc4a8d17270498a3","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - docs/agent/external-services.yaml
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - tests/validation_tools/external.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - tests/AGENTS.md
  - scripts/check-external-service-policy.py
required_specs:
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
focused_validation:
  - python3 tests/test-validation-tools.py
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
checked_summary_ja: TypeSafeの構造化判断をルート外部サービスとして登録する。

## Decisions

- Register TypeSafe only in the root policy. The Copier template stays generic, because a downstream project must not inherit this repository's provider choice.
- Follow the opencode_go section as the precedent: one named provider section that fixes the single operation, the read access class, the ordinary-only effect, and the credential boundary.
- Keep the access class read. A structured decision returns scores and changes no remote state, so no write effect and no confirmation-requiring effect is registered.
- Keep the credential parent-held. Unlike opencode_go, the evaluation caller is the parent session itself, so no socket relay is introduced; instead the specification forbids handing the credential to any delegated or sandboxed process.
- State explicitly that a returned score is advisory. It can never relax, replace, or satisfy a deterministic validation, review, authorization, or stop condition.
- Authorize per request. The exact operation, target, payload, and current user request must match, matching the existing rule that a changed target is a different authorization.
- Declare the credential a denied payload under the existing denied_effects, so credential material transfer stays refused before the call rather than by convention.
- Add no new validation command. Extend the already registered RootExternalServicePolicyTest so the focused check runs through tests/test-validation-tools.py.
- Register no operation for any use case that this repository has not yet approved, so the policy never authorizes more than the currently requested reads.

## Tasks

- [ ] Add the TypeSafe provider entry to the root policy with its unavailable_fallback, preserving the existing schema version, access profile, and effect lists.
- [ ] Add the provider section to the root specification fixing the operation, read access class, ordinary-only effect, target form, and per-call authorization rule.
- [ ] State the credential boundary as a denied payload and name every place the credential must not reach.
- [ ] State that returned scores are advisory and cannot relax a deterministic check, a review requirement, an authorization, or a stop condition.
- [ ] Extend the external-service tests to cover the accepted read tuple, refusal of writes, non-ordinary effects, unlisted operations, and unlisted targets.
- [ ] Assert that no added file carries credential material and that diagnostics expose no credential-source binding.
- [ ] Confirm the generic template gains no TypeSafe fact and rerun the template alignment check.
- [ ] Run the focused checks, then the full validation suite, and commit through the ordinary lifecycle.

## Validation Notes
