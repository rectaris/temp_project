# Report a completed active plan the archive step never marked

status: backlog
primary_invariant: the agent completion gate reports an active plan whose recorded evidence already satisfies the archive precondition, so a finished plan cannot pass completion by never being marked ready to archive
task_types:
  - template_workflow
  - planning_docs
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 1
implementation_risk: low
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"scripts/check-agent-completion.sh skips every plan whose status is not ready_to_archive, so an in_progress plan with all tasks checked and non-pending Validation Notes returned agent completion gate passed while its archive step had never run."}
  - {"kind":"existing_mechanism","evidence":"scripts/complete-plan.sh already implements both predicates this gate needs: an unchecked-task scan and a non-pending Validation Notes scan over the same plan file."}
  - {"kind":"existing_mechanism","evidence":"tests/validation_tools/plan.py already builds repositories that exercise scripts/check-agent-completion.sh, and template/.project-agent-workflow/scripts/check-agent-completion.sh carries the same ready_to_archive-only filter."}
completion_conditions:
  - The agent completion gate reports an active plan whose status is in_progress when every task checkbox is checked and its Validation Notes hold non-pending evidence, and names scripts/complete-plan.sh as the next step.
  - The gate stays silent for an in_progress plan that still has an unchecked task or whose Validation Notes are empty or pending, and the existing ready_to_archive and dirty-worktree reports are unchanged.
completion_witness_map:
  - {"condition_sha256":"sha256:73afd52d41f0751b1db94d25aa507061afd21a1ba4d2f87748865528b8e7862d","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:2e7b6ddf14df34d1d09e785fa2683f86570fbeeba1548d73cd63aeb5fb3e6626","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/check-agent-completion.sh
  - template/.project-agent-workflow/scripts/check-agent-completion.sh
  - tests/validation_tools/plan.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/09/01-15/264-enforce-executable-plan-admission.md
  - scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Report an active plan that already records completed tasks and non-pending validation evidence but was never marked ready to archive, and keep every existing completion-gate report unchanged.
integration_gates:
  - keep the root gate and its template counterpart aligned in this change
  - reuse the predicates scripts/complete-plan.sh already applies rather than defining a second reading of the same plan fields
  - do not make the gate rewrite, mark, or archive a plan; it reports and exits non-zero
checked_summary_ja: 完了記録が揃っているのにready_to_archiveへ進めていないactive planを、完了ゲートが報告するようにする。

## Decisions

- Report rather than act. The gate must not run the archive step on its own, because archiving is an owner-visible lifecycle transition and the gate runs in contexts where a plan is deliberately held open.
- Reuse the two predicates `scripts/complete-plan.sh` already applies. A second, independently written reading of the same plan fields would let the gate and the archive step disagree.
- Keep the existing ready_to_archive and dirty-worktree reports unchanged. This plan adds one missing case; it does not restate the gate.

## Tasks

- [ ] Reproduce the silent pass read-only: confirm the gate returns success for an active in_progress plan whose tasks are all checked and whose Validation Notes are non-pending.
- [ ] Add the missing report to the root gate, reusing the unchecked-task and pending-notes predicates from `scripts/complete-plan.sh`, and name `scripts/complete-plan.sh` as the next step.
- [ ] Mirror the change into `template/.project-agent-workflow/scripts/check-agent-completion.sh`.
- [ ] Add coverage for the reported case, for an in_progress plan that must stay silent, and for the unchanged ready_to_archive report.
- [ ] Complete one independent read-only review and focused validation with zero unresolved High or Medium findings.

## Validation Notes

- Pending. The gap was found while archiving Plan 251, whose implementation was complete and validated while the plan sat in_progress and the gate reported success.
