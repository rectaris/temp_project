# Preserve execution-scoped model evidence through log capture and import

status: backlog
primary_invariant: Captured model statements retain their source meaning and observable execution scope without turning requested settings, missing identities or legacy aggregate usage into observed model execution.
task_types:
  - template_workflow
  - security
  - test_coverage
review_class: C
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"A synthetic turn_context with model and effort passed through normalize_record loses both fields; metadata retains source position and session identity, providing an existing narrow extension point.","kind":"reproduced_defect"}
  - {"evidence":"An exact original local CLI 0.154.0 transcript exposed turn_context.model, effort, turn_id and root_turn_id plus session_meta.model_provider and cli_version. Provider-resolved execution was not established.","kind":"existing_mechanism"}
  - {"evidence":"Manifest helpers already bind normalized source digests; the top-level manifest accepts optional fields while resource_observations v1 has strict independent consumers.","kind":"existing_mechanism"}
  - {"evidence":"Existing logging classes and manifest self-tests exercise root/generated hooks, source evidence, legacy input and secret exclusion through the installed wrappers.","kind":"existing_mechanism"}
completion_conditions:
  - Transcript import retains allowlisted model and reasoning context with explicit source kind and observed execution identifiers; turn_context is runtime-reported context, never provider-resolved execution.
  - Missing identities and values remain unobserved; a model change or interleaved child session cannot overwrite or inherit another execution context.
  - An independently versioned optional model observation object verifies source digests and record references; legacy manifests and resource_observations v1 retain their accepted shape and meaning.
  - Root and generated hooks retain only bounded allowlisted model metadata, expose malformed or unavailable values without inventing observations, and remain best-effort with no secret or body capture.
  - Repeated import and append preserve model evidence without duplicate derived entries, protect existing source bytes and default no-overwrite behavior, and never reattribute aggregate usage.
completion_witness_map:
  - {"condition_sha256":"sha256:91d67e37a81e9228d95b5024eb34a54b57c8fb2741288cbd91753f4f16f7b3b0","witness":"python3 tests/test-hooks.py AgentLogEventTest CodexTranscriptImportTest EvidenceDigestValidationTest RootLoggingCliDelegationTest"}
  - {"condition_sha256":"sha256:a2a0cf59a319708412145066bc673af9f0651b3a45cc31808e9b637da73f9749","witness":"python3 tests/test-hooks.py AgentLogEventTest CodexTranscriptImportTest EvidenceDigestValidationTest RootLoggingCliDelegationTest"}
  - {"condition_sha256":"sha256:8eacd728f989f9b96ba243599a2c3cf3a739b09cc86a6a560b9954c9ce8d7c4f","witness":"python3 scripts/check-agent-log-manifest.py --self-test"}
  - {"condition_sha256":"sha256:dea56b512605f9e239d645c44c9f16c4edacd1c7b606321fd6c842a63059fc54","witness":"python3 tests/test-hooks.py AgentLogEventTest CodexTranscriptImportTest EvidenceDigestValidationTest RootLoggingCliDelegationTest"}
  - {"condition_sha256":"sha256:73f9be757a2b4dbcce7c52a5506ae464e8baec7ce34050343cdc62ea996a8221","witness":"python3 tests/test-hooks.py AgentLogEventTest CodexTranscriptImportTest EvidenceDigestValidationTest RootLoggingCliDelegationTest"}
write_scope:
  - template/.project-agent-workflow/scripts/import-codex-transcript.py
  - template/.project-agent-workflow/scripts/agent_log_manifest.py
  - template/.project-agent-workflow/scripts/check-agent-log-manifest.py
  - template/.project-agent-workflow/hooks/agent_log_event.py
  - .project-agent-workflow/hooks/agent_log_event.py
  - docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md
  - tests/hooks/logging.py
  - tests/hooks/support.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/import-codex-transcript.py
  - scripts/check-agent-log-manifest.py
  - scripts/agent-log-event.py
  - .codex/hooks/agent_log_event.py
  - .codex/hooks.json
  - tests/test-hooks.py
  - template/.project-agent-workflow/scripts/summarize-agent-run.py
  - scripts/plan-execution-state.py
  - docs/plan/checked/2026/09/01-15/319-compare-harness-runs-locally.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_HARNESS_EVALUATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - references/validation.md
  - references/orchestration.md
focused_validation:
  - python3 tests/test-hooks.py AgentLogEventTest CodexTranscriptImportTest EvidenceDigestValidationTest RootLoggingCliDelegationTest
  - python3 scripts/check-agent-log-manifest.py --self-test
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Users can retain and verify model statements for their observable execution scope while requested, runtime-reported, provider-reported and unavailable values stay distinct.
  - Old logs remain readable and unchanged; the new optional model evidence cannot bypass source verification or reinterpret resource_observations v1.
  - Root and generated logging paths satisfy the same bounded metadata and evidence rules without capturing secrets or adding external effects.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:54a7212adf5d67f32de930d39ba9a5f581ebbd956d8b89d7b0145cde16733991","stage":"focused","witness":"python3 tests/test-hooks.py AgentLogEventTest CodexTranscriptImportTest EvidenceDigestValidationTest RootLoggingCliDelegationTest"}
  - {"acceptance_sha256":"sha256:21675c752158335a3b65be64168ab9c5367a1ac6c99af270cd4ecdc1f5de6731","stage":"focused","witness":"python3 scripts/check-agent-log-manifest.py --self-test"}
  - {"acceptance_sha256":"sha256:b12aa3965545f13aeb72cce000972dda0001cfd1d4cdc5a741d67c6438ca4a2b","stage":"focused","witness":"python3 tests/test-hooks.py AgentLogEventTest CodexTranscriptImportTest EvidenceDigestValidationTest RootLoggingCliDelegationTest"}
checked_summary_ja: モデルと推論設定を出典付きで保存し、未観測の情報と区別する。

## Decisions

- Keep run-oriented raw/transcript.jsonl and raw/events.jsonl. Retain detailed model statements on their source records, not one mutable model name for a whole file. Define one shared versioned normalization contract in the existing manifest helper; use it from importer and generated hook and preserve equivalent root-hook behavior.
- Add a schema-versioned optional model_observation object to normalized transcript metadata and hook payload metadata, and a separately versioned optional model_observations summary to the manifest. The summary holds bounded coverage and evidence references; detailed execution contexts remain in JSONL. Do not add keys to or change version 1 resource_observations, its counter interpretation or the execution ledger schema. A missing new object is valid legacy input.
- Separate requested settings, runtime-reported settings and provider-reported execution fields. Store model and reasoning effort independently with observed/not_observed status and source kind. Retain provider name as context, not proof that a provider executed a model. Preserve exact model identifiers; never infer an alias snapshot, a default model, or one agent model from a role/profile name.
- Initially support the observed transcript turn_context.model and turn_context.effort fields, session_meta.model_provider and cli_version, and bounded hook model/effort values when supplied. Their classification is runtime-reported metadata unless an explicitly documented source field has stronger semantics. Keep requested and provider-reported slots unobserved when a supported source does not supply them. Unknown event shapes remain unobserved; do not scan arbitrary nested dictionaries or message bodies for model-looking strings.
- Preserve available session, turn, response and worker-attempt identifiers and explicit parent links with their source. Use hashed session identities in manifest summaries. Retain turn_id and root_turn_id as distinct identifiers; neither a root turn id nor a source-line fallback establishes a parent session or an actual turn. Do not propagate the last model by timestamp across missing boundaries, independent sessions, tool results or helper executions.
- Bind each derived statement to the exact normalized source digest and record position, retaining source_line where supplied. Hash complete accepted source bytes; do not use current config, paths, display text, an agent self-report or a caller assertion as execution evidence. Recompute summaries from source records on accepted updates so append or repeat import cannot leave stale digests or duplicate entries. Keep conflicting same-scope statements available rather than choosing a winner.
- Use explicit field allowlists and bounded types, strings, identity counts and summary size. Persist no raw request/response bodies, instructions, environment values, credentials or external transcript paths in the new metadata. Omitted, malformed and unsupported evidence must be distinguishable through bounded diagnostic codes; hooks still return best-effort success and do not block execution, while explicit validators reject malformed records.
- Preserve the current no-overwrite import default and existing source files. Do not automatically reimport or migrate old logs. An explicitly requested historical import can retain supported facts under the ordinary existing import contract; this plan grants no historical rewrite. Missing evidence remains missing and aggregate token totals remain exactly what resource_observations v1 previously represented.
- Initial capture coverage is runtime-reported metadata only; requested and provider-reported fields remain not_observed for the initially supported sources. Synthetic requested/runtime disagreement cases validate the schema and separation rules, not empirical capture of those additional evidence classes.
- Extend existing self-tests and logging test classes, including synthetic samples shaped after the inspected runtime records. These fixtures prove parser behavior only. Cover single model, turn change, interleaved parent/child sessions, unavailable identifiers, fallback attempts, requested/runtime disagreement, missing provider snapshot, unknown fields, invalid types, secret-like values, oversized metadata, duplicate import, source tampering and absent legacy fields. Keep source-envelope and wrapper parity checks.
- Mirror the policy and applicable root/tooling changes in the listed template counterparts. Existing root import/check wrappers and .codex hook wrappers already delegate; retain their behavior and prove it through the existing wrapper tests. Do not add another capture backend, model runner, metric schema, review authority or mandatory every-task gate.

## Tasks

- [ ] Implement and document the shared optional model observation contract and its source-classification, bounds and missing-value rules.
- [ ] Preserve supported source metadata in import and both root/generated hook paths; update derived manifest evidence without changing old resource observations.
- [ ] Extend the manifest checker and existing focused tests for positive, adversarial, legacy and root/generated cases; review evidence semantics independently.
- [ ] Run parent-owned focused checks, then the unchanged authoritative suite, and complete the ordinary reviewed commit/publication lifecycle.

## Validation Notes

- Owner instruction: この方針でプランを作成せよ。 The owner accepted the preceding five design decisions and the capture-then-reporting split. This authoring task does not execute product changes or real model comparisons.
- Tier 2: this work changes the accepted logging metadata contract and security-sensitive allowlist, with multiple acceptance clauses. It preserves external-effect and validation authority. Use bounded parent implementation with the existing execution ledger and independent review because specification, hook and validation-helper paths are protected runner inputs; do not grant them to a writable delegated worker.
- Pre-admission evidence was gathered read-only. The exact local source for an existing imported session was inspected for metadata only: CLI 0.154.0 session_meta included model_provider and cli_version; turn_context included model, effort, turn_id and root_turn_id. This establishes runtime-reported context fields, not provider-resolved execution or snapshot identity. Raw sources and session identifiers are not part of this plan.
- Provider-resolved identity, exact snapshot and some execution links may be unavailable; explicit unknowns are valid outcomes, not missing implementation work. No provider call, home-directory discovery, automatic historical migration or new runtime capture backend is authorized.
