# Compare named run configurations by the exact dimensions that differ, keeping schema-1 comparisons unchanged

status: replan_required
primary_invariant: A schema-2 comparison attributes an effect to one dimension only when exactly that declared dimension differs between a pair, reports identical configurations as replication with the recommendation withheld, and every schema-1 protocol and observation is judged exactly as before.
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
  - {"evidence":"compare-harness-runs.py accepts only schema_version 1 with three fixed slots and two fixed comparisons in COMPARISONS, and require_controlled_axes rejects every other declared difference, so an identical-configuration pair or a backend change cannot be expressed today and a new schema is required.","kind":"existing_mechanism"}
  - {"evidence":"parse_protocol and parse_observation dispatch on schema_version and require exact key sets, so a schema-2 parser can be added beside the schema-1 path without changing how schema-1 records are read.","kind":"existing_mechanism"}
  - {"evidence":"The tool validates configuration_digest only as a digest string and never recomputes it; tests use sha(\"configuration:slot\"). A schema-2 digest computed over the declared dimensions closes that gap without affecting schema 1.","kind":"existing_mechanism"}
  - {"evidence":"tests/test-harness-comparison.py builds protocols and observations programmatically, runs the real command, and its build_suite lists every test class, and check-copier-template.py enforces root and template SPEC_HARNESS_EVALUATION.md alignment after path normalization.","kind":"existing_mechanism"}
completion_conditions:
  - A schema-2 protocol declares a repository baseline per case and two to eight named configurations, each with harness (backend and runtime), declared model, reasoning settings, instructions (asset digests with the Harness Profile selection digest), capability registry digest, context policy, tool policy, subagent topology and environment digest, plus explicit comparison pairs.
  - Every schema-2 configuration_digest is recomputed as the canonical digest of its declared dimensions, and a digest mismatch, an unknown key, a duplicate configuration, a comparison naming an undeclared configuration, or an observation whose repository baseline differs from its own case's baseline rejects the report.
  - A pair whose only differing dimension is the model, the instructions, the harness, the context policy, the tool policy, the subagent topology, the capability registry or the environment reports that single-axis effect, with the existing instruction-loading checks for instructions; two or more differing dimensions, or differing reasoning settings, report a configuration_comparison.
  - A pair with no differing dimension reports replication, states both sides' outcome, quality and elapsed coverage with their denominators, and always withholds the recommendation with a named replication blocker.
  - Every existing schema-1 test passes unchanged, and a schema-1 protocol mixed with a schema-2 observation, or the reverse, rejects the report.
  - The generated flat copy of compare-harness-runs.py produces the same schema-2 report as the root wrapper for the same inputs.
  - Both SPEC_HARNESS_EVALUATION.md copies describe schema-2 configurations, the dimension classification and replication, stay aligned under the template checker, and keep every existing evidence, coverage and outcome rule.
completion_witness_map:
  - {"condition_sha256":"sha256:24502bdabe08fccc2749121c5da32fa8b44d49d85ff9c34b1a5cf312e1ec4a46","witness":"python3 tests/test-harness-comparison.py"}
  - {"condition_sha256":"sha256:e2143215ed2be9ba0aed0e42e0f88412e774694817838a953d1fc80ae5865372","witness":"python3 tests/test-harness-comparison.py"}
  - {"condition_sha256":"sha256:a95b794c06735c1bd5552fecf48c02212bdbc1e54d9c32597ca595a69ce3f3ff","witness":"python3 tests/test-harness-comparison.py"}
  - {"condition_sha256":"sha256:cafb9aa2c6f456a1f2d85370702c28c09923c62e098f734ef0ac640493c03bed","witness":"python3 tests/test-harness-comparison.py"}
  - {"condition_sha256":"sha256:cbbf8526f629a45e38624331fd363b6e80303e4dc03081b1b240cb2fbb63dbe0","witness":"python3 tests/test-harness-comparison.py"}
  - {"condition_sha256":"sha256:ad9add4a9887b8121261d8e1399a972f82388a5e71565c7b60ac8eadd55efae4","witness":"python3 tests/test-harness-comparison.py --generated"}
  - {"condition_sha256":"sha256:251aeb6edc813ee82ac0cf8c04f10d5668fcf9c9a960bebf03e8da51285197aa","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - template/.project-agent-workflow/scripts/compare-harness-runs.py
  - tests/test-harness-comparison.py
  - docs/agent/SPEC_HARNESS_EVALUATION.md
  - template/.project-agent-workflow/docs/agent/SPEC_HARNESS_EVALUATION.md
  - CHANGELOG.md
  - scripts/plan_validation_commands.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - scripts/compare-harness-runs.py
  - tests/fixtures/harness-comparison/evaluation-protocol.md
  - docs/agent/SPEC_HARNESS_PROFILES.md
  - docs/plan/checked/2026/09/16-31/410-resolve-codex-runner-through-capability-registry.md
required_specs:
  - docs/agent/SPEC_HARNESS_EVALUATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-harness-comparison.py
  - python3 tests/test-harness-comparison.py --generated
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The comparison layer classifies whether evidence supports a single-axis effect or only a multi-axis configuration comparison, now including harness, context, tool, topology, routing and environment dimensions, without a second comparison engine.
  - Two identical run configurations can be compared as a replication whose report withholds every recommendation and names no new adoption outcome.
  - Existing Plan 319 schema-1 comparisons, evidence semantics and Harness Profile meaning remain unchanged and authoritative.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:f887b30541a71622b3803789811e7b871eff4501a202c9a8e47deed650ae1bd3","stage":"focused","witness":"python3 tests/test-harness-comparison.py"}
  - {"acceptance_sha256":"sha256:a79b52e451801b3b88561e957de4c21a56ee0affc114fba863fccbbd7248798b","stage":"focused","witness":"python3 tests/test-harness-comparison.py"}
  - {"acceptance_sha256":"sha256:24d60fbb31f397e30d1b9de6d509aebbe69207d3cd4e56352b8174f9cb57d09e","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - docs/plan/checked/2026/09/16-31/410-resolve-codex-runner-through-capability-registry.md
replan_reason_codes:
  - scope_drift
checked_summary_ja: 名前付きの実行構成を、違う次元の集合で分類して比べられるようにし、schema 1 の比較はそのまま保つ。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct; the writable runner refuses this write scope as validation authority.
- Extend compare-harness-runs.py; add no second comparison engine and no new adoption outcome. Protocols and observations carry schema_version 2 for the new shape, schema_version 1 keeps the three slots and two fixed comparisons unchanged, and a report mixes no versions. Require an integer schema_version.
- Name schema-2 configurations with configuration_id and group their declared dimensions under one dimensions object: harness (backend and runtime together), declared_model, reasoning_settings, instructions (instruction_asset_digests with harness_profile_selection_digest), capability_registry_digest, context_policy, tool_policy, subagent_topology and environment_configuration_digest. Backend and runtime form one dimension because a backend change always changes the runtime, and a profile selection and its asset digests form one because changing a selected revision changes both.
- Recompute configuration_digest as SHA-256 of the canonical JSON of dimensions, sorted keys and compact separators, so a declared digest can no longer disagree with its configuration.
- Declare comparisons as an ordered list of comparison_id, baseline and candidate. Classify each pair by its set of differing dimensions: none is replication, exactly one is that dimension's single-axis effect, and anything else, or differing reasoning settings, is configuration_comparison with the recommendation withheld.
- Bind repository_baseline per case in schema 2, because each fixture case builds its own repository, and check every observation against its own case's baseline; schema 1 keeps its single protocol-level baseline.
- Report replication with both sides' outcome, quality and elapsed coverage and their denominators, and withhold the recommendation with the blocker replication_comparison. It is a reproducibility check, not evidence for adopting either side.
- Replace slot with configuration_id in schema-2 observations and keep every other observation field, evidence rule, coverage rule and outcome rule of schema 1.
- Add python3 tests/test-harness-comparison.py and python3 tests/test-harness-comparison.py --generated to the root validation-command allowlist in scripts/plan_validation_commands.py, because this plan declares both as focused witnesses.
- Keep the Plan 328 term Harness Profile for optional instruction selection only; a schema-2 configuration records its selection digest and never redefines the term.

## Tasks

- [ ] Add the two comparison suite commands to the root validation-command allowlist.
- [ ] Record the unchanged schema-1 behavior of the comparison suite before product edits.
- [ ] Add the schema-2 protocol, configuration and observation parsers with digest recomputation and exact key sets.
- [ ] Add dimension classification, replication reporting and the mixed-version refusal, and route schema-1 inputs through the existing path unchanged.
- [ ] Add schema-2 test classes for every dimension, multi-axis and reasoning degradation, replication, digest mismatch, per-case baselines including a baseline swapped between cases, and mixed versions, register them in build_suite, and cover the generated copy.
- [ ] Describe schema 2 in both SPEC_HARNESS_EVALUATION.md copies and CHANGELOG.md.
- [ ] Obtain independent review through a fresh read-only reviewer, resolve findings within the existing budget, run the focused checks, then the authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Owner instruction on 2026-09-26, 「提案の方針で進める。」, accepted splitting Issue #15 Phase 1 into four plans with a root-only controller, evidence under .agent-artifacts/evaluations/<experiment-id>/, and one real-model identical-configuration check after all four are checked. The configuration identity that plan 410 deferred to Issue #15 is this plan's dimensions object.
