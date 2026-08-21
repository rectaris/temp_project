# Local Git Worktree And Branch Retirement

This specification governs local inspection and removal of registered linked worktrees and their checked-out local branches.

It does not authorize remote branch deletion, provider writes, force deletion, filesystem removal, or destructive stale-worktree metadata pruning.

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

## Validation Isolation

Every removal test creates its repository and linked worktrees below an isolated temporary directory.

Tests snapshot the source repository's registered worktrees and refs before and after execution and require them to remain unchanged.

Fixtures must cover accepted, blocked, state-change, path-boundary, unsupported-operation, idempotency, and untuned holdout cases.

Provider-assisted squash or rebase evidence, remote branch deletion, and actual stale-worktree metadata pruning require separate active plans and applicable authorization.
