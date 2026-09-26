# Resolve the Codex plan runner through a managed Capability Registry and a CodexBackend with no behavior change

status: in_progress
primary_invariant: Every capability resolves to an existing Codex implementation, and the runner's Codex attempts launch the exact command, sandbox, model routing, fallback, receipts, manifests and validation they launched before, obtained only through the resolved CodexBackend.
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"execute_isolated_attempt builds every Codex argv through one default_worker_command call and passes it unchanged to build_bwrap_command, so moving that builder behind CodexBackend leaves the Bubblewrap argv, environment sanitization, binary staging and receipt code untouched.","kind":"existing_mechanism"}
  - {"evidence":"The runner already loads its managed sibling modules planlib.py and plan_validation_commands.py through importlib from its own directory, so worker_backends.py can be loaded the same way in the root scripts/project_workflow layout and the flat generated layout.","kind":"existing_mechanism"}
  - {"evidence":"tests/test-sandboxed-plan-worker.py drives the root runner against fake codex executables through --codex-bin and asserts that the root and template runner copies are byte-identical, so the unchanged Codex path is observable end to end.","kind":"existing_mechanism"}
  - {"evidence":"check-copier-template.py already requires byte and mode equality for the root and generated opencode_go_transport.py copies, and SOURCE_REQUIRED and GENERATED_REQUIRED in copier_inventory.py list every shipped module, which the new module and registry can follow.","kind":"existing_mechanism"}
  - {"evidence":"ownership.yaml marks .project-agent-workflow/** copier_managed and .codex/agents/*.toml seeded_project_owned, and root .codex/agents and template/.codex/agents both carry the seven profiles, so a managed registry can name those profiles without owning or rewriting them.","kind":"existing_mechanism"}
completion_conditions:
  - docs/agent/capability-registry.json and its byte-identical managed copy declare schema_version 1 and exactly repository_exploration, bounded_implementation, plan_implementation, evidence_synthesis, documentation_research and deep_review, with plan_implementation resolving to the Codex sandboxed runner and every other capability to existing .codex/agents profiles.
  - worker_backends.py refuses a registry that is missing, symlinked, non-regular or oversized, is not one exact JSON object, repeats, omits or reorders a capability, declares an unknown key, backend, kind or access value, attaches the sandboxed runner to any capability except plan_implementation, or names a malformed profile.
  - Every profile the registry names exists as a root .codex/agents profile and a template/.codex/agents seed, and this plan changes no .codex/agents file.
  - CodexBackend builds exactly the Codex argv the runner built before this plan for any executable, clone, last-message path, model and reasoning, and the runner's primary, fallback and correction Codex attempts obtain their command only from the resolved backend.
  - run and correct resolve plan_implementation through the registry before any lifecycle, execution-ledger or attempt effect on the Codex path and refuse with a bounded error when resolution fails, while the custom --worker-binary path, model routing, fallback, receipts, manifests and validation keep their behavior.
  - The generated copy of worker_backends.py imports only the standard library and, placed in a flat scripts directory beside a generated docs/agent registry, resolves plan_implementation to CodexBackend.
  - The module and registry are registered in SOURCE_REQUIRED, GENERATED_REQUIRED and the Copier update source inventory, and their root and generated copies stay byte- and mode-identical under the template checker.
completion_witness_map:
  - {"condition_sha256":"sha256:8927f8e6eaca751dcf83dbed3b5f129c09374c10388e0be8ce8222bcce8d86a4","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:87bca16bb2ac6ffb3dbf40addb139b049a57bada46ab9c3203f096e1c27bcc1b","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:f6954b8ff8910e62f8105a4cf2e41214232666d7f8ba5e0522afc7a0d787efe6","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:965fdafef3d09a39da4ba8607241530a2f68fa886c483086557248b9b604abb4","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:acfebb04211ebdc23bbd578cf6c5dba616d851cc68a5c9f71c232ee5c1996905","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:0ceecc78f02772bbfd26ef60bbe23a9d14b98be3baa88bc9fb6aac181d224d66","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:3bafb31c013d2a98b6f9dd0319df1ecc868a542e7f3f48a29a32bbaeb882861c","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - docs/agent/capability-registry.json
  - template/.project-agent-workflow/docs/agent/capability-registry.json
  - scripts/project_workflow/worker_backends.py
  - template/.project-agent-workflow/scripts/worker_backends.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - tests/test-sandboxed-plan-worker.py
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - CHANGELOG.md
  - scripts/check-copier-template.py
  - scripts/project_workflow/copier_inventory.py
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - template/.project-agent-workflow/ownership.yaml
  - .codex/agents/repo_explorer.toml
  - .codex/agents/scoped_worker.toml
  - docs/plan/backlog/404-run-read-only-capabilities-through-opencode-go-backend.md
  - docs/plan/backlog/407-bind-worker-backend-dispatch-provenance.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
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
  - A capability registry resolves every current Codex worker role to its existing implementation without rewriting a project-owned agent profile.
  - Existing Codex-only workflows retain the same externally visible behavior by default, and the existing writable-worker contract, receipt, candidate manifest, sandbox and validation artifacts are reused rather than replaced.
  - Copier copy and update install the new managed module and registry while preserving project-owned code, policy, configuration and agent profiles.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:054823b42556f443b8571efc0b038c35350ae36c3b66b983cae82af7121f347a","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:ced46c62c2126a87cba0684d1cdf19b38485f4193c59612d836ea11a6012ec7a","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:0226676271caf0a2538cca7c441ef56af54191f85431a31f7810cf91b591b81a","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
integration_gates:
  - Plans 404 to 409 edit the module and registry at the exact paths this plan creates; keep those paths and their root and managed pairing.
checked_summary_ja: 管理された Capability Registry と CodexBackend を加え、既存の Codex の実行経路を動作を変えずにその境界の下に置く。

## Decisions

- Keep the parent orchestrator's interpretation, authorization, review selection, validation, lifecycle, commit and publication ownership, and implement parent-direct; the writable runner refuses this write scope as validation authority.
- Create the managed registry at docs/agent/capability-registry.json with its byte-identical copy at template/.project-agent-workflow/docs/agent/capability-registry.json, and the module at scripts/project_workflow/worker_backends.py with its byte-identical copy at template/.project-agent-workflow/scripts/worker_backends.py. Plans 404 to 409 already name these paths.
- Use one exact registry shape: schema_version 1 and an ordered capabilities list, each entry with id, access and a non-empty implementations list. An implementation is backend codex with kind sandboxed_runner, or backend codex with kind native_profile and a non-empty ordered profiles list. The first implementation is the resolution; this plan adds no optional implementation, enablement field or selection flag.
- Map plan_implementation to the sandboxed runner, repository_exploration to repo_explorer, bounded_implementation to fast_scoped_worker and scoped_worker, evidence_synthesis to evidence_synthesizer, documentation_research to docs_researcher and deep_review to change_reviewer. The parent's existing rules still choose between listed profiles and the runner's existing rule still chooses the model.
- Name profiles only. The registry never stores a model, reasoning value or instruction, and it never writes a .codex/agents file, which stays project-owned.
- Define WorkerBackend with a stable backend_id and one command builder, and CodexBackend as its only implementation. Move the Codex argv verbatim from default_worker_command into CodexBackend and remove default_worker_command; the runner keeps binary staging, Bubblewrap, environment sanitization, fallback classification, receipts and manifests.
- Resolve plan_implementation in run and correct before any lifecycle, ledger or attempt effect when no --worker-binary is given, and pass the resolved backend into execute_isolated_attempt. The custom --worker-binary path stays an explicit parent executable and does not consult the registry.
- Locate the module and registry from the runner's own directory: worker_backends.py or project_workflow/worker_backends.py beside it, and docs/agent/capability-registry.json under its parent. Refuse a missing, symlinked, non-regular, oversized or malformed registry; there is no environment or argument override.
- Keep worker_backends.py standard-library only with no sibling imports, so the generated flat copy needs no rewrite. Offer a read-only resolve command that prints one capability's resolution as JSON for the parent and later plans.
- Add no harness identity or telemetry field. The configuration identity that Issue #15 consumes is decided in the #15 evaluation plan, because it changes the Plan 319 observation schema rather than this boundary.

## Tasks

- [ ] Before product edits, prepare the parent-direct execution ledger with prepare-parent-direct, record the review-route check, and record the pre-change Codex argv and runner suite result this plan must keep.
- [ ] Add worker_backends.py with registry loading, validation, resolution, WorkerBackend, CodexBackend and the resolve command, and the registry in both layouts.
- [ ] Route the primary, fallback and correction Codex attempts through the resolved backend in both runner copies and remove default_worker_command.
- [ ] Add registry refusal, resolution, exact argv, resolution-before-effect and flat-layout cases to tests/test-sandboxed-plan-worker.py, and keep the existing runner cases unchanged.
- [ ] Register the module and registry in the inventories and the Copier update source inventory, and add the template checker alignment and profile-existence checks.
- [ ] Document the boundary in references/orchestration.md, the generated SPEC_ORCHESTRATION.md and CHANGELOG.md.
- [ ] Record a passing adversarial preflight, obtain independent review through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Owner instruction on 2026-09-26, 「1. のプランを実装せよ。」, selected the Issue #14 foundation as the next step after the reconstruction of plans 394 to 399, with the recommended choices: the #15 configuration identity stays out of this plan, the registry holds the six Issue #14 capabilities, and the foundation runs before the #15 controller.
