# Safely retire ancestry-merged local worktrees and branches

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
implementation_ambiguity: ordinary
replan_reason_codes:
  - multiple_independent_invariants
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/git-retirement.yaml
  - docs/agent/spec-index.yaml
  - docs/plan/
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/retire-merged-worktrees.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_GIT_RETIREMENT.md
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - template/.project-agent-workflow/ownership.yaml
  - template/.project-agent-workflow/scripts/retire-merged-worktrees.py
  - template/docs/agent/git-retirement.yaml.jinja
  - tests/copier-update.sh
  - tests/fixtures/git-retirement/
  - tests/smoke.sh
  - tests/test-git-retirement.py
context_files:
  - AGENTS.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_FILE_MANAGEMENT.md
  - docs/agent/SPEC_GIT_WORKFLOW.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/spec-index.yaml
  - references/validation.md
  - template/.project-agent-workflow/ownership.yaml
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_FILE_MANAGEMENT.md
  - docs/agent/SPEC_GIT_WORKFLOW.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-git-retirement.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-git-retirement.py
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
replan_source: docs/plan/active/112-retire-merged-local-worktrees.md
replan_contract: docs/plan/replanned/contracts/112-retire-merged-local-worktrees.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/142-define-local-git-retirement-policy.md
  - docs/plan/active/143-implement-read-only-retirement-scan.md
  - docs/plan/active/144-implement-revalidated-local-apply.md
  - docs/plan/active/145-integrate-retirement-copier-preservation.md
  - docs/plan/active/146-integrate-local-git-retirement.md
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
checked_summary_ja: 祖先関係を確認したlocal branchとcleanなlinked worktreeだけを、固定manifestの再検証後に強制指定なしで削除できるようにする。

## Context

A registered non-primary linked worktree and its checked-out local branch.

The condition that the local branch tip is an ancestor of one configured local merge-target ref.

The condition that the worktree is not current, not locked, clean, inside an explicitly allowed root, and checked out on a non-protected local branch with no upstream-ahead commits.

A registered linked worktree and its checked-out local branch whose ancestry and eligibility checks all pass.

A local retirement candidate is a registered linked worktree and its checked-out local branch whose ancestry and eligibility checks all pass.

A JSON record containing repository identity, worktree path, branch ref, branch tip OID, merge-target ref and OID, upstream relation, every eligibility result, and a content digest.

A local retirement manifest is a JSON record containing repository identity, exact worktree and branch targets, pinned OIDs, eligibility results, and a content digest for apply-time revalidation.

The action that revalidates the manifest facts, removes the exact worktree with git worktree remove without force, and deletes the exact local branch with git branch -d.

Elapsed time, branch naming, or absence from the current worktree list used alone as deletion evidence.

The repository currently lacks one deterministic command that can inventory locally merged linked worktrees, explain every blocked condition, and remove only an unchanged exact pair after revalidation. The plan adds that local workflow while preserving Git refusal modes and excluding external writes.

## Decisions

- Use one CLI with `scan` and `apply-local` subcommands so discovery and removal share one eligibility and manifest implementation while retaining separate effect boundaries.
- Use configured local refs and Git ancestry as the only integration proof in this plan; do not infer squash or rebase integration from names, age, patches, pull requests, or provider state.
- Keep reusable project configuration safe-disabled and project-owned, and pass the host-specific allowed root only as a runtime argument.
- Pin exact identities and OIDs in the scan artifact and revalidate all facts immediately before ordinary Git removal commands.
- Automate scan and reporting only; keep each removal as an explicit local operation.
- Defer remote deletion, provider-assisted non-ancestry evidence, and destructive stale metadata pruning to separately authorized plans.

## Tasks

- [ ] Add the root and generated Git-retirement specification, project-owned configuration schema, routing policy, ownership classification, and Unreleased changelog entry.
- [ ] Implement the byte-identical root and generated CLI with read-only scan, structured explanations, versioned manifests, exact apply-time revalidation, and non-force local removal.
- [ ] Extend root-policy, template-inventory, fresh-generation, and non-destructive Copier-update checks for the new managed and project-owned files.
- [ ] Add disposable Git repository fixtures and tests for the accepted, blocked, state-change, path-boundary, unsupported-operation, idempotency, and holdout cases.
- [ ] Run focused validation, review the candidate diff and critical invariants, run the authoritative validation suite exactly once for an otherwise acceptable candidate, complete independent review, and archive the accepted plan.

## Validation Notes

- Decision audit selected a local-only first phase, one shared CLI contract, project-owned safe-disabled defaults, Git ancestry plus eligibility evidence, non-force Git commands, scan-only automation, and temporary-repository validation.
- The advisory referent contract separates the linked worktree and branch pair, ancestry proof, eligibility gates, admitted pair, pinned manifest, exact removal action, and insufficient deletion evidence.
- Plan 111 is independent; neither active plan depends on the other or broadens the other's authorization.
