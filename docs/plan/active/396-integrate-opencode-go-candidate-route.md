# Integrate the OpenCode Go candidate route into routing, skills and Copier distribution

status: deferred
completion_deferred_reason: Plans 394 and 395 must be checked first, and plan 356's reconstruction successors before them.
implementation_mode: parent_direct
primary_invariant: An explicitly enabled Go candidate route is discoverable in root and generated installations, while default installations, Codex routing and unrelated custom workers behave exactly as before.
replan_sources:
  - docs/plan/active/357-delegate-candidate-implementation-to-opencode-go.md
replan_contract: docs/plan/replanned/contracts/357-delegate-candidate-implementation-to-opencode-go.json
successor_plans:
  - docs/plan/active/394-bind-custom-worker-dispatch-provenance.md
  - docs/plan/active/395-run-opencode-go-candidate-worker.md
  - docs/plan/active/396-integrate-opencode-go-candidate-route.md
inherited_acceptance_digests:
  - sha256:d930bc55fa2da26dfb2e6a2bd4f2a0b00d7079bf28176e0828141c143967b5bd
  - sha256:72b4b9ee612345af0ad93689efed29eda6b85063c25fc7f41dd82388205ada6b
  - sha256:68efe554460079f7e5645eb24e5697d41905580d3d4cfc7a1a2a7b71bf15673c
  - sha256:8ded8e74d9aa6291e5f488ffb4529ab04a1e0e49f624c89b0af5fcac8721d6a0
  - sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb
  - sha256:66465497df1b019a9452678898554cfb155cf7c0a1093d5737df21431e302e8f
integration_source_ids:
  - 357
predecessor_plans:
  - docs/plan/active/394-bind-custom-worker-dispatch-provenance.md
  - docs/plan/active/395-run-opencode-go-candidate-worker.md
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
  - {"evidence":"The writable-runner routing rule sits in AGENTS.md, template/.project-agent-workflow/AGENTS.md.jinja, references/orchestration.md and the generated SPEC_ORCHESTRATION.md, and check-root-agent-policy.py and check-copier-template.py pin its spark and terra markers.","kind":"existing_mechanism"}
  - {"evidence":"The telemetry sentence stating that custom workers record one attempt duration and zero model starts appears in references/orchestration.md and SPEC_ORCHESTRATION.md and must change when Go attempts record a model.","kind":"existing_mechanism"}
  - {"evidence":"tests/copier-update.sh copies exactly the files listed in tests/fixtures/orchestration/copier-update-source-inventory.txt into its versioned update source, so every new managed file needs an inventory line.","kind":"existing_mechanism"}
completion_conditions:
  - Root and generated AGENTS instructions, orchestration guidance and the delegation skill describe the Go candidate route as available only after explicit local enablement and an eligible plan, and the policy checkers assert those statements.
  - Default root and generated installations still route writable work to Codex, keep Sol for review, and run unrelated custom workers unchanged.
  - The combined read-only helper and candidate cases pass together against one shared launcher.
  - Versioned update sources include every managed file of plans 394 to 396, and copy and update install them without replacing project-owned policy or configuration bytes.
  - The root and generated inventory and mechanically rewritten counterparts stay aligned under the template checker.
completion_witness_map:
  - {"condition_sha256":"sha256:f1cc42ff54601d4079fd8739fdc6b405d72cf8c0d9b5ec610054ecd58c21d756","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:6dac38b3903433731fb17164ca9d499adda18de544601ba190d827c0ae54260f","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:e3ce82f87cc3949c7d687ee6015ccf7fa50ef6917999d2fe5fe269bb05506da5","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:cf02f77d3973db80e941c943e01592a8109277b10f8c914b1f961f674257c002","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:91c515f8dce7c4667b0d7923026d687bc0676675f33e2915656d7ec0eda253ec","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - AGENTS.md
  - template/AGENTS.md.jinja
  - template/.project-agent-workflow/AGENTS.md.jinja
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - docs/agent/opencode-go.json
  - template/docs/agent/opencode-go.json.jinja
  - .codex/skills/opencode-delegate/SKILL.md
  - .codex/skills/opencode-delegate/references/worker-contract.md
  - .codex/skills/opencode-delegate/agents/openai.yaml
  - template/.project-agent-workflow/skills/opencode-delegate/SKILL.md
  - template/.project-agent-workflow/skills/opencode-delegate/references/worker-contract.md
  - template/.project-agent-workflow/skills/opencode-delegate/agents/openai.yaml
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
  - Plan 356 and the plans its reconstruction creates must reach checked archives before this plan starts, because this plan reuses the read-only helper launcher, configuration and discovery surfaces they add.
checked_summary_ja: OpenCode Go の実装候補経路を案内、スキル、Copier の配布に組み込み、既定の動作を保つ。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct.
- Own the final integration verification of plan 357's complete acceptance list here; do not create a verification-only successor.
- Add an explicit candidate-enable field to the project-owned opencode-go.json seeded by plan 356's successors; keep it disabled by default and add no Copier question.
- Update both the generated root AGENTS seed and the managed .project-agent-workflow/AGENTS.md body so preserved downstream root instructions can discover the route.
- Keep formal review on the existing independent reviewer route; a Go helper never claims review authority.

## Tasks

- [ ] Before product edits, resolve every predecessor to its checked archive, prepare the parent-direct execution ledger with the reviewer registry, continuation registry, review-route check and adversarial preflight, and record the unchanged baseline behavior this plan must keep.
- [ ] Update the routing rule and telemetry sentence in root and generated instructions and orchestration guidance, and their checker markers.
- [ ] Extend the delegation skill, its worker contract, UI metadata and the sequential orchestrator skill with the explicit candidate route.
- [ ] Add the candidate-enable field to the configuration and its preservation case.
- [ ] Run the combined helper and candidate cases and generated-layout smoke cases for the Go route and unchanged defaults.
- [ ] Extend tests/fixtures/orchestration/copier-update-source-inventory.txt and tests/copier-update.sh so the versioned update source contains every managed file this plan adds, reading the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite; do not weaken the fixture grammar.
- [ ] Obtain independent review of the exact in-scope patch and its security cases through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the unchanged authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Pre-activation review on 2026-09-26 reconstructed plan 357 into three successors: its write scope lacked scripts/project_workflow/copier_inventory.py, the Go-path selector and tool permission set were undecided, two completion conditions had witnesses that cannot establish them, and its OpenCode 1.18.30 evidence no longer matched the installed 2.0.15 CLI.
