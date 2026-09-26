# Discover read-only capabilities through the registry in skills, routing and Copier distribution

status: deferred
completion_deferred_reason: Plans 404 and 405 must be checked first.
implementation_mode: parent_direct
primary_invariant: Root and generated installations discover read-only delegation through one provider-neutral skill and capability-based routing guidance, while default resolution, Codex routing, Sol review and every existing validation stay unchanged.
replan_sources:
  - docs/plan/active/397-isolate-read-only-opencode-go-helper.md
  - docs/plan/active/398-seed-opencode-go-helper-configuration.md
  - docs/plan/active/399-integrate-opencode-go-read-only-helper.md
replan_contract: docs/plan/replanned/contracts/397-target-read-only-capability-backends.json
successor_plans:
  - docs/plan/active/404-run-read-only-capabilities-through-opencode-go-backend.md
  - docs/plan/active/405-seed-disabled-opencode-go-backend-configuration.md
  - docs/plan/active/406-discover-read-only-capabilities-through-registry.md
inherited_acceptance_digests:
  - sha256:6a93344caf98fde95f6920a3db153727b5203c0bc6f8700503494d5c2c64b59c
  - sha256:2c6b904e8013fa92f54ad13d9707d3d2ad62ba0d96eca963e72e395529132af0
  - sha256:518cd64e6d0416977a47728c0c8c65705c78b4d993a7b86279942f16329a2426
  - sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb
  - sha256:66465497df1b019a9452678898554cfb155cf7c0a1093d5737df21431e302e8f
integration_source_ids:
  - 399
predecessor_plans:
  - docs/plan/active/404-run-read-only-capabilities-through-opencode-go-backend.md
  - docs/plan/active/405-seed-disabled-opencode-go-backend-configuration.md
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
  - {"kind":"existing_mechanism","evidence":"Checked plan 107 shipped natural-japanese with root and managed skill copies, root and generated .agents bridges, ownership.yaml bridge entries with the matching CURRENT_OWNERSHIP_SHA256 in both validate-copier-update.py copies, REUSABLE_SKILLS parity and generated bridge assertions."}
  - {"kind":"existing_mechanism","evidence":"Helper roles and model selection live in references/orchestration.md and the generated SPEC_ORCHESTRATION.md, and check-root-agent-policy.py compares root and generated orchestration statements."}
  - {"kind":"existing_mechanism","evidence":"check-root-agent-policy.py check_agent_model_profiles pins the concrete model of each of the seven .codex/agents profiles, so routing guidance can name those profiles as the default implementations of each capability without changing a pinned model."}
completion_conditions:
  - Root and generated installations discover the capability-delegate skill through their bridges, and the skill tells the parent when to request a read-only capability, how to resolve it, how to invoke a native Codex profile result or read a process backend's evidence artifact, and how to reject unsupported or failed dispatch.
  - Root and generated AGENTS instructions, spec-index routes and orchestration guidance route read-only helper requests by capability name, name no provider as a routing concept, and leave Codex routing and the Sol review role unchanged.
  - The helper cases of plan 404 and the configuration refusals of plan 405 pass together; with the seeded configuration every read-only capability resolves to its unchanged native Codex profile without a process, and an enabled repository_exploration implementation dispatches through the process path.
  - Versioned update sources include every managed file of plans 404 to 406, and copy and update install them without replacing project-owned policy or configuration bytes.
  - The ownership record, its digest in both validate-copier-update.py copies, the inventory and the mechanically rewritten counterparts stay aligned under the template checker.
completion_witness_map:
  - {"condition_sha256":"sha256:4239b4c57eb688a105954d0b9dd6903afc9af87169c6688560be7fd10007897e","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:2189c61f2a99d022c032c90f7407ae8c0fb40ab2914384d456328b82f422857e","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:e2b307d20449b0e1e92180e3f31341088ece616bcae9360c29cbd9ddedaa97c3","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:8466b020dc1d4f0085433b673bead1503ae4e40513e03851704b15b3fe503f30","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:3d0a51d802661121e14313008519306ae589a709e7a6dcef30513ec011ac2cb5","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - .codex/skills/capability-delegate/SKILL.md
  - .codex/skills/capability-delegate/agents/openai.yaml
  - .codex/skills/capability-delegate/references/worker-contract.md
  - .agents/skills/capability-delegate/SKILL.md
  - template/.project-agent-workflow/skills/capability-delegate/SKILL.md
  - template/.project-agent-workflow/skills/capability-delegate/agents/openai.yaml
  - template/.project-agent-workflow/skills/capability-delegate/references/worker-contract.md
  - template/.agents/skills/capability-delegate/SKILL.md
  - AGENTS.md
  - template/AGENTS.md.jinja
  - template/.project-agent-workflow/AGENTS.md.jinja
  - docs/agent/spec-index.yaml
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/ownership.yaml
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - tests/assert-generated-semantics.py
  - tests/test-sandboxed-plan-worker.py
  - tests/smoke.sh
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/plan/checked/2026/09/01-15/107-complete-natural-japanese-copilot.md
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
  - The orchestrator can invoke the shipped helper command with an exact Go model, bounded task and explicit repository input paths and receive an answer while retaining every adoption and validation decision.
  - A real isolated fixture proves source/ref/index bytes stay unchanged and the helper cannot obtain host credentials, run repository code, expand input paths through symlinks, load external plugins/MCP/skills or use a different provider.
  - The result records the requested backend/model and directly observed runtime identity separately, never upgrades a request to provider-execution evidence, and reports bounded failures including 429, timeout, error events and incomplete output.
  - Versioned Copier update sources include the new managed files and copy/update fixtures install them without replacing existing project-owned policy or configuration bytes.
  - The root/generated artifact inventory and mechanically rewritten counterparts for this plan stay aligned under the existing template checker.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:6a93344caf98fde95f6920a3db153727b5203c0bc6f8700503494d5c2c64b59c","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:2c6b904e8013fa92f54ad13d9707d3d2ad62ba0d96eca963e72e395529132af0","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:518cd64e6d0416977a47728c0c8c65705c78b4d993a7b86279942f16329a2426","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
  - {"acceptance_sha256":"sha256:66465497df1b019a9452678898554cfb155cf7c0a1093d5737df21431e302e8f","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - docs/plan/checked/2026/09/01-15/359-isolate-opencode-go-inference-credentials.md
checked_summary_ja: 読み取り専用の委任を、能力の名前で要求する形でスキル、案内、Copier の配布に組み込む。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct.
- Own the final integration verification of plan 399's complete acceptance list here; do not create a verification-only successor.
- Ship one provider-neutral capability-delegate skill instead of a provider-specific delegation skill. It describes resolving a declared read-only capability through run-read-only-worker.py, spawning the named native Codex profile for a native resolution, reading the evidence artifact for a process backend, and it names no provider as a routing choice.
- Route by capability name in AGENTS instructions, spec-index and orchestration guidance. OpenCode, OMP and local models appear only in backend-specific configuration and backend modules, never as a first-class routing concept.
- Keep the native .codex/agents profiles as the default implementation of each read-only capability, and keep the advertised alternate backend conditional on the explicit local enablement recorded in plan 405's configuration.
- Update both the generated root AGENTS seed and the managed .project-agent-workflow/AGENTS.md body so preserved downstream root instructions can discover the route.
- Reserve the generated capability-delegate bridge in ownership.yaml and never overwrite an existing project-owned bridge on an unclassified collision.
- Keep Orca as transport metadata only; capability or backend selection grants Orca no review, validation, apply, publication or lifecycle authority.

## Tasks

- [ ] Before product edits, resolve every predecessor and integration gate to its checked archive or recorded evidence, prepare the parent-direct execution ledger with the reviewer registry, continuation registry, review-route check and adversarial preflight, and record the unchanged baseline behavior this plan must keep.
- [ ] Add the capability-delegate skill, its worker-contract reference, UI metadata and the root and generated bridges.
- [ ] Add the capability-based routing entry to root and generated AGENTS instructions, spec-index and orchestration guidance, and their checker markers.
- [ ] Register the bridge in ownership.yaml, update the ownership digest in both validate-copier-update.py copies, extend skill parity and generated bridge assertions and smoke coverage.
- [ ] Run the combined helper and configuration cases, and exercise both the native-profile resolution under the seeded configuration and process dispatch under an enabled implementation.
- [ ] Extend tests/fixtures/orchestration/copier-update-source-inventory.txt and tests/copier-update.sh so the versioned update source contains every managed file this plan adds, reading the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite; do not weaken the fixture grammar.
- [ ] Obtain independent review of the exact in-scope patch and its security cases through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the unchanged authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Reconstructed on 2026-09-26 from plans 397 to 399 on the owner's instruction under Issue #14: the source plans added an OpenCode-specific helper command, skill and routing entry, while the owner now requires read-only delegation to request a capability through the Capability Registry and the WorkerBackend boundary, with OpenCode Go as one optional backend.
