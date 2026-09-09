# Complete effect-adjacent manifest revalidation

status: checked
task_types:
  - template_workflow
  - security
  - referent_first
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: low
implementation_mode: parent_direct
parent_direct_reason: the local-effect executable and its deterministic safety tests are parent-owned validation-authority paths
primary_invariant: the exact canonical manifest file parses to the unchanged startup manifest with a valid content digest immediately before each local deletion effect
replan_source: docs/plan/active/146-integrate-local-git-retirement.md
replan_contract: docs/plan/replanned/contracts/146-integrate-local-git-retirement.json
integration_gates:
  - plans 142, 145, 147, 148, 149, and 150 must remain checked before product correction starts
  - every removal and manifest-race test must stay inside a disposable repository and preserve the source repository worktrees and refs
  - plan 152 must start only after this implementation is checked and committed
successor_plans:
  - docs/plan/active/151-complete-effect-adjacent-manifest-revalidation.md
  - docs/plan/active/152-certify-integrated-local-git-retirement.md
inherited_acceptance_digests:
  - sha256:6958ab89c494d1adfd48540a046650cf4cfc1672306d43e0c3a8ecd70264a26e
  - sha256:945e37cf14543bb37e02cafb153b2d8c528eb174970a10995e7647ced980d35e
  - sha256:5d9b1cae94a56d755c5dd22deab898f8776227ffd1fa908adb706c5890afa72b
  - sha256:fb5c41fc615e6e548dee36f7eadd970cd746570e8e97507c8bdbbf2db2d2b5bf
  - sha256:4d44ce23a04fa81fd22ea1684cdfa307ccb916558b04ff2f936fa8e9f0d19177
  - sha256:31b60f932bf07f6ee1589f786f849e78eebbddec7625a95690026e5aa29f7bce
  - sha256:dab3be427e961b4584d9e634104eba538cd644eaf9e8657f25558acda39895cf
  - sha256:a2b23ff25475494004da91dd894d47a90e42ef06c9de39a3b3a4b7a70573a433
  - sha256:ac0c3d8d8604109b7a1cde9b1e4d553fbeada2fa2c29362b11f04ebf3971bf4f
  - sha256:3688d2080c082315da128caac3e8acf11b8dab8aa552a4490a66c34d0c2277aa
write_scope:
  - scripts/retire-merged-worktrees.py
  - template/.project-agent-workflow/scripts/retire-merged-worktrees.py
  - tests/test-git-retirement.py
context_files:
  - docs/plan/replanned/2026/08/16-31/112-retire-merged-local-worktrees.md
  - docs/plan/replanned/2026/08/16-31/146-integrate-local-git-retirement.md
  - docs/plan/checked/2026/08/16-31/149-complete-exact-ref-local-apply.md
  - docs/plan/checked/2026/08/16-31/150-certify-exact-ref-local-apply.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/git-retirement.yaml
  - references/validation.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 -m py_compile scripts/retire-merged-worktrees.py template/.project-agent-workflow/scripts/retire-merged-worktrees.py tests/test-git-retirement.py
  - git diff --check
parent_behavior_validation:
  - python3 tests/test-git-retirement.py
validation:
  - python3 -m py_compile scripts/retire-merged-worktrees.py template/.project-agent-workflow/scripts/retire-merged-worktrees.py tests/test-git-retirement.py
  - git diff --check
acceptance:
  - Provide one root and generated CLI with separate read-only `scan` and explicit `apply-local` subcommands that share one manifest schema and eligibility implementation.
  - Make `apply-local` accept an exact manifest path and exact allowed root, revalidate repository identity, canonical and symlink-safe paths, refs, pinned OIDs, upstream relation, worktree registration, lock and clean state, configuration, eligibility results, and digest immediately before each effect, and fail closed on any difference.
  - Remove the exact worktree first with `git worktree remove` without force; stop if that command fails; then delete only the exact local branch with `git branch -d`; never call filesystem removal, `git worktree remove --force`, or `git branch -D`.
  - Distinguish an already absent exact target from a changed or mismatched target without broadening the removal set, and keep repeated scans and applies deterministic.
  - Expose no remote-delete, force-delete, or destructive-prune command; `git worktree prune --dry-run --verbose` findings may be reported without applying them.
  - Keep scheduled automation read-only by permitting scan and report generation only; require a current explicit operator action for every local apply.
  - Keep root and generated CLI files byte-identical, keep the root and generated specifications semantically aligned, and document the intentional difference between enabled root policy and safe-disabled generated project configuration.
  - Add disposable-repository median, edge, negative, and untuned holdout scenarios for an eligible merged pair; current, primary, dirty, untracked, locked, outside-root, symlink-escaping, protected, upstream-ahead, untracked-upstream, and non-ancestor cases; changed branch or target OIDs and changed worktree state between scan and apply; rejected force and remote operations; and age- or name-only evidence.
  - Never run removal tests against the source repository; create every test repository and linked worktree under an isolated temporary directory and assert the source repository's registered worktrees and refs remain unchanged.
  - Keep provider-assisted squash or rebase integration evidence, remote branch deletion, and actual stale-worktree metadata pruning outside this implementation; require separate active plans and applicable authorization before adding them.
checked_summary_ja: exact manifest pathの内容とdigestを各local削除effectの直前に再検証し、起動時snapshotとの差を閉じて拒否する。

## Context

Complete effect-adjacent manifest revalidation means re-reading and validating the exact manifest immediately before both local deletion commands while retaining the startup snapshot as authority.

The accepted CLI validates the manifest and its content digest at startup and safely pins all effects to that immutable in-memory value.

The source acceptance additionally requires the exact manifest path and digest to be revalidated immediately before each deletion effect. This successor closes only that compliance gap.

## Decisions

- Revalidate the exact canonical manifest input path, schema, and content digest immediately before `git worktree remove` and immediately before `git branch -d`.
- Require the re-read manifest value to equal the startup-validated manifest exactly; do not adopt new manifest bytes during an invocation.
- Perform the worktree-effect revalidation while the existing worktree HEAD lock and exact branch-ref transaction are held.
- Preserve the existing exact-ref lock, Git environment sanitization, disabled repository hooks, guarded branch deletion, strict schema, exact-pair absence behavior, and unsupported-operation boundaries.

## Tasks

- [x] Add one fail-closed helper that revalidates the exact manifest path and compares the parsed digest-valid value to the startup snapshot.
- [x] Invoke it immediately before each deletion command without releasing the existing target locks.
- [x] Add deterministic manifest replacement or mutation races before worktree removal and before branch deletion, and assert the pending command is not invoked.
- [x] Keep root and generated executables byte-identical and mode `0755`.
- [x] Complete parent diff review, independent security review, focused validation, and one authoritative behavior validation before acceptance.

## Validation Notes

- The stopped Plan 146 ledger run `146-parent-direct-20260821` ended in `replan_required`; do not reuse or reopen it.
- Initialize a fresh parent-owned execution ledger and candidate lifecycle before changing product files.
- Parent behavior validation additionally runs `python3 tests/test-git-retirement.py`; the repository does not depend on pytest.
- Parent ledger run `151-parent-direct-20260821` used `/home/rectaris/tmp/gakumasu-project/plan-execution-ledgers/151-candidate-lifecycle.json`, recorded one focused validation and exactly one authoritative validation, and remained active without a stop reason.
- Independent review round 1 reported High 0, Medium 1, and Low 1 because path validation and file opening were not descriptor-bound. The bounded correction added descriptor-relative nonblocking no-symlink traversal, regular-file enforcement, and two-read inode/byte equality.
- Independent review round 2 reported Accept with High 0, Medium 0, and Low 2. The Low findings are direct descriptor-walk/FIFO coverage precision and the previously recorded prepared-transaction acquisition coverage opportunity, not current correctness or source-acceptance defects.
- Focused validation passed Python compilation, root/generated byte parity, and `git diff --check`.
- The authoritative run passed all 39 disposable-repository tests in 7.912 seconds, Python compilation, root/generated byte parity, and `git diff --check`.
