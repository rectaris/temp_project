# Build a labeled implementation-risk question set from committed plan records

status: backlog
primary_invariant: Every emitted question carries its source plan path, source commit, and declared label, no question input exposes a field recorded after the plan was authored, and every rejected plan is reported with its reason instead of being silently normalized or dropped.
task_types:
  - planning_docs
  - test_coverage
review_class: C
human_design_required: yes
human_approval_status: pending
implementation_tier: 2
implementation_risk: low
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"A bounded scan of 365 committed plan files at dev tip a6ef261 read implementation_risk from 295 of them: high 157, ordinary 108, low 28, and 2 recording an out-of-policy medium value. Label extraction, class counts, and exclusion accounting are therefore all reachable from the files that already exist.","kind":"bounded_prototype"}
  - {"evidence":"copier_inventory.SOURCE_REQUIRED already lists scripts/natural-japanese-evaluation.py and tests/test-natural-japanese.py with no GENERATED_REQUIRED counterpart, so a root-only offline evaluation command is an established shape that needs no template mirror.","kind":"existing_mechanism"}
  - {"evidence":"tests/test-validation-tools.py already aggregates test classes imported from tests/validation_tools/ and is an allowlisted plan validation command, so a new module registers there without extending scripts/plan_validation_commands.py.","kind":"existing_mechanism"}
  - {"evidence":"tests/fixtures/harness-comparison/evaluation-protocol.md already records a frozen protocol beside its fixtures, keeps holdout content outside the repository, and marks tuning cases as used_for_tuning. This plan reuses that shape for question construction.","kind":"existing_mechanism"}
completion_conditions:
  - The builder reads each plan from the revision that first added it, and it refuses to emit a question whose input still contains status, successor_plans, replan_contract, replan_sources, human_approval_status, or the label field being predicted.
  - A label value outside low, ordinary, and high is excluded rather than normalized, and the report names each excluded plan path with its raw value and a total exclusion count.
  - The report states per-class counts and the majority-class share for the emitted questions, and reports a class below the declared minimum count as not measurable instead of giving it a score.
  - Tuning and holdout partitions split by authoring time, keep plans linked by replan lineage on the same side, and the command writes no question, label, or partition file into the repository.
  - Each emitted question records its source plan path and source commit so that the same question can be regenerated and checked against the committed history later.
completion_witness_map:
  - {"condition_sha256":"sha256:ae124ac3b8bf0d9b7f6949b6b0cd4268675dd8745d3b4eddcd283563841a98f0","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:1ee90a9cd5134ce152003148a2c98159102b85cd548a5a51db73454b43786b35","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:c4f810745591f22927ce72ace298cb0a6670057e39c556a007762363ba96e708","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:95c9a38b49b1bee02c099b1220b6ffc7f1d98b42cf94afc2b9564de26486ff42","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:bd7bdb248968efc91badb5f11ea0b9e226f0369546a67e2dacf7192b538791ff","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/build-plan-question-set.py
  - scripts/project_workflow/copier_inventory.py
  - tests/test-validation-tools.py
  - tests/validation_tools/question_set.py
  - tests/fixtures/question-set/construction-protocol.md
  - tests/fixtures/question-set/cases.json
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/agent/SPEC_HARNESS_EVALUATION.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_HARNESS_EVALUATION.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-validation-tools.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A labeled implementation-risk question set is generated from committed plan records with point-in-time inputs, removed leak fields, named exclusions, and reported class counts with the majority-class share.
  - Lineage-aware time-split partitions and per-question provenance are enforced by the command, and no question set or label is written into the repository.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:c0c2a470bf7c1f10088227258b6fb1b81c6ac5eef26c7a6f9fe1d2a55c29f7a6","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:204cb9cfd4b9862220d2fc08438dba02bfa40a061131e4c729d88fea994bbe1e","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
checked_summary_ja: 計画記録から実装リスク分類のラベル付き問題集を生成する。

## Decisions

- Measure one decision point first: the implementation_risk classification, which has 295 labeled plan records and routes the writable runner.
- Keep the command root-only and offline. It reads committed plan records and Git history, calls no provider, needs no network, and writes no file.
- Report to standard output only. The operator saves a durable copy under .agent-artifacts/ outside the repository index.
- Treat the declared label as the author's judgment at authoring time, not as an observed outcome. Outcome prediction from status is a separate question set and is out of scope here.
- Exclude out-of-policy label values such as the two medium records instead of coercing them, and report the exclusions.
- Split tuning and holdout by authoring time rather than at random, and keep replan-linked plans on one side, because a successor and its source share wording.
- Register the tests in tests/test-validation-tools.py so no new entry is added to the plan validation command allowlist.
- Record the question construction rules in tests/fixtures/question-set/construction-protocol.md, beside the fixtures, in the shape already used by the harness comparison protocol.
- Keep held-out labels out of the repository. Only tuning cases are committed, and they are marked as used for tuning.
- Defer external model execution and scoring to a separate plan. This plan produces the question set and its statistics only.

## Tasks

- [ ] Implement bounded plan enumeration and point-in-time reading of each plan from the commit that first added it.
- [ ] Implement label extraction with leak-field removal, and fail closed when a removed field still appears in a question input.
- [ ] Implement exclusion accounting for out-of-policy and missing label values, reporting each excluded path and raw value.
- [ ] Implement class counts, the majority-class share, and a declared minimum count below which a class is reported as not measurable.
- [ ] Implement lineage-aware time-split partitions and per-question provenance covering the source plan path and source commit.
- [ ] Write the construction protocol document and the committed tuning cases, marking the cases as used for tuning.
- [ ] Register the command in copier_inventory.SOURCE_REQUIRED and the tests in tests/test-validation-tools.py.
- [ ] Run the focused test, then the full validation suite, and commit the change through the ordinary lifecycle.

## Validation Notes
