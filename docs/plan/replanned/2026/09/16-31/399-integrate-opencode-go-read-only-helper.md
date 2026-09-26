# Integrate the read-only OpenCode Go helper into skills, routing and Copier distribution

status: replanned
implementation_mode: parent_direct
predecessor_plans:
  - docs/plan/active/397-isolate-read-only-opencode-go-helper.md
  - docs/plan/active/398-seed-opencode-go-helper-configuration.md
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
  - {"evidence":"Checked plan 107 shipped natural-japanese with root and managed skill copies, root and generated .agents bridges, ownership.yaml bridge entries with the matching CURRENT_OWNERSHIP_SHA256 in both validate-copier-update.py copies, REUSABLE_SKILLS parity and generated bridge assertions.","kind":"existing_mechanism"}
  - {"evidence":"Helper roles and model selection live in references/orchestration.md and the generated SPEC_ORCHESTRATION.md, and check-root-agent-policy.py compares root and generated orchestration statements.","kind":"existing_mechanism"}
completion_conditions:
  - Root and generated installations discover the opencode-delegate skill through their bridges, and the skill tells the parent when to choose the helper, which entrypoint to call, what to pass, how to await the result and how to reject unsupported or failed dispatch.
  - Root and generated AGENTS instructions, spec-index routes and orchestration guidance route read-only Go delegation to the skill without changing Codex routing or the Sol review role.
  - The helper cases of plan 397 and the configuration refusals of plan 398 pass together.
  - Versioned update sources include every managed file of plans 397 to 399, and copy and update install them without replacing project-owned policy or configuration bytes.
  - The ownership record, its digest in both validate-copier-update.py copies, the inventory and the mechanically rewritten counterparts stay aligned under the template checker.
completion_witness_map:
  - {"condition_sha256":"sha256:cf09c63b6a1e57e73a66b588a30446e6d6005498b2cdb24ecf1e5f58711a4599","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:9c91f894366f853f95c6c3b75505e1f7ed55cceaacae17ecd5674ba42b509c24","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:30fcef55642c4b4dbbee126f87d254e825b4738d6c0b73e3d373abd2f3ea8812","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:171daef719357108c29ea3d1d15061ae73505fada9e197ad417e0bd0828f43e2","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:3d0a51d802661121e14313008519306ae589a709e7a6dcef30513ec011ac2cb5","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - .codex/skills/opencode-delegate/SKILL.md
  - .codex/skills/opencode-delegate/agents/openai.yaml
  - .codex/skills/opencode-delegate/references/worker-contract.md
  - .agents/skills/opencode-delegate/SKILL.md
  - template/.project-agent-workflow/skills/opencode-delegate/SKILL.md
  - template/.project-agent-workflow/skills/opencode-delegate/agents/openai.yaml
  - template/.project-agent-workflow/skills/opencode-delegate/references/worker-contract.md
  - template/.agents/skills/opencode-delegate/SKILL.md
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
primary_invariant: preserve the complete coupled source acceptance baseline
replan_sources:
  - docs/plan/active/397-isolate-read-only-opencode-go-helper.md
  - docs/plan/active/398-seed-opencode-go-helper-configuration.md
  - docs/plan/active/399-integrate-opencode-go-read-only-helper.md
replan_contract: docs/plan/replanned/contracts/397-target-read-only-capability-backends.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
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
checked_summary_ja: 読み取り専用の OpenCode Go 補助を、スキル、案内、Copier の配布に組み込む。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct.
- Own the final integration verification of plan 356's complete acceptance list here; do not create a verification-only successor.
- Update both the generated root AGENTS seed and the managed .project-agent-workflow/AGENTS.md body so preserved downstream root instructions can discover the route.
- Reserve the generated opencode-delegate bridge in ownership.yaml and never overwrite an existing project-owned bridge on an unclassified collision.
- Keep the advertised capability conditional on the explicit local enablement of plan 398's configuration.

## Tasks

- [ ] Before product edits, resolve every predecessor to its checked archive, prepare the parent-direct execution ledger with the reviewer registry, continuation registry, review-route check and adversarial preflight, and record the unchanged baseline behavior this plan must keep.
- [ ] Add the opencode-delegate skill, its worker-contract reference, UI metadata and the root and generated bridges.
- [ ] Add the routing entry to root and generated AGENTS instructions, spec-index and orchestration guidance, and their checker markers.
- [ ] Register the bridge in ownership.yaml, update the ownership digest in both validate-copier-update.py copies, extend skill parity and generated bridge assertions and smoke coverage.
- [ ] Run the combined helper and configuration cases.
- [ ] Extend tests/fixtures/orchestration/copier-update-source-inventory.txt and tests/copier-update.sh so the versioned update source contains every managed file this plan adds, reading the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite; do not weaken the fixture grammar.
- [ ] Obtain independent review of the exact in-scope patch and its security cases through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the unchanged authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Pre-activation review on 2026-09-26 reconstructed plan 356 into three successors: its write scope lacked scripts/project_workflow/copier_inventory.py and the orchestration guidance, the runner's Bubblewrap builder cannot mount a Unix socket, one completion condition had a witness that cannot observe an update, and its OpenCode 1.18.30 run --pure evidence no longer matched the installed 2.0.15 CLI.
