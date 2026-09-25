# Retire and publish members without false completion

status: deferred
completion_deferred_reason: Plan 379 must first make integration evidence authoritative; publication and retirement decisions read those records, so repairing them against the current caller-supplied values would encode the defect this reconstruction removes.
implementation_mode: parent_direct
primary_invariant: A member is reported complete and its worktree and branch are retired only after the parent-owned ledger, publication journal and retirement record all agree that this exact member finished; an interruption at any step leaves a recoverable state rather than a deleted branch or a false completion.
replan_sources:
  - docs/plan/active/374-publish-and-verify-separate-session-plan-results.md
replan_contract: docs/plan/replanned/contracts/374-publish-and-verify-separate-session-plan-results.json
successor_plans:
  - docs/plan/active/379-bind-integration-evidence-to-parent-owned-authority.md
  - docs/plan/active/380-retire-and-publish-members-without-false-completion.md
  - docs/plan/active/381-align-root-and-generated-parallel-session-surfaces.md
  - docs/plan/active/382-demonstrate-live-parallel-sessions-end-to-end.md
inherited_acceptance_digests:
  - sha256:4f7453fc0e59e3ccda836275d66739d8568b487ff2def2db542e550e784841cd
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The epoch-0 review of plan 374 recorded one High finding here: completion consults only the manifest fields and the private record and never the ledger's `required_evidence_reserved` event, so losing the private record alone removes the obligation. Only `plan-execution-state.py` and `verify-parallel-plan-sessions.py` mention that event today.","kind":"reproduced_defect"}
  - {"evidence":"Four Medium findings locate exactly: every schema-2 lifecycle operation is refused at `scripts/parallel-plan-state.py:2158`; `group_complete` at `:3109` reports completion from publication flags while retirement is outstanding; retirement deletes the member branch with `git branch -d` at `scripts/manage-plan-worktrees.py:1568`; and the quarantine rename at `:1482` is not recorded.","kind":"reproduced_defect"}
  - {"evidence":"A fifth Medium finding is that retirement succeeding before its journal advances leaves a `published` journal whose recovery calls retirement again against a deleted ownership record, so the repair is an ordering and journal-advance fix in code that already writes that journal.","kind":"reproduced_defect"}
  - {"evidence":"The publication journal, the ownership records and the quarantine helper already exist in `scripts/manage-plan-worktrees.py`, and `scripts/plan-execution-state.py` already records and reads `required_evidence_reserved`, so each finding closes by routing an existing caller through an existing record.","kind":"existing_mechanism"}
completion_conditions:
  - Completion consults the ledger's `required_evidence_reserved` event in addition to the manifest fields and the private record, so removing the private record alone refuses instead of releasing the obligation.
  - Schema-2 group lifecycle operations complete and finalize a published group instead of being refused unconditionally, and `group-complete` reports completion only when retirement has also finished.
  - Retirement removes only the exact completed member worktree and branch, tolerates a replayed member commit instead of requiring a fast-forward branch delete, and records the quarantine rename so an interruption between the rename and the registration repair recovers instead of stranding the directory.
  - A retirement that succeeds before its journal advances leaves no `published` journal for recovery to act on, so recovery never calls retirement again against a deleted ownership record.
  - Root and generated lifecycle and worktree command bytes stay aligned after the change.
completion_witness_map:
  - {"condition_sha256":"sha256:5a6c975bf49587184e5a5f4810a3cebb6ffe05e8f7d3927c5c2704bcc8eb3af7","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:95ce281b631d76c88504601e21c3be6b92a55106f297a4988d7e5c863d6f4818","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:3ec08384002acabfefdcf78a40c58ea54760bb07447904d67f0a04aa4f26627b","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:8f173952ca61e2eb977707e0927520bf413bcf40fafc17dbe889edf89017a1d8","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:afc54936a85760e7fac6f2adf7b319d93c0d86f459e07006a4bed7f0b6b45e8c","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/manage-plan-worktrees.py
  - template/.project-agent-workflow/scripts/manage-plan-worktrees.py
  - scripts/parallel-plan-state.py
  - template/.project-agent-workflow/scripts/parallel-plan-state.py
  - scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - scripts/check-agent-completion.sh
  - template/.project-agent-workflow/scripts/check-agent-completion.sh
  - scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - tests/test-sandboxed-plan-worker.py
  - tests/validation_tools/worktrees.py
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/plan/replanned/2026/09/16-31/374-publish-and-verify-separate-session-plan-results.md
  - docs/agent/spec-index.yaml
  - scripts/plan-execution-state.py
  - scripts/verify-parallel-plan-sessions.py
  - scripts/project_workflow/worktree_guard.py
  - docs/plan/active/379-bind-integration-evidence-to-parent-owned-authority.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Checked publication and serialized lifecycle updates retire only exact completed-member worktrees/branches; interruptions, dirty state or failed B retain accepted A and recoverable B without duplicate publication or false completion.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:4f7453fc0e59e3ccda836275d66739d8568b487ff2def2db542e550e784841cd","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - Start only after plan 379 is checked and published, and read the authoritative records it establishes rather than re-deriving them here.
  - Start a fresh parent-direct execution ledger. The stopped plan 374 ledger is at `descope_required` and must not be read, rewritten or resumed.
  - Exercise retirement and publication only against isolated fixtures. Do not retire a real task worktree, delete a real branch or advance a real publication journal as part of implementation.
  - Leave root and generated guidance to plan 381 and the live two-session demonstration to plan 382.
checked_summary_ja: 公開と撤収を親所有の記録の合意だけで進め、中断しても復旧可能な状態を残す。

## Decisions

- The one High and five Medium findings in this boundary all concern the same question: when may the system say a member is finished and remove its artifacts. They are repaired as one plan because a partial repair leaves a path that still deletes work.
- Retirement stops using `git branch -d` as its safety check. The safety check becomes the parent-owned retirement record, so a replayed member commit is handled by evidence rather than by Git's fast-forward test.
- The quarantine rename is recorded before it happens, so recovery can find a directory that a crash left renamed.

## Tasks

- [ ] Reproduce the High finding and each Medium finding as failing fixtures before changing behavior.
- [ ] Make completion consult the ledger `required_evidence_reserved` event.
- [ ] Enable schema-2 group lifecycle completion and finalization, and gate `group-complete` on finished retirement.
- [ ] Replace the fast-forward branch delete with a record-driven retirement check and record the quarantine rename.
- [ ] Advance the publication journal before retirement returns, and make recovery idempotent against a deleted ownership record.
- [ ] Mirror every changed command into `template/.project-agent-workflow/`.
- [ ] Run the focused commands, then the authoritative suite once.

## Validation Notes

- This plan is a reconstruction successor of plan 374. Its findings were recorded in review `plan-374-review-001` at epoch 0.
- Waiver: plans 370, 371 and 378 are shelved on owner instruction. The assurance they would have added is a bounded execution-resumption path for retained work after a verified descope; this plan skips it and stops for the owner instead of resuming, should its own run stop.
