# Declare evaluation experiments, run configurations, environments and benchmark cases, and freeze their digests and run matrix before execution

status: backlog
primary_invariant: Resolving an experiment binds the digest of every case, run configuration, instruction asset, capability registry and environment it uses and fixes the complete run matrix before any run, without launching a model, using the network or writing outside its experiment directory.
task_types:
  - harness_evaluation
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"compare-harness-runs.py reads one frozen protocol whose repository baseline, cases, repetitions, budget, metric boundaries and decision limits must be fixed before observations, so a resolver can derive that protocol from declared experiment files instead of an operator writing it by hand.","kind":"existing_mechanism"}
  - {"evidence":"Plan 354 added a root-only command with one tests module, committed synthetic fixtures and SOURCE_REQUIRED entries, and scripts/lint-project-workflow.sh runs each root test entrypoint explicitly, which this plan follows for scripts/agent-eval.py and tests/test-agent-eval.py.","kind":"existing_mechanism"}
  - {"evidence":"A Git repository created with fixed GIT_AUTHOR_DATE, GIT_COMMITTER_DATE, author and committer identity from the same files yields the same commit id on every run, so a fixture tree gives a reproducible repository baseline without depending on this repository's history.","kind":"bounded_prototype"}
  - {"evidence":"docs/agent/capability-registry.json from checked plan 410 is one bounded file, so a run configuration can bind its exact digest as the capability routing revision.","kind":"existing_mechanism"}
completion_conditions:
  - agent_eval_definitions.py parses schema-1 ExperimentDefinition, RunConfiguration, EnvironmentConfiguration and benchmark case JSON with exact key sets and bounded sizes, and refuses unknown keys, non-integer versions, duplicate ids, undeclared references, and paths that are absolute, traversing, symlinked, non-regular or outside evals/.
  - A case's fixture tree becomes a Git repository with fixed author, committer, timestamps and file modes, so the same tree always yields the same baseline commit, and a changed fixture byte changes that commit.
  - resolve writes one resolved experiment record binding the digests of every case task, acceptance text, validation command list, fixture tree, run configuration, instruction asset, the capability registry and the environment, and refuses an experiment directory that already exists.
  - resolve derives one schema-2 comparison protocol whose configuration digests equal the recomputed dimension digests and which the comparison command's own schema-2 protocol parser accepts.
  - resolve lists every case, configuration and repetition cell in declared or balanced order, where balanced alternates which configuration runs first per repetition, states the total run count, and refuses before execution a matrix above the declared budget or one whose protocol, observations and four evidence files per run exceed the comparison command's 64-file or 256-observation limits.
  - resolve launches no model, opens no network socket and writes only under .agent-artifacts/evaluations/<experiment-id>/, and the repository tree is byte-identical afterwards.
  - evals/ ships two synthetic development cases, a small deterministic fix and a cross-file change, whose deterministic validation fails at the baseline, plus a Codex run configuration, a replica with identical dimensions, the bwrap-default environment and a replication experiment that resolves.
  - scripts/agent-eval.py, agent_eval_definitions.py and tests/test-agent-eval.py are registered in SOURCE_REQUIRED, tests/test-agent-eval.py runs from scripts/lint-project-workflow.sh, and no template file changes.
completion_witness_map:
  - {"condition_sha256":"sha256:fc5ada87e6f9e041a3c1fd351ae9ebe910b8538598b76a103150dc03a8317689","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:a1d043e90808a2ae079a2d3eb4fafeb933b54bc77ecc10a5a79bc53a1b6761d8","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:f99bc574b4810b9390a4860c3e5d5da5e7178755c04e144f77b571f2411a1615","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:13d93418a55bf5c6d9916d11a3c58cc59959e80e29d5d55e2eb11dfbbc1ce9a1","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:41fba02bcb733282b444718c429839a382ffdd49dec66713bcfb88a3a1a4f1ac","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:c09879b648e02d31ef8774a06daec6da39175473baadb22d34aaddc324c24515","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:6c095f22a39e550f04d65101854cf1f974675db7f5d1c48bc79550cd0b1f10c3","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:8f20a2b7b169ad977edf022e0a05f2d1a767fc3f1fccc73a920a49a7a26864e8","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/project_workflow/agent_eval_definitions.py
  - tests/test-agent-eval.py
  - scripts/agent-eval.py
  - scripts/lint-project-workflow.sh
  - scripts/project_workflow/copier_inventory.py
  - evals/README.md
  - evals/prompts/task-frame-v1.md
  - evals/configurations/codex-current.json
  - evals/configurations/codex-current-replica.json
  - evals/environments/bwrap-default.json
  - evals/experiments/codex-replication-dev.json
  - evals/cases/coding-core-dev/small-fix/case.json
  - evals/cases/coding-core-dev/small-fix/task.md
  - evals/cases/coding-core-dev/small-fix/acceptance.md
  - evals/cases/coding-core-dev/small-fix/repository/calc.py
  - evals/cases/coding-core-dev/small-fix/repository/test_calc.py
  - evals/cases/coding-core-dev/cross-file-change/case.json
  - evals/cases/coding-core-dev/cross-file-change/task.md
  - evals/cases/coding-core-dev/cross-file-change/acceptance.md
  - evals/cases/coding-core-dev/cross-file-change/repository/limits.py
  - evals/cases/coding-core-dev/cross-file-change/repository/report.py
  - evals/cases/coding-core-dev/cross-file-change/repository/test_report.py
  - scripts/plan_validation_commands.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - scripts/compare-harness-runs.py
  - docs/agent/capability-registry.json
  - docs/agent/SPEC_HARNESS_PROFILES.md
  - docs/plan/backlog/415-compare-named-run-configurations-by-changed-dimensions.md
required_specs:
  - docs/agent/SPEC_HARNESS_EVALUATION.md
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
  - Existing Harness Profile semantics remain unchanged and are not overloaded by the new RunConfiguration, EnvironmentConfiguration or ExperimentDefinition types.
  - Resolved experiment, configuration, case and environment digests are persisted before any run starts.
  - A two-configuration experiment can be declared in one ExperimentDefinition and resolved into a frozen run matrix before execution.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b29851bdd548f7877d03875d0eeba5ad7121ec3ab176cd68764e8fbada78cd36","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:c720a5768f4990b153813d14bc88677805a9275532e581e798849c900bc0813a","stage":"focused","witness":"python3 tests/test-agent-eval.py"}
  - {"acceptance_sha256":"sha256:b6985c26a1affa7fc20dd37cc46116e2eacfcca8ec830116ea4df9808c512354","stage":"focused","witness":"python3 tests/test-agent-eval.py"}
integration_gates:
  - docs/plan/backlog/415-compare-named-run-configurations-by-changed-dimensions.md must reach a checked archive before this plan starts, because resolve derives its schema-2 protocol.
checked_summary_ja: 評価の実験、実行構成、実行環境、ベンチマークの事例を定義し、実行前に digest と実行の組み合わせを確定させる。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct.
- Ship the evaluation tooling for this repository only: scripts/agent-eval.py, scripts/project_workflow/agent_eval_*.py and evals/. Nothing is added under template/ in Phase 1.
- Write definitions as schema-1 JSON read with the standard library. Keep cases under evals/cases/<suite>/<case-id>/ with case.json, task.md, acceptance.md and a repository/ fixture tree; run configurations under evals/configurations/, environments under evals/environments/ and experiments under evals/experiments/.
- A case declares suite, category, fixture_kind, holdout, timeout_seconds, allowed write paths, protected paths and deterministic validation commands. Build its baseline from repository/ with fixed identity, timestamps and modes, so the baseline commit is reproducible and independent of this repository's history.
- A run configuration declares backend, declared CLI runtime, model, reasoning, instruction assets, Harness Profile selection or none, context policy, tool policy, subagent topology and environment id. Bind the capability registry digest at resolve time. The development configuration uses gpt-5.6-terra with medium reasoning, and its replica differs only in configuration_id.
- The bwrap-default environment declares Bubblewrap, shared network for the provider only through the evaluated process, the cold cache policy, and uncontrolled CPU and memory, stated explicitly rather than implied.
- Store resolved state under .agent-artifacts/evaluations/<experiment-id>/ as experiment.json, protocol.json and matrix.json. Refuse an existing directory; a changed definition needs a new experiment id.
- Offer declared and balanced ordering. Balanced ordering alternates which configuration runs first per repetition; randomized ordering, cgroup limits and warm caches stay in Issue #15 Phase 2.
- Add python3 tests/test-agent-eval.py to the root validation-command allowlist in scripts/plan_validation_commands.py, because this plan and plans 417 and 418 declare it as a focused witness.
- Mark the development suite used_for_tuning and synthetic, so its comparisons demonstrate tool behavior only and never support a recommendation.
- Size every experiment for one comparison invocation: one protocol, one observation per run and exactly four evidence files per run (events, candidate patch, execution record, validation record), each under the command's 8 MiB file limit. An experiment that cannot fit is refused at resolve time instead of after its runs.

## Tasks

- [ ] Add python3 tests/test-agent-eval.py to the root validation-command allowlist.
- [ ] Implement the definition parsers, path confinement and deterministic fixture baselines.
- [ ] Implement resolve with the frozen record, schema-2 protocol derivation, balanced ordering and the budget refusal.
- [ ] Add the development suite, configurations, environment, experiment and evals/README.md.
- [ ] Add tests/test-agent-eval.py cases for every refusal, baseline determinism, protocol acceptance, ordering and the no-execution boundary, register the sources, and run the entrypoint from scripts/lint-project-workflow.sh.
- [ ] Obtain independent review through a fresh read-only reviewer, resolve findings within the existing budget, run the focused checks, then the authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Owner instruction on 2026-09-26, 「提案の方針で進める。」, fixed a root-only controller and evidence under .agent-artifacts/evaluations/<experiment-id>/. A local probe on 2026-09-26 found that this workstation's ChatGPT-account Codex CLI refuses gpt-5.3-codex-spark, so the development configuration uses gpt-5.6-terra.
