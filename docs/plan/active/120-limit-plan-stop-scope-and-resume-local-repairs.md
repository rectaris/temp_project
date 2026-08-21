# Limit plan stop scope and resume after independent repairs

status: in_progress
primary_invariant: one independently repairable defect stops the affected execution run without replacing its source plan, while actual boundary drift and exhausted correction budgets remain fail-closed hard replan conditions
task_types:
  - planning_docs
  - referent_first
  - security
  - skill_authoring
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/active/119-integrate-verify-copier-update-skill.md
  - docs/plan/active/120-limit-plan-stop-scope-and-resume-local-repairs.md
  - docs/plan/plan.md
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/
  - tests/fixtures/orchestration/
  - tests/smoke.sh
  - tests/test-plan-execution-state.py
  - tests/test-plan-restructure.py
  - tests/test-sandboxed-plan-worker.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/118-harden-original-repository-snapshot.md
  - references/orchestration.md
  - scripts/restructure-plan.py
  - scripts/run-sandboxed-plan-worker.py
  - tests/fixtures/orchestration/plan-restructuring-holdout.json
  - tests/fixtures/orchestration/plan-restructuring-scenarios.json
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-plan-restructure.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Replace the unconditional post-authoritative replan rule with an evidence-based classification that distinguishes one independently repairable defect from a change that requires reconstructing the source plan; elapsed time, implementation difficulty, and repeated investigation alone must not select either outcome.
  - Enter `repair_required` only when one observed defect has bounded write and validation scope, can be accepted independently, leaves every source acceptance item and accepted safety condition unchanged, does not change external-effect authority, and does not leave multiple independently validatable invariants coupled.
  - Make `repair_required` terminal for the affected execution-ledger run so candidate generation, correction, validation, apply, completion, and archival remain blocked for that run; never use it to continue the failed candidate lifecycle or to bypass the one-authoritative-run and correction-budget gates.
  - Keep the source plan and active index at `status: deferred` with a concrete prerequisite, create a separate bounded repair plan without copying or rewriting source acceptance, and never archive the source plan as `replanned` for this path.
  - After the repair plan is checked, require a fresh source-plan digest, source HEAD, candidate lifecycle, and execution ledger, then return the source plan and active index to `in_progress` without new user approval only when requirements, safety conditions, scope, validation authority, and external-effect authorization remain unchanged.
  - Keep `replan_required` mandatory for scope, required-spec, or security-boundary drift, multiple independently validatable invariants that remain coupled, exhausted candidate or parent-remediation budgets, and post-authoritative discoveries that require changing source-plan boundaries, methods, validation authority, or acceptance mapping.
  - Preserve atomic restructuring and exact acceptance mapping for every `replan_required` path, preserve dirty product work, and reject any attempt to relabel requirement or security-boundary change as an independent repair.
  - Add deterministic median, edge, negative, and untuned holdout scenarios that cover the Plan 119 localized validation-authorization incident, same-run continuation rejection, deferred-source resumption after a checked repair, scope and security drift, coupled invariants, exhausted budgets, altered authority, and unauthorized requirement replacement.
  - Apply the accepted rule to Plan 119 by keeping it deferred, recording the localized defect as a separate bounded repair prerequisite after this plan is checked, and returning Plan 119 to `in_progress` only after that prerequisite is checked; do not create successor plans or a replan contract for Plan 119.
  - Keep root and generated agent policy, plan workflow, orchestration Skill, execution-ledger schema, fixtures, and deterministic checks aligned, preserve supported non-destructive Copier updates, run the authoritative suite exactly once for an otherwise acceptable policy candidate, and finish with zero unresolved High or Medium independent-review findings.
checked_summary_ja: 独立して修復できる局所障害では元planを置換せず、該当実行だけを停止して修復後に再開できる規則へ改める。

## Context

Plan 119 reached authoritative validation after focused checks and independent review had passed. A generated validation-command authorization defect then caused the current rule to require replacement of the entire integration plan, even though its requirement baseline and accepted safety conditions were unchanged.

This plan corrects the repository-wide classification and lifecycle rule. It does not absorb the Plan 119 implementation defect or weaken a hard replan trigger.

## Decisions

- Reuse `status: deferred` for the preserved source plan instead of adding another active-plan status.
- Add `repair_required` as a terminal execution-ledger state distinct from `replan_required`; both states block the current run before further effects.
- Select the independent-repair path only from explicit bounded-scope, unchanged-acceptance, unchanged-safety, unchanged-authority, and single-invariant evidence.
- Resume the source plan through a fresh run after the repair prerequisite is checked; never reopen the stopped ledger run.
- Use bounded parent implementation because this plan changes a fail-closed execution boundary. Require independent read-only review before focused and authoritative validation.

## State and Transition Contract

- `repair_required`: A terminal execution-ledger state for the current candidate lifecycle after one independently repairable defect is observed; it blocks more operations in that run but does not replace the source plan.
- Observed scope, required-spec, or security-boundary drift; multiple independently validatable invariants that remain coupled; exhausted candidate or parent-remediation budget; or a post-authoritative discovery that requires changing the source plan boundaries, methods, validation authority, or acceptance mapping.
- One observed defect with bounded write and validation scope that can be accepted independently while source acceptance, accepted safety boundaries, external-effect authority, and the remaining source plan stay unchanged.
- The original file under docs/plan/active and its docs/plan/plan.md row both use status deferred with completion_deferred_reason; the file is not archived or replaced.
- A separate numbered file in docs/plan/active with write scope limited to the defect, its deterministic validation, and the source-plan resume gate.
- A parent-owned transition that changes the original plan and active index from deferred to in_progress after the repair plan is checked and revalidates that source acceptance, safety conditions, scope, and authority are unchanged.
- The source plan user requirements, accepted safety conditions, write and validation boundaries, and external-effect authorization are byte-for-byte or semantically unchanged after the repair.

## Tasks

- [ ] Define exact plan and execution-ledger transitions for independent repair, hard replan, deferral, repair-plan creation, and fresh-run resumption.
- [ ] Update root and generated policy, orchestration Skill, ledger schema, runner gate messages, and lifecycle checks without weakening atomic restructuring.
- [ ] Add deterministic tuned and holdout scenarios for both independent repair and preserved hard-replan cases.
- [ ] Reclassify the recorded Plan 119 incident under the accepted rule and record its separate bounded repair prerequisite without replacing Plan 119.
- [ ] Complete independent review and focused validation, run the authoritative suite exactly once, archive this plan, and leave Plan 119 in the state required by its repair gate.

## Validation Notes

- Decision audit selected the existing deferred plan state and a new terminal execution-run state so plan retention does not imply unsafe same-run continuation.
- The advisory referent contract fixes the concrete conditions, stopped run, preserved plan, repair artifact, and fresh-run transition before introducing `repair_required`.
- Commit `19784a7` reverted the earlier technical successor split; Plan 119 remains the sole source plan for the Copier Skill integration.
