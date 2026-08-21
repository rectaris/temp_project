# Integrate bounded repair lifecycle and resume preserved plans

status: deferred
deferred_prerequisite: plan 121 must be checked and committed with zero unresolved High or Medium findings
primary_invariant: integrate the accepted independent-repair classifier across root and generated policy while preserving every Plan 120 acceptance item and the hard-replan boundary
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
  - references/orchestration.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/
  - docs/plan/
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
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/119-integrate-verify-copier-update-skill.md
  - docs/plan/active/121-bind-repair-classification-to-unchanged-boundaries.md
  - docs/plan/replanned/2026/08/16-31/120-limit-plan-stop-scope-and-resume-local-repairs.md
  - scripts/restructure-plan.py
  - scripts/run-sandboxed-plan-worker.py
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
replan_source: docs/plan/active/120-limit-plan-stop-scope-and-resume-local-repairs.md
replan_contract: docs/plan/replanned/contracts/120-limit-plan-stop-scope-and-resume-local-repairs.json
integration_gates:
  - plan 121 must be checked and committed before integration validation begins
  - the final independent review must report zero unresolved High or Medium findings across both successor slices
successor_plans:
  - docs/plan/active/121-bind-repair-classification-to-unchanged-boundaries.md
  - docs/plan/active/122-integrate-bounded-repair-lifecycle.md
inherited_acceptance_digests:
  - sha256:8898adaa364a4932f3660cf4f5c47114cfd7e9687d06f7cc62e73dbf1ba65a3d
  - sha256:cfd2b46510f6bd3533c62c3e1503dc2d3010b1995e49ed5163cdf81cd509dbaf
  - sha256:5948c72448f7d7d118ab173f9a56b625194b98ed698a878ba21573a7b9ba2c1f
  - sha256:3714eb9a5dcf504cd2bd515325dfd58e754b4907dbb2c4f40d6dc5c04d55fbc5
  - sha256:54255e9fb54c80aba47dee344b89680d0f78239f90793711f99adefd6e5ec94d
  - sha256:3f22e83f645a804faff92f5c76d5f3282436ba9c71d11fbe054c9eb8cc1e27e1
  - sha256:d7f246113a7eab876a763129f839d293c7e8d8cf02958093933cda4eb99aba19
  - sha256:5190311890ea0c0a26c5398ebd7eb6c998c331c65fec90036e89b5139805d911
  - sha256:d32c58b78d02173ce16bcbcfc594b19dcf5f77bd7552fc1b2daf1c3f5adbb27f
  - sha256:ecca71c4a2aa0f3679c22cdcc72cd5aea1b5464de1532ea6d05f3fdadae8625f
checked_summary_ja: 局所修復と強制再構成を区別する規則をrootと生成物へ統合し、元planを修復後に新しい実行として再開できるようにする。

## Decisions

- Admit only the checked Plan 121 classifier implementation before policy integration.
- Preserve all hard-replan reasons and require atomic hard stop for every false unchanged-boundary predicate.
- Keep Plan 119 as one deferred source plan; create only a bounded repair prerequisite for its localized validation-authorization defect.
- Run the authoritative suite exactly once after independent review and focused validation pass.

## Tasks

- [ ] Admit Plan 121 and align root and generated policy, Skill, fixtures, and deterministic marker checks.
- [ ] Prove median, edge, negative, and untuned holdout outcomes without weakening hard-replan scenarios.
- [ ] Record Plan 119's bounded repair prerequisite without creating a successor or replan contract for Plan 119.
- [ ] Complete independent review, focused validation, and the authoritative suite exactly once.
- [ ] Archive this integration plan and leave Plan 119 in the state required by its repair gate.

## Validation Notes

- This integration successor copies every source acceptance item exactly.
