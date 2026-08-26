# Close the archived context tolerance repository wide

status: backlog
implementation_tier: 2
primary_invariant: no live plan names an archived plan's former active path in context_files, whichever command performed the archival
task_types:
  - planning_docs
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: pending
implementation_risk: high
implementation_ambiguity: high
write_scope:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - docs/plan/
preservation_scope:
  - none
context_files:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/checked/2026/08/16-31/220-resolve-active-plan-context-references.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
acceptance:
  - Rebind referrer context for the ordinary active-to-checked finalization path and for lifecycle-protected contract successors, then reject any surviving archived-path context entry repository wide.
predecessor_plans:
  - docs/plan/active/221-rebind-referrer-context-on-archive.md

## Decisions

- Plan 221 retains the restructuring-transaction rebinding. This plan carries the deferred remainder of the original Plan 221 acceptance; the split changed when the requirement runs, never whether it runs.
- `scripts/finalize-active-plan.sh` archives an active plan to the checked archive outside any transaction. It writes the archive, deletes the source, and rewrites two indexes in separate non-journaled steps, so it cannot gain referrer rebinding without either an atomicity boundary or delegation to the transaction engine.
- Refusing to finalize while a referrer exists is not an option. A deferred successor names its predecessor's active path, and that predecessor cannot be checked before the successor activates, so refusal deadlocks the ordinary lifecycle.
- Closing the tolerance repository wide fails three tests that encode the current accepted behavior: `test_a_deferred_plan_may_await_activation_rebinding`, `test_activation_promotion_rejects_context_drift`, and `test_activation_rebinds_context_references_to_the_checked_archive`. Decide for each whether it encodes an accepted requirement or only the tolerated state, and record that decision before changing it. Plan 221 already converted `test_a_transaction_may_archive_a_referenced_context_plan` to assert the rebind.
- Existing backlog debt must be migrated before the closure, not after. Plans 166, 167, and 186 hold four tolerated archived-path entries whose archives already exist, so no future archiving transaction will ever trigger the Plan 221 mechanism for them.
- Repository verification currently reads context only for active-index plans, so backlog debt stays invisible until promotion. Decide whether the closure also extends verification to backlog residents, and migrate the debt in the same change if it does.

- Plan 221 leaves lifecycle-protected contract successors on the tolerance. A protected referrer cannot be rewritten, because `validate_lifecycle_evolution` guards `context_files`, and cannot be rejected, because a single-source specification has no `rebindings` field and a rebinding cannot target a backlog resident. Give those two routes a rebinding channel before closing the tolerance for protected plans.

## Tasks

- [ ] Decide and record the atomicity boundary for referrer rebinding in the ordinary finalization path.
- [ ] Give the single-source and backlog-resident routes a rebinding channel for protected referrers.
- [ ] Rebind referrer context when a plan is finalized from the active index to the checked archive.
- [ ] Migrate the existing tolerated archived-path entries in Plans 166, 167, and 186.
- [ ] Close the archived-path tolerance in `validate_plan_context_files` and reclassify the four affected tests.
- [ ] Document the closed rule in the root and generated plan workflow specifications.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, then archive and commit this plan.

## Validation Notes

- This plan owns the deferred half of the original Plan 221 acceptance and must not weaken the retained half.
- Do not close the tolerance before the ordinary finalization path can rebind its referrers.
