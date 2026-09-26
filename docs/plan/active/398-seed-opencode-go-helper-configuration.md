# Seed a disabled project-owned OpenCode Go helper configuration

status: deferred
completion_deferred_reason: Plan 397 must be checked first.
implementation_mode: parent_direct
primary_invariant: Every installation starts with the Go helper disabled, and a project-owned helper configuration is never replaced by a Copier update.
replan_sources:
  - docs/plan/active/356-delegate-read-only-tasks-to-opencode-go.md
replan_contract: docs/plan/replanned/contracts/356-delegate-read-only-tasks-to-opencode-go.json
successor_plans:
  - docs/plan/active/397-isolate-read-only-opencode-go-helper.md
  - docs/plan/active/398-seed-opencode-go-helper-configuration.md
  - docs/plan/active/399-integrate-opencode-go-read-only-helper.md
inherited_acceptance_digests:
  - sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb
predecessor_plans:
  - docs/plan/active/397-isolate-read-only-opencode-go-helper.md
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
  - {"evidence":"ownership.yaml marks docs/agent/** seeded_project_owned, so a template/docs/agent/opencode-go.json.jinja seed is rendered on copy and preserved on update, as template-feedback.json already is.","kind":"existing_mechanism"}
  - {"evidence":"Adding a Copier question to copier_inventory.py QUESTIONS would force edits to every answers fixture, the pairwise table, the smoke answer loop and the copier-update data list, so a seed without a question keeps the change bounded.","kind":"existing_mechanism"}
completion_conditions:
  - docs/agent/opencode-go.json and its generated seed hold schema_version 1, mode disabled, an explicit model map, the chat_completions protocol and bounded execution limits, store no credential, and are asserted by the template checker.
  - The helper refuses to dispatch while mode is disabled, when the model map lacks the requested model, or when the protocol is unsupported.
  - A real Copier update keeps a locally edited opencode-go.json byte-identical, and a fresh copy renders the disabled seed.
completion_witness_map:
  - {"condition_sha256":"sha256:86a9a9a986f81c554c17c9eba987f1ee644219f84656097cbe99cdc17f6ef7b1","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:61dac4bb5ef831fe5b9b1799f8ef8198716dfabaca5370454d271a1897d7332e","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:b86bcdefa103c4b24e6e351b4bbe4f5f7ee1e49950b2cd2dbf00f26190eea08f","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - docs/agent/opencode-go.json
  - template/docs/agent/opencode-go.json.jinja
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
checked_summary_ja: OpenCode Go 補助の設定を無効の状態で配布し、更新でプロジェクトの設定を上書きしない。

## Decisions

- Implement parent-direct and keep the parent orchestrator's final ownership.
- Seed the configuration without a Copier question. The project owner enables the helper by editing the project-owned file; no installer, account or credential step is automated.
- Keep docs/agent/opencode-go.json in the root disabled as well; the root repository enables it only by an explicit local edit.

## Tasks

- [ ] Before product edits, resolve every predecessor to its checked archive, prepare the parent-direct execution ledger with the reviewer registry, continuation registry, review-route check and adversarial preflight, and record the unchanged baseline behavior this plan must keep.
- [ ] Add the root configuration and the generated seed, register the seed in GENERATED_REQUIRED and assert its content in the template checker.
- [ ] Make the helper load the project-owned file by default and add the disabled, unknown-model and unsupported-protocol refusals.
- [ ] Extend tests/fixtures/orchestration/copier-update-source-inventory.txt and tests/copier-update.sh so the versioned update source contains every managed file this plan adds, reading the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite; do not weaken the fixture grammar.
- [ ] Obtain independent review of the exact in-scope patch and its security cases through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the unchanged authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Pre-activation review on 2026-09-26 reconstructed plan 356 into three successors: its write scope lacked scripts/project_workflow/copier_inventory.py and the orchestration guidance, the runner's Bubblewrap builder cannot mount a Unix socket, one completion condition had a witness that cannot observe an update, and its OpenCode 1.18.30 run --pure evidence no longer matched the installed 2.0.15 CLI.
