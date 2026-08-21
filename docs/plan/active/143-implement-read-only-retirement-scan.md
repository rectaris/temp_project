# Implement read-only retirement scan

status: in_progress
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
primary_invariant: scan inventories registered linked worktrees and writes a pinned manifest without changing worktrees branches refs or remote state
replan_source: docs/plan/active/112-retire-merged-local-worktrees.md
replan_contract: docs/plan/replanned/contracts/112-retire-merged-local-worktrees.json
integration_gates:
  - plan 142 must be checked before scan implementation starts
  - plan 144 must preserve scan behavior while adding the separate local apply effect boundary
  - plan 146 must verify the combined successors against every source acceptance item
successor_plans:
  - docs/plan/active/142-define-local-git-retirement-policy.md
  - docs/plan/active/143-implement-read-only-retirement-scan.md
  - docs/plan/active/144-implement-revalidated-local-apply.md
  - docs/plan/active/145-integrate-retirement-copier-preservation.md
  - docs/plan/active/146-integrate-local-git-retirement.md
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
  - python3 -m pytest tests/test-git-retirement.py
  - python3 -m py_compile scripts/retire-merged-worktrees.py template/.project-agent-workflow/scripts/retire-merged-worktrees.py
  - git diff --check
validation:
  - python3 -m pytest tests/test-git-retirement.py
  - python3 -m py_compile scripts/retire-merged-worktrees.py template/.project-agent-workflow/scripts/retire-merged-worktrees.py
  - git diff --check
acceptance:
  - Require `--allowed-root` at runtime, reject the repository root, home directory, filesystem root, unresolved paths, and paths outside the exact allowed root, and never persist host-specific absolute worktree roots in reusable files.
  - Enumerate registered worktrees with Git plumbing and admit only a non-primary, non-current, unlocked, clean linked worktree on an exact local branch that is not protected and whose tip is an ancestor of one configured local merge-target ref.
  - Require an upstream for the local branch and block it when the upstream comparison has any ahead commits, is unavailable, or is ambiguous; do not fetch or claim remote freshness.
  - Treat elapsed time, branch naming, a missing provider pull request, and absence from the current worktree list as insufficient deletion evidence.
  - Write scan output only to an ignored local artifact path and include repository identity, exact canonical worktree path, branch full ref and tip OID, merge-target ref and OID, upstream relation, every eligibility result, schema version, and content digest.
checked_summary_ja: Git plumbingだけでlinked worktreeの適格性を調べ、local状態を変更せずに固定manifestを出力する。

## Context

This successor owns the read-only half of the shared command contract.

It must enumerate registered worktrees, explain every eligibility result, and write only the local ignored manifest artifact.

## Decisions

- Use configured local refs and ancestry as integration evidence.
- Keep upstream evidence local and do not fetch or claim remote freshness.
- Keep every scan path and ref operation read-only.

## Tasks

- [ ] Implement allowed-root canonicalization and boundary rejection.
- [ ] Implement Git-plumbing worktree inventory and eligibility explanations.
- [ ] Emit deterministic versioned manifests with pinned identities, OIDs, results, and content digest.
- [ ] Add disposable-repository scan scenarios without any removal operation.
- [ ] Complete parent diff review, independent review, and focused validation before acceptance.

## Validation Notes

- Parent-direct implementation is required because the executable and tests are validation-authority paths rejected from worker candidates.
