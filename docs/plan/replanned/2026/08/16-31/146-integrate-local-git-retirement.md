# Integrate local Git retirement

status: replanned
task_types:
  - planning_docs
  - template_workflow
  - security
  - referent_first
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: low
implementation_mode: parent_direct
parent_direct_reason: final acceptance validation lifecycle and reporting authority remain parent-owned
replan_reason_codes:
  - multiple_independent_invariants
write_scope:
  - CHANGELOG.md
  - docs/plan/
context_files:
  - docs/plan/replanned/2026/08/16-31/112-retire-merged-local-worktrees.md
  - docs/plan/replanned/2026/08/16-31/143-implement-read-only-retirement-scan.md
  - docs/plan/replanned/2026/08/16-31/144-implement-revalidated-local-apply.md
  - docs/plan/checked/2026/08/16-31/147-complete-exact-root-retirement-scan.md
  - docs/plan/checked/2026/08/16-31/148-certify-exact-root-retirement-scan.md
  - docs/plan/checked/2026/08/16-31/149-complete-exact-ref-local-apply.md
  - docs/plan/checked/2026/08/16-31/150-certify-exact-ref-local-apply.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/git-retirement.yaml
  - references/validation.md
  - scripts/retire-merged-worktrees.py
  - template/.project-agent-workflow/ownership.yaml
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
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 -m py_compile scripts/retire-merged-worktrees.py template/.project-agent-workflow/scripts/retire-merged-worktrees.py tests/test-git-retirement.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - git diff --check
acceptance:
  - Provide one root and generated CLI with separate read-only `scan` and explicit `apply-local` subcommands that share one manifest schema and eligibility implementation.
  - Make generated project configuration safe-disabled by default; require each project to configure merge-target refs and protected local branches before scanning or applying, while the root repository explicitly protects `main` and `dev` and selects its local merge target.
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
  - Add the new managed files to Copier ownership and inventory checks while preserving project-owned retirement configuration byte-for-byte through supported Copier updates.
  - Add disposable-repository median, edge, negative, and untuned holdout scenarios for an eligible merged pair; current, primary, dirty, untracked, locked, outside-root, symlink-escaping, protected, upstream-ahead, untracked-upstream, and non-ancestor cases; changed branch or target OIDs and changed worktree state between scan and apply; rejected force and remote operations; and age- or name-only evidence.
  - Never run removal tests against the source repository; create every test repository and linked worktree under an isolated temporary directory and assert the source repository's registered worktrees and refs remain unchanged.
  - Route cleanup requests through the new specification in root and generated agent policy, record the behavior under Unreleased, run all validation commands, and finish with zero unresolved High or Medium independent-review findings.
  - Keep provider-assisted squash or rebase integration evidence, remote branch deletion, and actual stale-worktree metadata pruning outside this implementation; require separate active plans and applicable authorization before adding them.
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/146-integrate-local-git-retirement.md
replan_contract: docs/plan/replanned/contracts/146-integrate-local-git-retirement.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/151-complete-effect-adjacent-manifest-revalidation.md
  - docs/plan/active/152-certify-integrated-local-git-retirement.md
inherited_acceptance_digests:
  - sha256:6958ab89c494d1adfd48540a046650cf4cfc1672306d43e0c3a8ecd70264a26e
  - sha256:27f9713e8bde723f894fc8c6ebf44f0daf5109f16c4502b16dddf1a9fbd92557
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
  - sha256:a24659ceb636d526e4ad01d26f86c6a0ba7a74cea99d59481fdd36229d35816f
  - sha256:a2b23ff25475494004da91dd894d47a90e42ef06c9de39a3b3a4b7a70573a433
  - sha256:ac0c3d8d8604109b7a1cde9b1e4d553fbeada2fa2c29362b11f04ebf3971bf4f
  - sha256:e68c131cb92d4f444edaa9257ee5f16e677e808ba07c64b631a7b8410a842695
  - sha256:3688d2080c082315da128caac3e8acf11b8dab8aa552a4490a66c34d0c2277aa
checked_summary_ja: 分割した実装を統合し、元planの全受入条件と安全条件を変更せずに検証する。

## Context

This integration successor owns the Unreleased entry and no new executable behavior.

It verifies the accepted outputs of plans 142 through 145 against the exact source acceptance baseline and retains final validation lifecycle commit and reporting authority in the parent.

## Decisions

- Do not reconstruct or weaken source acceptance text.
- Do not remediate product defects inside this integration plan; classify an independently repairable defect or require restructuring under the existing policy.
- Run the authoritative source validation suite exactly once only after the combined diff and critical invariants are otherwise acceptable.

## Tasks

- [ ] Confirm plans 142 through 145 are checked with independent-review evidence.
- [ ] Record the accepted behavior under Unreleased.
- [ ] Review combined changes against every source acceptance item and critical safety invariant.
- [ ] Run the authoritative validation suite exactly once.
- [ ] Confirm zero unresolved High or Medium independent-review findings.
- [ ] Archive this integration plan and preserve the restructuring lineage.

## Validation Notes

- The integration plan inherits every source acceptance item in exact source order.
- Parent behavior validation additionally runs `python3 tests/test-git-retirement.py`; the repository does not depend on pytest.
- Parent execution ledger run `146-parent-direct-20260821` stopped with `replan_required` after one focused validation and before authoritative validation.
- Independent receipt `.agent-artifacts/reviews/146-final-retirement.md` reported High 0, Medium 2, and Low 1. The implementation validates the manifest digest only at startup rather than from the exact manifest path immediately before each effect, and this plan incorrectly describes replanned Plans 143 and 144 as checked predecessors.
- Preserve the current Unreleased change as unaccepted integration work. Do not continue validation or archive this plan under the stopped run.
