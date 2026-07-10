# Sequential Plan Worker Agent

status: checked
task_type: template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
target_files:
  - template/.codex/agents/sequential_plan_worker.toml
  - scripts/check-copier-template.py
  - tests/smoke.sh
  - template/docs/plan/sub-agents/custom-agents.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
validation:
  - python3 scripts/check-codex-toml.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The generated project contains sequential_plan_worker.toml.
  - The agent uses exactly gpt-5.3-codex-spark and does not introduce descendant delegation.
  - The agent enforces bounded writes, required validation, structured handoff, and no next-plan execution.
  - Plan 026 can invoke the worker by name without duplicating its model or prompt contract.
  - Existing agents, model defaults, tests, and unrelated template behavior remain unchanged.
expected_output: full-implementation
checked_summary_ja: 連番プランを一つずつ実装する gpt-5.3-codex-spark 使用サブエージェントを追加し、生成と検証で設定を保証する。

## Objective

Add a project-scoped custom subagent for the sequential active-plan skill and configure it to use `gpt-5.3-codex-spark`.

The worker must implement only the active plan assigned by the parent agent, return structured evidence, and remain bounded by the plan's write scope.

## Decisions

- The custom agent is named `sequential_plan_worker`.
- Its model is `gpt-5.3-codex-spark`.
- Its default reasoning effort is `medium` because the worker is optimized for bounded implementation and fast iteration; the parent may override this only through an explicit task-level setting.
- The worker uses `workspace-write` because implementation plans may require repository edits.
- The worker must not spawn child agents; the project remains at one delegation level for this workflow.
- The worker writes only the files listed in the delegated task's explicit write scope and does not edit the assigned plan's status or lifecycle state.
- The worker returns implementation and validation evidence without committing; the parent agent remains responsible for status transitions, acceptance, integration decisions, commits, and all final responses.
- The worker configuration is validated in the template and generated output; model availability is outside repository validation scope.
- Plan 026 is accepted and archived, so this plan's deferred dependency is cleared.

## Implementation Instructions

1. Read the checked Plan 026 record and preserve its worker name, task contract, and sequencing semantics.
2. Define `sequential_plan_worker` with required `name`, `description`, `model`, `model_reasoning_effort`, `sandbox_mode`, and concise developer instructions.
3. Set:

   ```toml
   model = "gpt-5.3-codex-spark"
   model_reasoning_effort = "medium"
   sandbox_mode = "workspace-write"
   ```

4. Require the worker to:
   - read the assigned plan and its required specs;
   - stay inside the explicit write scope;
   - return validation notes without changing the assigned plan's status, `ready_to_archive` state, or archive location;
   - preserve unrelated user changes;
   - run the plan's required validation;
   - report changed paths, validation results, blockers, cross-plan impacts, and remaining risks.
5. Explicitly prohibit the worker from processing the next active plan, spawning descendants, committing changes, changing lifecycle state, or weakening tests.
6. Keep the existing `[agents].max_depth = 1` unchanged and verify that the worker configuration does not introduce recursive delegation.
7. Add deterministic template and smoke assertions for the agent file and its model string.
8. Validate generated output through the repository's existing Copier and TOML checks, including exact model and delegation guardrail assertions; do not attempt to probe external model availability.

## Expected Output

- A validated Spark-backed custom subagent definition.
- Template and smoke coverage proving the model and orchestration guardrails are present.
- A final report confirming the sequential workflow is ready for use.

## Summary

Added the generated `sequential_plan_worker` agent and connected its bounded worker contract to template checks and smoke coverage.

## Completed Work

- Added the `gpt-5.3-codex-spark` worker definition with medium reasoning and workspace-write access.
- Restricted the worker to one assigned plan, explicit write scope, required validation, and structured evidence without lifecycle changes, descendant delegation, or commits.
- Added custom-agent documentation, Copier static checks, and generated-project smoke assertions.
- Corrected the existing sequential orchestrator metadata assertion to match its established `one bounded worker at a time` wording.

## Validation Notes

- `git diff --check` passed.
- `python3 scripts/check-codex-toml.py` passed.
- `python3 scripts/check-copier-template.py` passed.
- `python3 scripts/validate-changes.py --all` passed.
- `scripts/lint-project-workflow.sh` passed.
- `tests/smoke.sh` passed. Copier emitted `DirtyLocalWarning` because the smoke test intentionally rendered the in-progress dirty template.
- Model availability was not probed because it is outside deterministic repository validation scope.
