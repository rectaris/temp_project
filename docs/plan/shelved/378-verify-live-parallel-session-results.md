# Verify live parallel-session results

status: shelved
shelved_reason: Owner instruction 2026-09-25: 374 以外の関連プランはすべて棚上げして良い. The live two-session acceptance it held returns to a plan 374 successor, so this destination is superseded.
shelved_at: 2026-09-25
primary_invariant: Only runtime-proven distinct sessions with overlapping implementation work and verified publication and retirement can satisfy the deferred live parallel-session acceptance.
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
  - {"evidence":"Plan 374 already defines the bounded read-only verifier, required-evidence record, transcript-first evidence rules, and deterministic lifecycle tests needed before the live run.","kind":"existing_mechanism"}
  - {"evidence":"The plan-374-descope-001 ledger event preserves this exact acceptance digest and defers it to this exact backlog path without changing the source invariant or authority boundaries.","kind":"existing_mechanism"}
  - {"evidence":"The plan 374 implementation branch is preserved locally with the unpublished verifier and integration changes; this plan starts only after the retained plan 374 work is accepted and published.","kind":"existing_mechanism"}
completion_conditions:
  - Two real sessions overlap implementation in distinct task worktrees and publish A then B with both changes retained and completed tasks retired; a pre-implementation plan/acceptance-bound required-evidence record and verified live report gate completion even without the environment variable.
completion_witness_map:
  - {"condition_sha256":"sha256:78d5a40ddf9da07975330961711334ee747e8bdf119961e1373ab28b57c42411","witness":"tests/root-plan-lifecycle.sh"}
write_scope:
  - scripts/verify-parallel-plan-sessions.py
  - template/.project-agent-workflow/scripts/verify-parallel-plan-sessions.py
  - tests/root-plan-lifecycle.sh
  - tests/test-sandboxed-plan-worker.py
  - docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md
preservation_scope:
  - none
context_files:
  - docs/plan/active/374-publish-and-verify-separate-session-plan-results.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - references/orchestration.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - tests/root-plan-lifecycle.sh
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Two real sessions overlap implementation in distinct task worktrees and publish A then B with both changes retained and completed tasks retired; a pre-implementation plan/acceptance-bound required-evidence record and verified live report gate completion even without the environment variable.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:78d5a40ddf9da07975330961711334ee747e8bdf119961e1373ab28b57c42411","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
integration_gates:
  - Start only after plan 374 is checked with its three retained acceptance items and its implementation is published.
  - Use two real operator-started sessions in distinct managed task worktrees; fixtures, synthetic events, candidate-only runs, and one session playing both roles do not satisfy acceptance.
  - Initialize the plan/acceptance-bound required-evidence record before implementation and preserve primary transcript bytes outside the repository.
  - Keep publication, final review acceptance, validation, lifecycle updates, and retirement serialized under the integration owner.
checked_summary_ja: 異なる実セッションの作業重複、順次公開、変更保持、終了処理を一次証跡で検証する。

## Decisions

- This plan contains exactly the acceptance item deferred by `plan-374-descope-001`; it neither weakens nor rewrites that requirement.
- Treat unavailable primary transcript evidence or unavailable real sessions as a blocker, not as permission to use mock evidence.
- Reuse the verifier and required-evidence mechanism accepted with plan 374. Limit repository changes to defects exposed by the live run and keep root/generated mirrors aligned.
- Preserve raw transcripts and runtime artifacts outside the repository. Commit only bounded verifier, test, or policy corrections required to make the exact live evidence verifiable.

## Tasks

- [ ] Confirm plan 374 is checked and its retained implementation is published before activation.
- [ ] Initialize the required-evidence record bound to this plan and the unchanged acceptance digest.
- [ ] Run two real operator-started implementation sessions in distinct managed task worktrees with overlapping implementation intervals.
- [ ] Publish A then B, verify both changes at the final tip, and retire both completed task worktrees without losing evidence.
- [ ] Bind the verified report and primary transcript digests, then run focused and authoritative validation.
- [ ] Complete only after independent review clears High and Medium findings for any repository change made by this plan.

## Validation Notes

- Origin: bounded descope of plan 374. The source ledger records this exact backlog path and acceptance digest.
- Owner authorization: the owner selected “plan 374 の停止状態と index を別タスクで整合し、その後 367 を再開”.
