# Admit lineage rebinding for checked predecessors

status: in_progress
primary_invariant: a lineage rebinding may restate a former active reference as the same plan id's checked archive only when that archive is unambiguous and checked, and it still changes no plan identity, no status, and no unadmitted reference
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
implementation_tier: 2
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - tests/test-plan-restructure.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/plan/checked/2026/08/16-31/241-admit-lineage-rebinding-for-divergent-successors.md
  - docs/plan/checked/2026/08/16-31/240-reconcile-pre-boundary-lifecycle-and-replanned-lineage.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - A lineage rebinding admits a replacement that restates a former active reference as the same plan id's unambiguous checked archive, and rejects a target that is missing, ambiguous, not checked, a different plan id, still resident at the active path, or otherwise unadmitted.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:5caac2048dd18c5ce85281cb78d84793f472e04816838e4a670b56fbb440c0cb","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/241-admit-lineage-rebinding-for-divergent-successors.md
successor_plans:
  - none
integration_gates:
  - do not change the activation record gate; a deferred baseline with a stopped reason stays the only route that also enters in_progress
  - do not change how a replanned source resolves to a checked successor; that replacement class stays byte-for-byte as Plan 241 checked it
  - do not activate any backlog plan in this change; reactivating a rebound successor is separate work

## Decisions

- Name the blocked referent before naming the fix. The object that cannot progress is not one plan. It is a backlog-resident or deferred replan successor whose `predecessor_plans`, `context_files`, `integration_gates`, or body still names a `docs/plan/active/` path that has since become a checked archive. `docs/plan/backlog/187-verify-plan183-successor-acceptance.md` is the first observed instance and ten backlog plans sit behind it.
- Fix a contradiction between two documented rules, not a missing feature. Successor Backlog Deferral instructs removing `completion_deferred_reason` and `replan_reason_codes`. The only operation that could rewrite an active reference to its checked archive is a `kind: activation` record, and that record requires a `deferred` baseline carrying a non-empty `completion_deferred_reason`. `backlog` cannot re-enter `deferred`, so a successor sent down the sanctioned deferral path can never resolve its lineage.
- Widen `rebind_lineage` rather than `activation`. `rebind_lineage` is already the designated operation for an unresolvable reference in an unstarted plan, already permits `predecessor_plans`, `context_files`, and `integration_gates`, already requires `status` in `deferred` or `backlog`, and already forbids a status change. Only the admitted replacement class is missing. Widening `activation` instead would let a backlog plan resolve its lineage and enter `in_progress` in one transaction, which removes the proof that a plan leaving `deferred` was genuinely stopped.
- Prove the target with the primitive the activation route already trusts. Resolve a checked replacement through `activation_checked_pairs()`, which requires the same plan id, the same file name, an existing archive whose `status` is `checked`, and an unambiguous single match. Reusing it keeps the two routes from drifting apart, and it already rejects a former active path that still holds a file.
- Keep reactivation a separate act. Rebind while the plan is still `backlog`, then reactivate through the route the specification already describes: move the file under `docs/plan/active/`, restore an active status, and re-add the active index row. `validate_lifecycle_evolution` already accepts a `backlog` baseline reaching `in_progress` with no protected-field change, so no further mechanism is needed.
- Correct the section label to match its referent. The specification section is titled `Replanned Predecessor Lineage Rebinding`, and its opening sentence defines the operation as being for a replanned source. After this change the operation admits two replacement classes, so the title names less than the operation does. Retitle it and state the two classes separately, so a later agent looking for a checked predecessor finds the rule.

## Tasks

- [ ] Admit a second replacement class in `validate_lineage_reference_transition`: an old reference that names one active plan path which `activation_checked_pairs()` resolves to the same plan id's checked archive, where the new text equals the old text under exactly that substitution.
- [ ] Keep every existing gate unchanged: the replanned replacement class, the protected plan identity comparison, the `deferred` or `backlog` status requirement, and the prohibition on changing status.
- [ ] Reject an unadmitted target: an active reference with no checked archive, an ambiguous archive, an archive that is not `checked`, a different plan id, an active path that still holds a file, and a replacement that changes any text outside the resolved substitution.
- [ ] Retitle the specification section to name both admitted replacement classes and state the checked-archive class, in `docs/agent/SPEC_PLAN_WORKFLOW.md` and its template counterpart.
- [ ] Add regression tests to `tests/test-plan-restructure.py` covering an admitted checked-archive rebinding, each rejection above, and an unchanged replanned-source rebinding.
- [ ] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Pending. The decision audit for this plan records the measured evidence that the two lifecycle rules contradict each other and the reasons the other three repair sites were rejected.
