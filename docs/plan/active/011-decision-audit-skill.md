# Decision Audit Skill

## Manifest

- `status`: `active`
- `task_type`: `orchestration_meta`
- `review_class`: `B`
- `human_design_required`: `no`
- `human_approval_status`: `not_required`
- `target_files`:
  - `template/.codex/skills/decision-audit/SKILL.md`
  - `template/.codex/skills/decision-audit/agents/openai.yaml`
  - `template/docs/agent/SPEC_DECISION_AUDIT.md`
  - `template/docs/agent/spec-index.yaml.jinja`
  - `template/docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `template/AGENTS.md.jinja`
  - `scripts/check-copier-template.py`
  - `tests/`
- `required_specs`:
  - `AGENTS.md`
  - `template/docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `template/docs/agent/SPEC_ORCHESTRATION.md`
- `validation`:
  - `scripts/lint-project-workflow.sh`
  - `tests/smoke.sh`
- `acceptance`:
  - Generated projects provide a reusable decision-audit workflow for unstated important decisions.
  - The workflow can be triggered by explicit user prompts such as `decision-audit` or natural-language requests for missing decisions, approaches, recommendations, and reasons.
  - Agents are instructed to run a decision audit automatically before creating or materially updating active implementation plans when meaningful design choices remain open.
  - Full decision-audit output is kept separate from `docs/plan/active`; active plans receive only final accepted decisions.
  - Generated routing documentation tells agents when to use decision audit and which supporting specs to read.
  - Smoke or template checks confirm the generated decision-audit files exist and the plan-routing references are present.
- `acceptance_focus`:
  - reusable decision-audit prompt
  - automatic plan-preflight behavior
  - active-plan artifact boundary
  - generated-template coverage
- `expected_output`: generated decision-audit skill/spec, routing updates, plan workflow guidance, and tests.
- `checked_summary_ja`: 未明示の重要な決定事項を洗い出す decision-audit workflow をテンプレートに追加し、active plan 作成前に必要なら自動提示するルールを整備した。
- `completion_deferred_reason`: ``

## Problem

The user frequently asks agents to identify important decisions that are not explicit in the current request or plan, explain each decision, compare viable approaches, and recommend a direction with reasons.

This question is valuable before implementation and before plan authoring, but repeating the full prompt manually is inefficient.

The output format also includes approach matrices and recommendation rationale, which should not be copied into active implementation plans.

Generated projects need a reusable workflow that prompts agents to surface this analysis at the right time while preserving the boundary between decision analysis and executable active-plan instructions.

## Goal

Add a reusable decision-audit workflow to generated projects.

Make the workflow easy to trigger explicitly and likely to run automatically before non-trivial plan creation or major plan updates.

Keep decision-audit analysis separate from `docs/plan/active`.

Record only final accepted decisions in active plans.

## Implementation Instructions

Create a generated `decision-audit` Codex skill when the current Codex project-skill discovery model supports repository-local skills under `.codex/skills`.

If repository-local skill discovery is not supported, create the same workflow as agent policy under `docs/agent/SPEC_DECISION_AUDIT.md` and document the limitation clearly in the template README or agent docs.

The skill frontmatter must use `name: decision-audit`.

The skill description must trigger for:

- explicit `decision-audit` requests
- questions about unstated important decisions
- requests to compare approaches
- requests for recommendations with reasons
- plan creation or material plan updates where meaningful design, storage, validation, lifecycle, security, or artifact-boundary choices remain open

The skill body must instruct agents to inspect the user request, relevant active plan, and routed project docs before producing the audit.

The skill output must use a numbered decision-item format with approach labels and recommendation rationale.

Use English labels in the reusable skill body, but allow Japanese responses when the user is communicating in Japanese.

Add `SPEC_DECISION_AUDIT.md` to generated project docs.

The spec must define:

- when to run decision audit automatically
- when to skip it for small or already-determined changes
- how to distinguish explicit requirements from inferred gaps
- how to handle insufficient context without inventing decisions
- how to convert accepted audit outcomes into active-plan final decisions
- where not to store full audit output

Update `SPEC_PLAN_WORKFLOW.md` so plan creation and material plan updates include a preflight decision-audit step when non-trivial choices remain open.

State that the full audit belongs in chat, raw logs, handoff research artifacts, decision artifacts, or `.agent-artifacts/decision-audits/`, not in `docs/plan/active`.

Update `spec-index.yaml.jinja` with a `decision_audit` route.

The route must require development flow and decision-audit guidance, and it must include plan workflow guidance when the audit affects plan lifecycle files.

Update `AGENTS.md.jinja` with a concise operating rule that agents should run decision audit before creating or materially updating active plans when meaningful choices are still open.

Update template checks and smoke tests so generated projects include the new decision-audit files and references.

Do not add a Copier prompt that makes this optional unless implementation proves generated repo-local skills are not viable.

## Decisions

1. The reusable workflow is named `decision-audit`.

2. Decision audit is installed or documented by default in generated projects.

3. Agents should run decision audit automatically before non-trivial active-plan creation or material active-plan updates when meaningful choices remain open.

4. Explicit prompts such as `decision-audit`, `未決事項を洗い出せ`, and `決めるべき重要事項はあるか` should trigger the workflow.

5. Full decision-audit output must not be copied into `docs/plan/active`.

6. Active plans should receive only final accepted decisions after the audit is resolved.

7. The generated skill should allow Japanese output when the user is communicating in Japanese.

8. The feature should be default-on rather than a Copier choice.

## Tasks

- [ ] Inspect current Codex support for repository-local generated skills under `.codex/skills`.
- [ ] Add the generated `decision-audit` skill when repository-local skill discovery is supported.
- [ ] Add `template/docs/agent/SPEC_DECISION_AUDIT.md`.
- [ ] Update `template/docs/agent/spec-index.yaml.jinja` with a `decision_audit` route.
- [ ] Update `template/docs/agent/SPEC_PLAN_WORKFLOW.md` with the decision-audit preflight rule and artifact boundary.
- [ ] Update `template/AGENTS.md.jinja` with the automatic decision-audit operating rule.
- [ ] Update template required-file checks.
- [ ] Add or update smoke tests for generated files and route references.
- [ ] Confirm active-plan guardrails still keep full audit matrices out of active plans.
- [ ] Run `scripts/lint-project-workflow.sh` and `tests/smoke.sh`.

## Open Decisions

- None.

## Validation Notes

Confirm that the generated project contains the decision-audit workflow files and that routing docs reference the workflow.

Confirm that existing active plans remain valid and do not need to contain decision-audit matrices.

Confirm that the new workflow remains compatible with `010-plan-authoring-guardrails`.
