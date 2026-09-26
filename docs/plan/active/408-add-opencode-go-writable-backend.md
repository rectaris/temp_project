# Add OpenCode Go as the first non-Codex writable WorkerBackend

status: deferred
completion_deferred_reason: Plans 404, 405 and 407 must be checked first, and the Issue #15 read-only comparison must support a writable OpenCode backend.
implementation_mode: parent_direct
primary_invariant: Only the runner-resolved OpenCodeGoBackend writable profile reaches the credential relay, and the OpenCode process edits only the admitted writable shadows with no shell, network or credential access.
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
  - sha256:68efe554460079f7e5645eb24e5697d41905580d3d4cfc7a1a2a7b71bf15673c
  - sha256:8ded8e74d9aa6291e5f488ffb4529ab04a1e0e49f624c89b0af5fcac8721d6a0
integration_source_ids:
  - 395
predecessor_plans:
  - docs/plan/active/404-run-read-only-capabilities-through-opencode-go-backend.md
  - docs/plan/active/405-seed-disabled-opencode-go-backend-configuration.md
  - docs/plan/active/407-bind-worker-backend-dispatch-provenance.md
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
  - {"kind":"bounded_prototype","evidence":"OpenCode 2.0.15 in bwrap with --unshare-net, run --standalone --format json, OPENCODE_DISABLE_PROJECT_CONFIG=1, OPENCODE_DISABLE_MODELS_FETCH=1 and permission * deny plus read, edit, write, glob and grep offered the provider exactly edit, glob, grep, read and write; shell, execute, webfetch, subagent and skill were absent."}
  - {"kind":"bounded_prototype","evidence":"In that sandbox, edit rewrote a single-file writable bind mount in place with the inode unchanged, and a write into a read-only directory produced a tool_use error event while the process exited 0, so success must be judged from events, not the exit status."}
  - {"kind":"bounded_prototype","evidence":"The same CLI retried HTTP 429 and 500 without limit and ignored provider maxRetries, ending only at the external timeout, and it launched a persistent serve daemon unless --standalone was given; a hostile project opencode.json or plugin executed code unless project config was disabled."}
  - {"kind":"existing_mechanism","evidence":"Checked plan 359 ships opencode_go_transport.py: the parent relay holds the credential and serves a Unix socket that a sandbox mounts, and its tests bind that socket into bwrap."}
completion_conditions:
  - Selecting the opencode-go backend for plan_implementation through the WorkerBackend boundary makes the runner resolve its own shipped adapter, start the relay and mount only its socket; a caller-supplied --worker-binary never receives the relay, and the default Codex and custom paths are unchanged.
  - The writable profile reuses plan 404's feature probe, event parser and relay binding, starts OpenCode 2.x with --standalone, JSON events, project configuration and model fetch disabled, a fresh HOME and XDG tree, the exact configured model and only read, edit, write, glob and grep tools, and refuses a runtime lacking any of these.
  - A successful candidate from the exact source HEAD edits only the existing writable shadows and the new-file root; a tool_use error, error event, 429, 500, timeout, model drift, missing final answer or out-of-scope write fails the attempt with no automatic retry or fallback.
  - Neither the OpenCode process nor parent-owned validation can read the real API key, and validation stays credential-free and network-isolated.
  - Each attempt carries plan 407's dispatch record naming the opencode-go backend, and the worker contract, completion receipt, candidate manifest, correction lineage and review and correction budgets keep their Codex-path semantics.
  - New root and template files are registered in the source inventory and byte-aligned under the documented mapping.
completion_witness_map:
  - {"condition_sha256":"sha256:0bbfdc231f277fa6d84574cf3ec58fa508c474b54f52ec97aeefbaa4f8de7aa4","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:f071c5020b81c3e83c58c52144aa0a4c8ae08d84643bdc09d54e2c7e765db7a2","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:484aede0179e7dc8406b50a9fc989f57c2444bb08c3e25806d585590abce53b2","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:359cf1deaf63d89df9559345ee9c7457734b2aff426a1bb65bc1549c9aa66a4d","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:4ef8e80bde215cb0cd9bc063997330493747154c8dd34da17d68154a80cd05c7","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:3cac3763b5b63126a79c0cd83e86d0e442afaffd71c9dd9290251d4b1f977bdf","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/opencode-plan-worker.py
  - template/.project-agent-workflow/scripts/opencode-plan-worker.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - scripts/project_workflow/worker_backends.py
  - template/.project-agent-workflow/scripts/worker_backends.py
  - scripts/project_workflow/opencode_go_backend.py
  - template/.project-agent-workflow/scripts/opencode_go_backend.py
  - docs/agent/capability-registry.json
  - template/.project-agent-workflow/docs/agent/capability-registry.json
  - tests/opencode_go_candidates.py
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
  - The Go adapter consumes the runner contract and correction brief, reads required specifications directly, writes only bounded advisory claims, and returns an in-scope candidate without committing or changing lifecycle state.
  - The Go process and any repository code it runs cannot receive the real API key or escape the existing filesystem/network boundary; parent-owned validation remains credential-free and network-isolated.
  - Explicit Go routing remains subject to risk/ambiguity eligibility, attempt and review budgets, stopped-ledger gates and unchanged acceptance witnesses; no custom-worker error triggers the Codex fallback or replenishes an execution budget.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:d930bc55fa2da26dfb2e6a2bd4f2a0b00d7079bf28176e0828141c143967b5bd","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:68efe554460079f7e5645eb24e5697d41905580d3d4cfc7a1a2a7b71bf15673c","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:8ded8e74d9aa6291e5f488ffb4529ab04a1e0e49f624c89b0af5fcac8721d6a0","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
integration_gates:
  - docs/plan/checked/2026/09/01-15/359-isolate-opencode-go-inference-credentials.md
  - An Issue #15 comparison of Codex and OpenCode Go read-only behavior must be recorded before this plan starts, covering finding acceptance and quality, frontier-model token use where directly observed, helper calls, elapsed time, retries and errors, and human intervention, and it must support enabling a writable OpenCode backend.
checked_summary_ja: 汎用の WorkerBackend 境界に、Codex 以外で最初の書き込み実装として OpenCode Go を加える。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct.
- Implement the writable OpenCode Go backend behind the foundation's WorkerBackend selection, not as an OpenCode-specific runner option. The runner resolves the adapter it ships for backend id opencode-go, starts the parent credential relay before the attempt, mounts only the relay socket, and unshares the network. An arbitrary --worker-binary keeps its existing environment and never receives the relay.
- Register opencode-go in both registry copies as an optional implementation of plan_implementation only. bounded_implementation keeps its native Codex profiles because it has no sandboxed candidate path, and adding one is outside this plan.
- Select the backend only when plan 405's configuration enables plan_implementation and the plan is already eligible for writable delegation; either high risk or high ambiguity still refuses. Keep Sol for independent review.
- Extend opencode_go_backend.py with one writable profile. Offer OpenCode only read, edit, write, glob and grep; deny shell, execute, webfetch, websearch, subagent, skill and question explicitly, because execute exposes fetch.
- Build the adapter instruction from the worker contract, the correction brief and the named plan and specification files; honor WORKER_REPO, SCRATCH_DIR, NEW_FILE_ROOT, COMPLETION_CLAIMS and CORRECTION_BRIEF, write only the allowed claims, and never commit or change lifecycle state.
- Judge success from the JSON event stream: any tool_use error, error event or missing final answer fails the attempt even at exit 0. Enforce a bounded wall-clock timeout because provider errors retry without limit.
- Stop on authentication, network, 429, protocol, semantic or validation failure with no provider, model, backend or Codex fallback and no replenished budget.
- Use a fresh scratch tree, OpenCode state, relay socket and bridge for the single permitted correction, preserving the source HEAD, prior manifest and patch digests.
- Record dispatch provenance through plan 407's record; do not add fields to the worker receipt.

## Tasks

- [ ] Before product edits, resolve every predecessor and integration gate to its checked archive or recorded evidence, prepare the parent-direct execution ledger with the reviewer registry, continuation registry, review-route check and adversarial preflight, and record the unchanged baseline behavior this plan must keep.
- [ ] Rerun the OpenCode feature probe and the write-path prototype against the installed CLI and record the observed version and tool list in Validation Notes.
- [ ] Implement the adapter and the writable backend profile, register the backend with the WorkerBackend boundary and the registry, and add the relay start and socket mount to both runner copies.
- [ ] Add candidate cases for a successful candidate, a failed attempt with partial changes, a new allowed file, denied authority edits, exact claims, replay, one correction and a refused second correction, stopped ledgers, 429 and 500 without fallback, model drift, tool_use errors at exit 0, interruption, disabled-capability refusal and credential isolation during parent validation.
- [ ] Register the new files in the source inventory and template checker, and rerun the read-only backend cases as integration coverage.
- [ ] Obtain independent review of the exact in-scope patch and its security cases through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the unchanged authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Reconstructed on 2026-09-26 from plans 394 to 396 on the owner's instruction under Issue #14: the source plans added an OpenCode-specific runner selector and routing rule, while the owner now requires writable delegation to resolve a capability through the Capability Registry and the WorkerBackend boundary, with OpenCode Go as the first non-Codex backend.
