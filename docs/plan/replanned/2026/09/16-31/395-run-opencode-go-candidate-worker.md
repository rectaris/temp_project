# Run an OpenCode Go candidate worker behind a runner-owned backend selector

status: replanned
implementation_mode: parent_direct
predecessor_plans:
  - docs/plan/active/394-bind-custom-worker-dispatch-provenance.md
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
  - {"evidence":"OpenCode 2.0.15 in bwrap with --unshare-net, run --standalone --format json, OPENCODE_DISABLE_PROJECT_CONFIG=1, OPENCODE_DISABLE_MODELS_FETCH=1 and permission * deny plus read, edit, write, glob and grep offered the provider exactly edit, glob, grep, read and write; shell, execute, webfetch, subagent and skill were absent.","kind":"bounded_prototype"}
  - {"evidence":"In that sandbox, edit rewrote a single-file writable bind mount in place with the inode unchanged, and a write into a read-only directory produced a tool_use error event while the process exited 0, so success must be judged from events, not the exit status.","kind":"bounded_prototype"}
  - {"evidence":"The same CLI retried HTTP 429 and 500 without limit and ignored provider maxRetries, ending only at the external timeout, and it launched a persistent serve daemon unless --standalone was given; a hostile project opencode.json or plugin executed code unless project config was disabled.","kind":"bounded_prototype"}
  - {"evidence":"Checked plan 359 ships opencode_go_transport.py: the parent relay holds the credential and serves a Unix socket that a sandbox mounts, and its tests bind that socket into bwrap.","kind":"existing_mechanism"}
completion_conditions:
  - The runner option --worker-backend opencode-go makes the runner resolve its own shipped adapter, start the relay and mount only its socket; a caller-supplied --worker-binary never receives the relay, and the default Codex and legacy custom paths are unchanged.
  - The adapter starts OpenCode 2.x with --standalone, JSON events, project configuration and model fetch disabled, a fresh HOME and XDG tree, the exact configured model and a tool set of read, edit, write, glob and grep only, and refuses a runtime whose feature probe lacks any of these.
  - A successful candidate from the exact source HEAD edits only the existing writable shadows and the new-file root; a tool_use error, error event, 429, 500, timeout, model drift, missing final answer or out-of-scope write fails the attempt with no automatic retry or fallback.
  - Neither the OpenCode process nor parent-owned validation can read the real API key, and validation stays credential-free and network-isolated.
  - New root and template files are registered in the source inventory and byte-aligned under the documented mapping.
completion_witness_map:
  - {"condition_sha256":"sha256:35414bbe4e07280050ebe66b4b3cf9baea74edba864383b7b9f0d8774b9cb9bd","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:0d636ecb9719c59c8f4b9c5c0dc2e0d5e74600f112eb135df302a725ae6e0404","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:484aede0179e7dc8406b50a9fc989f57c2444bb08c3e25806d585590abce53b2","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:359cf1deaf63d89df9559345ee9c7457734b2aff426a1bb65bc1549c9aa66a4d","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:3cac3763b5b63126a79c0cd83e86d0e442afaffd71c9dd9290251d4b1f977bdf","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/opencode-plan-worker.py
  - template/.project-agent-workflow/scripts/opencode-plan-worker.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - scripts/project_workflow/opencode_go_execution.py
  - template/.project-agent-workflow/scripts/opencode_go_execution.py
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
primary_invariant: preserve the complete coupled source acceptance baseline
replan_sources:
  - docs/plan/active/394-bind-custom-worker-dispatch-provenance.md
  - docs/plan/active/395-run-opencode-go-candidate-worker.md
  - docs/plan/active/396-integrate-opencode-go-candidate-route.md
replan_contract: docs/plan/replanned/contracts/394-target-writable-worker-backends.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/407-bind-worker-backend-dispatch-provenance.md
  - docs/plan/active/408-add-opencode-go-writable-backend.md
  - docs/plan/active/409-discover-plan-implementation-backends-through-registry.md
inherited_acceptance_digests:
  - sha256:d930bc55fa2da26dfb2e6a2bd4f2a0b00d7079bf28176e0828141c143967b5bd
  - sha256:68efe554460079f7e5645eb24e5697d41905580d3d4cfc7a1a2a7b71bf15673c
  - sha256:8ded8e74d9aa6291e5f488ffb4529ab04a1e0e49f624c89b0af5fcac8721d6a0
checked_summary_ja: ランナーが選んだ OpenCode Go アダプターだけが中継に接続し、許可された書き込み先だけを編集する実装候補を生成する。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct.
- Add a runner-owned --worker-backend opencode-go selector. The runner resolves the adapter it ships, starts the parent credential relay before the attempt, mounts only the relay socket, and unshares the network for the Go path. An arbitrary --worker-binary keeps its existing environment and never receives the relay.
- Extend the shared launcher from the read-only helper with one writable profile. Offer OpenCode only read, edit, write, glob and grep; deny shell, execute, webfetch, websearch, subagent, skill and question explicitly, because execute exposes fetch.
- Build the adapter instruction from the worker contract, the correction brief and the named plan and specification files; honor WORKER_REPO, SCRATCH_DIR, NEW_FILE_ROOT, COMPLETION_CLAIMS and CORRECTION_BRIEF, write only the allowed claims, and never commit or change lifecycle state.
- Judge success from the JSON event stream: any tool_use error, error event or missing final answer fails the attempt even at exit 0. Enforce a bounded wall-clock timeout because provider errors retry without limit.
- Permit the Go backend only for plans already eligible for writable delegation; either high risk or high ambiguity still refuses. Keep Sol for independent review, and stop on authentication, network, 429, protocol, semantic or validation failure with no provider, model or Codex fallback and no replenished budget.
- Use a fresh scratch tree, OpenCode state, relay socket and bridge for the single permitted correction, preserving the source HEAD, prior manifest and patch digests.
- Record the dispatch provenance through plan 394's record; do not add fields to the worker receipt.

## Tasks

- [ ] Before product edits, resolve every predecessor to its checked archive, prepare the parent-direct execution ledger with the reviewer registry, continuation registry, review-route check and adversarial preflight, and record the unchanged baseline behavior this plan must keep.
- [ ] Rerun the OpenCode feature probe and the write-path prototype against the installed CLI and record the observed version and tool list in Validation Notes.
- [ ] Implement the adapter and the writable launcher profile, and add the backend selector, relay start and socket mount to both runner copies.
- [ ] Add candidate cases for a successful candidate, a failed attempt with partial changes, a new allowed file, denied authority edits, exact claims, replay, one correction and a refused second correction, stopped ledgers, 429 and 500 without fallback, model drift, tool_use errors at exit 0, interruption and credential isolation during parent validation.
- [ ] Register the new files in the source inventory and template checker, and rerun the read-only helper cases as integration coverage.
- [ ] Obtain independent review of the exact in-scope patch and its security cases through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the unchanged authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Pre-activation review on 2026-09-26 reconstructed plan 357 into three successors: its write scope lacked scripts/project_workflow/copier_inventory.py, the Go-path selector and tool permission set were undecided, two completion conditions had witnesses that cannot establish them, and its OpenCode 1.18.30 evidence no longer matched the installed 2.0.15 CLI.
