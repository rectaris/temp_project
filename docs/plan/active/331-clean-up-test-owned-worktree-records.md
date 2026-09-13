# Make each test remove the ownership records it created, so a validation run leaves the shared record directory as it found it.

status: in_progress
primary_invariant: A validation run leaves no ownership record for the task worktrees its own tests created, so repeated runs cannot drive the shared record directory toward the count at which the guard refuses to read it.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 1
implementation_risk: low
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The shared record directory held 523 records against MAX_RECORDS_SCANNED = 512 during the v1.4.7 release, so the guard failed closed and 33 tests failed for a reason outside the change under test. After the directory was emptied it reached 93 records again, every one of them dead.","kind":"reproduced_defect"}
  - {"evidence":"Measured per run: tests/test-hooks.py adds 9 records and tests/test-sandboxed-plan-worker.py adds 3. tests/test-validation-tools.py and tests/test-copier-adoption.py add none, so the leak is confined to the two suites that call manage-plan-worktrees.py prepare.","kind":"reproduced_defect"}
  - {"evidence":"tests/hooks/support.py bind_direct_task_worktree already derives the record, journal and lock paths through guard.metadata_paths and returns them, and every caller is a unittest.TestCase, so addCleanup can remove exactly those paths without any new discovery mechanism.","kind":"existing_mechanism"}
completion_conditions:
  - Every test that prepares a task worktree removes the record, journal and lock files it created, and a regression test proves that an inner test case leaves none of those three paths behind.
completion_witness_map:
  - {"condition_sha256":"sha256:90c9f1fd021e305ebee5b4f72148eea9bc7713a3eaf6952cf738d5bb29d907b1","witness":"python3 tests/test-hooks.py"}
write_scope:
  - tests/hooks/support.py
  - tests/hooks/gates.py
  - tests/test-sandboxed-plan-worker.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - tests/AGENTS.md
  - scripts/AGENTS.md
  - docs/plan/checked/2026/09/01-15/330-check-tracked-text-hygiene-locally.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - references/validation.md
focused_validation:
  - python3 tests/test-hooks.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Running the validation suite repeatedly no longer moves the shared ownership-record directory toward the count at which the guard refuses to read it, because each test removes the records it created rather than leaving them for a later owner to find and judge.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:10e905c6b0e9faf37b0f9422667eccbb692f24defe97419aaea87a771be54850","stage":"focused","witness":"python3 tests/test-hooks.py"}
checked_summary_ja: テストが自ら作成した所有権記録を後始末し、検証実行が共有ディレクトリを元の状態で残すようにする。

## Decisions

- Let the fixture that creates a record remove it, rather than adding a command that prunes records it did not create. SPEC_GIT_RETIREMENT.md keeps destructive stale-worktree metadata pruning outside the retirement authority, and cleanup by the creator raises no question about whose record is being judged.
- Require the TestCase as an argument of bind_direct_task_worktree instead of accepting an optional one, so a caller that forgets cleanup fails immediately rather than leaking quietly.
- Prove the cleanup by running an inner test case and checking that its three paths are gone, rather than by comparing counts in the shared directory, so the regression test does not depend on what else ran before it.
- Leave the guard's own record-count limit unchanged. The limit is what made the leak visible, and raising it would hide the next leak instead of removing this one.

## Tasks

- [ ] Give bind_direct_task_worktree the TestCase that calls it and register removal of the record, journal and lock paths through addCleanup.
- [ ] Update every caller in tests/hooks/gates.py to pass its test case.
- [ ] Register the same cleanup for the prepare helper in tests/test-sandboxed-plan-worker.py, which currently discards the record paths.
- [ ] Add a regression test that runs an inner test case binding a task worktree and asserts that none of its three record paths survive.

## Validation Notes
