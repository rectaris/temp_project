# Seed a disabled project-owned OpenCode Go backend configuration

status: deferred
completion_deferred_reason: Plan 404 must be checked first.
implementation_mode: parent_direct
primary_invariant: Every installation starts with no capability enabled for the OpenCode Go backend, and a project-owned backend configuration is never replaced by a Copier update.
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
  - sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb
integration_source_ids:
  - 398
predecessor_plans:
  - docs/plan/active/404-run-read-only-capabilities-through-opencode-go-backend.md
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"ownership.yaml marks docs/agent/** seeded_project_owned, so a template/docs/agent/opencode-go.json.jinja seed is rendered on copy and preserved on update, as template-feedback.json already is."}
  - {"kind":"existing_mechanism","evidence":"Adding a Copier question to copier_inventory.py QUESTIONS would force edits to every answers fixture, the pairwise table, the smoke answer loop and the copier-update data list, so a seed without a question keeps the change bounded."}
completion_conditions:
  - docs/agent/opencode-go.json and its generated seed hold schema_version 1, an empty enabled_capabilities list, an explicit model map, the chat_completions protocol and bounded execution limits, store no credential, and are asserted by the template checker.
  - Capability resolution never selects the OpenCode Go backend for a capability absent from enabled_capabilities, and dispatch is refused when the model map lacks the requested model, the protocol is unsupported, or enabled_capabilities names a capability the registry does not map to the backend.
  - A real Copier update keeps a locally edited opencode-go.json byte-identical, and a fresh copy renders the disabled seed.
completion_witness_map:
  - {"condition_sha256":"sha256:6e9c8578689d097d88857139c87a7bea3a9a41ea3e70dc6d94788e559acfa63f","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:1f980f56541a260a22bf51bbb1946aa9f9175a62089467627ae1451dbec48011","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:b86bcdefa103c4b24e6e351b4bbe4f5f7ee1e49950b2cd2dbf00f26190eea08f","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - docs/agent/opencode-go.json
  - template/docs/agent/opencode-go.json.jinja
  - scripts/project_workflow/opencode_go_backend.py
  - template/.project-agent-workflow/scripts/opencode_go_backend.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/test-sandboxed-plan-worker.py
  - tests/opencode_go_helpers.py
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - template/.project-agent-workflow/ownership.yaml
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
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Versioned Copier update sources include the new managed files and copy/update fixtures install them without replacing existing project-owned policy or configuration bytes.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
integration_gates:
  - docs/plan/checked/2026/09/01-15/359-isolate-opencode-go-inference-credentials.md
checked_summary_ja: OpenCode Go の実装の設定を、どの能力も有効にしない状態で配布し、更新でプロジェクトの設定を上書きしない。

## Decisions

- Implement parent-direct and keep the parent orchestrator's final ownership.
- Treat opencode-go.json as backend-specific configuration that the Capability Registry references. The registry stays the routing source of truth; this file only enables registered implementations and supplies the model map, protocol and limits.
- Express enablement as an enabled_capabilities list of registry capability names, empty by default, instead of a provider mode switch, so a later writable capability needs no new field.
- Seed the configuration without a Copier question. The project owner enables a capability by editing the project-owned file; no installer, account or credential step is automated.
- Keep docs/agent/opencode-go.json in the root with no capability enabled as well; the root repository enables one only by an explicit local edit.

## Tasks

- [ ] Before product edits, resolve every predecessor and integration gate to its checked archive or recorded evidence, prepare the parent-direct execution ledger with the reviewer registry, continuation registry, review-route check and adversarial preflight, and record the unchanged baseline behavior this plan must keep.
- [ ] Add the root configuration and the generated seed, register the seed in GENERATED_REQUIRED and assert its content in the template checker.
- [ ] Make OpenCodeGoBackend load the project-owned file by default and add the unenabled-capability, unknown-model, unsupported-protocol and unregistered-capability refusals.
- [ ] Extend tests/fixtures/orchestration/copier-update-source-inventory.txt and tests/copier-update.sh so the versioned update source contains every managed file this plan adds, reading the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite; do not weaken the fixture grammar.
- [ ] Obtain independent review of the exact in-scope patch and its security cases through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the unchanged authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Reconstructed on 2026-09-26 from plans 397 to 399 on the owner's instruction under Issue #14: the source plans added an OpenCode-specific helper command, skill and routing entry, while the owner now requires read-only delegation to request a capability through the Capability Registry and the WorkerBackend boundary, with OpenCode Go as one optional backend.
