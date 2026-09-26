# Bind parent-authored custom-worker dispatch provenance to every candidate attempt

status: replan_required
implementation_mode: parent_direct
primary_invariant: Every custom-worker attempt carries a parent-authored dispatch record bound to its exact attempt, and no worker claim can supply, replace or satisfy that record on any admission path.
replan_sources:
  - docs/plan/active/357-delegate-candidate-implementation-to-opencode-go.md
replan_contract: docs/plan/replanned/contracts/357-delegate-candidate-implementation-to-opencode-go.json
successor_plans:
  - docs/plan/active/394-bind-custom-worker-dispatch-provenance.md
  - docs/plan/active/395-run-opencode-go-candidate-worker.md
  - docs/plan/active/396-integrate-opencode-go-candidate-route.md
inherited_acceptance_digests:
  - sha256:72b4b9ee612345af0ad93689efed29eda6b85063c25fc7f41dd82388205ada6b
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
  - {"evidence":"run-sandboxed-plan-worker.py accepts --worker-binary on run and correct, passes it as custom_command to execute_isolated_attempt, and records null model and reasoning metadata and zero model starts for a custom attempt, so provenance is an addition at the attempt and manifest boundary.","kind":"existing_mechanism"}
  - {"evidence":"Worker receipt validators compare exact key sets and plan-execution-state.py consumes verify_candidate_manifest from the runner, so keeping the receipt schema unchanged and adding an optional manifest field keeps both consumers' shapes stable.","kind":"existing_mechanism"}
  - {"evidence":"tests/test-sandboxed-plan-worker.py already asserts that the root and template runner copies are byte-identical and drives custom workers through fake executables.","kind":"existing_mechanism"}
completion_conditions:
  - Each initial and correction custom attempt records a parent-authored dispatch record naming the backend selector, requested model, adapter digest and attempt id, bound into the candidate manifest; legacy custom attempts without a selector keep null model metadata and verify unchanged.
  - Run, correction, candidate read, preflight, validation and apply paths reject a missing, swapped, stale or inconsistent dispatch record before candidate admission, and a worker completion claim never supplies or overrides it.
  - The root and template runner copies stay byte-identical, and plan-execution-state.py accepts provenance-bearing and legacy candidate manifests with unchanged behavior.
completion_witness_map:
  - {"condition_sha256":"sha256:17ffae2caa932f5b3b4b4007797d23d73c94993b9eb5ca4f736b7ce070edd9ea","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:064bc042258eae4da07fc26001adef76ac32b85f6e60633c64d0b128567c729e","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:92ff2b8c5eefa38d7c0dda40b22e37aeb4ab7774e26afcb9f27522f86c90b1d4","witness":"python3 tests/test-plan-execution-state.py"}
write_scope:
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
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
  - Plan 356 and the plans its reconstruction creates must reach checked archives before this plan starts, because this plan reuses the read-only helper launcher, configuration and discovery surfaces they add.
replan_reason_codes:
  - scope_drift
checked_summary_ja: カスタムワーカーの試行ごとに、親が記録した起動情報を結び付けて検証する。

## Decisions

- Keep the parent orchestrator's interpretation, authorization, review selection, validation, lifecycle, commit and publication ownership. Implement parent-direct; do not delegate these runner edits to a worker.
- Keep this plan backend-neutral. It adds the dispatch record for every custom worker and names no provider; plan 395 adds the Go backend that uses it.
- Keep the worker receipt schema unchanged. Add the dispatch record at the attempt and candidate-manifest boundary, authored only by the parent before the worker starts.
- Treat a manifest without a dispatch record as legacy evidence only when its attempt had no backend selector; any selector-bearing attempt without a matching record is refused.
- Leave plan-execution-state.py unchanged; its manifest consumer must keep working through the runner's verify_candidate_manifest.

## Tasks

- [ ] Before product edits, resolve every predecessor to its checked archive, prepare the parent-direct execution ledger with the reviewer registry, continuation registry, review-route check and adversarial preflight, and record the unchanged baseline behavior this plan must keep.
- [ ] Define the dispatch record and bind it to the attempt id, candidate manifest and correction lineage in both runner copies.
- [ ] Verify the record on the run, correction, candidate read, preflight, validation and apply paths, and refuse missing, swapped, stale or inconsistent records.
- [ ] Add fake-worker cases for accepted, legacy, forged, replayed and swapped records, a failed attempt with partial changes, one correction and a refused second correction, and rerun the execution-state suite.
- [ ] Obtain independent review of the exact in-scope patch and its security cases through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the unchanged authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Pre-activation review on 2026-09-26 reconstructed plan 357 into three successors: its write scope lacked scripts/project_workflow/copier_inventory.py, the Go-path selector and tool permission set were undecided, two completion conditions had witnesses that cannot establish them, and its OpenCode 1.18.30 evidence no longer matched the installed 2.0.15 CLI.
- Stopped at replan_required on 2026-09-26 on the owner's instruction to reconstruct plans 394 to 399 through the governed route under Issue #14: the plans add OpenCode-specific launch, routing and discovery surfaces, while the owner now requires them to target the generic Capability Registry and WorkerBackend boundary, which changes their write scopes and implementation methods.
