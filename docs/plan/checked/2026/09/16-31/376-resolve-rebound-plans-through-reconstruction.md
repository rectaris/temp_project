# Resolve a lineage_rebind record whose plan was later reconstructed, through the reconstruction contract's verified source content rather than the replanned archive wrapper.

status: checked
implementation_mode: parent_direct
primary_invariant: A lineage_rebind record still names exactly one plan after that plan is reconstructed, and the content it verifies is the contract's stopped source, not the archive wrapper.
task_types:
  - validation_tools
  - planning_docs
review_class: A
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Measured at dev bcb646a through the committed test fixtures: after docs/plan/backlog/050-stranded.md is archived to docs/plan/replanned/2020/01/01-15/050-stranded.md, locate_stranded_plan('docs/plan/backlog/050-stranded.md') returns None and register_stranded_reference_plans records no entry for that key.","kind":"reproduced_defect"}
  - {"evidence":"locate_stranded_plan already gathers same-name candidates from live_plan_records(), the recorded path and checked_paths_for_successor(), and already refuses when more than one candidate remains. The reconstruction case is the one location it does not consult.","kind":"existing_mechanism"}
  - {"evidence":"The reconstruction contract already carries verified original_content and stopped_content for its source plan. That is the canonical stopped plan, unlike the replanned archive, whose status is replanned and which carries no replan_reason_codes.","kind":"existing_mechanism"}
  - {"evidence":"verify_rebind_records already resolves every record against the live successors that register_stranded_reference_plans builds, so a record that registers no entry is refused as an unknown live successor.","kind":"existing_mechanism"}
completion_conditions:
  - A rebind record whose plan was reconstructed resolves to exactly one location, found through the reconstruction contract that owns that plan as its source.
  - The registered entry verifies the contract's stopped source content, so an archive wrapper that differs from it cannot satisfy the record.
  - A record that matches more than one location is still refused, and a record that matches none is still refused as an unknown live successor.
  - The forty rebind records the repository already holds keep verifying without editing any of them.
  - The template copy of the restructure module stays byte-identical to the root copy and the two specification copies stay aligned.
  - The authoritative suite passes with the changed resolution in place.
completion_witness_map:
  - {"condition_sha256":"sha256:1e1f0644b09b407282dc9ecc2479fa50c6e8e0a3184c9663636be3252a4a13fb","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:c52963acc6319c9f37b6af88b13991e96099c8e7ab8597d0be5b47d7c2fd81ee","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:0c226461b510a5ac534501b1c46d4dd65d1983cb457aec1b543d7a77b12a1dd7","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:94671258bb6f208e8d5a2baab89ff0affce65d8c026279e306348acebb4874ac","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:f6618e4974a56458eb856f2042bfd7f8b89e371706a5dbcfb33820313bbc9ea9","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:144dbc4f4d5ba4e8dd8ae175a0aa9a3d0bb96a6a9ab81ef2a933dcd4e5265df7","witness":"tests/smoke.sh"}
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/plan/checked/2026/09/01-15/360-resolve-multigeneration-lineage-rebinding.md
  - docs/plan/checked/2026/08/16-31/243-admit-lineage-rebinding-for-checked-predecessors.md
  - docs/plan/checked/2026/08/16-31/240-reconcile-pre-boundary-lifecycle-and-replanned-lineage.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-copier-template.py
  - tests/smoke.sh
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A rebind record whose plan was reconstructed resolves through the reconstruction contract to exactly one location.
  - The registered entry carries the contract's verified stopped source content, and an archive wrapper that differs from it does not satisfy the record.
  - Resolution to more than one location is refused, and a record matching no location is refused as an unknown live successor.
  - Every rebind record the repository already holds verifies unchanged.
  - The root and template copies stay aligned.
  - The authoritative suite passes.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:3238f7d48f30f6e0df9e95a14811509a6d01ad503da69a65e5a0298affdc41ba","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:ba60c450dee2429f45b8aa96b172248fd35f61fdc62c774f4537f9a1187dacf7","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:7830a34b4ac71794e3247aeb679ec309fca9af09f46f83c714b49081cd3e2ed2","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:f559864f66700d874af308a3da937e22432ca3b5302dba9b9d7ba1b378dc9268","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:6e6877c40696cb0307bd554ab16076229fa9cb253bf8ffe0073d990d966d2557","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:252f87d8e7c97ba898346eb03524eb23885ffa17b44e04e6f707710ba47ea36e","stage":"focused","witness":"tests/smoke.sh"}
checked_summary_ja: 付け替え記録を持つプランが後で再構築された場合に、再構築契約が持つ検証済みの元内容から解決できるようにする。

## Decisions

- Resolve through the reconstruction contract that owns the plan as its source, not through the replanned archive. Plan 360's fourth review rejected the archive route because the archive is a wrapper whose status is replanned and which carries no replan_reason_codes, so it is not the stopped plan the record was written against.
- Verify the entry against the contract's own original_content or stopped_content, so the content the record is checked against stays the bytes the contract already verified.
- Keep the existing refusals unchanged. A record that still matches more than one location must stay refused, and a record that matches none must stay refused rather than be silently dropped.
- Do not widen locate_stranded_plan into a general search. Consult exactly the contract that names the recorded path as its source, so one more lookup cannot introduce a second candidate.
- Mirror the module byte-for-byte into the template so generated projects gain the same resolution with no second implementation.

## Tasks

- [x] Confirm the write scope and the current required specifications, and reproduce the stranded record with the committed test fixtures before changing anything.
- [x] Find the reconstruction contract that names the recorded path as its source, and resolve the plan's current location from it.
- [x] Register the entry with the contract's verified stopped source content, and keep the ambiguity and unknown-plan refusals unchanged.
- [x] Add tests for resolution, for the verified content, and for both refusals, and confirm each one fails when its production line is reverted.
- [x] Mirror the module into the template byte-for-byte and record the rule in both copies of the plan workflow specification.
- [x] Run the focused validation, then run the authoritative suite once on the final candidate.

## Validation Notes

- Plan 360 recorded this as an accepted known gap. A fix was written during its fourth review round and then withdrawn on the owner's instruction, because that attempt verified the replanned archive wrapper instead of the reconstruction contract's stopped source.
- The gap is latent rather than active. Reaching it needs a rebound plan to be promoted, stopped and reconstructed, which no plan in the repository has done yet. The forty records currently held all resolve.
- The probe used for the evidence above is not committed. It reuses the committed fixtures in tests/test-plan-restructure.py so the observation comes from the production module unchanged.
- On 2026-09-15 the owner confirmed that the previous writer had stopped and authorized pausing this plan while plans 333, 335 and 344 proceed. Its five dirty product paths remain unchanged in the existing plan-376 task worktree; this deferral neither accepts that candidate nor resumes its execution.
- On 2026-09-16 the owner requested implementation of the active and backlog plans after 333, 335 and 344 were checked and published. Resume this same plan in its existing task worktree, preserve the original candidate, and pass the current review-route gate before any further product edit. No prior execution ledger or admitted formal review exists for this plan; the earlier rejected helper response grants no acceptance evidence.
- The parent resumed the existing task binding after the prior writer had stopped, preserved the original binary patch outside the repository, and adopted published source `5bcd6aabaf99e85578989f1df4a01800aff98738` by a conflict-free fast-forward with Git autostash. Stable patch identities before and after adoption matched; all five original dirty paths were preserved.
- Execution `plan376-20260916` began with fresh epoch-zero reviewer and continuation registries. Runtime probe `plan376-route-probe-20260916` observed the execution-bound packet at turn zero and one tool call; the parent admitted the probe and passed the execution gate without claiming a formal review.
- The four added reconstruction and refusal cases passed. Five isolated mutation controls detected removal of contract-location lookup, stopped-source selection, single-source registration, ambiguity refusal and unknown-source refusal. No production file was changed by those controls.
- Fresh read-only reviewer `plan376-review1-20260916` inspected the complete five-file target and reported no High or Medium findings. Its bound manifest observed turn zero and 31 tool calls. The parent admitted this first formal review against the exact target and unchanged required specifications. The reviewer's attempted fixture execution was blocked by its read-only temporary-directory boundary; parent-owned execution supplied the behavioral evidence instead.
- Focused validation passed: `python3 tests/test-plan-restructure.py` ran 208 tests; `tests/root-plan-lifecycle.sh`, `python3 scripts/check-copier-template.py` and `tests/smoke.sh` each exited zero. All 40 existing rebind records remained unchanged and verified.
- The authoritative suite ran once on the final candidate: `scripts/lint-project-workflow.sh` and `tests/smoke.sh` each exited zero. The parent bound the final lifecycle results without adding a review or validation attempt.
- Product commit `6f43ce1fceb71902c73fa4e31240cc73d52f34c1` contains exactly the five reviewed paths. Its complete diff from the published source hashes to the admitted review target `sha256:cca6db365e11c9a7cab1329d2cc13c0d939630d73fe23b7690a4d07b4d9759f3`.
- Probe and reviewer manifests retain both runtime transcript and hook sources under their run ids. The parent execution ledger, review receipt, preserved original patch and validation outputs remain in the local Copilot session `2b6824b8-6e98-4b54-8959-26a72f107f88`; no parent transcript manifest or session checkpoint is claimed.
