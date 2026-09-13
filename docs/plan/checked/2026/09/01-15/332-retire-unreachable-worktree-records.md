# Remove ownership records no repository can ever reach again

status: checked
primary_invariant: A record is removed only when no existing repository can reproduce its identity, proven from a mounted filesystem rather than from an absent path, and every other record is left exactly as it was found.
task_types:
  - template_workflow
  - test_coverage
  - planning_docs
review_class: C
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The shared record directory reached 523 records against MAX_RECORDS_SCANNED = 512 during the v1.4.7 release. candidate_record_paths raised, and 33 tests failed for a reason outside the change under test.","kind":"reproduced_defect"}
  - {"evidence":"publish and retire unlink the record, but both need the repository the record names. Once that repository is gone no command can reach the record, so 139 records survive with no removal path.","kind":"reproduced_defect"}
  - {"evidence":"scripts/retire-merged-worktrees.py already carries the shape this needs: a versioned manifest with a content digest, deterministic ordering, full revalidation immediately before the effect, and a set that never widens.","kind":"existing_mechanism"}
  - {"evidence":"Classifying all 139 live records showed every one has its repository path absent while the nearest existing ancestor sits on the recorded device, so the filesystem is mounted and the repository is really gone.","kind":"bounded_prototype"}
completion_conditions:
  - scan reports a record as removable only when its lease expired beyond the grace period, its worktree is absent or reidentified, its repository is absent or reidentified, and each absent path has a nearest existing ancestor on that path's recorded device.
  - apply-local removes only the records one unchanged manifest names, revalidating every fact immediately before each unlink and stopping without widening the set when any fact changed.
  - The root retirement specification records the new authority and its template counterpart carries the same statement.
  - The guard names the removal command when it refuses an implausible record count, so the failure reports its own remedy.
completion_witness_map:
  - {"condition_sha256":"sha256:bdc7ef76589d4162be3bbb1f3f54700f3cb3939f507246ee788e7e25bb4a366c","witness":"python3 tests/test-stale-record-retirement.py"}
  - {"condition_sha256":"sha256:29c272edf5cfeb1c395f02511f21ab0d3a1b3874e6a8a1f015c2ac3434439595","witness":"python3 tests/test-stale-record-retirement.py"}
  - {"condition_sha256":"sha256:a343483dd1fe115c2f3927b30de56d2f306c3a2b85fee341ae979cfbac147133","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:878dc62df4da72d861db04d728d838f53d3b9778cd89aee141e81dc8fc6e9534","witness":"python3 tests/test-stale-record-retirement.py"}
write_scope:
  - scripts/retire-stale-worktree-records.py
  - tests/test-stale-record-retirement.py
  - scripts/lint-project-workflow.sh
  - scripts/project_workflow/copier_inventory.py
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - template/.project-agent-workflow/docs/agent/SPEC_GIT_RETIREMENT.md
  - template/.project-agent-workflow/scripts/retire-stale-worktree-records.py
  - scripts/check-copier-template.py
  - template/.project-agent-workflow/scripts/worktree_guard.py
  - scripts/check-root-agent-policy.py
  - scripts/project_workflow/worktree_guard.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/manage-plan-worktrees.py
  - scripts/retire-merged-worktrees.py
  - tests/AGENTS.md
  - scripts/AGENTS.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - references/validation.md
focused_validation:
  - python3 tests/test-stale-record-retirement.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A record left behind by a repository that no longer exists can be removed through an explicit operator action that proves the repository is gone rather than assuming it from an absent path.
  - A refusal caused by the record count tells the operator which command clears it, instead of leaving the remedy to be rediscovered.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b58a3415cf35a216c584d2fc4ea6176e3ce8cf68a567d87b25effa83be688e3b","stage":"focused","witness":"python3 tests/test-stale-record-retirement.py"}
  - {"acceptance_sha256":"sha256:11af2b038c755100091ba382b3e28747b07bf618144aabb712bed5f898038560","stage":"focused","witness":"python3 tests/test-stale-record-retirement.py"}
checked_summary_ja: 到達不能になった所有権記録を、ファイルシステムの存在を根拠に安全に除去する手段を設ける。

## Decisions

- Put the authority in its own script rather than in manage-plan-worktrees.py. The manager acts for the current task, and a record whose repository is gone belongs to no current task. retire-merged-worktrees.py is bounded by one repository and an allowed root, while these records live in an account-wide directory.
- Take an absent path as evidence of death only when the nearest existing ancestor sits on the device the record names. An absent path alone cannot tell a deleted repository from an unmounted disk; a matching ancestor device proves the filesystem is present and the path is really gone.
- Require the lease to have expired beyond a grace period. The guard already caps a lease at MAX_LEASE_SECONDS, so an expired lease is the guard's own statement that the record claims nothing, not a threshold invented here.
- Keep the grace period a constant in the script instead of a field in git-retirement.yaml. A configurable grace period can be shortened, and the existing configuration parser is validated for the merged-worktree workflow alone.
- Remove the record, journal, publication journal and lock for an eligible key, because leaving any of them keeps the key half present for a later reader to judge.
- Leave MAX_RECORDS_SCANNED unchanged. The limit is what made the leak visible, and raising it would postpone the next one.

## Tasks

- [x] Add scripts/retire-stale-worktree-records.py with a read-only scan that writes a digest-bearing manifest below .agent-artifacts/ and an apply-local that consumes one exact manifest.
- [x] Implement the eligibility test: lease expired beyond the grace period, worktree absent, repository absent, no symlink component, and for each absent path a nearest existing ancestor on the recorded device confirmed by the deepest covering mount.
- [x] Revalidate every manifest fact immediately before each move, and stop without widening the set when any fact changed.
- [x] Name the retirement command in the guard's implausible-count refusal.
- [x] Add tests/test-stale-record-retirement.py covering accepted, blocked, changed-state, idempotency and holdout cases against an isolated directory.
- [x] Register the script and its tests in lint-project-workflow.sh and the Copier inventory.
- [x] Record the new authority in SPEC_GIT_RETIREMENT.md and mirror it into the template.

## Validation Notes

`./scripts/lint-project-workflow.sh` and `./tests/smoke.sh` pass. `tests/test-stale-record-retirement.py` holds 59 tests. Every guard this plan adds was mutation-tested: each was replaced with a permissive variant and each replacement was killed by at least one test. Three guards survived their first mutation round and gained the tests that prove them; two tests that passed against a mutated implementation were rewritten, and one ordering guard that no reachable state could observe was deleted rather than covered artificially.

Six independent read-only `code-review` rounds were obtained. They changed the design twice.

The first round rejected treating a path that exists under a different device and inode as unreachable, because device numbers are not stable across a reboot; present paths are now never retirable. It also found that the command took the per-key lock and then unlinked it, that a non-regular sibling could leave a key partly deleted, and that manifest validation checked names but not types or provenance.

The third round showed that no local check can prove unreachability at all: the mount table describes one namespace, and a same-device bind mount or a reused device number defeats any device comparison. The plan's premise was that deletion needed proof. It does not need proof if it is not deletion. The command now MOVES a record, its journal and its publication journal into a `retired` directory beside them, and never touches the lock. A wrong verdict costs an operator one move: the guard still fails closed, the refusal is visible, and the bytes are intact.

Making retirement reversible moved the risk to visibility, and the later rounds closed it. A retired record that matches a live repository indicates a wrong retirement, so outstanding-task reporting reads the retired directory and labels each entry, every record-creating path refuses a retired key, and the stop gate names the restore instead of `publish` or `retire`, which both need the record that moved. The retired directory carries no count limit, because refusing on it would stop completion checks for every repository on the account and would push an operator to hide the only evidence that a retirement was wrong.

The final two rounds reproduced two races in that new reporting. A record can move while it is being enumerated, so enumeration reads live, retired and live again, resolves each name against both locations rather than trusting a scan result, and retries the live location after the retired one.

Residual, accepted: a repository whose device and inode are reused at the same path can match a retired record. The result is a labelled report and a refusal that names both ways out, never a deletion. Recording a non-reusable repository incarnation would need a record-schema change, which would not help the existing records this plan exists to clear.
