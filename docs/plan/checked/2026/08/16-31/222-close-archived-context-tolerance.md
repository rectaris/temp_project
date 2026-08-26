# Close the archived context tolerance repository wide

status: checked
checked_summary_ja: archiveされたplanの旧active pathをcontext_filesに持つlive planを、どのcommandがarchiveしたかに関わらずrepository全体で拒否する。ordinaryなactiveからcheckedへのfinalizationがreferrerをarchive pathへ再束縛し、lifecycle保護されたcontract successorはcanonical relocation projectionにより同一性を保ったまま再束縛できる。既存の許容entry 4件も移行済み。
implementation_tier: 2
primary_invariant: no live plan names an archived plan's former active path in context_files, whichever command performed the archival
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
  - docs/plan/checked/2026/08/16-31/221-rebind-referrer-context-on-archive.md

## Decisions

- Plan 221 retains the restructuring-transaction rebinding. This plan carries the deferred remainder of the original Plan 221 acceptance; the split changed when the requirement runs, never whether it runs.
- `scripts/finalize-active-plan.sh` archives an active plan to the checked archive outside any transaction. It writes the archive, deletes the source, and rewrites two indexes in separate non-journaled steps, so it cannot gain referrer rebinding without either an atomicity boundary or delegation to the transaction engine.
- Refusing to finalize while a referrer exists is not an option. A deferred successor names its predecessor's active path, and that predecessor cannot be checked before the successor activates, so refusal deadlocks the ordinary lifecycle.
- Closing the tolerance repository wide fails three tests that encode the current accepted behavior: `test_a_deferred_plan_may_await_activation_rebinding`, `test_activation_promotion_rejects_context_drift`, and `test_activation_rebinds_context_references_to_the_checked_archive`. Decide for each whether it encodes an accepted requirement or only the tolerated state, and record that decision before changing it. Plan 221 already converted `test_a_transaction_may_archive_a_referenced_context_plan` to assert the rebind.
- Existing backlog debt must be migrated before the closure, not after. Plans 166, 167, and 186 hold four tolerated archived-path entries whose archives already exist, so no future archiving transaction will ever trigger the Plan 221 mechanism for them.
- Repository verification currently reads context only for active-index plans, so backlog debt stays invisible until promotion. Decide whether the closure also extends verification to backlog residents, and migrate the debt in the same change if it does.

- Plan 221 leaves lifecycle-protected contract successors on the tolerance. A protected referrer cannot be rewritten, because `validate_lifecycle_evolution` guards `context_files`, and cannot be rejected, because a single-source specification has no `rebindings` field and a rebinding cannot target a backlog resident. Give those two routes a rebinding channel before closing the tolerance for protected plans.

- The rebinding channel for protected referrers is a canonical relocation projection, not a declared rebinding record. `validate_lifecycle_evolution` and the rebind chain-gap comparison now project both compared sides through `project_context_archive_relocation`, which replaces a `context_files` entry naming a missing active plan path with that plan's single checked or replanned archive. A declared-rebinding channel was rejected because it exists only inside a restructuring transaction, and the ordinary finalization path has no specification to declare one in.
- The relocation is identity preserving, so protection is not weakened. It changes only entries whose active file is absent and whose plan id and file name resolve to exactly one archive, it leaves `predecessor_plans`, `successor_plans`, and body prose untouched, and an ambiguous or unarchived entry is left alone and still rejected.
- The atomicity boundary of the ordinary finalization path is the exclusive archive creation. Referrer rebinding runs immediately after that commit point and before the source plan is removed, replaces each referrer file through a temporary file and `os.replace`, and on failure restores every referrer it already rewrote and removes the new archive. The later source removal and index rewrites stay unjournaled and keep their existing Git-based repair.
- The generated finalization script carries the same rebinding as an inline step in `finalize-active-plan.sh`. Adding a `lint-plan-docs.py` subcommand instead would have written outside this plan's `write_scope`.
- Repository-wide enforcement covers exactly the archived former active path, in every live plan. The pre-existing entries that name a plan moved into `docs/plan/backlog/` belong to Plan 220's separate rule, are still unverified for backlog residents, and are not migrated here.
- Six tests changed rather than four. `test_a_deferred_plan_may_await_activation_rebinding` encoded only the tolerated state and now asserts rejection. `prepare_checked_predecessor` now reproduces the finalization rebinding, so `test_activation_promotion_rejects_context_drift` and the activation context test compare against the rebound plan. `referrer_context_rebind_protection` no longer exists, so the two Plan 221 protection tests became a relocation-projection test and a protected-referrer rebinding test.

## Tasks

- [x] Decide and record the atomicity boundary for referrer rebinding in the ordinary finalization path.
- [x] Give the single-source and backlog-resident routes a rebinding channel for protected referrers.
- [x] Rebind referrer context when a plan is finalized from the active index to the checked archive.
- [x] Migrate the existing tolerated archived-path entries in Plans 166, 167, and 186.
- [x] Close the archived-path tolerance in `validate_plan_context_files` and reclassify the four affected tests.
- [x] Document the closed rule in the root and generated plan workflow specifications.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, then archive and commit this plan.

## Validation Notes

- This plan owns the deferred half of the original Plan 221 acceptance and must not weaken the retained half.
- Do not close the tolerance before the ordinary finalization path can rebind its referrers.
- `python3 tests/test-plan-restructure.py` passed with 140 tests, including the new finalization referrer test, the relocation-projection test, the rebound-referrer lifecycle test, and the backlog rejection test.
- `sh tests/root-plan-lifecycle.sh` passed, so the added finalization step keeps the concurrent-finalizer outcome at exactly one successful writer.
- `python3 scripts/restructure-plan.py --verify` passed after the four tolerated entries in Plans 166, 167, and 186 were rebound, and rejected each of them before the migration.
- `python3 scripts/check-copier-template.py` passed, confirming both plan workflow specifications and both engine copies stay aligned.
- Independent review ran twice against the same diff. The first round raised two Medium findings and no High finding. The second round closed both with no remaining High or Medium finding.
- The first Medium finding was fixed. The finalization step now reads a referrer entry exactly as `parse_manifest` does, so an entry written with unusual list spacing is rebound too, and `test_finalization_rebinds_every_live_referrer_context_entry` covers that form.
- The second Medium finding was classified as a pre-existing boundary rather than fixed. Finalizing two different plans at once can lose a referrer rewrite, but the pre-existing active-index rewrite loses a row the same way, so finalization was already a single-writer command and this change weakens no guarantee it provided. Both specifications now state that assumption.
- `./scripts/lint-project-workflow.sh` and `./tests/smoke.sh` passed once as the authoritative suite, with `sh -n` clean on both finalization scripts and `git diff --check` clean.
