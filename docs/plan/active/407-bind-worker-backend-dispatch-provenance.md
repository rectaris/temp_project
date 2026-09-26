# Bind parent-authored WorkerBackend dispatch provenance to every candidate attempt

status: deferred
completion_deferred_reason: The Issue #14 foundation plan must be checked first, as integration_gates records.
implementation_mode: parent_direct
primary_invariant: Every attempt the runner dispatches through a WorkerBackend carries a parent-authored dispatch record bound to its exact attempt, and no worker claim can supply, replace or satisfy that record on any admission path.
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
  - sha256:72b4b9ee612345af0ad93689efed29eda6b85063c25fc7f41dd82388205ada6b
integration_source_ids:
  - 394
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
  - {"kind":"existing_mechanism","evidence":"run-sandboxed-plan-worker.py passes --worker-binary as custom_command to execute_isolated_attempt on run and correct; a custom attempt keeps model and reasoning unset, publishes worker_result kind custom and records zero model starts, so provenance is an addition at the attempt and manifest boundary."}
  - {"kind":"existing_mechanism","evidence":"Worker receipt validators compare exact key sets and plan-execution-state.py consumes verify_candidate_manifest from the runner, so keeping the receipt schema unchanged and adding a manifest field keeps both consumers' shapes stable."}
  - {"kind":"existing_mechanism","evidence":"tests/test-sandboxed-plan-worker.py already asserts that the root and template runner copies are byte-identical and drives custom workers through fake executables."}
completion_conditions:
  - Each initial and correction attempt the runner dispatches through a WorkerBackend, including CodexBackend and the custom --worker-binary backend, records a parent-authored dispatch record naming the capability, backend id, requested model and reasoning, adapter digest and attempt id, bound into the candidate manifest.
  - Run, correction, candidate read, preflight, validation and apply paths reject a missing, swapped, stale or inconsistent dispatch record before candidate admission, and a worker completion claim never supplies or overrides it.
  - The default Codex path keeps its command, model routing, fallback, receipt and validation behavior, a manifest under the earlier manifest schema without a record verifies as legacy evidence, and the root and template runner copies stay byte-identical.
  - plan-execution-state.py accepts provenance-bearing and legacy candidate manifests with unchanged behavior.
completion_witness_map:
  - {"condition_sha256":"sha256:be3e8a5d2de2df7057a257a351bef69d7ae4000cfa975a3387a7361bb2631c30","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:064bc042258eae4da07fc26001adef76ac32b85f6e60633c64d0b128567c729e","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:1a2a477e7e678aa99d78ac121ea2769094901fa2a889baf02e935bf8d2edf73d","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:54088d9518948c0f4c6a6595a9ffae8a8eee537998b9ee29563f1152a4935941","witness":"python3 tests/test-plan-execution-state.py"}
write_scope:
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - scripts/project_workflow/worker_backends.py
  - template/.project-agent-workflow/scripts/worker_backends.py
  - tests/test-sandboxed-plan-worker.py
  - tests/test-plan-execution-state.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - scripts/plan-execution-state.py
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
  - python3 tests/test-plan-execution-state.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A verified initial attempt and one fresh correction preserve source baseline and prior-patch lineage; unknown completion claims, error events, model drift, replay and out-of-scope writes never become accepted candidates.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:72b4b9ee612345af0ad93689efed29eda6b85063c25fc7f41dd82388205ada6b","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
integration_gates:
  - The Issue #14 foundation plan must reach a checked archive before this plan starts. It adds the managed Capability Registry in docs/agent/capability-registry.json and its template copy, and the WorkerBackend boundary with CodexBackend in scripts/project_workflow/worker_backends.py and its template copy, while every capability still resolves to the unchanged Codex path.
checked_summary_ja: WorkerBackend を通じた試行ごとに、親が記録した起動情報を結び付けて検証する。

## Decisions

- Keep the parent orchestrator's interpretation, authorization, review selection, validation, lifecycle, commit and publication ownership. Implement parent-direct; do not delegate these runner edits to a worker.
- Make this record the provenance of the generic WorkerBackend boundary. It names no provider; plan 408 adds the OpenCode Go backend that uses it, and a later OMP or local backend uses it unchanged.
- Keep the worker receipt schema unchanged. Add the dispatch record at the attempt and candidate-manifest boundary, authored only by the parent before the worker starts.
- Accept a manifest without a dispatch record only under the manifest schema version that predates this plan. Every manifest this runner writes carries the record, and a current-schema manifest without a matching record is refused.
- Record the custom --worker-binary path as its own backend id with no requested model, and keep its environment, telemetry and stop-without-fallback behavior unchanged.
- Leave plan-execution-state.py unchanged; its manifest consumer must keep working through the runner's verify_candidate_manifest.

## Tasks

- [ ] Before product edits, resolve every predecessor and integration gate to its checked archive or recorded evidence, prepare the parent-direct execution ledger with the reviewer registry, continuation registry, review-route check and adversarial preflight, and record the unchanged baseline behavior this plan must keep.
- [ ] Define the dispatch record in worker_backends.py and bind it to the attempt id, candidate manifest and correction lineage in both runner copies.
- [ ] Verify the record on the run, correction, candidate read, preflight, validation and apply paths, and refuse missing, swapped, stale or inconsistent records.
- [ ] Add fake-worker cases for accepted, legacy, forged, replayed and swapped records, the unchanged default Codex path, a failed attempt with partial changes, one correction and a refused second correction, and rerun the execution-state suite.
- [ ] Obtain independent review of the exact in-scope patch and its security cases through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the unchanged authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Reconstructed on 2026-09-26 from plans 394 to 396 on the owner's instruction under Issue #14: the source plans added an OpenCode-specific runner selector and routing rule, while the owner now requires writable delegation to resolve a capability through the Capability Registry and the WorkerBackend boundary, with OpenCode Go as the first non-Codex backend.
