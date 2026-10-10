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
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_AGENT_LOGGING.md
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
integration_gates:
  - This existing unstarted plan stays backlog and is not admitted for execution. Do not promote or initialize execution until unnumbered design preflight fixes the independent/live implementation partition and an honest witness for every retained whole requirement. Current offline tests cannot establish genuine acquisition or full E1-E5 acceptance.
  - Public a8cb807 lacks PR1 owner-acquisition and prospective bootstrap contracts. Develop only the independent stable-controller and offline-fixture portion through an available lawful stable high-risk parent-direct admission with native independent review. PR1 adoption is a dependency for its live integration, not a blanket prerequisite for independent stable development; unavailable or refused execution/review stays stopped.
  - Do not infer real acquisition authenticity from role strings, caller JSON or synthetic fixture success. Live PR1-dependent integration waits for its exact independently accepted adopted version and an explicitly bounded follow-up scope; all E1-E5 product acceptance remains required.
  - Missing old445/446 ledgers, inconclusive original diagnoses, consumed starts and service/access refusals remain preserved. This is a new independent execution, not continuation, refund, reset, replacement evidence or authority over the ended task.
checked_summary_ja: 未確定診断と受入保留を保持した限定的な実装復帰を実装する。

## Decisions

- Keep public dev a8cb807b296c140896554dfc4b2825c4d07fd259 as the immutable product ancestry baseline and merge-base. For any later admitted execution, source_head is the exact published descendant containing its active in_progress plan and equals task HEAD. Do not import local dev's 81 commits or old publication history.
- Extend the existing state controller and its established root/template specification pair. Preserve original evidence availability, inconclusive diagnoses, cumulative consumption and every independent hold. No separate recovery ledger and no old445/446 source-reuse or lost-ledger reconstruction.
- Fix the security contract before later admission: the parent obtains actual conversation approval/provenance; only an exact separately accepted adopted consumer may use it. Bind repository, published active plan, consumer version, final target, exact scope, restoration/recheck evidence and actual retained consumption. Keep original append-only records and missing evidence; unknown or modified provenance fails closed. Candidate controls never authorize their own execution or acquisition. Exact key spelling may follow these boundaries; a changed owner, consumer or security boundary requires design preflight first.
- Do not include absent PR1 owner_delegation.py, delegation-policy.json, fixed runtime or local plan448 as scope or required context. PR1-dependent live integration and genuine acquisition require the exact separately reviewed adopted version and a separately bounded scope; no copying candidate code into this unit.
- All five E1-E5 acceptance items remain binding. Do not mark product acceptance, shipment, adoption or operational use from offline fixture results. Mandatory validation and exact-target independent quality review remain required.
- Initial local-authoring restrictions are preparation history, not a permanent execution prohibition. Current owner authorization permits the formal activation/publication transition, one fresh native review-route check and independent implementation after the adopted gates pass. Preserve PR1's 37-file candidate and existing evidence; no main/dev merge, PR1 adoption, live integration, refused namespace retry or review25 retry.

## Tasks

- [x] Complete local preparation and parent review, then publish the exact plan-only commit6d9cc8674f7e7296f49cc618b43db172faadfc49. This active lifecycle update also remains provisional until formal publication.
- [ ] Before product edits, prepare the fresh stable high-risk parent-direct execution and record its genuine native review-route check. Use the available fresh native entry and adopted hook/importer; do not retry rejected service/namespace routes, incrementally bootstrap candidate policy, reopen stopped runs or replenish historical budgets.
- [ ] Bind the published active plan, lawful current source, exact acquisition and actual retained cumulative usage. Missing historical records stay unknown; this plan never creates their replacement genesis.
- [ ] Within the five declared product paths, extend existing append-only state validation and operation predicates so implementation/ordinary validation are scoped separately from retained completion/adoption holds. Preserve old-schema read behavior and existing stopped runs.
- [ ] Add positive and negative offline fixtures for every E1-E5 predicate, including restoration/recheck prerequisites, unchanged original records, replay, all acceptance holds, recurrence and independent service/access refusals. Mirror root/template policy and controller bytes as their existing parity checks require.
- [ ] Run focused state tests, obtain a lawful exact-target independent clearing review, and run unchanged mandatory lint/smoke in the implementation worktree's own locked environment. Original unresolved matters and PR1-dependent integration remain held even if independent offline development passes.

## Validation Notes

- Owner instruction reported verbatim: 提案の方針で開発を進めよ. Initial local preparation authorized only plan authoring and a local commit. Subsequent explicit delegation authorized plan publication and PR19, then this serial activation with plan418 deferred, a fresh native route check and independent implementation after formal start conditions. No standing continuation authorization is added.
- Issue18 read-only snapshot updated2026-10-09T17:27:20Z: section13 E1-E5 remain unperformed. Original unnumbered e1-e5-implementation-draft.md is the content source. The old numbered authoring input is advisory input only; its plan448 context and obsolete push/PR authorization are removed.
- Product ancestry baseline and merge-base are a8cb807b296c140896554dfc4b2825c4d07fd259; they are distinct from the later execution source_head containing the active plan. Local dev and main remain unchanged. Official allocation uses this bound source plus valid shared reservations. Preserve the existing447 plan and unrelated reservations. Identify this plan by repository temp_project, source issue18/e1-e5-plan-only, baseline, exact commit and file path; the same identifier in a different local-dev history does not denote this plan.
- The future declared tests are witness claims to be exercised against implementation changes, not proof from this authoring session. PR1 tree786a3e6c272d5109a629b1e35a1f5ea8acf0376a and its existing receipts are not validation for this draft or the original failure causes.
- Estimate: design20-35m, implementation45-90m, focused state suite45-60m, mandatory lint/smoke about10m, handoff10m. Native review availability/time and genuine acquisition integration are unresolved dependencies. Estimates grant no starts, elapsed-time allowance or authority.

- Activation preflight on 2026-10-10 confirmed adopted high-risk parent_direct admission, fresh native creation/read APIs, and existing tracked hook/importer entrypoints. Static availability is not successful route evidence: keep product writes closed until the execution-bound packet, zero inherited turns and observed tool call are verified from actual runtime logs. The nested CLI help socket error is not an E1-E5 model/service refusal, and that command is not retried.

- PR19 public comments are advisory plan feedback, not formal quality-review receipts. Activation commit6dd6e4605ebde19c0cecd7e95c2df375db275ced preceded this feedback hold; no product execution ledger, writable attempt or native review was started. Returning this unstarted plan to backlog is an ordinary lifecycle correction, not descope, repair classification or reconstruction of a stopped execution. Plan418 remains deferred and its requirements/history are unchanged.
- The former validation_witness_map incorrectly bound every whole E1-E5 acceptance to offline tests and is withdrawn. Original acceptance text, completion conditions and their source-order digests remain byte-identical. The retained completion_witness_map is an unfulfilled draft claim, not admission or full acceptance evidence. Do not restore active status until a corrected checked authoring input gives plan-local conditions for the independent implementation and preserves all whole requirements with honest genuine-acquisition/final-target/independent-quality witnesses in the live unit. No numbered investigation or placeholder integration successor is created.
- Static route availability may be established before activation; after an admitted plan is formally active and published, prepare-parent-direct binds the exact source HEAD and plan blob, then the fresh native packet/check must pass before product writes. The help-only socket error and public bot review are not substitutes for that genuine runtime evidence. Old review25 and refused namespace operations remain untouched.

## Independent fixture scope and observation preconditions (2026-10-10)

- The current published source is dev f254ae2036d5e08f02a8bc3165cc4656c1c1a89f, with tree b11c907b80796ed3545274de5c3afe15c0e73247. Its parents are a8cb807b296c140896554dfc4b2825c4d07fd259 and aaf348cb39c52e9b2bf95c3f312bdf1275575e67. Use f254ae2036d5e08f02a8bc3165cc4656c1c1a89f as this new task's start and merge-base; a8cb807 remains the earlier product ancestry reference. Source ref is refs/heads/issue18/plan387-independent-fixtures-20261010. A later execution source_head must still equal the exact published descendant containing its admitted active plan.
- The parent supplied actual authenticated conversation-read results: proposal Sentinel_9281c2c7898c8191b41f4d2337a1aa16 and user approval Sentinel_bed36d11693481918eed7687e7e7aa81 on 2026-10-09; proposal Sentinel_c8fedf6768308191b20e55c14a844984 and user approval Sentinel_7224b46291a88191b337f6199e72ca0c on 2026-10-10. Preserve the verbatim approvals and the parent-acquired bodies in local evidence. The received capture digest proves custody of those received bytes; it is neither a locally performed source read nor a signature. The source service returned no reply linkage or original chat identifier, so do not manufacture either. These approvals do not lift a service refusal or supply missing runtime review evidence.
- Independent development stays within the existing five exact write_scope paths. It may extend the adopted state controller's append-only validation and operation predicates and their root/template policy pair, with offline tests in the existing registered state test. It may not import any PR1 candidate owner-acquisition/bootstrap implementation, modify its 37-file candidate, create real restoration/acquisition/consumption evidence from fixtures, or adopt its own controls.
- Before that implementation can start, fix an honest checked acceptance-to-witness correspondence and formally publish an admitted active plan. A focused fixture command establishes only the predicates below. It does not establish every whole E1-E5 requirement. All five original acceptance strings, completion-condition strings and their source-order digests remain unchanged and unmet; these local predicates do not replace, partition away or waive them. No validation_witness_map is restored by this backlog update.

The independent fixtures must observe each of these concrete behaviors:

1. For both confirmed-environment and inconclusive cases, compare the retained original failure, diagnosis, evidence-availability, consumption and refusal records before and after a proposed limited implementation transition. Require equality of the preserved fields. Missing records stay missing and unknown consumption stays unknown; no replacement genesis, refunded allowance or later-success diagnosis confirmation is permitted.
2. At the fixed parent/acquired-source and adopted-consumer boundary, reject malformed, replayed, wrong-repository, wrong-plan, wrong-consumer-version, wrong-target, wrong-scope and modified-source proposals. Fixtures may supply synthetic bytes to exercise rejection predicates; a synthetic role string or digest never proves actual acquisition. Repetition never creates a second authority or a budget credit.
3. Distinguish a fixture's proposed implementation/ordinary-validation permission from completion, shipment, adoption and live acquisition authority. Require every original unresolved matter, mandatory final-target validation hold and independent quality-review hold to remain effective, including when a fixture reports a positive implementation predicate. Offline success grants no real operation or publication authority.
4. For recurrence, another anomaly, or changed assumptions/target/scope, require affected work to stop for diagnosis while unrelated stop reasons remain in force. Keep service safety refusal and access restrictions independent of implementation permission. No fixture clears review25 or a namespace refusal.

For each fixture, retain the exact input/schema, expected permitted/refused operation, actual exit/result, retained-state comparison and case identity in bounded local evidence. Run the existing focused command unchanged; do not describe its output as authenticated acquisition, original-cause confirmation, actual reviewer consumption or whole E1-E5 acceptance. Preserve old-schema reads and stopped histories.

- The adopted high-risk route is parent_direct with native read-only independent review; the writable worker refuses this risk classification. After active-plan publication, prepare-parent-direct must bind that exact plan blob and source HEAD to fresh task-specific destinations. Do not touch unrelated registries, reconstruct old445/446, reopen a stopped execution or reset consumption. Direct-task document authoring is not a product execution and does not initialize this ledger.
- Before any product write, obtain the distinct execution-genesis-bound review-route-packet as the first prompt of a genuinely fresh read-only reviewer. Record review-route-check only from an actual bound manifest proving exact packet start, zero inherited turns and at least one actual tool call. The later clearing quality review also requires the actual external transcript's final assistant verdict. Existing API summaries, caller-written JSON, static entrypoint availability, the acquisition capture and successful offline tests are not these observations.
- This fresh target is the independent stable-controller fixture implementation, not the old PR1 candidate or old review25 target. That difference alone does not prove independence from a service refusal: first establish the old refusal's bounded target and the proposed new route's permission from real retained source evidence. If that comparison or required runtime capture remains unavailable, leave product writes closed. Never retry review25 or a refused namespace through another route, changed prompt, replacement session or alternate provider.
- On 2026-10-10, source/API inspection confirmed the stable packet/check and transcript-verdict gates but did not establish usable actual packet/tool/transcript capture or the exact old refusal's full scope. No reviewer session, route probe, product execution ledger or product write was started. This plan remains backlog. The nested help-only socket error is preserved separately and was not retried.
- Authoring evidence is local under .agent-artifacts/issue18-plan387-independent-preflight-20261010 in the original temp_project checkout, alongside the parent-acquired source capture under .agent-artifacts/issue18-plan387-design-20261010. Evidence paths do not become portable approval or runtime receipts. Record missing transcript and hook sources explicitly. Subsequent implementation requires focused state tests, actual exact-target independent quality clearance and the unchanged mandatory lint/smoke suite in its own locked task environment; latest CI is required for its final published commit.
