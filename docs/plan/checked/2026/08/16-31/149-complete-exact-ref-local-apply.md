# Complete exact-ref local apply

status: checked
task_types:
  - template_workflow
  - security
  - referent_first
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: ordinary
implementation_mode: parent_direct
parent_direct_reason: the local-effect executable and its deterministic safety tests are parent-owned validation authority under the current runner
primary_invariant: the exact local branch ref remains at the manifest OID from final candidate revalidation through completed ordinary worktree removal
replan_source: docs/plan/active/144-implement-revalidated-local-apply.md
replan_contract: docs/plan/replanned/contracts/144-implement-revalidated-local-apply.json
integration_gates:
  - plans 142, 147, and 148 must remain checked before replacement apply implementation resumes
  - every removal and race test must stay inside a disposable repository and preserve the source repository worktrees and refs
  - plan 150 must independently certify this checked implementation before plan 145 starts
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
  - scripts/retire-merged-worktrees.py
  - template/.project-agent-workflow/scripts/retire-merged-worktrees.py
  - tests/fixtures/git-retirement/holdout.json
  - tests/fixtures/git-retirement/scenarios.json
  - tests/test-git-retirement.py
context_files:
  - docs/plan/replanned/2026/08/16-31/112-retire-merged-local-worktrees.md
  - docs/plan/replanned/2026/08/16-31/144-implement-revalidated-local-apply.md
  - docs/plan/checked/2026/08/16-31/147-complete-exact-root-retirement-scan.md
  - docs/plan/checked/2026/08/16-31/148-certify-exact-root-retirement-scan.md
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
checked_summary_ja: manifestが固定したbranch refをworktree削除完了まで保持し、競合時にも別OIDの対象を削除しない。

## Context

Complete exact-ref local apply means the action of finishing the preserved apply candidate by holding the expected local branch ref through final revalidation and ordinary worktree removal.

This successor owns the preserved unaccepted Plan 144 candidate and the one remaining High finding.

A concurrent direct update of the checked-out local branch ref can currently occur after final candidate revalidation and before ordinary worktree removal. The replacement must exclude that update across the entire removal interval without changing the branch ref itself.

## Decisions

- Use a Git-owned prepared reference transaction to verify and hold the exact expected local branch ref across final revalidation and ordinary worktree removal.
- Abort the no-change transaction after worktree removal to release the ref lock.
- Keep the existing worktree HEAD lock, sanitized Git environment, disabled repository hooks, guarded ordinary branch deletion, strict manifest validation, exact-pair absence handling, and unsupported-operation boundaries.
- Preserve the stopped candidate and add a deterministic same-tree different-commit branch-update race scenario.

## Tasks

- [x] Hold the exact local branch ref at the manifest OID through final revalidation and completed ordinary worktree removal.
- [x] Fail closed without removing the worktree when the ref cannot be verified or held.
- [x] Add the direct branch-update race regression and keep root/generated executables byte-identical.
- [x] Review the preserved candidate against every inherited safety condition.
- [x] Complete independent security review, focused validation, and one authoritative validation run before acceptance.

## Validation Notes

- The stopped Plan 144 ledger run 144-parent-direct-20260821 ended in replan_required; do not reuse or reopen it.
- Parent ledger run `149-parent-direct-20260821` used `/home/rectaris/tmp/gakumasu-project/plan-execution-ledgers/149-candidate-lifecycle.json`, recorded focused validation and exactly one authoritative validation, and remained active without a stop reason.
- Independent review receipt `.agent-artifacts/reviews/149-apply-review-1.md` reported High 0, Medium 0, and Low 1. The Low finding is a dedicated coverage opportunity for transaction-prepare failure; the implementation already stops before worktree removal, and the inherited changed-OID behavior remains covered.
- Ledger event `independent-review-1` contains a receipt-digest transcription error. The immediately following `independent-review-receipt-correction` event records the actual receipt digest `sha256:63e2a8bdd01a9c83f06f3924876d938d1999fa5ec20ed5258201b55e05c05407`; no execution state or finding classification changed between the two events.
- Focused validation passed Python compilation, the same-tree different-commit branch-ref race test, root/generated byte parity, and `git diff --check`.
- The authoritative run passed all 35 disposable-repository tests in 7.697 seconds, Python compilation, root/generated byte parity, and `git diff --check`.
- Parent behavior validation additionally runs python3 tests/test-git-retirement.py; the plan command allowlist does not accept a newly introduced direct test path, and the repository does not depend on pytest.
