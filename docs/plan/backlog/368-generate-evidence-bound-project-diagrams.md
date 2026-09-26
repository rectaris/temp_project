# Generate evidence-bound project diagrams and refresh configured artifacts before plan completion

status: backlog
primary_invariant: A configured diagram is rendered only from graph data whose every node and edge cites a current source digest, a refused render leaves prior output byte-identical, and an unconfigured project completes plans exactly as before.
task_types:
  - template_workflow
  - skill_authoring
  - planning_docs
review_class: A
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Both complete-plan.sh copies already run an optional check guarded by the presence of its script (scripts/referent-contract.py) before the ready transition, and tests such as tests/root-plan-lifecycle.sh copy complete-plan.sh alone into fixtures, so an artifact check that is a no-op when its script or configuration is absent keeps those fixtures valid.","kind":"existing_mechanism"}
  - {"evidence":"docs/agent/** is seeded_project_owned in ownership.yaml, so a template/docs/agent/project-artifacts.json.jinja seed is preserved on update, and .agent-artifacts/ is ignored by template/.gitignore.jinja.","kind":"existing_mechanism"}
  - {"evidence":"Checked plan 107 registered a vendored skill through ownership.yaml, both validate-copier-update.py copies, copier_inventory.py, check-root-agent-policy.py, check-copier-template.py, assert-generated-semantics.py, smoke.sh, copier-update.sh and the update-source inventory.","kind":"existing_mechanism"}
  - {"evidence":"tests/test-validation-tools.py imports test modules from tests/validation_tools/ and is an admitted validation command, so the artifact tests need no new allowlist entry.","kind":"existing_mechanism"}
completion_conditions:
  - project-artifacts.py render writes a Mermaid flowchart for kind concept and an erDiagram for kind relational from graph JSON whose every node and edge cites a repository path and SHA-256, deterministically and by atomic replacement.
  - A stale or missing citation, an absolute, traversing, symlinked or out-of-root path, or malformed graph data refuses the render and leaves the prior output byte-identical.
  - complete-plan.sh runs project-artifacts.py check before the ready transition only when the script and the project configuration exist and enable an artifact; a stale configured artifact stops completion, and an absent or empty configuration changes nothing.
  - Root and generated project-artifacts skills, bridge and specification stay aligned, the generated configuration seed defaults to no artifacts, and the root skill set passes parity.
  - Every new managed file is registered in the inventory and ownership records, and the template checker passes.
  - A real Copier update installs the project-artifacts additions and preserves an edited project-owned artifact configuration and existing workflow behavior.
  - Both validation-command allowlists admit `python3 tests/test-web-demo-live.py` as a plain Python test entrypoint and still refuse every other new form.
completion_witness_map:
  - {"condition_sha256":"sha256:8735b3e81ecf94d2452fc0f6e45ed89a5a2ca4be0b1fba893d94bcc4fa6d3d1d","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:50c7cf84047c1a1dea61ec41a769151a78530da5a9e02b6735c50eba45d14971","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:2f2d3e9faab1aacc3abd61c7d4731cdea3d6b964d8c471aee901c768847c75fe","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:c2875cb04a651ff2704dc07b1c868dca8d4ab039c603838938fcbbb30ad438b8","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:2159ad317e2cfb6583816c5c07d167c6530205f28bbaec9132fff4c1849d625d","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:6930da986db843c879632e8f0ca96674388a6d221033d1f9504604efbc0fd902","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:5740326496a03205b2137f4e73a7ec7828905f5b9f8e774bdc1a6fad927200d5","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/project-artifacts.py
  - template/.project-agent-workflow/scripts/project-artifacts.py
  - docs/agent/SPEC_PROJECT_ARTIFACTS.md
  - template/.project-agent-workflow/docs/agent/SPEC_PROJECT_ARTIFACTS.md
  - tests/validation_tools/project_artifacts.py
  - template/docs/agent/project-artifacts.json.jinja
  - docs/agent/spec-index.yaml
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - .codex/skills/project-artifacts/SKILL.md
  - .codex/skills/project-artifacts/agents/openai.yaml
  - .codex/skills/project-artifacts/references/configuration.md
  - template/.project-agent-workflow/skills/project-artifacts/SKILL.md
  - template/.project-agent-workflow/skills/project-artifacts/agents/openai.yaml
  - template/.project-agent-workflow/skills/project-artifacts/references/configuration.md
  - template/.agents/skills/project-artifacts/SKILL.md
  - scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - tests/root-plan-lifecycle.sh
  - scripts/lint-project-workflow.sh
  - scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - README.md
  - template/.project-agent-workflow/README.md
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
  - copier.yml
  - docs/plan/checked/2026/09/01-15/107-complete-natural-japanese-copilot.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - references/orchestration.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Changed specifications or data structures produce evidence-bound conceptual Mermaid diagrams and ER diagrams where a relational model applies; stale evidence and unsafe paths refuse without overwriting prior output.
  - Root and generated skills, ownership, routing and completion wiring remain aligned; Copier copy and update preserve project-owned configuration and existing workflow behavior.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:9ab18d3632eaa400788b035f86dde7d3d2b12f8f0270cf1e31758914c702dd71","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:96ea69c75ea5f16a959af889e6a4e161abb7b8982bf7f583d7c24839c53fc4e2","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
checked_summary_ja: 仕様とデータ構造の変更に根拠付きのMermaid図とER図を追従させ、完了前に鮮度を検査する。

## Decisions

- Implement parent-direct because completion lifecycle and validation registration are parent-owned authority. Initialize an external execution ledger and obtain independent review before focused and authoritative validation.
- Use the owner-selected trigger: specification and data-model changes refresh diagrams at task completion.
- Seed a project-owned docs/agent/project-artifacts.json with schema_version 1 and an empty diagrams list. Each diagram names an id, a kind of concept or relational, a graph JSON path and a Mermaid output path, both under docs/diagrams/.
- Agents write the graph JSON from the configured specifications; the script never infers concepts or ORM schemas. It verifies every citation digest, renders deterministic Mermaid, and replaces output atomically.
- Keep graph JSON and Mermaid output reviewable in Git. Keep Stop hooks read-only and add no hook.
- Make the completion check a no-op when the script or configuration is absent or lists no artifact, so existing fixtures and unconfigured projects complete unchanged.
- Put the tests in tests/validation_tools/project_artifacts.py under tests/test-validation-tools.py instead of adding a new validation command.
- Admit `python3 tests/test-web-demo-live.py` in both validation-command allowlists here, so the dependent Web demo plan 391 can declare its live witness before it starts. Plan 391 creates that file; running the entry earlier fails because the file is absent.
- Register every new managed file the way checked plan 107 registered a vendored skill: ownership.yaml copier_managed bridge entries with the matching CURRENT_OWNERSHIP_SHA256 in both validate-copier-update.py copies, SOURCE_REQUIRED and GENERATED_REQUIRED entries, root skill parity in check-root-agent-policy.py, generated bridge assertions, smoke coverage and the versioned copier-update source inventory.

## Tasks

- [ ] Implement graph and configuration validation, citation freshness, path safety and atomic Mermaid rendering in the paired project-artifacts.py commands.
- [ ] Add ProjectArtifactsTest with adversarial fixtures and register it in tests/test-validation-tools.py.
- [ ] Wire the conditional check into both complete-plan.sh copies and extend tests/root-plan-lifecycle.sh for configured, stale and unconfigured cases.
- [ ] Add the project-artifacts skill with its configuration reference, the root and generated specification, the spec-index route and the generated configuration seed.
- [ ] Admit the plan 391 live-demo entry in both allowlists and extend the plan-command tests.
- [ ] Register every new file and bridge, and update README script entries.
- [ ] Extend the update-source inventory and real update scenarios, reading the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite, and assert preserved project-owned bytes and existing validation.
- [ ] Obtain independent review of the exact in-scope patch, run the focused checks, then the full validation suite once, and publish through the ordinary lifecycle without pushing.

## Validation Notes

- Pre-activation review at d61b41e split the original plan 368 into this plan and the three plans named in docs/plan/backlog/README.md, because its four features share no invariant, its write scope missed the registration files every comparable checked plan touched, and its node --test witnesses are not admitted validation commands.
