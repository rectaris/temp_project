# Reconstruct the shell parser lineage from backlog residents

status: in_progress
implementation_tier: 2
primary_invariant: the reconstruction transaction preserves source acceptance, the committed non-authoritative rejected-candidate blobs, downstream implementation authority, and every active predecessor edge while assigning each shell and Copier semantic boundary to exactly one successor plan
replan_sources:
  - docs/plan/active/212-reconstruct-shell-parser-lineage.md
replan_contract: docs/plan/replanned/contracts/212-reconstruct-shell-parser-lineage.json
integration_gates:
  - combined successors must satisfy every source acceptance item
  - declare only immutable contract, replanned, and checked paths as context so no declared input is invalidated by the lifecycle relocation this plan performs
  - reactivate the exact closure of Plans 165, 166, 179, 184, 185, 186, 187, 197, and 198 with their exact pre-deferral active bytes and index rows before building the coupled specification
  - use only the coupled reconstruction capability accepted by checked Plan 211
  - verify the decomposed validation commands admitted by checked Plan 199 before building the coupled specification
  - keep the blobs for scripts/project_workflow/copier_fixture.py and tests/test-copier-fixture.py byte-identical to commit 3ff2309dc85b4ebbb31904acae1949e12654fa88 and never use them as acceptance authority
  - preserve the exact Plan 191 acceptance text and digest in every mapped successor and the final integration plan
  - preserve the exact Plan 183 acceptance text, write scopes, and downstream authority while rebinding Plans 185 and 186
  - before Plans 185, 186, or 166 become in_progress, replace every active Plan 202 through 205 predecessor or context reference with that plan's exact checked archive and append the exact activation rebind to the checked overlay
successor_plans:
  - docs/plan/active/223-reconstruct-backlog-resident-shell-lineage.md
inherited_acceptance_digests:
  - sha256:b3051fadc391a911379a6aeea9908d350b1320b725c68957355e41c255d4db6d
integration_source_ids:
  - 212
reserved_plan_ids:
  - 202
  - 203
  - 204
  - 205
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - docs/plan/
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/replanned/contracts/191-freeze-bounded-copier-fixture-validator.json
  - docs/plan/replanned/contracts/183-build-bounded-copier-transition-fixture.json
  - docs/plan/replanned/contracts/130-map-acceptance-validation-witnesses.json
  - docs/plan/replanned/2026/08/16-31/201-reconstruct-shell-parser-lineage.md
  - docs/plan/replanned/2026/08/16-31/212-reconstruct-shell-parser-lineage.md
  - docs/plan/checked/2026/08/16-31/199-admit-decomposed-shell-validation.md
  - docs/plan/checked/2026/08/16-31/211-verify-coupled-lineage-acceptance.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-root-agent-policy.py
  - git diff --check
validation:
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-root-agent-policy.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Replace stopped Plans 197 and 198 with independently executable shell lexical, function-table, execution-graph, and Copier validator plans while preserving rejected candidate paths and keeping Plans 185 through 195 executable with unchanged acceptance.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b3051fadc391a911379a6aeea9908d350b1320b725c68957355e41c255d4db6d","stage":"focused","witness":"python3 scripts/restructure-plan.py --verify"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/211-verify-coupled-lineage-acceptance.md
checked_summary_ja: backlogへ退避したPlan 197と198をactiveへ復帰させたうえで、停止したshell parser lineageを字句、関数表、実行graph、Copier validatorの独立planへ原子的に再構築する。

## Decisions

- Plan 212 stopped before implementation because its declared `context_files` name the `docs/plan/backlog/` residence of Plans 197, 198, 185, 186, and 166, while the coupled reconstruction accepts only active-index sources and active rebinding targets. Reactivating those plans deletes the exact declared paths, and no authorized channel repairs a backlog-path context entry.
- This successor keeps every accepted Plan 212 decision and changes only the declared inputs and the execution ordering. The requirement baseline, safety conditions, and the single acceptance item are unchanged.
- Declare only immutable contract, replanned, and checked paths as context. A live plan path is not a stable declared input for a plan whose own work relocates live plans.
- Read the created bytes of Plans 197 and 198 from the immutable Plan 191 contract, the created bytes of Plans 185 and 186 from the Plan 183 contract, and the created bytes of Plan 166 from the Plan 130 contract, then read each live file at execution time.
- Reactivate exactly the nine-plan closure {165, 166, 179, 184, 185, 186, 187, 197, 198}. That closure is the transitive closure of `context_files` and `predecessor_plans` references over the sources and the three rebinding targets, and a smaller set leaves an unresolvable active context entry.
- Restore each reactivated plan's exact pre-deferral active bytes, which are the exact inverse of commit `2f761c8`, and re-add its active index row with the status those bytes carry.
- After the reconstruction is checked, return every plan that stays unreachable to `docs/plan/backlog/` so the active index again carries only runnable plans. Backlog residence preserves lineage, acceptance, and inherited digests.
- coupled_lineage_reconstruction means one atomic lifecycle transition that replaces a stopped successor and each immutable active dependent that would otherwise retain its archived predecessor path.
- bounded_shell_lexical_projection means the checked quote-aware, comment-aware, and here-document-aware record projection of supplied shell bytes.
- bounded_shell_function_table means the checked unique top-level function declaration table derived from the accepted lexical projection.
- bounded_shell_execution_graph means the checked command and control-transfer graph used to determine permitted reachable fixture regions.
- bounded_copier_fixture_validator means the Copier-specific predicates evaluated over the three checked shell projections through the exact fixture check CLI.
- The rejected candidate paths are exactly `scripts/project_workflow/copier_fixture.py` and `tests/test-copier-fixture.py`; they are committed non-authoritative evidence from the stopped Plan 197 attempt, not source-plan successors or accepted implementation.
- Both rejected candidate blobs are committed and clean, so they take no `preservation_scope` entry; keep them byte-identical to commit `3ff2309dc85b4ebbb31904acae1949e12654fa88` through the reconstruction transaction.
- Repository validation-command policy and tests updated before parser implementation so each new module and test entrypoint has an admitted focused and compile command.
- Execute the reconstruction in seven ordered phases: verify checked Plans 199 and 211; reactivate the nine-plan closure; create independent prerequisite Plans 202 through 204 and archive ordered sources Plans 197 and 198 into mapped integration Plan 205 in the same transaction; prove both rejected candidate blobs unchanged and disjoint from every successor write scope; apply exact Plans 185, 186, and 166 rebindings; verify every unaffected active plan and historical contract; then complete this plan before the separate Plan 202 activation update.
- Create Plan 202 for `scripts/project_workflow/shell_lexical.py` and `tests/test-shell-lexical.py`; reject undecoded bytes, NUL, unsupported shell forms, comments, quotes, substitutions, arithmetic shifts, here-documents, line continuations, separators, redirections, and operators that cannot be projected without ambiguity.
- Create Plan 203 for `scripts/project_workflow/shell_functions.py` and `tests/test-shell-functions.py`; consume only checked lexical records and reject duplicate, nested, split, piped, dynamically evaluated, conditionally defined, or otherwise non-top-level function declarations.
- Create Plan 204 for `scripts/project_workflow/shell_execution.py` and `tests/test-shell-execution.py`; consume checked lexical and function records and model lists, pipelines, conditions, loops, asynchronous commands, function calls, terminal effects, and one explicit permitted success path.
- Create integration Plan 205 for `scripts/project_workflow/copier_fixture_validator.py` and `tests/test-copier-fixture-validator.py`; apply only Copier-specific operation predicates and preserve the exact `--check tests/copier-update.sh` contract under the newly admitted CLI path.
- Treat Plans 202, 203, and 204 as separately authorized prerequisite plans with layer-local acceptance and witnesses; they are not successors in the Plan 197/198 source-acceptance contract and carry no inherited source digest.
- Give Plan 202 the local acceptance `Project supplied shell bytes into deterministic lexical records without hiding executable regions or accepting ambiguous unsupported syntax.` with focused witness `python3 tests/test-shell-lexical.py`.
- Give Plan 203 the local acceptance `Derive one unique top-level function table from checked lexical records and reject every alternate definition path.` with focused witness `python3 tests/test-shell-functions.py`.
- Give Plan 204 the local acceptance `Derive one explicit reachable command graph from checked lexical and function records and reject every hidden or terminal bypass.` with focused witness `python3 tests/test-shell-execution.py`.
- Create Plan 202 as `deferred` behind this active plan; defer 203 behind 202, 204 behind 203, and 205 behind 204 through exact active predecessors.
- After this plan is checked, replace Plan 202's active predecessor with this plan's exact checked archive and activate Plan 202 in the same parent-owned lifecycle update.
- Map the exact Plan 191 acceptance digest only to Plan 205 and require Plan 205 to retain the exact source acceptance text as the sole mapped integration successor for both Plans 197 and 198.
- Use one schema-3 multi-source contract for ordered sources Plan 197 and Plan 198, two source archives, mapped successor Plan 205, separately authorized prerequisite Plans 202 through 204, and Plan 205 `integration_source_ids` containing both source ids.
- No created plan may write, import, execute, or use either rejected candidate path as expected output.
- Rebind Plan 185 to active Plan 205 and replace only its validator context, focused command, authoritative command, witness, deferred reason, predecessor, integration-gate references, and exact body references from checked Plan 198 to checked Plan 205.
- Rebind Plan 186 to active Plan 205 and replace only its validator context and command references plus exact body references from checked Plan 191 to checked Plan 205; preserve its checker write scope and Plan 183 acceptance.
- Rebind Plan 166 only at its exact context and integration-gate references from Plan 191 to Plans 202, 203, 204, and 205 so its single inventory includes every prerequisite-owned module and test path plus the integration validator paths; preserve its inventory write scope, validation, acceptance, and every unrelated byte.
- Add active Plan 186 as an exact Plan 166 predecessor during the initial rebind because Plan 166's inventory cannot be complete before the connected checker is checked.
- Record Plans 185, 186, and 166 in the checked append-only live-successor rebind overlay without changing either immutable owning contract or the existing validation baseline.
- Keep Plans 185, 186, and 166 deferred while any rebound predecessor or context path is active; each later parent-owned activation update must replace all such paths with exact checked archives, append the resulting projection to the rebind overlay, and only then set the dependent plan `in_progress`.
- When Plan 186 activates after checked Plan 185, promote `tests/copier-update.sh` from preservation to exact checked read-only context; when Plan 166 activates after checked Plan 186, promote `scripts/check-copier-template.py` the same way.
- Leave Plans 187, 184, 179, 165, 167, and 192 through 195 byte-identical apart from their reactivation lifecycle fields, then verify their predecessor graph and owning contracts after the transaction.
- Keep Plans 202 through 205 small enough that each review addresses one semantic boundary and one independently executable mutation suite.
- Mark Plans 202 through 205 as high-risk bounded parent implementations with fresh independent review because each writes protected parser, test, or validation-authority paths that the writable runner cannot own.

## Tasks

- [x] Phase 1: verify the exact checked Plan 199 validation admission through checked Plan 211 and bind both checked archive paths into the coupled specification evidence.
- [x] Phase 2: reactivate the nine-plan closure with its exact pre-deferral active bytes and index rows, and confirm repository verification passes before any reconstruction write.
- [x] Phase 3: build and execute one coupled specification bound to the current HEAD, exact Plan 197 and Plan 198 bytes, both owning contracts, independent prerequisite Plans 202 through 204, and mapped integration Plan 205; archive both sources and create all four plans as deferred records in the same transaction without activating implementation.
- [x] Phase 4: prove both rejected candidate blobs stay byte-identical to commit 3ff2309dc85b4ebbb31904acae1949e12654fa88 and disjoint from every successor write scope.
- [x] Phase 5: apply exact rebind projections for Plans 185, 186, and 166 through the append-only overlay, including active Plan 186 as a Plan 166 predecessor.
- [x] Phase 6: verify both source archives, the schema-3 contract, the rebind overlay, all created plan files, every index, unchanged bytes for unaffected downstream Plans 187, 184, 179, 165, 167, and 192 through 195, the complete predecessor graph, and repository-wide historical contract verification.
- [x] Record the future activation projections that replace active Plans 202 through 205 with exact checked archives before Plans 185, 186, and 166 can leave `deferred`.
- [x] Record the exact activation-only preservation-to-context promotions for `tests/copier-update.sh` in Plan 186 and `scripts/check-copier-template.py` in Plan 166.
- [ ] Complete focused validation and independent review over lifecycle consistency with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once and archive and commit this planning transition.
- [ ] Phase 7: in the separate parent-owned post-check activation update, replace Plan 202's predecessor with this plan's exact checked archive, set Plan 202 to `in_progress`, and return every still-unreachable plan to the backlog.

## Validation Notes

- This successor owns final acceptance of the original Plan 201 requirement carried through Plan 212; no earlier plan does.
- This plan performs planning and lifecycle effects only; it creates no parser, validator, runtime, or checker implementation.
- The four successor plans must use the exact validation commands admitted by checked Plan 199.
- The decision audit for the Plan 212 stop is stored locally at `.agent-artifacts/decision-audits/plan212-replan.md`.
- Phase 3 stopped this execution run before any reconstruction write: the coupled transaction rejects every rebinding of Plans 185, 186, and 166 because `compare_contract_identity` compares the first rebind record against the owning contract's created bytes including `preservation_scope`, and all three plans legitimately gained a `preservation_scope` entry after creation under Plan 130 and Plan 183 schema-1 contracts that record no preservation baseline.
- The same defect blocks every future activation rebind for those plans, so it is an independently repairable engine defect rather than a defect in this plan's scope, acceptance, validation authority, or safety conditions.
- Plan 224 is the separate bounded repair plan for that defect. This plan resumes through a fresh run after Plan 224 is checked; `status: deferred` is unreachable for a schema-3 contract successor, so this plan waits in the backlog instead.
- Phases 1 and 2 are already complete and committed; the reactivated nine-plan closure stays active and verified while this plan waits.
- Plan 224 is checked, so this plan resumes through a fresh Phase 3 run with unchanged requirements, safety conditions, scope, validation authority, and acceptance.
- Phase 3 through Phase 6 completed in one coupled transaction over source HEAD `f1c676aadaeb8a80633825d7e5e8d29dabe16340`: Plans 197 and 198 archived, contract `docs/plan/replanned/contracts/197-freeze-bounded-shell-structure-parser.json` created, prerequisite Plans 202 through 204 and mapped integration Plan 205 created as deferred records, and three rebind records appended for Plans 185, 186, and 166.
- Phase 4 verified: `scripts/project_workflow/copier_fixture.py` stays at blob `b85209cc0a7c905057a481b9b051d6c2c81fe581` and `tests/test-copier-fixture.py` at blob `47da27ecb5a35d396f7d682c380ad2a9b2de2df9`, both byte-identical to commit `3ff2309dc85b4ebbb31904acae1949e12654fa88` and disjoint from every created write scope.
- Two recorded Plan 166 rebind decisions are not expressible through the accepted rebind capability and were intentionally not applied: an initial rebind may replace only exact reference tokens, so the prose integration gate naming `Plans 164, 165, 186, and 191` cannot be rewritten, and `docs/plan/active/186-bind-connected-copier-fixture-checker.md` is not a transaction-owned new reference, so it cannot be added as a Plan 166 predecessor. Plan 166 already names Plan 186 as exact read-only context, and neither omission changes this plan's acceptance, any write scope, any validation authority, or any safety condition.
- The engine defect discovered in the first Phase 3 attempt was repaired independently through checked Plan 224 before this run; this plan's requirements, scope, validation authority, and acceptance are unchanged.
- The authoritative suite passed once after the transaction: `python3 scripts/restructure-plan.py --verify`, `python3 scripts/check-root-agent-policy.py`, `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, and `git diff --check`.
