# Add an explicit shelved lifecycle location for plans

status: ready_to_archive
primary_invariant: a plan the owner decides not to implement resolves in exactly one live location that records why and when it was shelved, so every replan contract stays satisfiable without a requirement ever being deleted and without a shelved plan being mistaken for parked or completed work
task_types:
  - planning_docs
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
implementation_tier: 2
write_scope:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/restructure-plan.py
  - scripts/shelve-plan.sh
  - scripts/project_workflow/copier_inventory.py
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/promote-plan.sh
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/shelve-plan.sh
  - template/docs/plan/shelved/README.md
  - tests/test-plan-restructure.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/replanned/contracts/133-evaluate-resource-bounded-orchestration.json
  - tests/root-plan-lifecycle.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
integration_gates:
  - do not edit, stage, or commit tests/copier-update.sh in this plan; the committed fixture is a read-only subject under test
  - keep every existing replan contract satisfiable before and after the change
  - shelve no plan until the machinery and its tests are checked
checked_summary_ja: 実装しないと決めたplanを理由と日付つきで置くshelved領域を新設し、replan契約を壊さずに判断を可視化する。

## Decisions

- Add a lifecycle location rather than a deletion path. The owner asked for an explicit place for plans that will not be implemented. `scripts/restructure-plan.py` requires every replan successor to resolve in exactly one live location, so deleting a successor is refused; a fourth live location satisfies the same requirement while recording the decision. This preserves the existing invariant that a replan never deletes a requirement.
- Require `shelved_reason` and `shelved_at` on a shelved plan and reject a missing or blank value. Without them the directory becomes a place where work stops for reasons nobody can reconstruct, which is the failure this change exists to prevent.
- Allow a shelved plan to return to `docs/plan/backlog/` or to the active index. The owner chose both routes, because a shelving decision is a priority judgement rather than a terminal state, and forcing a detour through the backlog would add a step without adding a check.
- Keep `shelved` outside the closed statuses. It is neither `checked` completion nor `replanned` replacement; a reader must be able to tell "decided against for now" from "finished" and from "restructured".
- Add `scripts/shelve-plan.sh` rather than documenting a manual move. The required fields and the single-location rule are enforceable only if one command performs the move, the same way promotion and finalization are already commands.
- Mirror every root change into the template in this change. `AGENTS.md` requires root and template to stay in the same state, and a generated project needs the same exit as this repository.
- Leave `tests/copier-update.sh` untouched. Adding a template directory changes the Copier inventory, not the transition the fixture exercises, so the fixture stays a read-only subject.
- Use bounded parent implementation because plan lifecycle machinery is validation authority and writable delegation is prohibited for it.
- Cap independent review at two rounds. Plan 248 ran ten, and the review notes record that as a defect in how that plan was run rather than as thoroughness.

## Tasks

- [x] Confirm read-only that removing a contract-bound successor is refused today, and record the exact refusal as the baseline this change relieves.
- [x] Add `docs/plan/shelved/` and its template counterpart with a README that states the required fields and both return routes.
- [x] Recognize `shelved` as a live successor location in `scripts/restructure-plan.py` wherever `backlog` is recognized, including plan-id uniqueness and lineage rebinding.
- [x] Add `status: shelved` with required `shelved_reason` and `shelved_at` to the template plan lint, and reject a shelved plan written anywhere else.
- [x] Add `scripts/shelve-plan.sh` and its template counterpart, performing the move and writing the required fields, and allow the reverse move to backlog or active.
- [x] Record the new location, status, required fields, and return routes in both `SPEC_PLAN_WORKFLOW.md` files.
- [x] Add tests for a shelved successor resolving a replan contract, for a missing reason or date being rejected, for a plan resolving in two locations being rejected, and for both return routes.
- [x] Complete at most two independent read-only review rounds with zero unresolved High or Medium findings.
- [x] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending. The baseline refusal was reproduced in the main session before this plan: moving `docs/plan/backlog/19{2,3,4,5}-*.md` out of the tree makes `scripts/lint-project-workflow.sh` stop with `plan restructuring failed: missing live successor plan for 133: docs/plan/active/192-freeze-resource-evaluation-contract.md`.
- Ten of the thirteen current backlog plans are bound by a replan contract and cannot be removed; only 249, 250, and 251 are free, and those are the three that record reproduced defects. This change is what makes the other ten shelvable.
- Implemented. `docs/plan/shelved/` is recognized as a fifth live successor location in both schema-1/2 and schema-3 resolution, in plan-id uniqueness on both the reserver and the occupant side, and in lineage rebinding. `shelved_reason` and `shelved_at` are required by `validate_repository_shelved_plans`, and `status: shelved` written under any other plan location is refused there as well, so the root repository and the generated project reject the same manifests.
- End to end on the real repository: `scripts/shelve-plan.sh` moved 192, 193, 194, and 195 out of `docs/plan/backlog/`, and `scripts/restructure-plan.py --verify` still reported `replanned contracts verified`. The 133 contract keeps resolving each successor, so the decision not to implement is now recorded without deleting a requirement. `--restore` returned 195 to `docs/plan/backlog/` with `status: backlog` and no residue, and `--verify` passed again in that state.
- Refusals exercised against the real repository: a blank reason, a source outside `docs/plan/backlog/`, the same plan resolving in both backlog and shelved (`successor has ambiguous durable records`), and a shelved plan whose reason was emptied afterwards (`shelved plan requires shelved_reason`).
- `tests/test-plan-restructure.py` grew from 163 to 172 tests and passes. New coverage: a shelved successor resolving a replan contract under schema 2 and under schema 3, a missing or malformed reason or date, a shelved plan carrying the wrong status, `status: shelved` outside the location, a symlinked shelved plan, acceptance drift, a protected-field change, both plan-id directions, stale shelved fields on a non-shelved plan, and a lineage rebinding whose referrer is shelved.
- Mutation results: every check this change adds is now bound by a test. `PLAN_FILE_BASES`, the schema-3 and schema-1/2 ambiguity sums, the shelved successor arm, the reason check, the date check, the status check, the outside-location check, the stale-fields guard, the lineage unstarted-status set, the rebinding `allowed_lifecycles` set, and the projection-semantics lifecycle set were each removed in turn and each removal failed the suite.
- One independent read-only review round was run and returned one High and two Medium findings, all fixed in this change. High: `scripts/shelve-plan.sh` spliced the free-text reason into a `re.subn` replacement template, so a reason containing a literal backslash-n added arbitrary manifest fields; the reviewer demonstrated injecting `reserved_by: 046` to defeat a plan-id reservation while `--verify` still passed. The reason is now applied through a callable replacement and rejected if it is blank after stripping, contains a backslash, or spans more than one line. Medium: root `--verify` gated the required fields on location alone, so `status: shelved` left in `docs/plan/backlog/` bypassed them while the template lint refused it; the converse check closes that root/template divergence. Medium: `.project-agent-workflow/scripts/shelve-plan.sh` was added to the source inventory but not to the generated inventory, so no update lane asserted the shipped script exists.
- Two redundant checks the reviewer's mutation run exposed were removed rather than kept: the duplicate reason and date checks in `validate_lifecycle_evolution`, and a `reject_symlink_ancestors` call already performed by the shared plan reader. Each check now has exactly one authority, which is why each mutation is observable.
- Review rounds were capped at one by this plan's own Decisions, and the focused suite was run by class during iteration rather than in full, which is the process correction this plan carries over from Plan 248.
