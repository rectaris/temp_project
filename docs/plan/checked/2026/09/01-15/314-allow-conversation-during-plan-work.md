# Allow conversation during plan work across sessions

status: checked
primary_invariant: Ending a conversation turn never requires completing repository work; publication, write ownership and plan completion remain enforced at their existing operation boundaries.
task_types:
  - hook_behavior
  - planning_docs
  - test_coverage
review_class: C
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Stop alone calls outstanding_tasks across the repository. PreTool checks only writes at effective cwd; distinct authoring and plan worktrees already coexist in tests/validation_tools/worktrees.py. Pre-commit and CI independently run the completion gate.","kind":"existing_mechanism"}
completion_conditions:
  - Stop returns an empty decision on its first and repeated calls with pending plans, retained worktrees, missing gates or failing checks, without changing retained state.
  - Separate authoring and implementation task worktrees remain preparable, with existing ownership and publication checks unchanged.
  - Root and generated projects receive the same advisory Stop behavior and documented session entry workflow.
completion_witness_map:
  - {"condition_sha256":"sha256:4c40df370d8379d3997812afcbc8f43b02ee0041dc30e70d485011ae33c7e04d","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:e8296b2caf5740bd2d3325caa901d9c0bf74f1e91b8b0e41950d91a95fb61d1c","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:3fe93aa01a1657659389f5b1de127b9702e91d7b12d8f1909113de90985525e7","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - .project-agent-workflow/hooks/stop_review_gate.py
  - template/.project-agent-workflow/hooks/stop_review_gate.py
  - tests/hooks/gates.py
  - scripts/check-copier-template.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - template/.project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/project_workflow/worktree_guard.py
  - scripts/manage-plan-worktrees.py
  - .githooks/pre-commit
  - tests/validation_tools/worktrees.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - references/validation.md
focused_validation:
  - python3 tests/test-hooks.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Users can converse during implementation and begin plan authoring or implementation from another session without Stop demanding repository-wide completion.
  - Separate-session entry retains task ownership, identifier allocation and publication protection.
  - Generated projects have the same conversation behavior and operating instructions.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:12e723c967e4ebb3ac297e43f43aa0b07ad602878b2b7d6f923919a85ff27f35","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:e655023d2b1c58768782619e6269b27fc7b93095e6b297ce104d43738a69ab6f","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:727a36c046e100cbbd3cbff645cb9ef5f407d0b22e39fb0c713c3bd78be47c98","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: プランの実装中にも会話を終え、別セッションで作業を開始できるようにする。

## Decisions

- Use bounded parent implementation with independent read-only review for the inseparable hook, policy and validation changes.
- Make Stop advisory for every turn without classifying message text or session identity. Keep the shared adapter and read-only diagnostics; bound subprocess waits and return an empty decision even if diagnostics fail.
- Stop reading or writing the obsolete repetition counter, preserving any existing local state. Keep pre-commit, CI, write guards and publication checks unchanged.
- Document separate-session direct-task preparation and committed-plan preparation, exclusive use of an existing task checkout and serial publication. Existing execution-group admission remains required for simultaneous plan implementation.

## Tasks

- [x] Replace Stop blocking and repetition persistence with bounded read-only reminders in both adapter copies.
- [x] Align root/generated communication and workflow policy and document separate-session entry.
- [x] Update Stop regression cases and parity assertions while retaining write and commit boundary tests.
- [x] Obtain independent review, run focused and authoritative checks, commit and publish the accepted change.

## Validation Notes

- Owner request on 2026-09-12 explicitly asks to allow conversation during implementation and start plan creation or implementation from a separate session.
- Stop now returns one empty decision on the first and every later turn, including absent/failing gates, malformed input or guard reports and diagnostic timeouts. It preserves task records and ignores legacy repetition state without deleting it.
- Added root/generated separate-session instructions using existing direct-task and published-plan preparation. Same-task concurrent writers, execution-group admission, review budgets and publication refusals remain governed by their existing rules.
- Read-only exploration confirmed that separate task preparation already works and isolated the repository-wide Stop enumeration as the interference. Independent read-only change review reported no High or Medium findings; the parent accepted the exact eight-file diff after checking its invariants and focused witnesses.
- Focused validation passed: python3 tests/test-hooks.py (122 tests), python3 tests/test-validation-tools.py (302 tests), python3 scripts/check-copier-template.py, python3 scripts/check-root-agent-policy.py and git diff --check.
- Authoritative validation passed once for this accepted implementation: scripts/lint-project-workflow.sh and tests/smoke.sh. Smoke rendered generated projects and ended with smoke test passed.
- Implementation commit: 0d6a54e. Publication of the checked descendant commit and retirement of this task worktree are the final manager transaction; no remote push is authorized or performed.
- Diagnostic timeouts bound the directly launched process. A custom gate that starts descendants may leave those processes running after a timeout; the shipped checks remain read-only and this does not delay the Stop response.
