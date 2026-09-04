# Report a completed active plan the archive step never marked

status: backlog
primary_invariant: the root and generated-project completion gates exit non-zero without changing repository state when matching in_progress lifecycle records pass the same completion-evidence predicates used by complete-plan.sh, and each gate directs the caller to its corresponding mark-ready command
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"At a60a0c7, synthetic root and generated repositories with matching in_progress records, only checked tasks, and non-pending Validation Notes make both completion gates exit zero and print agent completion gate passed."}
  - {"kind":"existing_mechanism","evidence":"Both complete-plan.sh variants run the unchecked-task and non-pending-Validation-Notes predicates before their first lifecycle write, so one early-return mode can expose the same decision without mutation."}
  - {"kind":"existing_mechanism","evidence":"tests/validation_tools/plan.py already provides temporary-repository, Git, and subprocess fixtures that can execute both script variants; it currently has no completion-gate behavior test."}
completion_conditions:
  - Each root and generated-project completion gate exits non-zero without changing repository bytes when the active-index row and its plan file both declare in_progress and --check-completion-evidence succeeds, and it names the correct root or generated-project complete-plan.sh command to run next.
  - The two completion-evidence predicates executed before the first repository write in each complete-plan.sh decide both --check-completion-evidence and the ordinary mark-ready path, and the read-only mode returns before lifecycle mutation for both accepted and rejected evidence.
  - The gates remain silent for unchecked tasks, empty or pending-only Validation Notes, deferred and replan_required plans, and mismatched in_progress records; existing ready_to_archive, missing-evidence, dirty-worktree, --plans-only, usage, and success outputs and exit statuses remain unchanged.
completion_witness_map:
  - {"condition_sha256":"sha256:0716060b9ebbde74a33f6102fb08d115a60bbece648f569f98b3906daece2f60","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:f9b098ad19ef4f467aa6a4c8b9a779d49bee79faede8af9daf59359b0dd2c038","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:949356b8a27ed21b3881e607e19be476c55709a15c5a6e43c7b17412660702b3","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/check-agent-completion.sh
  - scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/check-agent-completion.sh
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - tests/validation_tools/plan.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/07/01-15/028-completion-lifecycle-gate.md
  - docs/plan/checked/2026/09/01-15/264-enforce-executable-plan-admission.md
  - scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/planlib.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Make the root and generated-project completion gates block without mutation when matching in_progress lifecycle records pass the same completion-evidence check used by their complete-plan.sh, direct the caller to the correct mark-ready command, and preserve every existing report and incomplete-plan pass.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:67d6f8b15f89f37d555c3b613f12f6c11e27a6b64451cba60a0924b504bab310","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - keep the root and generated-project predicates semantically aligned while preserving their distinct scripts/ and .project-agent-workflow/scripts/ next-command paths
  - expose the existing complete-plan.sh evidence decision through one read-only mode in each script; do not duplicate the checkbox or Validation Notes parser in either completion gate
  - do not let the completion gate rewrite, mark, lock, or archive a plan; it only reports and exits non-zero
  - preserve the checked Plan 028 decision that incomplete in_progress and intentionally deferred plans do not block ordinary completion checks
checked_summary_ja: complete-plan.sh と同じ完了証拠の判定を通る in_progress plan を、状態を変更せずに完了ゲートが報告するようにする。

## Decisions

- Report rather than act. The gate must not run the mark-ready or archive transition because both are owner-visible lifecycle writes and the gate also runs while work is deliberately open.
- `--check-completion-evidence` means the read-only complete-plan.sh mode that evaluates those predicates without changing the plan or active index. Both scripts accept `--check-completion-evidence <active-plan-path>`, return zero exactly when both predicates pass, and keep the existing one-argument transition unchanged. Factor the two completion-evidence predicates executed before the first repository write in each complete-plan.sh so this mode and the ordinary transition call the same implementation.
- Check new eligibility only when the active-index row and its plan file both declare in_progress. An inconsistent mapping remains for existing plan lint to report and must not receive a misleading mark-ready instruction.
- Name the root or generated-project complete-plan.sh command to run next according to the gate being executed: `scripts/complete-plan.sh` at the root and `.project-agent-workflow/scripts/complete-plan.sh` in a generated project.
- Narrow the checked Plan 028 non-blocking rule only for an `in_progress` plan that passes the shared completion-evidence check. Keep incomplete `in_progress`, `deferred`, and `replan_required` plans silent, and keep the ready-to-archive and dirty-worktree paths unchanged.
- Use bounded parent implementation because every write-scope path is validation authority and the writable runner refuses it. Require an independent read-only review before authoritative validation.

## Tasks

- [ ] Reproduce both silent passes at the exact activation HEAD in temporary Git repositories, and record exit status, output, and plan and index digests before and after each gate.
- [ ] Refactor each `complete-plan.sh` so the ordinary transition and `--check-completion-evidence` call the same unchecked-task and non-pending-Validation-Notes predicates, with the read-only mode returning before any lifecycle write or lock.
- [ ] Make each completion gate call the read-only mode only for matching `in_progress` index and file records, block on success, and print its own exact mark-ready command without changing repository bytes.
- [ ] Add root and generated-project behavior tests for eligible evidence, each incomplete-evidence form, deferred and replan_required states, index/file mismatch, ready-to-archive evidence messages, dirty and clean worktrees, --plans-only, invalid usage, read-only byte identity, and the unchanged ordinary completion transition.
- [ ] Run the root/template alignment check and record that only the installed command prefixes differ in the new report and invocation.
- [ ] Complete one independent read-only review and focused validation with zero unresolved High or Medium findings.

## Validation Notes

- Pre-activation synthetic repositories at `a60a0c7` confirmed that both gates exit zero and print `agent completion gate passed` for matching `in_progress` records with only checked tasks and non-pending Validation Notes.
- The Plan 251 commit immediately before archival still had one unchecked archive task, so it explains where the gap was noticed but is not evidence for the all-tasks-checked predicate.
- Implementation, no-mutation evidence, review, and validation remain pending.
