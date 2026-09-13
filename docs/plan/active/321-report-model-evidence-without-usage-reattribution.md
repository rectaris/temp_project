# Report verified model evidence and gaps without reattributing usage

status: in_progress
implementation_mode: parent_direct
primary_invariant: Model reporting exposes only source-bound execution facts and their coverage without treating mixed or unknown usage, unverified records or runtime settings as stronger execution evidence.
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
  - {"evidence":"The existing summary reads explicit manifests and raw evidence, verifies digests, retains metric provenance and unknowns, and renders bounded JSON/text without external effects.","kind":"existing_mechanism"}
  - {"evidence":"ResourceSummaryTest already creates portable input records and invokes root/template summary commands; extend those fixtures for the capture contract rather than introducing another comparison engine.","kind":"existing_mechanism"}
  - {"evidence":"Plan 319 already separates declared configuration from observed execution and withholds adoption when evidence is missing. Model coverage can be reported without changing its exact run-observation schema.","kind":"existing_mechanism"}
completion_conditions:
  - Explicit-input reports show requested, runtime-reported and provider-reported model/effort observations with verified-source coverage, missing values and source provenance.
  - Reports distinguish legitimate model changes across executions from incompatible statements about the same scope, preserve parent/child separation and avoid double counting duplicate evidence.
  - Unverified or absent model evidence remains explicitly unverified or not_observed; old manifests and existing aggregate usage totals retain their prior meanings and values.
  - The bounded JSON/text report exposes model evidence usable alongside Plan 319 inputs while clearly identifying that it is neither a complete run observation nor adoption, review or validation evidence.
  - Root and generated summary entrypoints produce equivalent model coverage on the same portable fixtures.
completion_witness_map:
  - {"condition_sha256":"sha256:e739bf93597f220aab79e9c3bf6196a16dcfc8ae68e0895e857a61d55fe859fa","witness":"python3 tests/test-hooks.py ResourceSummaryTest"}
  - {"condition_sha256":"sha256:ce3f09d91d76b684cfee82265e837d5d83c04c0bed370042b828d63474d0bb52","witness":"python3 tests/test-hooks.py ResourceSummaryTest"}
  - {"condition_sha256":"sha256:e764f1bb4cf536ab5912cc2897fe84cde5ecbbc3ed9dd08e3834fdfbe04fbec2","witness":"python3 tests/test-hooks.py ResourceSummaryTest"}
  - {"condition_sha256":"sha256:78bf9c9e3d50254419d4cbb0d10e78d59765f03a8df377f0f8fb323e953a81d2","witness":"python3 tests/test-hooks.py ResourceSummaryTest"}
  - {"condition_sha256":"sha256:2117f146a2610e09cb6da1015425afc52fbe5c57fb34bbae0d291d3d1e7fc8e6","witness":"python3 tests/test-hooks.py ResourceSummaryTest"}
write_scope:
  - template/.project-agent-workflow/scripts/summarize-agent-run.py
  - docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md
  - tests/hooks/resource_summary.py
  - tests/hooks/support.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/summarize-agent-run.py
  - template/.project-agent-workflow/scripts/agent_log_manifest.py
  - template/.project-agent-workflow/scripts/check-agent-log-manifest.py
  - template/.project-agent-workflow/scripts/import-codex-transcript.py
  - template/.project-agent-workflow/scripts/compare-harness-runs.py
  - tests/test-hooks.py
  - tests/test-harness-comparison.py
  - docs/plan/checked/2026/09/01-15/319-compare-harness-runs-locally.md
  - docs/plan/checked/2026/09/01-15/318-preserve-model-evidence-in-agent-logs.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_HARNESS_EVALUATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - references/validation.md
  - references/orchestration.md
focused_validation:
  - python3 tests/test-hooks.py ResourceSummaryTest
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Users can identify what model information is verified, missing, mixed or conflicting for explicitly supplied executions, without inferring absent parent links or provider execution.
  - Existing resource summaries remain compatible and no aggregate token count is assigned to a model without direct matching evidence; the report cannot manufacture a Plan 319 observation or adoption recommendation.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:0a4d3c530bddf1389030cf0202159241c09a26807775b45204fcfa7f1386fb96","stage":"focused","witness":"python3 tests/test-hooks.py ResourceSummaryTest"}
  - {"acceptance_sha256":"sha256:94f35529e9ac2cbe1b38d8734a173a3b4970389ebc1d863e5031a4da5d684805","stage":"focused","witness":"python3 tests/test-hooks.py ResourceSummaryTest"}
integration_gates:
  - docs/plan/checked/2026/09/01-15/318-preserve-model-evidence-in-agent-logs.md must be checked and published before this plan starts; resolve immutable plan id 318 in its current lifecycle location.
checked_summary_ja: モデル情報の取得状況と不一致を表示し、既存の利用量を誤ってモデル別に割り当てない。

## Decisions

- Start only after Plan 318 (docs/plan/checked/2026/09/01-15/318-preserve-model-evidence-in-agent-logs.md) is checked and its optional model observation contract is available at the published baseline. Resolve its immutable id after lifecycle moves. Consume that contract unchanged; do not fork or loosen its source semantics. These two plans share policy and fixture helpers and execute serially.
- Extend the existing summarize-agent-run.py JSON and text outputs, keeping existing totals and input limits intact. Use only explicitly supplied manifests and --evidence files; do not discover sessions, read the home directory, call a provider, mutate logs, start models or introduce a periodic collector.
- Verify model evidence by recomputing the supplied source digests and validating record references through the preceding contract before presenting a statement as source-verified. A declaration without its bytes remains unverified. Source verification establishes content consistency and recorded provenance, not the truth of a runtime claim or provider-resolved identity.
- Report requested, runtime-reported and provider-reported values separately, with source kind, observable execution identity, missing/unverified coverage and bounded record references. Use deterministic ordering and preserve units and denominators. List multiple models when distinct valid execution scopes report them; never choose the most recent model as the identity of the whole run.
- Define conflict only for incompatible statements about the same attribute, evidence class and confirmed execution scope. A requested/runtime difference is reported as such; a legitimate model change between turns or a different helper model is not a conflict. Unknown scope remains unresolved. Do not merge sessions using a shared root turn id or guess parent links from timestamps.
- Reuse verified source digest and record position to deduplicate repeated evidence references. Show overlapping transcript/hook statements as corroboration when a stable explicit execution link establishes it; otherwise retain separate source coverage and never claim the sum is a distinct execution count. Missing or malformed evidence never becomes an empty successful measurement.
- Leave resource_observations v1 totals, provenance and maxima unchanged. Model observation counts are not token counts, billed cost or distinct completed tasks. Do not distribute run-wide totals by the last model, turn counts, byte lengths or percentages. Report unavailable model-to-usage attribution explicitly; per-model token accounting is outside this plan.
- Expose a bounded machine-readable model evidence section using the preceding contract plus evidence references, so an operator can use it alongside Plan 319. Do not emit a purported complete Plan 319 observation or convert runtime context into provider-confirmed execution. Quality, billed cost, elapsed boundaries, human intervention and instruction loading retain their independent requirements. Preserve compare-harness-runs.py and check-harness-profile.py acceptance rules unchanged.
- Extend ResourceSummaryTest and portable fixture helpers for model absence, verified and unverified evidence, changed source digests, missing record references, unknown versions, mixed sessions/turns, conflicting same-scope statements, duplicate sources, legacy totals, provider snapshot absence and output bounds. Execute both the root wrapper and copied generated command on the same fixture inputs. Do not call actual models or assert performance gains from fixtures.
- Document the explicit-input operator workflow and its unknowns in root/template logging policy. Keep this report advisory and preserve existing log ownership, historical no-overwrite defaults, source retention, external-effect authority and parent validation/review ownership.

## Tasks

- [ ] Extend the existing summary parser and renderer to consume the accepted optional model evidence contract with exact evidence verification.
- [ ] Add execution-scope, missing/unverified coverage and disagreement reporting without changing usage arithmetic or Plan 319 acceptance.
- [ ] Extend existing summary fixtures and tests for negative, mixed, legacy and root/generated behavior; independently review the same-source deduplication and attribution boundaries.
- [ ] Run parent-owned focused checks, then the unchanged authoritative suite, and finish through the ordinary reviewed commit/publication lifecycle.

## Validation Notes

- Owner instruction: この方針でプランを作成せよ。 The owner accepted the preceding five design decisions and the capture-then-reporting split. This authoring task does not execute product changes or real model comparisons.
- Tier 2: this work changes the accepted logging metadata contract and security-sensitive allowlist, with multiple acceptance clauses. It preserves external-effect and validation authority. Use bounded parent implementation with the existing execution ledger and independent review because specification, hook and validation-helper paths are protected runner inputs; do not grant them to a writable delegated worker.
- Pre-admission evidence was gathered read-only. The exact local source for an existing imported session was inspected for metadata only: CLI 0.154.0 session_meta included model_provider and cli_version; turn_context included model, effort, turn_id and root_turn_id. This establishes runtime-reported context fields, not provider-resolved execution or snapshot identity. Raw sources and session identifiers are not part of this plan.
- Provider-resolved identity, exact snapshot and some execution links may be unavailable; explicit unknowns are valid outcomes, not missing implementation work. No provider call, home-directory discovery, automatic historical migration or new runtime capture backend is authorized.
