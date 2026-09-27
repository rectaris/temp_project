# Evaluation definitions

This directory holds the declared inputs of repository-local harness evaluations: benchmark cases, run configurations, environment configurations and experiments.
The tooling is root-only and never ships in the Copier template.
`scripts/agent-eval.py resolve` freezes one experiment before any run; the comparison itself stays with `scripts/compare-harness-runs.py` under `docs/agent/SPEC_HARNESS_EVALUATION.md`.

## Layout

```text
evals/
  cases/<suite>/<case-id>/case.json      benchmark case definition
  cases/<suite>/<case-id>/task.md        task given to the evaluated agent
  cases/<suite>/<case-id>/acceptance.md  acceptance text
  cases/<suite>/<case-id>/repository/    fixture tree of the baseline repository
  configurations/<configuration-id>.json run configuration
  environments/<environment-id>.json     environment configuration
  experiments/<experiment-id>.json       experiment definition
  prompts/                               instruction assets named by run configurations
```

Every definition is one JSON object with `schema_version` equal to the integer `1` and exactly the keys listed below.
An unknown or missing key, a repeated JSON key, a non-integer version, an id that differs from its file or directory name, and a file over its size bound are refused.
Ids are 1 to 64 letters, digits, `.`, `_` or `-`, starting with a letter or digit.
A path is repository-relative, normalized and inside `evals/`; an absolute, traversing, symlinked or non-regular path is refused.

## Benchmark case

`case.json` declares `case_id`, `suite`, `category`, `fixture_kind` (`synthetic` or `operational`), `holdout` (`withheld`, `not_used` or `used_for_tuning`), `timeout_seconds` (1 to 7200), `allowed_write_paths`, `protected_paths` and `validation_commands`.

- Write paths are exact paths relative to the fixture repository. A path may not be both allowed and protected.
- `validation_commands` is a list of argv lists, run in the fixture repository root. Every command must exit 0 for the case to pass, and the commands must fail at the baseline. Their canonical digest is the case's `rubric_digest`.
- `task.md` and `acceptance.md` are nonempty UTF-8 text. Their byte digests are the case's `task_digest` and `acceptance_digest`.
- `repository/` holds at most 256 regular files, 1 MiB each and 8 MiB in total, and at most 512 files and directories together. Symlinks, special files and `.git` components are refused.

The baseline repository is built from `repository/` alone as a bare SHA-256 Git repository with one commit on `baseline`.
Its author, committer, timestamp, message and file mode `100644` are fixed, so the same tree always yields the same commit and one changed byte yields another.
The commit does not depend on this repository's history, the host clock, the umask or file modes.
`repository_baseline` is `sha256:<commit id>`.

## Run configuration

A run configuration declares `configuration_id`, `backend`, `runtime` (`cli_version` and `tool_versions`), `model`, `reasoning` (`supported` and `effort`, which is null when reasoning is unsupported), `instruction_assets`, `harness_profile_selection`, `context_policy`, `tool_policy`, `subagent_topology` and `environment_id`.

- `instruction_assets` lists one to sixteen files under `evals/`, each bound by its byte digest.
- `harness_profile_selection` is null or `{"path": ...}` naming either the repository's `docs/agent/harness-profile.json` or a selection document under `evals/`. `scripts/check-harness-profile.py`'s own parser checks the selection and resolves it against `docs/agent/harness-instructions.json`, exactly as its `check` command does, so an invalid, unknown or drifted selection is refused. The resolved record binds the selection and catalog digests and the selected revisions, and every selected asset joins `instruction_asset_digests`. Harness Profile meaning stays with `docs/agent/SPEC_HARNESS_PROFILES.md`.
- At resolve time the configuration becomes the schema-2 comparison `dimensions`, with the byte digest of `docs/agent/capability-registry.json` as `capability_registry_digest` and the byte digest of its environment file as `environment_configuration_digest`. Two configurations that differ only in `configuration_id` have identical dimensions and one `configuration_digest`.

## Environment configuration

An environment declares `environment_id`, `sandbox`, `network`, `cache_policy`, `cpu_limit` and `memory_limit`.
Phase 1 admits only `bubblewrap`, the network modes `none` and `shared_for_provider`, the `cold` cache policy and `uncontrolled` CPU and memory.
`shared_for_provider` means the evaluated process shares the host network so that it can reach its model provider; it grants nothing else network access.
`uncontrolled` states that no limit is applied, rather than leaving the limit implied.
Randomized ordering, cgroup limits and warm caches are not available in Phase 1.

## Experiment

An experiment declares `experiment_id`, `invariant`, `authority`, `cases` (as `<suite>/<case-id>`), `configurations` (two to eight ids), `comparisons` (`comparison_id`, `baseline` and `candidate`), `repetitions`, `ordering` (`declared` or `balanced`), `budget` (`max_total_runs` and `max_elapsed_seconds`), `human_intervention_rule` and `decision_limits`.
All cases of one experiment must share one holdout status, which becomes the protocol's `holdout_status`.

## Resolve

```sh
python3 scripts/agent-eval.py resolve evals/experiments/<experiment-id>.json
```

Resolve checks every definition, reference and bound before its first write, then writes exactly three records under `.agent-artifacts/evaluations/<experiment-id>/`:

- `protocol.json`: the schema-2 comparison protocol. Resolve refuses to finish unless the comparison command's own protocol parser accepts it. Phase 1 protocols declare no ordering evidence, so the comparison command withholds every empirical recommendation for a resolved experiment.
- `matrix.json`: every case, configuration and repetition cell in execution order, with its run id (`run-001`, `run-002`, ... by execution position), baseline and configuration digest, plus the run count and the limits it was checked against.
- `experiment.json`: the digests of the experiment, every case definition, task, acceptance text, validation command list and fixture tree, every run configuration and instruction asset, the capability registry, every environment, the comparison command, and the protocol and matrix records.

Declared ordering runs the configurations in declared order for every case of every repetition. Balanced ordering rotates that order by one per repetition, so with two configurations the one that runs first alternates.

Resolve refuses before writing anything when the run count exceeds `max_total_runs`, when the sum of case timeouts over all runs exceeds `max_elapsed_seconds`, or when one comparison invocation could not hold the experiment.
That invocation takes the protocol, one observation per run and four evidence files per run (events, candidate patch, execution record and validation record), within the comparison command's 64-file and 256-observation limits, so one experiment holds at most 12 runs.

An existing experiment directory is refused; a changed definition needs a new experiment id.
Resolve launches no model, opens no network socket and writes no Python bytecode cache. Its only subprocess is Git with no system or user configuration, working inside the experiment directory, and the repository tree is unchanged afterwards.

## Development suite

`coding-core-dev` holds two synthetic cases, `small-fix` and `cross-file-change`, both marked `used_for_tuning`.
`codex-current` declares Codex with `gpt-5.6-terra` at medium reasoning in `bwrap-default`, and `codex-current-replica` differs from it only in `configuration_id`.
`codex-replication-dev` compares the two as a replication over both cases and two repetitions in balanced order, eight runs in total.
Its comparisons demonstrate tool behavior only and never support a recommendation.
