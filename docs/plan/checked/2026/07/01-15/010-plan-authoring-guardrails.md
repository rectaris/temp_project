# Plan Authoring Guardrails

## Manifest

- `status`: `checked`
- `task_type`: `planning_docs`
- `review_class`: `B`
- `human_design_required`: `no`
- `human_approval_status`: `not_required`
- `target_files`:
  - `template/docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `template/scripts/create-plan.sh`
  - `template/scripts/lint-plan-docs.py`
  - `template/scripts/format-plan-docs.py`
  - `docs/agent/SPEC_JAPANESE_TECH_WRITING.md`
  - `tests/`
- `required_specs`:
  - `AGENTS.md`
  - `template/docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `docs/agent/SPEC_JAPANESE_TECH_WRITING.md`
- `validation`:
  - `scripts/lint-project-workflow.sh`
  - `tests/smoke.sh`
- `acceptance`:
  - Active plans are documented as executable agent instructions, not deliberation transcripts.
  - Active-plan operational sections prefer English, while Japanese remains allowed for user-facing summaries and explicit Japanese-prose tasks.
  - Active plans record final decisions only; alternatives, recommendation analysis, and debate transcripts belong in raw logs or separate research artifacts.
  - Plan linting or tests catch obvious deliberation-log patterns in active plans.
- `acceptance_focus`:
  - active-plan format
  - decision-only records
  - lintable guardrails
- `expected_output`: updated plan workflow policy, plan scaffolding, lint checks, and tests.
- `checked_summary_ja`: active plan が検討ログ化しないよう、英語の実装指示と決定事項のみを残すガードレールを追加した。
- `completion_deferred_reason`: ``

## Problem

The previous active-plan update recorded option analysis, recommendations, and reasoning in the plan body.

That was the wrong artifact boundary.

An active plan should tell the next agent what to implement, which files are in scope, which decisions are already fixed, and how to validate the work.

It should not preserve the full discussion that led to those decisions.

Detailed option analysis belongs in the future raw-log system, handoff research artifacts, or a short durable decision record only when it is needed for implementation.

## Goal

Add guardrails that prevent future active plans from becoming deliberation logs.

Make the expected active-plan shape explicit in generated projects and in this repository.

Prefer mechanical checks for patterns that can be detected reliably.

Keep the checks conservative so valid Japanese summaries and legitimate product prose are not blocked.

## Implementation Instructions

Update `SPEC_PLAN_WORKFLOW.md` to say that active-plan bodies are executable instructions for agents.

State that operational sections should be in English by default.

Keep Japanese allowed for `checked_summary_ja`, user-facing summaries, domain terms, and tasks whose scope is Japanese prose.

State that active plans should keep only final decisions.

State that alternatives, recommendation matrices, debate transcripts, and long rationale blocks should not be stored in active plans.

Update plan scaffolding if the generated `create-plan.sh` template encourages ambiguous plan bodies.

Add lint coverage for obvious anti-patterns in active plans.

The check should reject headings or repeated markers that indicate option-analysis logs, such as `推奨:`, `理由:`, `A:`, `B:`, and `C:` when they appear as a structured recommendation block in active plans.

The check should not reject `review_class: B`, ordinary English prose, file names, or compact final decision lists.

Add tests for a bad active plan that contains a recommendation matrix and a good active plan that contains only final decisions.

## Decisions

1. Active plans are implementation instructions, not raw logs.

2. Active-plan operational detail should be English by default.

3. Active plans may contain Japanese only where it is intentionally user-facing or task-relevant.

4. Active plans should record final decisions, not option matrices.

5. Deliberation details belong in raw logs, handoff research artifacts, or intentionally scoped decision artifacts.

6. Lint checks should be conservative and target clear anti-patterns rather than all Japanese text.

## Tasks

- [x] Inspect current generated plan scaffolding and lint-plan behavior.
- [x] Update `template/docs/agent/SPEC_PLAN_WORKFLOW.md` with active-plan artifact boundaries.
- [x] Update generated plan scaffolding if needed.
- [x] Add active-plan lint rules for obvious deliberation-log patterns.
- [x] Add tests for rejected recommendation-matrix plans and accepted final-decision plans.
- [x] Confirm Japanese user-facing fields remain valid.
- [x] Run `scripts/lint-project-workflow.sh` and `tests/smoke.sh`.

## Open Decisions

- None.

## Validation Notes

Confirmed that generated plans with compact final decisions and Japanese `checked_summary_ja` still pass lint.

Confirmed that active plans containing a structured recommendation matrix are rejected by generated `lint-plan-docs.py`.

Confirmed that generated projects can still create and complete plans with normal lifecycle scripts.

Validated with:

- `scripts/lint-project-workflow.sh`
- `tests/smoke.sh`
- `git diff --check`

`tests/smoke.sh` emitted Copier `DirtyLocalWarning` because it rendered the template with uncommitted local changes, then passed.
