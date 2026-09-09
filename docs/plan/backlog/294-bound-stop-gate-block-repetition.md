# Bound stop-gate block repetition so a reported unresolvable retained state can end a turn

status: backlog
primary_invariant: The stop gate never withholds a turn indefinitely: after a bounded number of consecutive blocks that report the identical retained task state, it accepts the reported blocker as terminal, and it keeps blocking while that reported state still changes.
task_types:
  - hook_behavior
  - test_coverage
review_class: C
human_design_required: no
human_approval_status: pending
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"stop_review_gate.py has exactly one early return that can end the loop, the runtime-supplied stop_hook_active field, and no internal bound. On 2026-09-09 the same retained-task block was reissued eleven consecutive times while the ownership record, task worktree and temporary branch were all absent.","kind":"reproduced_defect"}
  - {"evidence":"tests/hooks/gates.py already drives stop_review_gate.py end to end in TaskWorktreeGateTest, and scripts/check-copier-template.py already enforces that the root and template hook copies stay identical, so both new behaviours are checked by existing commands.","kind":"existing_mechanism"}
completion_conditions:
  - The stop gate stops blocking once a bounded number of consecutive blocks have reported the identical retained task state, and the earlier attempts in that sequence still block.
  - The consecutive count resets whenever the reported retained state changes or no task worktree remains outstanding, so a changing state never consumes the bound.
  - The template copy of the stop gate carries the same bounded behaviour as the root copy and the copier template check accepts the pair.
completion_witness_map:
  - {"condition_sha256":"sha256:ee0de9f75a536d02e9b9d69a10fd9e6d5d9ec21c4a267e8d195aff655a87715a","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:487cddfe48776e6c5e1739f4cbbf174d4fc8b7574a644710e6773faf22904940","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:1d474ef0dd92935ca23b85ce4389fc070955e3a54cf3aa4372d4ee6b42c37ebf","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - .project-agent-workflow/hooks/stop_review_gate.py
  - tests/hooks/gates.py
  - template/.project-agent-workflow/hooks/stop_review_gate.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/project_workflow/worktree_guard.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_VALIDATION.md
focused_validation:
  - python3 tests/test-hooks.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - An agent that reports an unresolvable retained task state can end its turn instead of receiving the same instruction without limit.
  - A retained task worktree that can still be published or retired is withheld from success on its first attempts, so the gate keeps its original purpose.
  - A generated project receives the same bounded stop gate as this repository.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:29c55cbde3a720117a29d48f45a5a188dcca5c77b39d961b073f7b0b1fe8c5b5","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:3c1552027915962358512740ed6ab9d80387e571841738f5dd916fd8add00f54","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:8793390d30090749651b6b4cd3783774541e5b72e70b9473669b98d0818a09cc","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 解決不能な保持状態を報告したターンを終了できるよう、停止ゲートの連続ブロックに上限を設ける

## Decisions

- Bound the repetition inside the gate rather than relying only on the runtime-supplied stop_hook_active field, because that single external signal is the current sole loop breaker and its absence deadlocks the turn.
- Leave the block itself unchanged until the bound is reached, so a task worktree that can still be published or retired is still withheld from success.
- Key the count by repository identity and the digest of the exact block reason, and clear it whenever the reason changes or nothing is outstanding, so only a genuinely unchanging report consumes the bound.
- Add no separate branch for a remedy that cannot act: the gate already reports the worktree_present false case and names retire for it, and an absent ownership record produces no outstanding entry at all.
- Accept that a bounded release lets an agent reach success after repeated identical blocks. The gate's own message already names reporting the blocker as a valid response, and an unbounded block leaves no way to deliver that report.

## Tasks

- [ ] Add a bounded consecutive-block counter to the root stop gate, stored per repository identity and keyed by the digest of the block reason.
- [ ] Release the block and print an empty decision once the bound is reached, and clear the stored count when the reason changes or no task is outstanding.
- [ ] Mirror the change into the template copy of the stop gate so the two stay identical.
- [ ] Extend tests/hooks/gates.py to prove the withheld attempts, the bounded release, and both reset paths.
- [ ] Run the focused witnesses, then the authoritative suite once.

## Validation Notes
