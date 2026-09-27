# Verify each evaluation candidate in a fresh sandbox, emit schema-2 run observations and compare them with the existing command

status: backlog
primary_invariant: An evaluation run's acceptance comes only from deterministic validation of its candidate patch applied to the frozen baseline in a fresh network-less, credential-free sandbox, and every run, including failures, becomes one schema-2 observation that the existing comparison command judges.
task_types:
  - harness_evaluation
  - security
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"execute_validation_operation in run-sandboxed-plan-worker.py clones the head, applies only the verified patch after git apply --check, and runs Bubblewrap with a writable clone, network_enabled=False and no Codex home, which is the verifier shape this plan reuses for fixture baselines.","kind":"existing_mechanism"}
  - {"evidence":"run_bounded_subprocess bounds wall time and output with a process-group kill and returns timed_out and output_truncated, so validation commands can run under the case timeout without an unbounded wait.","kind":"existing_mechanism"}
  - {"evidence":"compare-harness-runs.py takes --protocol, repeated --observation and --evidence files and verifies declared evidence digests against supplied bytes, so compare can pass every record and artifact without reimplementing comparison.","kind":"existing_mechanism"}
  - {"evidence":"The quality judgment shape binds kind deterministic_test, an identity, a source evidence digest, reviewer provenance and the case acceptance and rubric digests, and agent_self_report never supports a recommendation, which fits a verifier-owned judgment.","kind":"existing_mechanism"}
completion_conditions:
  - verify builds a fresh fixture repository at the frozen baseline for each run, applies only that run's candidate.patch after git apply --check, and runs the case validation commands under Bubblewrap with no network, no credential, fresh HOME, TMPDIR and XDG directories and the case timeout, reusing nothing from the evaluated run.
  - A candidate patch that touches a protected path or a path outside the case's allowed write paths records critical_violation true and a failing acceptance result without executing candidate code, and a patch that does not apply records a failing acceptance result.
  - Acceptance passes only when every validation command exits 0 within its bound; the judgment is deterministic_test by agent-eval-verifier, binds the validation record digest and the case acceptance and rubric digests, and never reads the evaluated agent's messages or completion claims.
  - verify emits one schema-2 observation per run, including failed, timed-out and model-unavailable runs, repeating every frozen digest and binding evidence digests for the events, patch, execution and validation records, with unobserved values not_observed.
  - The development replication experiment runs from resolve through run, verify and compare with a fake Codex for two identical configurations and two repetitions, and the report classifies the pair as replication with full coverage and the recommendation withheld.
  - compare passes the resolved protocol, every observation and every evidence file to the existing compare-harness-runs.py and prints its report unchanged; it adds no scoring, adoption or aggregate outcome of its own.
  - agent_eval_verification.py is registered in SOURCE_REQUIRED, and evals/README.md documents verify, compare and the operator steps for the later real-model replication run.
completion_witness_map:
  - {"condition_sha256":"sha256:9741c155dc8abc8fca266ac8f165b4c841d80cb956139b18857d5e585fafb56d","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:f4848f2e040c77b48aec0934598811d12e72a9e4254c7e612513a9e130670666","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:fad333b7104d68deefb464c43fbf2e4298d84bf42f342487e2c9caa206860813","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:9d831bbd5397a34d74d1a0664a85b7ab61bd22087b976fde73baa3c27797fc34","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:d16d717238059d19ba523c9ab1e860817e13ba1f68f43d52ee5941f93e13df71","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:addaff2cda536dbe2386c31af900f3be093355747555d5383181cc0f12487b93","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:465c2c6884a03a66610f9672555689943fe442033cd3bafa191283e2a253e70c","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/project_workflow/agent_eval_verification.py
  - tests/test-agent-eval.py
  - scripts/agent-eval.py
  - scripts/project_workflow/copier_inventory.py
  - evals/README.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - scripts/run-sandboxed-plan-worker.py
  - scripts/compare-harness-runs.py
  - docs/plan/replanned/2026/09/16-31/415-compare-named-run-configurations-by-changed-dimensions.md
  - docs/plan/active/418-execute-evaluation-runs-in-isolated-codex-sandboxes.md
required_specs:
  - docs/agent/SPEC_HARNESS_EVALUATION.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-agent-eval.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Candidate verification runs in a fresh environment independent of the evaluated agent, and the agent under test never determines its own acceptance result.
  - The controller emits run observations accepted by the existing Plan 319 comparison implementation, with resolved configuration and environment digests persisted with every observation.
  - A two-configuration experiment launched from one ExperimentDefinition reaches a comparison report without Podman or any container dependency.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:4a5839468201a4b430e641c1cd532d71ec9596049454092ca7dda301e509b190","stage":"focused","witness":"python3 tests/test-agent-eval.py"}
  - {"acceptance_sha256":"sha256:62c2d24726526e8a1756d7baeed83aba4ae12dbf2702eff60b51fe5a187cac70","stage":"focused","witness":"python3 tests/test-agent-eval.py"}
  - {"acceptance_sha256":"sha256:a4096d9bc7cda8a80d255a5257887261a388bd06cef28d0ecf89f4471e39df06","stage":"focused","witness":"python3 tests/test-agent-eval.py"}
integration_gates:
  - docs/plan/backlog/418-execute-evaluation-runs-in-isolated-codex-sandboxes.md must reach a checked archive before this plan starts, because verify consumes its run records.
checked_summary_ja: 評価の候補を新しいサンドボックスで独立に検証し、schema 2 の実行記録を出力して既存の比較コマンドで比べる。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct with the parent-owned execution ledger, because the verifier executes model-generated code.
- Reuse build_bwrap_command and run_bounded_subprocess from run-sandboxed-plan-worker.py through importlib. Mount the fresh verifier clone writable and a fresh scratch, share no network, stage no credential, and pass PATH, locale and scratch HOME, TMPDIR and XDG paths only.
- Check the patch's changed paths against the case's allowed and protected paths before applying it. A violation is a critical violation and a failing acceptance result, and its candidate code never runs.
- Own the quality judgment in the verifier: kind deterministic_test, identity agent-eval-verifier, source evidence the validation record, and reviewer provenance naming the verifier code digest. The evaluated agent's messages and claims never enter the judgment.
- Keep execution outcome and acceptance separate: outcome comes from the run record of plan 418, and quality comes from verification, so a completed run can fail acceptance and a failed run still yields an observation.
- Implement compare as a thin wrapper that invokes compare-harness-runs.py and prints its stdout; report is not added in Phase 1, because the existing report is the output.
- Write each observation next to its run as observation.json beside validation.json. Keep billed cost and human interventions not_observed, because the controller observes neither.

## Tasks

- [ ] Before product edits, prepare the parent-direct execution ledger with prepare-parent-direct, record the review-route check, and record the unchanged comparison and evaluation suite results.
- [ ] Implement verify: fresh baselines, scope checks, patch application, sandboxed validation, the verifier judgment and schema-2 observation emission.
- [ ] Implement compare over the existing command with every evidence file.
- [ ] Add cases for scope violations, non-applying patches, failing and timed-out validation, network and credential absence in the verifier, failed-run observations and the end-to-end fake-Codex replication experiment.
- [ ] Register the module and document verify, compare and the real-model replication steps in evals/README.md.
- [ ] Record a passing adversarial preflight, obtain independent review through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Owner instruction on 2026-09-26, 「提案の方針で進める。」, fixed the root-only controller and the evidence location, and deferred the real-model identical-configuration check until this plan is checked. Implement in a new conversation session from the published plan.
