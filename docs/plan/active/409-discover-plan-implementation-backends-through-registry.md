# Discover alternate plan-implementation backends through the registry in routing, skills and Copier distribution

status: deferred
completion_deferred_reason: Plans 406, 407 and 408 must be checked first.
implementation_mode: parent_direct
primary_invariant: An explicitly enabled alternate implementation of plan_implementation is discoverable in root and generated installations through capability resolution, while default installations, Codex routing and unrelated custom workers behave exactly as before.
replan_sources:
  - docs/plan/active/394-bind-custom-worker-dispatch-provenance.md
  - docs/plan/active/395-run-opencode-go-candidate-worker.md
  - docs/plan/active/396-integrate-opencode-go-candidate-route.md
replan_contract: docs/plan/replanned/contracts/394-target-writable-worker-backends.json
successor_plans:
  - docs/plan/active/407-bind-worker-backend-dispatch-provenance.md
  - docs/plan/active/408-add-opencode-go-writable-backend.md
  - docs/plan/active/409-discover-plan-implementation-backends-through-registry.md
inherited_acceptance_digests:
  - sha256:d930bc55fa2da26dfb2e6a2bd4f2a0b00d7079bf28176e0828141c143967b5bd
  - sha256:72b4b9ee612345af0ad93689efed29eda6b85063c25fc7f41dd82388205ada6b
  - sha256:68efe554460079f7e5645eb24e5697d41905580d3d4cfc7a1a2a7b71bf15673c
  - sha256:8ded8e74d9aa6291e5f488ffb4529ab04a1e0e49f624c89b0af5fcac8721d6a0
  - sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb
  - sha256:66465497df1b019a9452678898554cfb155cf7c0a1093d5737df21431e302e8f
integration_source_ids:
  - 396
predecessor_plans:
  - docs/plan/active/406-discover-read-only-capabilities-through-registry.md
  - docs/plan/active/407-bind-worker-backend-dispatch-provenance.md
  - docs/plan/active/408-add-opencode-go-writable-backend.md
task_types:
  - template_workflow
  - security
  - skill_authoring
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"The writable-runner routing rule sits in AGENTS.md, template/.project-agent-workflow/AGENTS.md.jinja, references/orchestration.md and the generated SPEC_ORCHESTRATION.md, and check-root-agent-policy.py and check-copier-template.py pin its spark and terra markers."}
  - {"kind":"existing_mechanism","evidence":"The telemetry sentence stating that custom workers record one attempt duration and zero model starts appears in references/orchestration.md and SPEC_ORCHESTRATION.md and must change when backend-dispatched attempts record a model."}
  - {"kind":"existing_mechanism","evidence":"tests/copier-update.sh copies exactly the files listed in tests/fixtures/orchestration/copier-update-source-inventory.txt into its versioned update source, so every new managed file needs an inventory line."}
completion_conditions:
  - Root and generated AGENTS instructions, orchestration guidance, the capability-delegate skill and the sequential orchestrator skill describe alternate plan_implementation backends as available only after explicit local enablement and an eligible plan, name capabilities rather than providers, and the policy checkers assert those statements.
  - Default root and generated installations still route writable work to Codex under the unchanged Spark, Terra and Luna rule, keep Sol for review, and run unrelated custom workers unchanged.
  - The combined read-only and writable OpenCode Go backend cases pass together against one shared backend module.
  - Versioned update sources include every managed file of plans 407 to 409, and copy and update install them without replacing project-owned policy or configuration bytes.
  - The root and generated inventory and mechanically rewritten counterparts stay aligned under the template checker.
completion_witness_map:
  - {"condition_sha256":"sha256:312e4ccbc3f19aa5ee241d7282aedad85b930abd0b035a128b81208353c5d933","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:d82a95cb93df4bca41eaa9ec8929bc043ce5ac285d947c8e279d1de870067bd2","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:5ad5d569b90973b2784d2dae6b8e2c46798605260327138082d5dc7b20bcc6b2","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:0e058fad49c0d350bd66e002927292ca0931a4cf97b8ff60b3a83f894afb9dd8","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:91c515f8dce7c4667b0d7923026d687bc0676675f33e2915656d7ec0eda253ec","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - AGENTS.md
  - template/AGENTS.md.jinja
  - template/.project-agent-workflow/AGENTS.md.jinja
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - .codex/skills/capability-delegate/SKILL.md
  - .codex/skills/capability-delegate/references/worker-contract.md
  - .codex/skills/capability-delegate/agents/openai.yaml
  - template/.project-agent-workflow/skills/capability-delegate/SKILL.md
  - template/.project-agent-workflow/skills/capability-delegate/references/worker-contract.md
  - template/.project-agent-workflow/skills/capability-delegate/agents/openai.yaml
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - scripts/check-root-agent-policy.py
  - scripts/check-copier-template.py
  - tests/test-sandboxed-plan-worker.py
  - tests/smoke.sh
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/plan/checked/2026/09/01-15/359-isolate-opencode-go-inference-credentials.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The Go adapter consumes the runner contract and correction brief, reads required specifications directly, writes only bounded advisory claims, and returns an in-scope candidate without committing or changing lifecycle state.
  - A verified initial attempt and one fresh correction preserve source baseline and prior-patch lineage; unknown completion claims, error events, model drift, replay and out-of-scope writes never become accepted candidates.
  - The Go process and any repository code it runs cannot receive the real API key or escape the existing filesystem/network boundary; parent-owned validation remains credential-free and network-isolated.
  - Explicit Go routing remains subject to risk/ambiguity eligibility, attempt and review budgets, stopped-ledger gates and unchanged acceptance witnesses; no custom-worker error triggers the Codex fallback or replenishes an execution budget.
  - Versioned Copier update sources include the new managed files and copy/update fixtures install them without replacing existing project-owned policy or configuration bytes.
  - The root/generated artifact inventory and mechanically rewritten counterparts for this plan stay aligned under the existing template checker.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:d930bc55fa2da26dfb2e6a2bd4f2a0b00d7079bf28176e0828141c143967b5bd","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:72b4b9ee612345af0ad93689efed29eda6b85063c25fc7f41dd82388205ada6b","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:68efe554460079f7e5645eb24e5697d41905580d3d4cfc7a1a2a7b71bf15673c","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:8ded8e74d9aa6291e5f488ffb4529ab04a1e0e49f624c89b0af5fcac8721d6a0","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
  - {"acceptance_sha256":"sha256:66465497df1b019a9452678898554cfb155cf7c0a1093d5737df21431e302e8f","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - docs/plan/checked/2026/09/01-15/359-isolate-opencode-go-inference-credentials.md
checked_summary_ja: 書き込みの能力に対する別の実装を、能力の解決を通じて案内、スキル、Copier の配布に組み込み、既定の動作を保つ。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct.
- Own the final integration verification of plan 396's complete acceptance list here; do not create a verification-only successor.
- Describe writable delegation as a plan_implementation capability request. Keep the Spark, Terra and Luna rule as the Codex backend's model routing, and add no provider-specific routing branch; an enabled alternate backend is one resolution of the same capability.
- Take enablement only from plan 405's enabled_capabilities list; add no new configuration field and no Copier question.
- Update both the generated root AGENTS seed and the managed .project-agent-workflow/AGENTS.md body so preserved downstream root instructions can discover the route.
- Keep the backend identity and capability contracts free of OpenCode assumptions so a later OmpBackend or local backend implements the same boundary without another routing architecture; this plan adds no such backend.
- Keep formal review on the existing independent reviewer route; no alternate backend claims review, validation, lifecycle, commit or publication authority.

## Tasks

- [ ] Before product edits, resolve every predecessor and integration gate to its checked archive or recorded evidence, prepare the parent-direct execution ledger with the reviewer registry, continuation registry, review-route check and adversarial preflight, and record the unchanged baseline behavior this plan must keep.
- [ ] Update the writable routing and telemetry statements in root and generated instructions and orchestration guidance, and their checker markers.
- [ ] Extend the capability-delegate skill, its worker contract, UI metadata and the sequential orchestrator skill with plan_implementation capability resolution.
- [ ] Run the combined read-only and writable backend cases and generated-layout smoke cases for an enabled alternate backend and unchanged defaults.
- [ ] Extend tests/fixtures/orchestration/copier-update-source-inventory.txt and tests/copier-update.sh so the versioned update source contains every managed file this plan adds, reading the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite; do not weaken the fixture grammar.
- [ ] Obtain independent review of the exact in-scope patch and its security cases through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the unchanged authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Reconstructed on 2026-09-26 from plans 394 to 396 on the owner's instruction under Issue #14: the source plans added an OpenCode-specific runner selector and routing rule, while the owner now requires writable delegation to resolve a capability through the Capability Registry and the WorkerBackend boundary, with OpenCode Go as the first non-Codex backend.
