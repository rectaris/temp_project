# Sequential Active-Plan Skill

status: active
task_type: skill_authoring
review_class: B
human_design_required: no
human_approval_status: not_required
target_files:
  - template/.codex/skills/sequential-plan-orchestrator/SKILL.md
  - template/.codex/skills/sequential-plan-orchestrator/agents/openai.yaml
  - scripts/check-copier-template.py
  - tests/smoke.sh
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
validation:
  - python3 <skill-creator>/scripts/quick_validate.py template/.codex/skills/sequential-plan-orchestrator
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The skill has valid frontmatter and required UI metadata.
  - The skill enforces numeric plan ordering, one-plan-at-a-time delegation, waiting, parent acceptance, and cross-plan impact updates.
  - The skill delegates implementation rather than performing implementation itself.
  - Generated template checks and smoke tests recognize the skill.
  - No unrelated files or behavior are changed.
expected_output: full-implementation
checked_summary_ja: 連番の active plan を一つずつ委譲し、親エージェントが受入確認と依存プラン更新を行う Skill を追加する。

## Objective

Create a reusable project-local Codex skill that turns the repeated active-plan orchestration prompt into an executable workflow.

The skill must make the parent agent responsible for interpretation, sequencing, cross-plan updates, output acceptance, and final validation.

The parent agent must not implement the plan's product or code changes directly.

## Decisions

- The skill is named `sequential-plan-orchestrator`.
- The skill is generated under `template/.codex/skills/sequential-plan-orchestrator/`.
- The workflow processes `docs/plan/active/*.md` in numeric filename order.
- Each plan is delegated to one subagent, and the next plan starts only after the current plan's implementation and acceptance checks finish.
- Before delegation, the parent agent reads the active plan, its required specs, and the current active-plan index.
- The parent agent updates affected later plans when a completed plan changes their assumptions or target boundaries.
- The parent agent performs review and validation after each delegated plan and does not make implementation changes outside orchestration metadata, plan updates, and validation artifacts.
- Skill instructions must refer to the configurable worker agent name rather than hard-coding an unavailable runtime mechanism.

## Implementation Instructions

1. Read `docs/agent/SPEC_PLAN_WORKFLOW.md`, `docs/agent/SPEC_SKILL_AUTHORING.md`, and `references/orchestration.md` before authoring the skill.
2. Use the system `skill-creator` workflow and keep `SKILL.md` concise.
3. Put the trigger in the frontmatter description for requests to execute numbered active plans sequentially with one subagent per plan.
4. Define the workflow in direct operational steps:
   - enumerate and numerically sort active plan files;
   - stop and report if an active plan is ambiguous, blocked, or missing required inputs;
   - delegate exactly one bounded plan at a time;
   - wait for that plan's subagent result;
   - inspect changed paths, validation evidence, and cross-plan impact;
   - update later active plans when required;
   - accept or reject the result before advancing;
   - finish with a consolidated validation and remaining-risk report.
5. Define the subagent request contract, including plan path, explicit read scope, explicit write scope, required validation, expected return fields, and prohibition on unrelated changes.
6. State that subagent output is advisory until the parent agent accepts it through repository validation.
7. Do not include project-specific supportcard facts, credentials, external-service writes, or a second orchestration loop in the skill.
8. Generate `agents/openai.yaml` with metadata matching the skill name and trigger.
9. Register the new skill in repository template checks and smoke coverage if those checks enumerate expected skill directories.

## Expected Output

- A validated reusable skill definition for sequential active-plan orchestration.
- Updated template checks and smoke assertions when necessary.
- Validation results and a list of any remaining assumptions for Plan 027.

## completion_deferred_reason

Plan 027 depends on the worker-agent name and output contract defined here.
