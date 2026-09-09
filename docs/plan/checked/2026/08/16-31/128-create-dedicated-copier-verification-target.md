# Create a dedicated Copier verification target

status: checked
primary_invariant: keep the helper-specific relative source path confined to one committed disposable target fixture
replan_source: docs/plan/active/127-repair-temporary-copier-cli-shim.md
replan_contract: docs/plan/replanned/contracts/127-repair-temporary-copier-cli-shim.json
integration_gates:
  - Plan 129 must run the complete required-Copier fixture before Plan 126 resumes.
successor_plans:
  - docs/plan/active/128-create-dedicated-copier-verification-target.md
  - docs/plan/active/129-integrate-dedicated-copier-verification-target.md
inherited_acceptance_digests:
  - sha256:3df8b90dc12615e26c1a311aee943650fe2be5649b99c36b389bd70720a054f2
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - tests/copier-update.sh
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/active/119-integrate-verify-copier-update-skill.md
  - docs/plan/active/126-integrate-generated-verify-helper-compilation.md
  - docs/plan/replanned/2026/08/16-31/127-repair-temporary-copier-cli-shim.md
  - tests/lib-copier.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - sh -n tests/copier-update.sh
  - git diff --check
validation:
  - sh -n tests/copier-update.sh
  - git diff --check
acceptance:
  - In `tests/copier-update.sh`, create one dedicated committed target clone for the verification helper, set the sibling-relative `_src_path` only in that clone, and leave the existing target unchanged for its later ordinary update; do not modify the launcher, helpers, validators, validation allowlists, Plan 119 acceptance, safety conditions, or external-effect authority.
checked_summary_ja: helper専用のcommitted target cloneだけに相対Copier source pathを設定する。

## Decisions

- Clone the committed older generated target after its ordinary baseline commit.
- Rewrite and commit the sibling-relative source path only in the helper-specific clone.
- Keep the existing target byte-for-byte unchanged until its existing ordinary update.
- Use bounded parent implementation inside the preserved uncommitted fixture and require independent read-only review.

## Tasks

- [x] Add one helper-specific target clone and commit only its relative source answer.
- [x] Point the verification helper at the dedicated clone and leave the existing target unchanged.
- [x] Complete syntax, diff, and independent scope review.
- [x] Archive and commit the bounded fixture change before Plan 129 integration.

## Validation Notes

- The user explicitly authorized this exact target-fixture separation on 2026-08-21.
- Independent read-only review reported High 0 and Medium 0 and made no file changes.
- Authoritative validation passed: `sh -n tests/copier-update.sh` and `git diff --check`.
- Parent execution evidence: `/tmp/plan128-execution.9NsWkb/execution.json`.
