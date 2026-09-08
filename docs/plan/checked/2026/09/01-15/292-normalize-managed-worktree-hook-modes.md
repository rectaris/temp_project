# Normalize managed task-worktree hook modes

status: checked
primary_invariant: Every newly created or recovered managed task worktree materializes its repository-profile-aware required completion-gate hooks as single-linked regular files with exact filesystem mode 0755, independent of the caller's umask, before ownership publication.
task_types:
  - template_workflow
  - security
  - planning_docs
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 1
implementation_risk: low
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"A manager-created worktree under umask 0002 materialized both tracked pre-commit hooks as 0775, and scripts/check-copier-template.py rejected them because it requires exact mode 0755.","kind":"reproduced_defect"}
  - {"evidence":"The manager already owns the interval after git worktree add and before ownership-record publication, where it can validate and normalize the two exact tracked hook paths without broad chmod behavior.","kind":"existing_mechanism"}
completion_conditions:
  - Before ownership-record publication, source-template and generated layouts normalize .githooks/pre-commit and, only when tracked at the bound start commit, template/.githooks/pre-commit during normal creation and registered interrupted-create recovery through no-follow descriptors after requiring single-linked regular files.
  - The root and generated worktree managers remain aligned and the existing exact hook-mode validation remains unchanged.
completion_witness_map:
  - {"condition_sha256":"sha256:1fa0bc8efc441931ae7223d11461b66303a6a5d4aea5df2af137227c2cccb805","witness":"python3 -m unittest tests.validation_tools.worktrees.ManagedPlanWorktreesTest"}
  - {"condition_sha256":"sha256:4c012fbc02082693d1404c2090873b11af57f0ddfc9d6d5d6a13eaea27ad0f01","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/manage-plan-worktrees.py
  - template/.project-agent-workflow/scripts/manage-plan-worktrees.py
  - tests/validation_tools/worktrees.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/active/254-preserve-identical-human-report-supersede.md
  - scripts/check-copier-template.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 -m unittest tests.validation_tools.worktrees.ManagedPlanWorktreesTest
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Under umask 0002, source-template and generated repository layouts create or recover managed worktrees with exactly their tracked required hooks normalized safely to 0755 before ownership publication without changing other executable modes.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:97aa5ae23c55ff783a843855f89e14cfc6507d4c6fc8676555cde63dfb1030f1","stage":"focused","witness":"python3 -m unittest tests.validation_tools.worktrees.ManagedPlanWorktreesTest"}
checked_summary_ja: 管理対象のタスク worktree でフックの権限を正規化する。

## Decisions

- Derive the required hook set from the bound start commit: .githooks/pre-commit is always required, and template/.githooks/pre-commit is required only when that exact path is tracked there.
- Run the same normalization before ownership publication in both the normal post-checkout path and the registered interrupted-create recovery path; a failure preserves the journal and registration as unaccepted state for an exact same-task retry.
- Open path components and final hook files without following symlinks, require a regular file with link count one, apply mode 0755 through the open descriptor, and verify the resulting descriptor metadata.
- Do not change the mode of any executable outside the derived required hook set.
- Keep scripts/check-copier-template.py and the authoritative validation commands unchanged.

## Tasks

- [x] Add exact hook-path validation and mode normalization to both worktree-manager counterparts.
- [x] Add a disposable-worktree regression that creates tracked executable hooks under umask 0002 and asserts exact mode 0755.
- [x] Review, validate, archive, and publish the repair before resuming Plan 254 in a fresh run.

## Validation Notes

- The required hook set is .githooks/pre-commit in every supported repository and additionally template/.githooks/pre-commit only when that exact path is tracked at the bound start commit.
- Before either normal creation or registered interrupted-create recovery publishes an ownership record, the manager opens each required hook without following path-component or final symlinks, requires a single-linked regular file, changes its descriptor mode to 0755, verifies the result, and leaves the journal and registration unaccepted if any check fails.
- Plan 254's authoritative lint failed before its product test because a freshly prepared worktree contained both required hooks as 0775.
- Independent diagnosis and repair classification established one bounded worktree-materialization invariant and preserved Plan 254's staged candidate unchanged.
- The initial read-only review found that a supported-profile repository missing its root hook would fail only after worktree creation. Parent remediation moved required-hook derivation to the start of `create_worktree` and added a no-residue regression for that case.
- A fresh-session independent rereview of exact target `sha256:7073c8d2ec20746ff1366e09352ddf0608dcec5abd31aa9436e8c7c3db42bef9` found zero High and zero Medium findings and accepted the prior finding as resolved. The runtime manifest records the unavailable external transcript explicitly.
- Focused validation passed after review: `python3 -m unittest tests.validation_tools.worktrees.ManagedPlanWorktreesTest` ran 37 tests, and `python3 scripts/check-copier-template.py` passed.
- Authoritative validation passed once for the reviewed target: `scripts/lint-project-workflow.sh` and `tests/smoke.sh`. The smoke run skipped optional GitHub Actions lint because `actionlint` was unavailable.
- Product implementation commit: `98e58e9eedfc51924939f805cef2242fc247444e`.
