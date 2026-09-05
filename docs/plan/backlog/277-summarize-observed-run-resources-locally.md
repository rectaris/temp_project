# Summarize observed run resources locally without changing acceptance evidence

status: backlog
primary_invariant: A local read-only report exposes only evidence-backed resource and execution observations, preserves missingness and provenance, and cannot mutate or substitute for execution acceptance evidence.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"template/.project-agent-workflow/scripts/agent_log_manifest.py already records resource_observations with token counts, deterministic proxy counts, missing status, and source-evidence digests."}
  - {"kind":"existing_mechanism","evidence":"run-sandboxed-plan-worker.py already records candidate generations, model starts, runner duration, correction rounds, and validation counts; execution-state records stopping events independently."}
  - {"kind":"existing_mechanism","evidence":"SPEC_AGENT_LOGGING.md requires local ignored artifacts, digest-bound observations, explicit missing sources, and no prompt, response, environment, or credential bodies in metrics."}
completion_conditions:
  - A root wrapper and one generated implementation produce an offline JSON or text summary from explicit local inputs without changing the input files, execution ledgers, manifests, model defaults, or repository product files.
  - Reports preserve source identity, evidence digests, units, provenance, and not_observed values; reject invalid digests and schemas; and never convert missing fields to zero or proxy counts to provider tokens.
  - Observed phase durations and stop events retain their real boundaries, while unavailable phase times, human interventions, replans, and billed cost remain explicitly not_observed without inference or price lookup.
  - Explicit multiple-run inputs are deduplicated by identity and source digest; only compatible units and nonoverlapping observations are aggregated, and partial coverage is shown beside every total.
  - Generated installation includes the command and its short documentation, with bounded input/output, no automatic log deletion, no model calls, and no external network or service requirements.
completion_witness_map:
  - {"condition_sha256":"sha256:0e0ddcb9bfb7e54c2e3d4e23543537f793ad02649439e241b7de9e46bd3e61c7","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:701d210b74834346d8c5d9f6b3df5a5ee98c296edd762c2bbe8c757331f398bb","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:e58a10ec18eb9b58a0fd756bb30a4116a298fa470101acbd8d3491a49bbe72f7","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:6c0df356297a524a4bf3361900bfd016fd01b61d04f2745a4fea4b8cb68e0699","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:1f5d77129bdb936d3b22dce6b0d81ec5047d60be21a5508efdce674f1d70e9cd","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/summarize-agent-run.py
  - template/.project-agent-workflow/scripts/summarize-agent-run.py
  - docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/test-hooks.py
  - tests/hooks/resource_summary.py
  - README.md
  - template/README.md.jinja
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - template/.project-agent-workflow/scripts/agent_log_manifest.py
  - template/.project-agent-workflow/scripts/check-agent-log-manifest.py
  - scripts/run-sandboxed-plan-worker.py
  - scripts/plan-execution-state.py
  - tests/hooks/logging.py
  - docs/plan/shelved/192-freeze-resource-evaluation-contract.md
  - docs/plan/shelved/193-collect-resource-evaluation-evidence.md
  - docs/plan/shelved/194-apply-resource-evaluation-outcome.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_AGENT_LOGGING.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_AGENT_LOGGING.md
focused_validation:
  - python3 tests/test-hooks.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Provide a bounded read-only local summary with evidence identity, explicit missingness and units, partial-coverage reporting, and no double counting, external service, or raw sensitive content.
  - Keep all authoritative manifests, ledger schemas, source evidence, defaults, and shelved evaluation plans unchanged while distributing the summary command through the existing template inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:c9df185c52f64e60aafb1c1183e225151b1319b88fb313ce3aa4b7d1da1b5614","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:312e05f476652129db1b31cdf8d7fa847b62ec3ff58bd00462b1afb5d072abc5","stage":"focused","witness":"python3 tests/test-hooks.py"}
integration_gates:
  - Use bounded parent implementation and independent read-only review because input records can contain sensitive execution metadata and test authority changes.
  - Implement the command once under template/.project-agent-workflow/scripts and use the existing root-wrapper pattern; add its source/generated inventory entries.
  - Read only explicitly supplied local manifest, candidate-manifest, execution-state, and evidence files; do not scan a home directory or automatically discover sessions. Hash explicitly supplied raw evidence as a bounded stream without parsing or retaining transcript bodies.
  - Accept at most 32 explicit input files, each at most 8 MiB; bound output to 256 KiB and reject symlinked, nonregular, oversized, or structurally invalid inputs before unbounded reading.
  - Do not change runner telemetry or manifest schemas, hook behavior, acceptance evidence, execution-state transitions, review receipts, or the observation importer.
  - Use existing evidence verification without executing recorded commands; absent or explicitly not_observed evidence remains not_observed, while a supplied digest mismatch, malformed digest, unsupported schema, or malformed record rejects the input with a nonzero exit.
  - An unreadable explicitly supplied evidence file is an input error, not a missing-data observation; never hide a failed integrity check by downgrading it to not_observed.
  - Provider-token fields retain observed/proxy distinctions; report directly available usage only, with monetary cost not_observed unless an already-supported input contains an explicit billed value and currency.
  - Do not infer human intervention from pauses, replan count from missing plans, phase duration from total wall time, or billed cost from public model prices.
  - Write no files by default; print the report to stdout, leaving any explicit local save to the parent under .agent-artifacts or .agent-logs.
  - Do not revive shelved plans 192, 193, or 194, add paired benchmarks, change default models, set automatic optimization thresholds, or claim a performance improvement.
checked_summary_ja: 既存の実行記録にある時間と資源使用量を、欠測値と証拠の出所を保持したローカル集計として確認できるようにする。

## Decisions

- 対象は、既存の実行記録から時間と資源使用の観測値をローカルに表示するコマンドである。
- 前回の指摘は、日常作業の費用対効果を確認するための小さな集計が不足していることである。
- 既存のログ manifest と候補 manifest に観測値があるため、受入証拠の形式は変更せず、読み取り専用の表示を追加する。
- 正式な実行記録の外に出す集計は助言用の派生情報とし、承認や完了判定の入力には使わない。
- token、時間、回数を単位別に表示し、分母と観測対象の実行を明記する。
- モデルの請求額、人の介入、再計画回数が入力から直接分からない場合は未観測のまま表示する。
- 新しい費用評価基盤、外部への送信、自動削除、自動モデル変更は追加しない。

## Tasks

- [ ] Implement schema-specific read-only adapters for existing log resource observations, candidate telemetry, and execution-state stop records using their declared versions.
- [ ] Implement bounded explicit-input handling, existing digest verification, identity deduplication, missingness, unit-safe totals, and separate observed/proxy fields.
- [ ] Add JSON and short human-readable output that shows record coverage, source digests, directly observed time/counter values, and not_observed gaps without copying raw prompts or paths to credentials.
- [ ] Add deterministic fixtures for missing evidence, changed digests, partial hooks, zero versus missing values, duplicate records, incompatible units, corrupted data, symlinks, input/output bounds, and absence of network or source writes.
- [ ] Register the root wrapper and generated command, add a focused test domain under the existing test-hooks entrypoint, and document one local-only invocation.
- [ ] Run focused validation, obtain independent review, and run authoritative validation once; record no resource-saving claim from these correctness tests.

## Validation Notes

- Planning baseline: `987ed43` in `temp_project`.
- Owner request: 「指摘事項についてそれぞれプランを作成せよ。」
- This request authorizes preparing the backlog scope; it does not activate this plan, authorize product implementation now, or continue an unrelated stopped run.
- Feasibility evidence above is source inspection, not a claim that the proposed implementation or its future tests have passed.
- At activation, resolve every dependency to its unique checked record, confirm that the current source still supports this scope, and record the baseline before implementation.
- The parent owns policy interpretation, write-scope admission, review acceptance, validation, lifecycle changes, and commits; helpers have no write authority.
- No measured resource saving is claimed; completion of this plan requires its declared correctness witnesses, not an assumed productivity gain.
