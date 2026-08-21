# Certify exact-ref local apply

status: checked
task_types:
  - planning_docs
  - security
  - referent_first
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: low
implementation_ambiguity: low
implementation_mode: parent_direct
parent_direct_reason: independent acceptance mapping and validation lifecycle authority remain parent-owned
primary_invariant: the checked Plan 149 implementation satisfies every unchanged Plan 144 acceptance item with zero unresolved High or Medium finding
replan_source: docs/plan/active/144-implement-revalidated-local-apply.md
replan_contract: docs/plan/replanned/contracts/144-implement-revalidated-local-apply.json
integration_gates:
  - plan 149 must be checked and committed before certification starts
  - certification changes no executable behavior and must use a fresh independent review
  - plan 145 must not start until this certification is checked and committed
  - plan 146 must start only after plan 145 is checked and must verify the combined successors against every source acceptance item
successor_plans:
  - docs/plan/active/149-complete-exact-ref-local-apply.md
  - docs/plan/active/150-certify-exact-ref-local-apply.md
inherited_acceptance_digests:
  - sha256:6958ab89c494d1adfd48540a046650cf4cfc1672306d43e0c3a8ecd70264a26e
  - sha256:3005d6bd08511b36771d0469514d61f43c928fc57fffa9733d294dbac0e7e035
  - sha256:053494f2046950d1749673055c4e3d840b1991b2a51edac4b32e77b6f274b5ea
  - sha256:6b9408c8ebd718b6da2954363ee6624ada7af9791ff5e87981b92254f96ce759
  - sha256:3bf52a9421d768236116af7d7ad8e5a9d3d4c3339dd93dffd5992ded03dd477d
  - sha256:afc2af96b43affbae68ebf3ab4926a7e18429e9e6cb50e08c8351c958950965b
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
  - docs/plan/
context_files:
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/git-retirement.yaml
  - references/validation.md
  - scripts/retire-merged-worktrees.py
  - template/.project-agent-workflow/scripts/retire-merged-worktrees.py
  - tests/test-git-retirement.py
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
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
  - Require `--allowed-root` at runtime, reject the repository root, home directory, filesystem root, unresolved paths, and paths outside the exact allowed root, and never persist host-specific absolute worktree roots in reusable files.
  - Enumerate registered worktrees with Git plumbing and admit only a non-primary, non-current, unlocked, clean linked worktree on an exact local branch that is not protected and whose tip is an ancestor of one configured local merge-target ref.
  - Require an upstream for the local branch and block it when the upstream comparison has any ahead commits, is unavailable, or is ambiguous; do not fetch or claim remote freshness.
  - Treat elapsed time, branch naming, a missing provider pull request, and absence from the current worktree list as insufficient deletion evidence.
  - Write scan output only to an ignored local artifact path and include repository identity, exact canonical worktree path, branch full ref and tip OID, merge-target ref and OID, upstream relation, every eligibility result, schema version, and content digest.
  - Make `apply-local` accept an exact manifest path and exact allowed root, revalidate repository identity, canonical and symlink-safe paths, refs, pinned OIDs, upstream relation, worktree registration, lock and clean state, configuration, eligibility results, and digest immediately before each effect, and fail closed on any difference.
  - Remove the exact worktree first with `git worktree remove` without force; stop if that command fails; then delete only the exact local branch with `git branch -d`; never call filesystem removal, `git worktree remove --force`, or `git branch -D`.
  - Distinguish an already absent exact target from a changed or mismatched target without broadening the removal set, and keep repeated scans and applies deterministic.
  - Expose no remote-delete, force-delete, or destructive-prune command; `git worktree prune --dry-run --verbose` findings may be reported without applying them.
  - Keep scheduled automation read-only by permitting scan and report generation only; require a current explicit operator action for every local apply.
  - Keep root and generated CLI files byte-identical, keep the root and generated specifications semantically aligned, and document the intentional difference between enabled root policy and safe-disabled generated project configuration.
  - Add disposable-repository median, edge, negative, and untuned holdout scenarios for an eligible merged pair; current, primary, dirty, untracked, locked, outside-root, symlink-escaping, protected, upstream-ahead, untracked-upstream, and non-ancestor cases; changed branch or target OIDs and changed worktree state between scan and apply; rejected force and remote operations; and age- or name-only evidence.
  - Never run removal tests against the source repository; create every test repository and linked worktree under an isolated temporary directory and assert the source repository's registered worktrees and refs remain unchanged.
  - Keep provider-assisted squash or rebase integration evidence, remote branch deletion, and actual stale-worktree metadata pruning outside this implementation; require separate active plans and applicable authorization before adding them.
checked_summary_ja: checked済みapply実装を元の全受入条件へ対応付け、独立レビューと検証で安全境界を認証する。

## Context

Certify exact-ref local apply means the action of independently accepting the checked replacement implementation against every unchanged Plan 144 acceptance item before downstream integration.

This integration successor owns no new executable behavior. It certifies the checked Plan 149 replacement against every unchanged acceptance item inherited from stopped Plan 144.

## Decisions

- Reuse only the checked Plan 149 implementation.
- Independently exercise the exact branch-ref race, worktree HEAD lock, sanitized Git environment, disabled repository hooks, guarded branch deletion, strict manifest validation, exact-pair absence handling, unsupported-operation boundaries, disposable-repository isolation, and root/generated parity.
- Finish with zero unresolved High or Medium finding before downstream Copier or combined integration work starts.

## Tasks

- [x] Map checked Plan 149 behavior to all fifteen inherited acceptance items.
- [x] Run a fresh independent security review without changing product files.
- [x] Record focused and authoritative validation in a fresh parent-owned ledger.
- [x] Archive and commit this certification before Plan 145 begins.

## Validation Notes

- Do not remediate a product defect in this certification plan; classify it under the current plan workflow policy.
- Independent receipt `.agent-artifacts/reviews/150-apply-certification.md` mapped all fifteen acceptance items and reported Accept with High 0, Medium 0, and Low 1. The Low is a dedicated prepare/acquire-failure coverage opportunity, not a current correctness or source-acceptance defect.
- Parent ledger run `150-parent-direct-20260821` used `/home/rectaris/tmp/gakumasu-project/plan-execution-ledgers/150-candidate-lifecycle.json`, recorded one focused validation and exactly one authoritative validation, and remained active without a stop reason.
- Focused validation passed Python compilation, root/generated byte parity, and `git diff --check` without product changes.
- The authoritative run passed all 35 disposable-repository tests in 7.313 seconds, Python compilation, root/generated byte parity, and `git diff --check` without product changes.
- Parent behavior validation additionally runs python3 tests/test-git-retirement.py; the repository does not depend on pytest.
