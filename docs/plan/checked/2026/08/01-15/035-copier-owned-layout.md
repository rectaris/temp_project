# Isolate Copier-owned workflow files and remove heuristic Stop blocking

status: checked
task_types:
  - template_workflow
  - security
  - skill_authoring
review_class: C
human_design_required: yes
human_approval_status: approved
write_scope:
  - .codex/
  - .agents/
  - .project-agent-workflow/
  - AGENTS.md
  - README.md
  - copier.yml
  - docs/agent/
  - docs/plan/
  - scripts/
  - template/
  - tests/
context_files:
  - docs/agent/spec-index.yaml
  - .agent-artifacts/referent-contracts/copier-owned-layout/contract.json
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - tests/copier-minimum.sh
  - tests/root-plan-lifecycle.sh
  - git diff --check
acceptance:
  - Copier-managed workflow content is rendered under an isolated namespace and generated repositories have explicit project-owned extension paths.
  - Root discovery files contain stable routing only, and mutable project README, policy, configuration, and plan state are not overwritten by updates.
  - Updating fixtures with representative project-owned changes produces no rejection files or inline conflict markers.
  - Communication review is applied through policy and the write-for-reader Skill without a heuristic Stop continuation.
  - Deterministic completion failures may still block Stop, while duplicate user and project hook sources do not emit repeated communication-review blocks.
checked_summary_ja: Copier管理ファイルとプロジェクト所有ファイルを分離し、文章形状だけで発生するStop時の再実行要求を廃止した。

## Problem

Generated repositories edit the same paths that Copier later updates, producing rejection files during real upgrades.

The current Stop hook also requests another model pass solely from message length, marker words, or list shape, and the same project script can be invoked from both user and project hook sources.

Every Stop command loaded from the active user, project, managed, or plugin hook sources.

Each matching command runs independently.

A predicate over last_assistant_message length, selected words, or list count, independent of whether the required review already occurred.

That predicate currently controls communication review.

The project completion command returns non-zero because an open plan has not been completed or archived.

## Goal

Make fresh copies and later updates use explicit ownership boundaries, preserve repository-specific state, and keep Stop blocking limited to deterministic repository conditions.

## Terms

template-managed-core: Template-managed core means files rendered into an isolated namespace and changed only by Copier updates.

project-owned-layer: Project-owned layer means generated repository files that Copier seeds or recognizes but does not overwrite after adoption.

bridge-file: Bridge file means a small host-discovered file that routes to template-managed core and project-owned content.

## Decisions

- Render common workflow content into `.project-agent-workflow/` and keep project-specific extensions outside that namespace.
- Keep host-discovered root files small and stable; seed mutable project files with `_skip_if_exists` rather than updating their content.
- Keep one Copier template and one answers file.
- Remove message-shape-based Stop blocking and retain only deterministic completion blocking.
- Do not rely on hook-source precedence or concurrent-hook deduplication because Codex runs every matching hook source.
- Prefer `.agents/skills` for newly generated repository Skills and retain only the compatibility needed by supported generated projects.
- Add update tests that modify every declared project-owned extension point before updating.

## Implementation Instructions

1. Add the generated ownership manifest and isolated common workflow directory.
2. Convert generated root policy, configuration, documentation, scripts, and plan files to either stable bridges or project-owned seeds.
3. Update paths in generated policy, Skills, hooks, checks, and fixtures.
4. Replace heuristic communication blocking with non-blocking policy enforcement and focused tests.
5. Add migration and update coverage from supported tags, including representative downstream edits.
6. Run the full validation matrix, archive this plan, and commit the scoped work.

## Tasks

- [x] Implement the ownership layout and project extension points.
- [x] Update Hook behavior and regression tests.
- [x] Add Copier migration and realistic update coverage.
- [x] Align template documentation, Skills, and validation.
- [x] Run validation, archive the plan, and commit the completed work.

## Validation Notes

- `python3 scripts/validate-changes.py --all` passed after adding the namespaced template paths to the validation allowlist.
- `scripts/lint-project-workflow.sh` passed with 27 hook tests, 1 migration test, 8 referent tests, 10 validation-tool tests, and the root plan lifecycle test.
- `tests/smoke.sh` passed against the staged-tree Git snapshot, including pinned actionlint 1.7.12 for generated workflows.
- `tests/copier-update.sh` passed against v0.4.1, v0.4.6, a modified legacy managed file, and a future namespaced update with project-owned edits.
- `tests/copier-minimum.sh` passed with the declared minimum Copier and Python versions.
- `tests/root-plan-lifecycle.sh` passed.
- `git diff --cached --check` and `git diff --check` passed.
