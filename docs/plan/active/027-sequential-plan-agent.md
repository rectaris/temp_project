# Sequential Plan Worker Agent

status: active
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
- The parent agent remains responsible for acceptance, integration decisions, validation, and all final responses.

## Implementation Instructions

1. Read Plan 026 and preserve its worker name, task contract, and sequencing semantics.
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
   - update the assigned plan's status and validation notes only when the plan lifecycle permits it;
   - preserve unrelated user changes;
   - run the plan's required validation;
   - report changed paths, validation results, blockers, cross-plan impacts, and remaining risks.
5. Explicitly prohibit the worker from processing the next active plan, spawning descendants, committing unrelated changes, or weakening tests.
6. Keep `[agents].max_depth = 1` and verify that the worker configuration does not introduce recursive delegation.
7. Add deterministic template and smoke assertions for the agent file and its model string.
8. Validate generated output through the repository's existing Copier and TOML checks.

## Expected Output

- A validated Spark-backed custom subagent definition.
- Template and smoke coverage proving the model and orchestration guardrails are present.
- A final report confirming the sequential workflow is ready for use.

## completion_deferred_reason

Plan 026 now defines the final skill contract and worker invocation name; proceed after Plan 026 acceptance.
