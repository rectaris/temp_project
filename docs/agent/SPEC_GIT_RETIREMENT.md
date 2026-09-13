# Local Git Worktree And Branch Retirement

This specification governs local inspection and removal of registered linked worktrees and their checked-out local branches.

It does not authorize remote branch deletion, provider writes, force deletion, or filesystem removal.

It authorizes retirement of an ownership record only through the bounded command and conditions in `Unreachable Ownership Record Retirement` below.

## Configuration

The project-owned configuration is `docs/agent/git-retirement.yaml`.

Schema version 1 contains these fields:

- `version`: the integer `1`.
- `enabled`: a boolean that must be `true` before `scan` or `apply-local` can admit a target.
- `merge_target_refs`: one or more exact full local refs such as `refs/heads/dev` when enabled.
- `protected_local_branch_refs`: one or more exact full local branch refs that cannot be retired when enabled.

An empty ref list, a short branch name, a non-local ref, an unresolved ref, or `enabled: false` makes the configuration ineligible for both subcommands.

The template seeds generated projects with `enabled: false` and empty ref lists.

Each generated project must select its own merge targets and protected branches before enabling this workflow.

The template-development repository intentionally enables the workflow, selects its local integration ref, and protects `refs/heads/main` and `refs/heads/dev`.

Reusable policy and configuration must not contain a host-specific absolute worktree root.

## Task Worktree Retirement

A worktree prepared by `scripts/manage-plan-worktrees.py` for the current task is retired by that manager, not by this workflow.

`scripts/manage-plan-worktrees.py publish` automatically removes the exact successfully published current task worktree and its temporary local branch as the final step of one checked publication transaction. It runs those removals from the pre-existing checkout, so the transaction never depends on the directory it deletes.

`scripts/manage-plan-worktrees.py retire` removes a task worktree this transaction did not publish. It refuses unpublished commits, and `--stopped` removes only an effect-free stopped checkout.

Every other worktree stays under this specification: retirement remains an explicit operator action for any worktree not proven to be the exact successfully published current task.

## Command Boundary

`scripts/retire-merged-worktrees.py scan` is read-only and `scripts/retire-merged-worktrees.py apply-local` is an explicit local effect.

Both subcommands use the same configuration parser, eligibility implementation, and manifest schema.

Neither subcommand fetches, pushes, deletes a remote ref, queries a provider, or claims that local upstream information is remotely fresh.

Scheduled automation may run `scan` and report its local artifact.

Scheduled automation must not run `apply-local`.

Every `apply-local` invocation requires a current explicit operator action.

## Allowed Root

Both subcommands require `--allowed-root` as a runtime argument.

The command resolves the argument and every candidate path strictly before use.

It rejects an unresolved path, a symlink component, the filesystem root, the current user's home directory, the primary repository root, and any candidate that is not a strict descendant of the exact allowed root.

The allowed root is runtime-only and must not be written to reusable specifications, templates, or project configuration.

## Read-Only Scan

`scan` enumerates registered worktrees with Git plumbing.

It may report `git worktree prune --dry-run --verbose` findings, but it must not run non-dry-run prune.

A candidate is one registered worktree and the exact local branch checked out there.

The candidate is eligible only when every condition below is true:

- It is a linked worktree and not the primary worktree.
- It is not the current worktree.
- It is not locked.
- Its tracked and untracked worktree state is clean.
- Its canonical path is a strict symlink-safe descendant of the exact allowed root.
- It is attached to one exact full `refs/heads/*` branch.
- Its branch is not configured as protected.
- Its branch tip is an ancestor of at least one configured local merge-target ref.
- Its local branch has one resolvable upstream.
- The local upstream comparison is unambiguous and reports zero commits ahead.

Elapsed time, branch naming, a missing provider pull request, and absence from a current worktree list are insufficient deletion evidence.

The scan artifact must be written below `.agent-artifacts/git-retirement/` in the primary repository and remain ignored by Git.

The versioned JSON manifest records the repository identity, exact canonical worktree path, branch full ref and tip OID, selected merge-target ref and OID, upstream ref and ahead/behind relation, every eligibility result, schema version, and a content digest.

Manifest ordering and digest calculation must be deterministic.

## Explicit Local Apply

`apply-local` accepts one exact manifest path and the same exact allowed root.

It verifies the manifest schema and content digest before using any manifest field.

Immediately before worktree removal, it revalidates repository identity, canonical and symlink-safe paths, configuration, registered worktree identity, current and primary exclusions, lock state, tracked and untracked cleanliness, branch ref, branch tip OID, merge-target ref and OID, ancestry, upstream ref and relation, every eligibility result, and the allowed-root boundary.

Any changed, missing, unavailable, ambiguous, or mismatched fact stops the operation without broadening the target set.

An already absent exact worktree and branch pair is reported separately from a changed or mismatched target.

For an unchanged eligible target, the command first runs `git worktree remove` for the exact path without force.

If worktree removal fails, the command stops and does not attempt branch deletion.

Immediately before branch deletion, it revalidates repository identity, configuration, exact branch ref and tip OID, merge-target ref and OID, ancestry, upstream ref and relation, and that the exact removed worktree path is no longer registered.

After successful worktree removal, the command runs `git branch -d` for the exact local branch.

It never calls filesystem removal, `git worktree remove --force`, `git branch -D`, remote deletion, or non-dry-run worktree prune.

Repeated scans and applies must remain deterministic and must not expand the removal set.

## Unreachable Ownership Record Retirement

`scripts/manage-plan-worktrees.py` unlinks the ownership record it owns, and needs the repository that record names to do it.

A record whose repository no longer exists outlives every command that could reach it, and enough of them push the shared directory past the count at which the guard refuses to read it.

`scripts/retire-stale-worktree-records.py scan` is read-only and `scripts/retire-stale-worktree-records.py apply-local` is an explicit local effect.

Both subcommands require `--state-directory` as a runtime argument, so the directory about to be changed is named rather than assumed.

The command refuses a directory that is the filesystem root, the current user's home directory, not owned by the current user, readable by others, or reached through a symlink component.

Retirement moves a record aside instead of unlinking it, because absence of a path is evidence that a repository is gone and never proof of it. The command reads one mount namespace, and device numbers are reused across reboots, so no local check can establish that nothing anywhere can still reach the repository.

Keeping the bytes is what makes the evidence below sufficient. A wrong verdict costs an operator one move rather than the ownership record: the guard keeps failing closed, the refusal is visible, and the record can be put back byte for byte.

A record is retirable only when every condition below is true:

- The record is readable and valid under the guard's own record schema.
- Its filename equals the key the guard derives from the record's own repository identity and task selector.
- Its lease expired more than the command's fixed clock-skew allowance ago.
- Its worktree is absent.
- Its repository common Git directory is absent.
- Neither of those paths passes through a symlink at any component.
- For each of those paths, the nearest existing ancestor reports the device the record itself recorded, and the deepest current mount covering the path carries that same device.

A path that still exists is never treated as unreachable, whatever its device and inode now report. Device numbers are not stable across a reboot, so reading a mismatch as a different object would retire the record of a task that is still present.

The ancestor and mount conditions raise the cost of a wrong verdict; they do not remove it. A same-device bind mount, a reused device number, and a repository held in another mount namespace can all satisfy them.

The command refuses to judge anything when the mount table cannot be read.

The clock-skew allowance is a constant in the command. It is not configuration, because a configurable allowance can be shortened.

Retirement covers the record, its journal, and its publication journal, because leaving any of them keeps the key half present. All three move into a `retired` directory below the record directory, which the guard does not read.

Retirement for one key runs under the same per-key lock the task worktree manager takes for prepare, resume, publish, and retire.

The lock file is never moved or unlinked. It is the mutual-exclusion primitive itself, so removing it while holding it would let a second process create and lock a new file of that name and believe it held the key. A lock left beside no record is inert and is not counted against the record limit.

A key whose record is already gone is reported without taking its lock, so repeated runs leave no new lock files behind.

Every file the key owns is checked before any of them moves, the destination name must be free, and the record itself moves last, so a refusal partway through leaves the key accounted for by the record that describes it.

Restoring a retired record is moving its files back into the record directory. The command never writes to the `retired` directory except to place files in it.

A retired record stays visible where a wrong verdict would otherwise be silent. A correctly retired record names a repository that no longer exists, so it does not match a live repository identity. A record that does match indicates the retirement was wrong, or that a new repository reuses the device and inode of a deleted one at the same path. Either way it is a prompt to look, not a proof.

Outstanding-task reporting therefore reads the `retired` directory as well and labels each entry, so a completion check cannot pass while a real task is unfinished.

A record can move between the live and the retired directory while outstanding work is being enumerated, so reading each directory once is not enough: whichever is read first can lose a record that moves out of it afterwards, and no single order is safe in both directions. Enumeration reads the live directory, the retired directory, and the live directory again. Each name it collects is then resolved against the live location, the retired location, and the live location once more, because a restore between the first two reads would otherwise leave both looking at an empty path. One move in either direction cannot hide a record.

A retired directory that exists but cannot be read is an error, never an empty answer. Reporting nothing would hide exactly the mistakes this enumeration exists to show, so a symlinked, dangling, or non-directory path is refused.

Every path that creates an ownership record refuses a task whose record is retired, and the refusal names the retired path and both ways out, so a second record is never created for one task.

The stop gate reports a retired entry with the recovery it needs. Publication and retirement both load the record from its live location, so neither can run until the record is put back.

Retired records carry no count limit. The live limit exists because an implausible count there means the directory is wrong, and failing closed costs one repository. A large retired directory is ordinary, and refusing on it would stop completion checks for every repository on the account. It would also push an operator to move aside the only evidence that a retirement was wrong.

A record the command cannot read is reported and left in place. A file that is not named like a record is never considered.

`scan` writes one versioned JSON manifest below `.agent-artifacts/git-retirement/` recording the record directory, every candidate key, its task label, the recorded worktree and repository paths, the lease expiry, every eligibility result, and a content digest.

Manifest ordering and digest calculation must be deterministic.

`apply-local` accepts one exact manifest path directly below `.agent-artifacts/git-retirement/`, opens it without following a symlink at any component, reads at most the size bound, and verifies its schema, field types, and content digest before using any field.

It refuses a manifest produced for another record directory, a candidate whose verdict disagrees with its own recorded evidence, and a candidate naming any file outside its own key.

Immediately before each move it derives every eligibility fact again and requires the result to equal the manifest entry exactly.

Any changed, missing, or mismatched fact stops that candidate without broadening the set.

An already absent record is reported separately from one that changed since the scan.

Repeated scans and applies must remain deterministic and must not expand the retirement set.

Scheduled automation may run `scan`. Scheduled automation must not run `apply-local`.

## Validation Isolation

Every retirement test creates its repository and linked worktrees below an isolated temporary directory.

Tests snapshot the source repository's registered worktrees and refs before and after execution and require them to remain unchanged.

Fixtures must cover accepted, blocked, state-change, path-boundary, unsupported-operation, idempotency, and untuned holdout cases.

Provider-assisted squash or rebase evidence and remote branch deletion require separate active plans and applicable authorization.
