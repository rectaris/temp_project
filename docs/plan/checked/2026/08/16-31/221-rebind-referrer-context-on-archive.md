# Rebind referrer context on archive

status: checked
checked_summary_ja: restructuring transactionがplanをarchiveする際、その旧active pathをcontext_filesに持つ既存のlive planを同一transaction内でarchive pathへ再束縛し、未保護の参照が残る場合はtransactionを拒否する。lifecycle保護されたcontract successorは既存の許容規則に残しPlan 222へ繰り越す。
implementation_tier: 2
primary_invariant: a restructuring transaction that archives a plan leaves no unprotected pre-existing live plan naming that plan's former active path in context_files
task_types:
  - planning_docs
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: high
write_scope:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
preservation_scope:
  - none
context_files:
  - docs/plan/checked/2026/08/16-31/220-resolve-active-plan-context-references.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
acceptance:
  - Rebind every unprotected pre-existing live plan's context_files entry that names an active plan archived by a restructuring transaction, inside that transaction, and reject that transaction when such an entry would survive it.
predecessor_plans: []

## Decisions

- Plan 220 rejects a `context_files` entry whose plan was moved to `docs/plan/backlog/`, but tolerates an entry whose plan was archived to `docs/plan/checked/` or `docs/plan/replanned/`.
- That tolerance never closes for a plan outside a replan contract. `validate_activation_reference_transition` rebinds only `kind: activation` rebindings, and `validate_rebinding_specs` restricts those to live contract successors, so an ungoverned plan such as Plan 210 keeps its archived context entries indefinitely.
- Closing the tolerance without a rebinding mechanism is unsafe. A referring plan is not in the archiving transaction's write scope, so any immediate rejection would abort that transaction, and a post-commit rejection leaves a mutated repository that neither verification nor recovery can clear.
- Build the rebinding first, then close the tolerance. Do not reverse that order.
- Implementation evidence rejected the original single acceptance item as too wide, so this plan is descoped rather than restructured. Closing the tolerance globally fails four existing tests: `test_a_deferred_plan_may_await_activation_rebinding`, `test_a_transaction_may_archive_a_referenced_context_plan`, `test_activation_promotion_rejects_context_drift`, and `test_activation_rebinds_context_references_to_the_checked_archive`.
- Three of those failures run through `prepare_checked_predecessor`, which reproduces the ordinary active-to-checked archival that `scripts/finalize-active-plan.sh` performs outside any transaction. That script and its generated twin are not in this write scope, so the global closure is unachievable here.
- Retain the restructuring-transaction rebinding and defer the ordinary finalization path and the repository-wide tolerance closure to `docs/plan/backlog/222-close-archived-context-tolerance.md`. The deferral changes when the requirement runs, never whether it runs.
- Classify a referring plan by verifier state, not by contract membership. A live successor is protected when it carries a rebind chain or when `enforce_projection_semantics` is set, because `verify_rebind_records` then lifecycle-compares it. A legacy schema-1 successor without a chain is not lifecycle-compared, and a direct context rewrite of it passes verification.
- Rewrite an unprotected referring plan directly inside the transaction. Reject the transaction when a protected referring plan is not already covered by a declared rebinding, so the operator declares one instead of losing the reference.
- Never rewrite a plan the transaction creates. Successor content is bound by an immutable contract `content_digest`, so a created plan must name the archive path in its own declared bytes.

- Independent review proved that rejecting a lifecycle-protected referrer deadlocks the transaction. A single-source specification has no `rebindings` field, and `validate_rebinding_specs` refuses a target that already resides in the backlog, so the instruction to declare a rebinding names a remedy the validator forbids. Rewriting such a plan is equally impossible, because `validate_lifecycle_evolution` treats `context_files` as a protected manifest field.
- Leave lifecycle-protected referrers on the existing archived-path tolerance. That is exactly the behavior before this plan, so nothing regresses, and the unprotected majority, including this repository's own backlog debt, still gains the rebinding. Plan 222 carries the protected case together with the ordinary finalization path.
- Skip a plan the specification already rebinds. Its rebind record fixes the updated content digest before this step runs, so a later rewrite would make the recorded digest disagree with the written bytes.

## Tasks

- [x] Rebind unprotected referring live plans' `context_files` entries inside the archiving restructuring transaction.
- [x] Reject the transaction when an unprotected referring live plan would be left naming an archived former active path.
- [x] Record the retained and deferred acceptance split and create the deferred backlog plan.
- [x] Document the rule in the root and generated plan workflow specifications and keep both scripts byte-identical.
- [x] Add transaction tests covering protected and unprotected referring plans.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, then archive and commit this plan.

## Validation Notes

- `python3 tests/test-plan-restructure.py` passed with 137 tests, including the four new referrer-rebinding tests and the strengthened archive-referrer test.
- `python3 scripts/restructure-plan.py --verify`, `git diff --check`, and `diff -q` between the root and generated engine copies all passed.
- `python3 scripts/check-copier-template.py` passed, confirming both plan workflow specifications stay aligned.
- `scripts/lint-project-workflow.sh` and `tests/smoke.sh` each passed once as the authoritative suite.
- Two independent `code-review` rounds ran. The first reported one Medium and one Low finding, both fixed. The second reported zero High or Medium findings and three Low findings, all fixed.
- The Medium finding proved that rejecting a lifecycle-protected referrer deadlocks the transaction, so protected referrers stay on the existing tolerance and move to Plan 222.
