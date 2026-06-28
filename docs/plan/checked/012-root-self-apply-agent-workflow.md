# Root Self Apply Agent Workflow

## Manifest

- `status`: `checked`
- `task_type`: `planning_docs`
- `review_class`: `B`
- `human_design_required`: `no`
- `human_approval_status`: `not_required`
- `target_files`:
  - `AGENTS.md`
  - `.gitignore`
  - `docs/agent/`
  - `scripts/`
  - `docs/plan/`
- `required_specs`:
  - `AGENTS.md`
  - `docs/agent/SPEC_JAPANESE_TECH_WRITING.md`
- `validation`:
  - `scripts/lint-project-workflow.sh`
  - `tests/smoke.sh`
  - `git diff --check`
- `acceptance`:
  - Root project documents agent logging and context compression policy.
  - Root project documents decision-audit and active-plan authoring guardrails.
  - Local raw log paths are ignored by Git.
  - Root lint checks reject obvious active-plan recommendation matrices.
  - Template checks and smoke tests still pass.
- `acceptance_focus`:
  - root self-application
  - deterministic guardrails
  - template compatibility
- `expected_output`: root docs, ignore entries, helper scripts, checks, and checked plan record.
- `checked_summary_ja`: 009、010、011 の運用ルールをテンプレート開発 repo 本体にも最小適用した。
- `completion_deferred_reason`: ``

## Problem

Plans 009, 010, and 011 updated generated project templates, but the template development repository itself does not receive Copier updates.

Root-level agent policy should reflect the same operating rules where they are relevant to maintaining this repository.

## Goal

Apply the logging, context compression, active-plan guardrail, and decision-audit rules to this repository root without turning the root repository into a generated project.

## Implementation Instructions

Add root `docs/agent` policy files for agent logging, context compression, decision audit, and plan workflow.

Update root `AGENTS.md` so agents know to use those policies.

Ignore local raw log and artifact directories in root `.gitignore`.

Add root deterministic checks for policy presence, ignored local log paths, and active-plan recommendation-matrix anti-patterns.

Do not add generated project lifecycle scripts wholesale unless they are needed for this repository root.

Do not write into the environment-provided read-only `.codex/` directory; use root docs policy for decision audit in this repository.

## Decisions

1. Apply 009, 010, and 011 to the root repository as policy and checks, not by running Copier update.

2. Keep root structure distinct from generated project structure.

3. Use root `docs/agent/SPEC_DECISION_AUDIT.md` instead of a repo-local `.codex/skills/decision-audit` installation because root `.codex/` is environment-provided and read-only.

4. Add deterministic root checks to `scripts/lint-project-workflow.sh`.

## Tasks

- [x] Add root policy docs.
- [x] Update root `AGENTS.md`.
- [x] Update root `.gitignore`.
- [x] Add root helper/check scripts.
- [x] Validate root checks and generated template smoke tests.
- [x] Archive this plan to checked.

## Open Decisions

- None.

## Validation Notes

Validated with:

- `python3 scripts/check-root-agent-policy.py --self-test`
- `sh -n scripts/context-compress.sh`
- `python3 -m py_compile scripts/check-root-agent-policy.py scripts/check-copier-template.py`
- `git check-ignore .agent-logs/sample/manifest.json .agent-artifacts/sample/output.txt`
- `scripts/lint-project-workflow.sh`
- `tests/smoke.sh`
- `git diff --check`
- `HEADROOM_DISABLED=1 scripts/context-compress.sh README.md root-self-apply-smoke`

Confirmed that `scripts/context-compress.sh AGENTS.md` is refused.

`tests/smoke.sh` emitted Copier `DirtyLocalWarning` because it rendered the template with uncommitted local changes, then passed.

The local `.agent-logs/root-self-apply-smoke/` verification output is ignored by Git.
