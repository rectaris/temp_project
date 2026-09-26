# Run a read-only capability through an isolated OpenCode Go backend

status: deferred
completion_deferred_reason: The Issue #14 foundation plan and the Issue #15 minimal Evaluation Controller must be checked first, as integration_gates records.
implementation_mode: parent_direct
primary_invariant: A read-only capability request resolved to the OpenCode Go backend reads only the admitted snapshot files and returns a bounded advisory evidence artifact, with no shell, no network except the relay socket, no credential and no repository write.
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
integration_source_ids:
  - 397
task_types:
  - template_workflow
  - security
  - external_services
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"bounded_prototype","evidence":"OpenCode 2.0.15 with env -i, a fresh HOME and XDG tree and OPENCODE_CONFIG_CONTENT naming a loopback provider sent only the bare model glm-5.3 for both the answer and the title request, and run --format json wrote JSONL events step_start, text, tool_use, step_finish and error."}
  - {"kind":"bounded_prototype","evidence":"In bwrap with --unshare-net, --unshare-pid, --die-with-parent, read-only /usr and binary binds and a tmpfs HOME, run --standalone left no daemon; without --standalone it started a persistent serve process. A hostile project opencode.json or plugin ran code unless OPENCODE_DISABLE_PROJECT_CONFIG=1 was set."}
  - {"kind":"bounded_prototype","evidence":"The same CLI's read allowlist matched only workspace-relative patterns and followed symlinks out of the allowed directory, and HTTP 429 and 500 retried without limit until an external timeout, so isolation must come from the sandbox and a snapshot without symlinks, and the backend needs its own deadline."}
  - {"kind":"existing_mechanism","evidence":"Checked plan 359 ships opencode_go_transport.py, whose parent relay keeps the credential and serves a Unix socket; its tests bind that socket into bwrap with their own argv, because the runner's build_bwrap_command copies external inputs and cannot mount a socket."}
  - {"kind":"existing_mechanism","evidence":"No WorkerBackend or capability registry exists yet in scripts/, template/, docs/agent/ or references/, and the read-only Codex helpers are the repo_explorer, docs_researcher and evidence_synthesizer profiles that ownership.yaml seeds as project-owned, so a registry can default to them without rewriting a profile."}
completion_conditions:
  - run-read-only-worker.py accepts one declared read-only capability, a bounded task, an exact requested model and parent-listed repository-relative input paths, resolves the backend through the Capability Registry, and dispatches one fresh OpenCode 2.x process per request through the WorkerBackend boundary and the checked relay.
  - Absolute, traversing, symlinked or non-regular paths and secret or private configuration inputs are refused before dispatch, and the snapshot is mounted read-only with only task scratch writable.
  - OpenCodeGoBackend owns its bwrap argv, feature probe, JSON event parser and relay binding, runs with no network except the relay socket, --standalone, project configuration and model fetch disabled, a fresh HOME and XDG tree and only read, glob and grep tools, and refuses a runtime whose probe lacks any of these.
  - An adversarial fake CLI inside the real sandbox cannot read host credentials or OpenCode state, execute repository code, follow a symlink, load a plugin, MCP server or skill, or reach another provider, and source, ref and index bytes stay unchanged.
  - The result is one bounded backend-neutral read-only evidence artifact carrying status, findings, exact file and symbol references, source digests, unresolved questions, bounded confidence and escalation reason, with the requested backend and model recorded separately from runtime-observed identity.
  - A nonzero exit, error or tool_use error event, empty or truncated stream, model drift, 429, 500 or timeout fails without retry or backend fallback, and a capability resolving to an unregistered backend or a disabled implementation is refused before any process starts.
  - A capability that resolves to a native Codex profile starts no process and returns one bounded resolution result naming that profile, so the parent invokes the existing native helper mechanism unchanged.
  - New root and template files are registered in the source inventory, and the registry, backend and invocation copies stay aligned under a documented rewrite of the sibling-module import path.
completion_witness_map:
  - {"condition_sha256":"sha256:ab32003e860cfee88a0ada72021673feb45374d982207e95376402540a31c823","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:3af560aa1f7df0a6783e816fe9fac475cc72c0c366d7470c0812cac53830bf27","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:9016a14f59fc0917ba0d95901e2d20c13e882b41a07b1f84dd5052e5eb6e2c60","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:280ca3646a058504fb4796e6ed0497fd3fe272513998acd8438d08b95ee89c1c","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:7c1b5d532ae74f4152db92a28a89180626a8f3fd4a34622e0b077ba5e13d2a46","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:3bdd87cb618c542e922a8690732cf293350e77845285cdd15726d940d81987ad","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:e2d5630b3cf82a5b953a423527c2f00a93f6fc0309c8e108d0abb2c8916e8d9c","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:4159b4ae298bdc1e2a0303bbb5d217a782ef816d140f2693833f8892cfdf57b5","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/run-read-only-worker.py
  - template/.project-agent-workflow/scripts/run-read-only-worker.py
  - scripts/project_workflow/worker_backends.py
  - template/.project-agent-workflow/scripts/worker_backends.py
  - scripts/project_workflow/opencode_go_backend.py
  - template/.project-agent-workflow/scripts/opencode_go_backend.py
  - docs/agent/capability-registry.json
  - template/.project-agent-workflow/docs/agent/capability-registry.json
  - tests/opencode_go_helpers.py
  - tests/test-sandboxed-plan-worker.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - scripts/project_workflow/opencode_go_transport.py
  - scripts/run-sandboxed-plan-worker.py
  - .codex/agents/repo_explorer.toml
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
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The orchestrator can invoke the shipped helper command with an exact Go model, bounded task and explicit repository input paths and receive an answer while retaining every adoption and validation decision.
  - A real isolated fixture proves source/ref/index bytes stay unchanged and the helper cannot obtain host credentials, run repository code, expand input paths through symlinks, load external plugins/MCP/skills or use a different provider.
  - The result records the requested backend/model and directly observed runtime identity separately, never upgrades a request to provider-execution evidence, and reports bounded failures including 429, timeout, error events and incomplete output.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:6a93344caf98fde95f6920a3db153727b5203c0bc6f8700503494d5c2c64b59c","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:2c6b904e8013fa92f54ad13d9707d3d2ad62ba0d96eca963e72e395529132af0","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:518cd64e6d0416977a47728c0c8c65705c78b4d993a7b86279942f16329a2426","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
integration_gates:
  - docs/plan/checked/2026/09/01-15/359-isolate-opencode-go-inference-credentials.md
  - The Issue #14 foundation plan must reach a checked archive before this plan starts. It adds the managed Capability Registry in docs/agent/capability-registry.json and its template copy, and the WorkerBackend boundary with CodexBackend in scripts/project_workflow/worker_backends.py and its template copy, while every capability still resolves to the unchanged Codex path.
  - The Issue #15 minimal Evaluation Controller must reach a checked archive before this plan starts, so that one controlled run uses fresh Git state, isolated HOME, TMP and XDG directories, a fresh independent verifier and Plan-319-compatible run observations compared by the existing compare-harness-runs.py.
checked_summary_ja: 読み取り専用の能力の要求を、隔離した OpenCode Go の実装で処理し、利用者を特定しない形式の証拠として返す。

## Decisions

- Keep the parent orchestrator's interpretation, authorization, review selection, validation, lifecycle, commit and publication ownership, and implement parent-direct.
- Consume the Capability Registry and the WorkerBackend boundary that the Issue #14 foundation plan lands, and add OpenCodeGoBackend as the first non-Codex implementation of the repository_exploration capability. Add no OpenCode-specific entrypoint, routing branch or skill.
- Expose run-read-only-worker.py as the one parent-callable read-only invocation. It takes a capability name, never a provider name, and the parent may pass an exact model only from the backend configuration's model map.
- Resolve the capability before any dispatch. A native Codex profile resolution returns a bounded result naming the profile and starts no process, so the parent spawns that helper through the existing native mechanism; only an enabled process backend dispatches a process and returns the evidence artifact.
- Keep every OpenCode specific inside opencode_go_backend.py: the feature probe, JSON event parsing, bwrap argv, relay binding, error classification and provider configuration. Reuse the checked relay in opencode_go_transport.py unchanged; it stays an OpenCode primitive, not a generic credential mechanism.
- Define the read-only evidence artifact in worker_backends.py as the backend-neutral result of every read-only capability. Bound every field, keep it advisory, and never let it satisfy validation, review, authorization or lifecycle requirements; the parent verifies important claims before acceptance.
- Register opencode-go in both registry copies as an optional implementation of repository_exploration only. It is selected only when the backend configuration enables that capability; the default stays the native Codex profile.
- Keep the existing read-only Codex helpers as native .codex/agents profiles. This plan adds no Codex process backend, rewrites no project-owned profile and changes no default resolution.
- Let the backend own its bwrap argv, following the 359 transport tests, instead of extending the runner's build_bwrap_command. Mount the relay socket, the binary read-only, the snapshot read-only and task scratch writable, and nothing else.
- Admit an OpenCode runtime by a fail-closed feature probe of --standalone, --format json and the project-config and model-fetch switches, never by version string alone or by catalog entitlement.
- Build the snapshot from regular files only, because the CLI's read allowlist follows symlinks. Offer only read, glob and grep; deny shell, execute, edit, write, webfetch, websearch, subagent, skill and question explicitly.
- Judge success from JSON events: a tool_use error or error event fails the request even at exit 0. Apply the backend's own wall-clock deadline, because provider errors retry without limit.
- Read the backend configuration from a caller-supplied path in this plan; plan 405 seeds the project-owned file and makes it the default. Require an explicit exact model id and the chat_completions protocol, and store no credential.
- Prove the isolation boundary with an adversarial fake CLI inside the real bwrap sandbox on every host. Run a real OpenCode conformance case whenever an admitted binary is installed and record its result; CI installs no OpenCode, and no case installs, upgrades or authenticates a CLI.
- Keep large evidence local with missing transcript or hook coverage explicit, and retain only bounded identity, requested and observed settings, findings and status in the artifact.

## Tasks

- [ ] Before product edits, resolve every predecessor and integration gate to its checked archive or recorded evidence, prepare the parent-direct execution ledger with the reviewer registry, continuation registry, review-route check and adversarial preflight, and record the unchanged baseline behavior this plan must keep.
- [ ] Rerun the OpenCode feature probe and minimal sandbox argv against the installed CLI and record the observed version and switches in Validation Notes.
- [ ] Read the checked foundation's WorkerBackend interface and registry schema, and record in Validation Notes which interface members and registry fields this plan adds.
- [ ] Implement the read-only evidence artifact, the generic invocation, input validation, snapshot construction and OpenCodeGoBackend's argv, probe, event parsing and relay binding.
- [ ] Register opencode-go as an optional implementation of repository_exploration in both registry copies.
- [ ] Add cases for command and subagent attempts, read and symlink escapes, hostile project configuration and plugins, ambient credentials, unexpected models, malformed or oversized JSON, a missing final answer, error events at exit 0, nonzero exits, 429, 500, timeout, cancellation, retry refusal, native-profile resolution without a process and disabled-implementation refusal, and register them in tests/test-sandboxed-plan-worker.py.
- [ ] Register the new files in the source inventory and add their alignment check.
- [ ] Obtain independent review of the exact in-scope patch and its security cases through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the unchanged authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Reconstructed on 2026-09-26 from plans 397 to 399 on the owner's instruction under Issue #14: the source plans added an OpenCode-specific helper command, skill and routing entry, while the owner now requires read-only delegation to request a capability through the Capability Registry and the WorkerBackend boundary, with OpenCode Go as one optional backend.
