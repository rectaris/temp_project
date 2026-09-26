# Add Agent Reach research guidance limited to authorized Exa search reads

status: backlog
primary_invariant: Agent Reach research uses only the registered Exa search read through the existing per-provider authorization, installs nothing, imports no cookie or credential, and reports an unavailable route instead of fabricating a result.
task_types:
  - template_workflow
  - skill_authoring
  - external_services
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The generated default external_access_profile restricted renders a version-1 policy whose authorize_v1 refuses an unknown service and requires configured_read_only plus an allowlisted read, so a disabled agent_reach record with an allowed_reads entry is the existing per-provider gate.","kind":"existing_mechanism"}
  - {"evidence":"The task_scoped_default_allow profile and the root policy are version 2 and already register browser_run and opencode_go by unavailable_fallback entries; agent_reach is an entry of the same shape.","kind":"existing_mechanism"}
  - {"evidence":"SPEC_SKILL_AUTHORING.md requires a skill that uses an external service to be documented in the external-service policy and forbids adding dependency installation because upstream does it; checked plan 359 is the registration precedent.","kind":"existing_mechanism"}
completion_conditions:
  - The root policy and the version-2 template profile register agent_reach, and the version-1 restricted profile seeds it disabled with no allowed read, so a default generated project refuses every Agent Reach call until the owner configures exa.search.
  - Once configured, authorization admits only access read, operation exa.search and effect ordinary, and refuses writes, other operations and non-ordinary effects.
  - The skill routes only exa.search through the mcporter client, states that it installs no dependency, imports no cookie or credential and reports an unavailable route without inventing results, and the root policy check asserts those statements and the pinned upstream revision.
  - Root and generated agent-reach skills, the bridge and both specifications stay aligned, and every new managed file is registered and passes the template checker.
  - A real Copier update installs the skill and policy entries and preserves an edited project-owned external-service policy and existing workflow behavior.
completion_witness_map:
  - {"condition_sha256":"sha256:6734412368d599b2b958ab5f0431f3047c807e46845b2cc03f87d354a7a86d05","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:16e4720139bf35afce099747f3f20ce81788a13fbc78a0f067724351833b5d39","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:22081a76c94aa1a5852373407730652f871ec6b8b54a23ddb6708513fbf0f514","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:0a4f20a936ccde2bd7fbee8553c72ef7b6576adae0cd7a5a23e597263a0b57e2","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:126d0dc70940e4becd999f65c60d232cf6ca4b168b6e64df6f9a1f22bc383ae0","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - .codex/skills/agent-reach/SKILL.md
  - .codex/skills/agent-reach/agents/openai.yaml
  - .codex/skills/agent-reach/references/upstream.md
  - template/.project-agent-workflow/skills/agent-reach/SKILL.md
  - template/.project-agent-workflow/skills/agent-reach/agents/openai.yaml
  - template/.project-agent-workflow/skills/agent-reach/references/upstream.md
  - template/.agents/skills/agent-reach/SKILL.md
  - docs/agent/external-services.yaml
  - template/docs/agent/external-services.yaml.jinja
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja
  - tests/validation_tools/external.py
  - template/.project-agent-workflow/ownership.yaml
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - tests/assert-generated-semantics.py
  - tests/smoke.sh
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
  - tests/test-validation-tools.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - scripts/check-external-service-policy.py
  - template/.project-agent-workflow/scripts/check-external-service-policy.py
  - docs/plan/checked/2026/09/01-15/359-isolate-opencode-go-inference-credentials.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - references/orchestration.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Generated projects discover Agent Reach research guidance that uses supported upstream clients through existing per-provider authorization and reports unavailable routes without fabricating results.
  - Root and generated skills, ownership, routing and completion wiring remain aligned; Copier copy and update preserve project-owned configuration and existing workflow behavior.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:a2ef3e4817cb5f594f303f38d36b946ced2609b1192f997fbe5bb32185e4820f","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:96ea69c75ea5f16a959af889e6a4e161abb7b8982bf7f583d7c24839c53fc4e2","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
checked_summary_ja: Agent Reachの調査手順を、認可されたExa検索の読み取りだけに限って導入する。

## Decisions

- Admit only Exa search: service agent_reach, operation exa.search, access read, effect ordinary, reached through the mcporter client that Agent Reach uses. The owner selected this scope on 2026-09-26.
- Exclude every other Agent Reach channel, dependency installation (Node, mcporter, yt-dlp), cookie import and credential persistence. The skill tells the user how to configure the provider and never does it.
- Author the guidance against Agent Reach revision da5044d26fc6adddb6554d5679c94ac22e76e428 and record that revision and the adapted sections in references/upstream.md; do not vendor upstream code.
- Seed the version-1 restricted record with state disabled and an empty allowed_reads list; the project owner enables it by setting configured_read_only and listing exa.search. Version-2 profiles register the entry by its unavailable_fallback.
- Report an unavailable, unauthorized or failing route as such and fall back to local sources; never present an unsearched answer as a search result.
- Register every new managed file the way checked plan 107 registered a vendored skill: ownership.yaml copier_managed bridge entries with the matching CURRENT_OWNERSHIP_SHA256 in both validate-copier-update.py copies, SOURCE_REQUIRED and GENERATED_REQUIRED entries, root skill parity in check-root-agent-policy.py, generated bridge assertions, smoke coverage and the versioned copier-update source inventory.

## Tasks

- [ ] Add the agent_reach entries to the root policy and both template profiles, and the Agent Reach section to both SPEC_EXTERNAL_SERVICES files.
- [ ] Add the agent-reach skill, its upstream reference, UI metadata and the generated bridge.
- [ ] Extend the external-service tests for the disabled default, the configured read and every refusal, and add the statement markers to check-root-agent-policy.py.
- [ ] Register every new file and bridge.
- [ ] Extend the update-source inventory and real update scenarios, reading the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite, and assert preserved project-owned bytes and existing validation.
- [ ] Obtain independent review of the exact in-scope patch, run the focused checks, then the full validation suite once, and publish through the ordinary lifecycle without pushing.

## Validation Notes

- Pre-activation review at d61b41e split the original plan 368 into this plan and the three plans named in docs/plan/backlog/README.md, because its four features share no invariant, its write scope missed the registration files every comparable checked plan touched, and its node --test witnesses are not admitted validation commands.
