# Complete read-only retirement scan from the exact worktree root

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
parent_direct_reason: the executable and its deterministic tests are parent-owned validation authority under the current runner
primary_invariant: scan loads configuration only from the exact Git worktree root and writes a pinned manifest without changing worktrees branches refs remote state or configured hooks
replan_source: docs/plan/active/143-implement-read-only-retirement-scan.md
replan_contract: docs/plan/replanned/contracts/143-implement-read-only-retirement-scan.json
integration_gates:
  - plan 142 must remain checked before the replacement scan run starts
  - plan 148 must independently certify the replacement before plan 144 starts
  - plan 146 must verify the combined successors against every source acceptance item
  - preserve the stopped Plan 143 candidate only as unaccepted input inside this exact write scope
successor_plans:
  - docs/plan/active/147-complete-exact-root-retirement-scan.md
  - docs/plan/active/148-certify-exact-root-retirement-scan.md
inherited_acceptance_digests:
  - sha256:3005d6bd08511b36771d0469514d61f43c928fc57fffa9733d294dbac0e7e035
  - sha256:053494f2046950d1749673055c4e3d840b1991b2a51edac4b32e77b6f274b5ea
  - sha256:6b9408c8ebd718b6da2954363ee6624ada7af9791ff5e87981b92254f96ce759
  - sha256:3bf52a9421d768236116af7d7ad8e5a9d3d4c3339dd93dffd5992ded03dd477d
  - sha256:afc2af96b43affbae68ebf3ab4926a7e18429e9e6cb50e08c8351c958950965b
write_scope:
  - scripts/retire-merged-worktrees.py
  - template/.project-agent-workflow/scripts/retire-merged-worktrees.py
  - tests/fixtures/git-retirement/scenarios.json
  - tests/test-git-retirement.py
context_files:
  - docs/plan/replanned/2026/08/16-31/143-implement-read-only-retirement-scan.md
  - docs/plan/replanned/2026/08/16-31/112-retire-merged-local-worktrees.md
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
  - Require `--allowed-root` at runtime, reject the repository root, home directory, filesystem root, unresolved paths, and paths outside the exact allowed root, and never persist host-specific absolute worktree roots in reusable files.
  - Enumerate registered worktrees with Git plumbing and admit only a non-primary, non-current, unlocked, clean linked worktree on an exact local branch that is not protected and whose tip is an ancestor of one configured local merge-target ref.
  - Require an upstream for the local branch and block it when the upstream comparison has any ahead commits, is unavailable, or is ambiguous; do not fetch or claim remote freshness.
  - Treat elapsed time, branch naming, a missing provider pull request, and absence from the current worktree list as insufficient deletion evidence.
  - Write scan output only to an ignored local artifact path and include repository identity, exact canonical worktree path, branch full ref and tip OID, merge-target ref and OID, upstream relation, every eligibility result, schema version, and content digest.
checked_summary_ja: exactなGit worktree rootから設定を読み、外部hookを動かさずに固定manifestを出力するscanを完成させる。

## Context

Plan 143 stopped after two parent-direct remediation rounds. Its candidate already closes the earlier primary-identity, lazy-fetch, fsmonitor, submodule-ignore, upstream-ambiguity, configured-ref, and ignored-output findings, but remains unaccepted.

This replacement must remove the stopped ancestor-search method and bind configuration to the exact Git worktree root before any configuration content is trusted.

An `exact-root scan` means a read-only scan that first identifies the invoking checkout's exact Git worktree root with Git plumbing and then reads only the regular, symlink-safe `docs/agent/git-retirement.yaml` directly below that root.

## Decisions

- Resolve the invoking checkout with Git plumbing before reading configuration.
- Load only the regular, symlink-safe `docs/agent/git-retirement.yaml` below that exact worktree root.
- Reject nested command-adjacent shadow configuration and symlinked configuration ancestors.
- Retain every corrected read-only and fail-closed behavior already covered by the stopped candidate.

## Tasks

- [x] Replace ancestor marker search with exact Git worktree-root discovery before configuration parsing.
- [x] Add nested-shadow and symlink-ancestor regression cases with a safe-disabled root profile.
- [x] Re-run all disposable-repository scan cases and preserve root/generated byte parity.
- [x] Complete fresh parent diff review, independent review, focused validation, and authoritative validation.

## Validation Notes

- This is a fresh run after Plan 143 ledger `143-parent-direct-v3-20260821` entered `replan_required`.
- Parent behavior validation additionally runs `python3 tests/test-git-retirement.py`; the plan command allowlist does not accept a newly introduced direct test path, and the repository does not depend on pytest.
- Do not accept any stopped candidate correction without a fresh independent review under this plan.
- Fresh independent review round 1 found one High inherited Git-environment redirect; round 2 confirmed High 0, Medium 0, Low 0 after repository-local environment removal.
- Parent ledger run `147-parent-direct-v2-20260821` recorded one focused and one authoritative validation. All 22 disposable-repository tests, Python compilation, and `git diff --check` passed.
