# Preserve live-evidence obligations across an authorized acceptance partition

status: in_progress
primary_invariant: A live-evidence obligation is neither lost nor reported satisfied when its exact acceptance item moves to another plan; only a verified owner-authorized transfer releases the source while preserving the destination gate.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"At ae5b9f9, require reads a repository-local location and reports the plan 374 record missing. The original private record still exists and its self-digest equals the stopped ledger required_evidence_reserved event.","kind":"reproduced_defect"}
  - {"evidence":"A read-only probe verified the original record self-digest, execution genesis, reservation event and deferred acceptance digest, and reproduced both committed acceptance partitions from Git. No historical record changed.","kind":"bounded_prototype"}
  - {"evidence":"The verifier before 5c33a6a has bounded private record readers, the account-home canonical location, init, bind, show and require. Existing lifecycle commands already call require. Reconcile these mechanisms; do not restore an entire stale file.","kind":"existing_mechanism"}
completion_conditions:
  - The verifier resolves and verifies the original bounded private required-evidence record and ledger reservation without rewriting either, and restores compatible reservation, binding and inspection entrypoints.
  - One explicit owner-authorized transfer binds the canonical stopped ledger, exact committed acceptance partition, original obligation and destination; replay, drift, replacement, missing evidence and ambiguous crash recovery refuse without losing either obligation.
  - A verified transfer releases only the source live-evidence gate while the destination remains unmet until independently verified real-session evidence is bound; missing records, field removal, environment changes and direct lifecycle entrypoints cannot waive it.
  - Root and generated verifier and lifecycle guidance agree, and registered preservation fixtures cover historical records, project-owned plans, configuration and history during installation and Copier update.
completion_witness_map:
  - {"condition_sha256":"sha256:4da68662e86dec19776bb5072e6809c1c5fa39aaaf8f95a6fce4de7f2bc2b428","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:a8b909832d0e8a4e62eeac8ffe661873fc1987bc6587ea83e1bfeacfe8951d00","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:f28f4b47c87f3ab309c2cd2ad6d19c43a707839231ae46599f85838a3a2037a0","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:01f5e34a4cec8c027103824df330cd2f9151be965c7e242c68e5ed72ae0ce62e","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/verify-parallel-plan-sessions.py
  - template/.project-agent-workflow/scripts/verify-parallel-plan-sessions.py
  - tests/test-sandboxed-plan-worker.py
  - tests/root-plan-lifecycle.sh
  - scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - scripts/check-agent-completion.sh
  - template/.project-agent-workflow/scripts/check-agent-completion.sh
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - tests/validation_tools/generated.py
  - tests/smoke.sh
  - tests/copier-update.sh
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - scripts/plan-execution-state.py
  - scripts/project_workflow/worktree_guard.py
  - docs/plan/active/374-publish-and-verify-separate-session-plan-results.md
  - docs/plan/backlog/378-verify-live-parallel-session-results.md
  - docs/agent/spec-index.yaml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
acceptance:
  - Original required-evidence bytes and their execution reservation remain verifiable at their canonical private identity; absence, replacement or a forged reservation refuses rather than being recreated as historical evidence.
  - A single verified owner-authorized acceptance transfer preserves the original record and stopped ledger, accounts for the exact deferred item at one destination and supports only exact idempotent crash recovery.
  - Every source completion path requires either valid live evidence or the verified transfer, and every destination completion path retains the unfulfilled live requirement independently of manifest edits or report environment variables.
  - Root/generated commands and policy remain aligned and register Copier fixtures asserting preservation of project-owned plan, group, configuration and history bytes without touching private evidence.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:5476865eb4ad67917497ac0a208a8caf86458a028e3a183f4abce8f335898900","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:a64668ab97129eb85cf951c24c8b5e5204b4716b53504f1d02d90c80a2dd6635","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:57272969571ee919aa4c719ccef9344845bd847c61a7af4b9e105c0a50b84d8a","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:59b81ceb6885ea9ea1fd16a7e251a24f6fe5ef92f7d0d563d3e783e214b61b07","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Implement serially with a separate parent-direct execution ledger and independent review; never use this new transfer path to admit or accept its own implementation.
  - Do not execute a transfer against plans 374 or 378, edit those plans, mutate their private evidence, or resume their stopped execution in this prerequisite. Exercise effects only in isolated fixtures.
  - The later owner-authorized application must preserve both exact acceptance partitions and obtain its own task binding; a transfer records custody, never completed live acceptance.
checked_summary_ja: 実証を求める義務を証跡付きで移し、分離元の誤った完了判定を防ぐ。

## Decisions

- Owner approved A/A: add a bounded post-descope execution path separately from verified live-obligation transfer; preserve existing implementation and ledgers and do not increase the cumulative review limit.
- Restore the canonical account-home evidence identity and bounded original schema compatibility by reconciling the predecessor implementation with current code. Never copy old source files wholesale or prefer a repository-local replacement over original evidence.
- The original reserved live-evidence obligation, linked to the stopped execution and the exact acceptance item transferred to a backlog plan, remains immutable. Store a separately authenticated, versioned transfer record outside every repository worktree and bind its original identity to the ledger reservation.
- Verify the stopped ledger with the authoritative ledger reader and prove the exact source-ordered retained/deferred acceptance partition from committed Git bytes. Require an explicit owner authorization and exactly one destination carrying the unchanged deferred item.
- Journal and lock the one-time transfer so concurrent attempts, forks and partial publication cannot expose a released source with an unbound destination. Exact retry uses the same identities; ambiguous or lost evidence stays stopped.
- Discover the obligation through its execution reservation and canonical record, not prose or environment. A missing original record is a refusal, not permission to recreate historical evidence or infer no obligation.
- Restore full report binding and verification needed by the existing contract; a reserved record is never success. Keep real transcript, authority-state, Git retention, publication and retirement checks, and preserve plan 378 as the separate live demonstration.
- This plan changes the mechanism only. Applying the transfer, aligning the live plan instructions and reopening retained implementation are later parent-owned effects after both prerequisites are checked.

## Tasks

- [ ] Initialize this prerequisite's separate parent-direct ledger and pass the review-route and execution gates before product writes.
- [x] Add failing isolated tests for the historical record location, reservation binding and every source/destination transfer gate.
- [x] Reconcile the private record verifier and init, bind, show and require entrypoints without weakening original or current accepted safety predicates.
- [x] Implement locked, owner-authorized transfer with exact partition, replay and crash checks while preserving original evidence bytes.
- [x] Wire every lifecycle gate and root/generated guidance to the same verified obligation result and keep preservation fixtures aligned.
- [ ] Review the exact candidate, pass bound adversarial preflight and independent review, then run focused and unchanged authoritative validation.
- [ ] Publish and archive this prerequisite without applying it to the real plan 374 execution or evidence.

## Validation Notes

- Owner authorization on 2026-09-23: approve_bounded_prerequisites, selecting verified obligation transfer and a separate bounded execution continuation while preserving stopped records and review accounting.
- Read-only evidence at ae5b9f9: the original required record is reserved with no report; its digest matches required_evidence_reserved. One formal review is recorded. The retained 374 and deferred 378 acceptance digests exactly match plan-374-descope-001.
- The probe establishes input availability and the acceptance partition, not a live demonstration, valid completion, permission to reopen the old execution, or a passing formal review.
- Correction to an earlier note in this plan: that note claimed the review-route check, adversarial preflight and independent review were impossible because no independent reviewer session was available in this environment. That claim was wrong, and it repeated the exact error plan 374 already recorded and corrected. It generalized a property of the parent's runtime into a property of the repository. The Codex CLI is installed, `.codex/hooks.json` is trusted for this checkout, and a fresh `codex exec` session under those hooks emits one `ReviewPacketStart` carrying the declared packet digest at inherited turn zero, exactly as `docs/agent/SPEC_AGENT_LOGGING.md` specifies. The review route was never unavailable; it was never attempted. One further detail matters for anyone reproducing this: the hook reads the packet only when the first submitted prompt is the marker line followed by the canonical packet JSON and nothing else, because it parses the remainder of the prompt as one JSON document.
- The three gates were then performed against run `plan-370-parent-direct-001` with the candidate presented at its recorded identity: the task worktree was returned to the activation commit `58bef2c` with the candidate staged and the plan document restored to its activation bytes, so the ledger's repository baseline verified and the reviewed target equalled the write-scope diff. `plan-370-route-001` records the route check from a read-only probe session observing the probe packet at inherited turn zero with two tool calls. `plan-370-preflight-001` records a six-case bounded adversarial preflight bound to that review identity, target and specification digests; all six cases passed.
- `plan-370-review-001` records the first formal independent review, round one of epoch 0, performed by a separate read-only Codex session whose manifest reports an observed root session identity and twenty-five tool calls. The reviewer requested changes with three High and two Medium findings. High: `command_bind` accepts invented session identifiers and marks the record bound without checking transcripts, group authority, publication, retirement or retained changes; `ledger_reservation` returns an empty binding when the ledger records no reservation event, so a newly created record carrying copied run and genesis identifiers can authorize a transfer without proving it is the original obligation; and `command_transfer` never checks that the current committed source and destination acceptance lists equal the retained and deferred partitions, so it can release a source that still carries the deferred requirement. Medium: `verify_bound_report` and `bind` still require the manifest acceptance-digest field that a transferred destination deliberately lacks, so an inherited obligation cannot be discharged as documented; and `destination_locations` searches flat lifecycle directories only.
- Two findings were independently confirmed before the review was recorded. `PLAN_LIFECYCLE_DIRECTORIES` names `docs/plan/archive`, which does not exist in this repository, and omits both `docs/plan/checked` and `docs/plan/replanned`; checked plans are archived under `docs/plan/checked/<year>/<month>/<half>/`, so a normally archived destination is reported missing and the source release is invalidated. `ledger_reservation` does return an empty string when no reservation event is present. The review is therefore substantively correct rather than advisory noise.
- A first formal High finding in parent-direct mode moves the ledger to `descope_pending`, a stopped owner-decision state. The run is stopped at reason code `parent_remediation_budget_exhausted`; no correction, validation, apply, completion or archive operation may follow until the owner decides. This plan stays `in_progress` with tasks 1, 6 and 7 unchecked.
- A separate process defect in this run is recorded here rather than left implicit. The implementation was written, validated and published to `dev` as `6b13b7a` and `048fdc4` before any of these three gates ran, so task 1's requirement to pass the route and execution gates before product writes was violated. The ledger admitted the route check afterwards only because parent-direct mode records no writable-attempt event for it to refuse. The published commits therefore carry an unreviewed change that this review has now shown to be defective.
- Focused validation passed on the candidate: `python3 tests/test-sandboxed-plan-worker.py` (250 tests), `tests/root-plan-lifecycle.sh`, `python3 scripts/check-copier-template.py`.
- Authoritative validation passed: `scripts/lint-project-workflow.sh` and `tests/smoke.sh`. `tests/copier-update.sh --require-copier` compares the installed verifier against the committed template, so it is run against the commit that carries this change.
- The real plan 374 evidence was not touched. Its required-evidence record keeps its original bytes, its stopped ledger was not read for effect and no transfer was published against plans 374 or 378. Every transfer exercised here used isolated fixture repositories whose records were removed by the runs that created them.
- `require` resolves the original plan 374 record again at its canonical private identity and now refuses it for the right reason: the plan still declares an acceptance digest that its committed acceptance list no longer carries, because that exact item was deferred to plan 378. Publishing the owner-authorized transfer for that real partition is the later parent-owned effect this plan does not perform.
