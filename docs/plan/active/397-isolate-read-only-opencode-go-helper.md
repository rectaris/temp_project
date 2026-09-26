# Run an isolated read-only OpenCode Go helper against an admitted repository snapshot

status: replan_required
implementation_mode: parent_direct
primary_invariant: A parent-selected OpenCode Go helper reads only the admitted snapshot files and returns a bounded advisory answer, with no shell, network except the relay socket, credential, or repository write.
replan_sources:
  - docs/plan/active/356-delegate-read-only-tasks-to-opencode-go.md
replan_contract: docs/plan/replanned/contracts/356-delegate-read-only-tasks-to-opencode-go.json
successor_plans:
  - docs/plan/active/397-isolate-read-only-opencode-go-helper.md
  - docs/plan/active/398-seed-opencode-go-helper-configuration.md
  - docs/plan/active/399-integrate-opencode-go-read-only-helper.md
inherited_acceptance_digests:
  - sha256:6a93344caf98fde95f6920a3db153727b5203c0bc6f8700503494d5c2c64b59c
  - sha256:2c6b904e8013fa92f54ad13d9707d3d2ad62ba0d96eca963e72e395529132af0
  - sha256:518cd64e6d0416977a47728c0c8c65705c78b4d993a7b86279942f16329a2426
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
  - {"evidence":"OpenCode 2.0.15 with env -i, a fresh HOME and XDG tree and OPENCODE_CONFIG_CONTENT naming a loopback provider sent only the bare model glm-5.3 for both the answer and the title request, and run --format json wrote JSONL events step_start, text, tool_use, step_finish and error.","kind":"bounded_prototype"}
  - {"evidence":"In bwrap with --unshare-net, --unshare-pid, --die-with-parent, read-only /usr and binary binds and a tmpfs HOME, run --standalone left no daemon; without --standalone it started a persistent serve process. A hostile project opencode.json or plugin ran code unless OPENCODE_DISABLE_PROJECT_CONFIG=1 was set.","kind":"bounded_prototype"}
  - {"evidence":"The same CLI's read allowlist matched only workspace-relative patterns and followed symlinks out of the allowed directory, and HTTP 429 and 500 retried without limit until an external timeout, so isolation must come from the sandbox and a snapshot without symlinks, and the launcher needs its own deadline.","kind":"bounded_prototype"}
  - {"evidence":"Checked plan 359 ships opencode_go_transport.py, whose parent relay keeps the credential and serves a Unix socket; its tests bind that socket into bwrap with their own argv, because the runner's build_bwrap_command copies external inputs and cannot mount a socket.","kind":"existing_mechanism"}
completion_conditions:
  - run-opencode-helper.py starts one fresh OpenCode 2.x process per request against a snapshot of only the parent-listed repository-relative regular files, through the checked relay, and returns the advisory answer with bounded task and session identity.
  - Absolute, traversing, symlinked or non-regular paths and secret or private configuration inputs are refused before dispatch, and the snapshot is mounted read-only with only task scratch writable.
  - The launcher runs OpenCode in its own bwrap argv with no network except the relay socket, --standalone, project configuration and model fetch disabled, a fresh HOME and XDG tree and only read, glob and grep tools, and refuses a runtime whose feature probe lacks any of these.
  - An adversarial fake CLI inside the real sandbox cannot read host credentials or OpenCode state, execute repository code, follow a symlink, load a plugin, MCP server or skill, or reach another provider, and source, ref and index bytes stay unchanged.
  - The result records the requested backend and model separately from runtime-observed identity, and a nonzero exit, error or tool_use error event, empty or truncated stream, model drift, 429, 500 or timeout fails without retry or fallback.
  - New root and template files are registered in the source inventory and aligned under a documented rewrite of the sibling-module import path.
completion_witness_map:
  - {"condition_sha256":"sha256:1a7cd1bc320f6da6bfeb86505da5fb7b6627f471b675d3a7ea754819046f687a","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:3af560aa1f7df0a6783e816fe9fac475cc72c0c366d7470c0812cac53830bf27","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:1af227289f7f3692c31b5ece223713b2db6a84e7ba1eec6195aa6ba1814be59a","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:280ca3646a058504fb4796e6ed0497fd3fe272513998acd8438d08b95ee89c1c","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:976bd1a49bb3a9377665ba4013a1cfd85a271b1c026bc97f153c1a5a1bbe2fe7","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:7ee989eba0eba7365901cea7f27aa2f95b6d19e8baaa4167fbaac508e9661fea","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/run-opencode-helper.py
  - template/.project-agent-workflow/scripts/run-opencode-helper.py
  - scripts/project_workflow/opencode_go_execution.py
  - template/.project-agent-workflow/scripts/opencode_go_execution.py
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
replan_reason_codes:
  - scope_drift
checked_summary_ja: 隔離した OpenCode Go の補助プロセスに、許可したファイルだけの読み取り専用の調査を依頼する。

## Decisions

- Keep the parent orchestrator's interpretation, authorization, review selection, validation, lifecycle, commit and publication ownership, and implement parent-direct.
- Expose run-opencode-helper.py as the parent-callable entrypoint over the shared launcher in opencode_go_execution.py. Do not replace the parent model, Codex agent profiles, spawn_agent or the Sol review role.
- Let the launcher own its bwrap argv, following the 359 transport tests, instead of extending the runner's build_bwrap_command. Mount the relay socket, the binary read-only, the snapshot read-only and task scratch writable, and nothing else.
- Admit an OpenCode runtime by a fail-closed feature probe of --standalone, --format json and the project-config and model-fetch switches, never by version string alone or by catalog entitlement.
- Build the snapshot from regular files only, because the CLI's read allowlist follows symlinks. Offer only read, glob and grep; deny shell, execute, edit, write, webfetch, websearch, subagent, skill and question explicitly.
- Parse JSON events as events and judge success from them: a tool_use error or error event fails the request even at exit 0. Apply the launcher's own wall-clock deadline, because provider errors retry without limit.
- Read the helper configuration from a caller-supplied path in this plan; plan 398 seeds the project-owned file. Require an explicit exact model id and the chat_completions protocol, and store no credential.
- Prove the isolation boundary with an adversarial fake CLI inside the real bwrap sandbox on every host. Run a real OpenCode conformance case whenever an admitted binary is installed and record its result; CI installs no OpenCode, and no case installs, upgrades or authenticates a CLI.
- Keep large evidence local with missing transcript or hook coverage explicit, and retain only bounded identity, requested and observed settings, answer and status in the result.

## Tasks

- [ ] Before product edits, resolve every predecessor to its checked archive, prepare the parent-direct execution ledger with the reviewer registry, continuation registry, review-route check and adversarial preflight, and record the unchanged baseline behavior this plan must keep.
- [ ] Rerun the OpenCode feature probe and minimal sandbox argv against the installed CLI and record the observed version and switches in Validation Notes.
- [ ] Implement input validation, snapshot construction, the launcher argv, event parsing and the structured result.
- [ ] Add helper cases for command and subagent attempts, read and symlink escapes, hostile project configuration and plugins, ambient credentials, unexpected models, malformed or oversized JSON, a missing final answer, error events at exit 0, nonzero exits, 429, 500, timeout, cancellation and retry refusal, and register them in tests/test-sandboxed-plan-worker.py.
- [ ] Register the new files in the source inventory and add their alignment check.
- [ ] Obtain independent review of the exact in-scope patch and its security cases through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the unchanged authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Pre-activation review on 2026-09-26 reconstructed plan 356 into three successors: its write scope lacked scripts/project_workflow/copier_inventory.py and the orchestration guidance, the runner's Bubblewrap builder cannot mount a Unix socket, one completion condition had a witness that cannot observe an update, and its OpenCode 1.18.30 run --pure evidence no longer matched the installed 2.0.15 CLI.
- Stopped at replan_required on 2026-09-26 on the owner's instruction to reconstruct plans 394 to 399 through the governed route under Issue #14: the plans add OpenCode-specific launch, routing and discovery surfaces, while the owner now requires them to target the generic Capability Registry and WorkerBackend boundary, which changes their write scopes and implementation methods.
