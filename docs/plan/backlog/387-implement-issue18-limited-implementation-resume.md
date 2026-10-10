# Implement bounded Issue18 limited implementation resume without clearing acceptance holds

status: backlog
primary_invariant: Genuine exact-scope limited implementation authority never changes original diagnosis, evidence availability, consumption, refusal or acceptance authority.
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"At public dev a8cb807, scripts/plan-execution-state.py validates failure_diagnosis, retains inconclusive results and checks diagnosis_required before execution/completion. Extend those existing append-only records and gates; do not restore missing old ledgers.","kind":"existing_mechanism"}
  - {"evidence":"At a8cb807, tests/test-plan-execution-state.py has isolated inconclusive, replay, authority-drift and diagnosis-limit cases. Root/generated state scripts are a mechanically checked pair. These are feasible offline test seams, not E1-E5 success evidence.","kind":"existing_mechanism"}
completion_conditions:
  - E1: Separately retain confirmed environment failures and inconclusive non-reproducing failures; only genuine parent-acquired exact-target/scope authority with lawful restoration and affected-target recheck evidence permits implementation and ordinary validation.
  - E2: Preserve missing original logs, inconclusive diagnosis, original failures, stops and cumulative consumption. Later success and replay never replace missing evidence, confirm old causes, reconstruct lost ledgers, duplicate authority, refund or reset consumption.
  - E3: Distinguish implementation/ordinary validation from acceptance. Unresolved matters, missing mandatory final-target validation or missing independent quality review refuse completion, shipment and adoption; limited resume never authorizes publication or merge.
  - E4: Recurrence, another anomaly or changed assumptions, target or scope stops affected work for diagnosis; unrelated stop reasons remain in force.
  - E5: Preserve service safety refusal and access restrictions. Verify the acquired conversation approval source and exact target/scope; reject fabricated approval, modified provenance, wrong targets, candidate self-adoption and retrying a refused review through another route.
completion_witness_map:
  - {"condition_sha256":"sha256:0d7cabf5a1694a41432b61ad27875ee0c6b69fef2a86b37203c80bee57a323a2","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:2c84a36e2a222baad191de2332f4cb878a91510ec817db4737c9c521b5a41baa","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:2c30a0e1bd02f136f1741cda177f803e112048e5bdc61f37305b54b6f94ef372","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:47022777607a1553215cd75384af833bc3a754eac19a993823a82fa64e959cd2","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:edad9cbda2cc4ed9975bb1af205b31e2f7a1dd9b3f4242f7c8fb4add73b44e24","witness":"python3 tests/test-plan-execution-state.py"}
write_scope:
  - scripts/plan-execution-state.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - tests/test-plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - docs/agent/SPEC_SECURITY.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - E1: Separately retain confirmed environment failures and inconclusive non-reproducing failures; only genuine parent-acquired exact-target/scope authority with lawful restoration and affected-target recheck evidence permits implementation and ordinary validation.
  - E2: Preserve missing original logs, inconclusive diagnosis, original failures, stops and cumulative consumption. Later success and replay never replace missing evidence, confirm old causes, reconstruct lost ledgers, duplicate authority, refund or reset consumption.
  - E3: Distinguish implementation/ordinary validation from acceptance. Unresolved matters, missing mandatory final-target validation or missing independent quality review refuse completion, shipment and adoption; limited resume never authorizes publication or merge.
  - E4: Recurrence, another anomaly or changed assumptions, target or scope stops affected work for diagnosis; unrelated stop reasons remain in force.
  - E5: Preserve service safety refusal and access restrictions. Verify the acquired conversation approval source and exact target/scope; reject fabricated approval, modified provenance, wrong targets, candidate self-adoption and retrying a refused review through another route.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:0d7cabf5a1694a41432b61ad27875ee0c6b69fef2a86b37203c80bee57a323a2","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:2c84a36e2a222baad191de2332f4cb878a91510ec817db4737c9c521b5a41baa","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:2c30a0e1bd02f136f1741cda177f803e112048e5bdc61f37305b54b6f94ef372","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:47022777607a1553215cd75384af833bc3a754eac19a993823a82fa64e959cd2","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:edad9cbda2cc4ed9975bb1af205b31e2f7a1dd9b3f4242f7c8fb4add73b44e24","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
integration_gates:
  - Keep implementation unstarted until this exact plan is published and activated through the adopted stable workflow. The present authorization covers local plan authoring and a plan-only commit, not implementation or publication.
  - Public a8cb807 lacks PR1 owner-acquisition and prospective bootstrap contracts. Develop only the independent stable-controller and offline-fixture portion through an available lawful stable high-risk parent-direct admission with native independent review. PR1 adoption is a dependency for its live integration, not a blanket prerequisite for independent stable development; unavailable or refused execution/review stays stopped.
  - Do not infer real acquisition authenticity from role strings, caller JSON or synthetic fixture success. Live PR1-dependent integration waits for its exact independently accepted adopted version and an explicitly bounded follow-up scope; all E1-E5 product acceptance remains required.
  - Missing old445/446 ledgers, inconclusive original diagnoses, consumed starts and service/access refusals remain preserved. This is new local planning, not continuation, refund, reset, replacement evidence or authority over the ended task.
checked_summary_ja: 未確定診断と受入保留を保持した限定的な実装復帰を実装する。

## Decisions

- Use public dev a8cb807b296c140896554dfc4b2825c4d07fd259 as the sole implementation baseline. Do not merge, cherry-pick or otherwise import local dev's 81 additional commits or old publication history.
- Extend the existing state controller and its established root/template specification pair. Preserve original evidence availability, inconclusive diagnoses, cumulative consumption and every independent hold. No separate recovery ledger and no old445/446 source-reuse or lost-ledger reconstruction.
- Develop the independent stable-controller predicates and synthetic offline fixtures before PR1 adoption only under a lawful stable implementation admission. Candidate controls never authorize their own execution or acquisition. Keep concrete record spelling undecided until implementation preflight binds existing owners and consumers.
- Do not include absent PR1 owner_delegation.py, delegation-policy.json, fixed runtime or local plan448 as scope or required context. PR1-dependent live integration and genuine acquisition require the exact separately reviewed adopted version and a separately bounded scope; no copying candidate code into this unit.
- All five E1-E5 acceptance items remain binding. Do not mark product acceptance, shipment, adoption or operational use from offline fixture results. Mandatory validation and exact-target independent quality review remain required.
- This authoring session permits formal local plan generation and a plan-only local commit. It does not permit push, PR, merge, publication, deletion, force operation, product edit, reviewer/model start, namespace retry or review25 retry. Preserve PR1's 37-file candidate and all existing evidence.

## Tasks

- [ ] Keep this plan backlog and implementation unstarted during local preparation. After the parent checks the exact plan-only diff, use the formally authorized publication path before activation; plan bytes remain provisional until publication.
- [ ] Before activation, prove an available stable high-risk parent-direct admission and independent native review route without retrying rejected service/namespace routes, incrementally bootstrapping candidate policy, reopening any stopped run or replenishing historical budgets.
- [ ] Bind the published active plan, lawful current source, exact acquisition and actual retained cumulative usage. Missing historical records stay unknown; this plan never creates their replacement genesis.
- [ ] Within the five declared product paths, extend existing append-only state validation and operation predicates so implementation/ordinary validation are scoped separately from retained completion/adoption holds. Preserve old-schema read behavior and existing stopped runs.
- [ ] Add positive and negative offline fixtures for every E1-E5 predicate, including restoration/recheck prerequisites, unchanged original records, replay, all acceptance holds, recurrence and independent service/access refusals. Mirror root/template policy and controller bytes as their existing parity checks require.
- [ ] Run focused state tests, obtain a lawful exact-target independent clearing review, and run unchanged mandatory lint/smoke in the implementation worktree's own locked environment. Original unresolved matters and PR1-dependent integration remain held even if independent offline development passes.

## Validation Notes

- Owner instruction reported verbatim in the current delegation: 提案の方針で開発を進めよ. The current explicit task authorizes formal local plan generation and a plan-only local commit, followed by pre-publication reporting. Publication and product execution are outside this session. No standing continuation authorization is added.
- Issue18 read-only snapshot updated2026-10-09T17:27:20Z: section13 E1-E5 remain unperformed. Original unnumbered e1-e5-implementation-draft.md is the content source. The old numbered authoring input is advisory input only; its plan448 context and obsolete push/PR authorization are removed.
- Baseline/source and merge-base are a8cb807b296c140896554dfc4b2825c4d07fd259. Local dev and main remain unchanged. Official allocation uses this bound source plus valid shared reservations. Preserve the existing447 plan and unrelated reservations. Identify this plan by repository temp_project, source issue18/e1-e5-plan-only, baseline, exact commit and file path; the same identifier in a different local-dev history does not denote this plan.
- The future declared tests are witness claims to be exercised against implementation changes, not proof from this authoring session. PR1 tree786a3e6c272d5109a629b1e35a1f5ea8acf0376a and its existing receipts are not validation for this draft or the original failure causes.
- Estimate: design20-35m, implementation45-90m, focused state suite45-60m, mandatory lint/smoke about10m, handoff10m. Native review availability/time and genuine acquisition integration are unresolved dependencies. Estimates grant no starts, elapsed-time allowance or authority.
