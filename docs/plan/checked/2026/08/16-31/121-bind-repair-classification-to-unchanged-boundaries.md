# Bind repair classification to unchanged plan boundaries

status: checked
primary_invariant: classify one observed defect as independently repairable only when canonical evidence proves every source-plan and execution boundary remains unchanged
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/replanned/2026/08/16-31/120-limit-plan-stop-scope-and-resume-local-repairs.md
  - references/orchestration.md
  - tests/fixtures/orchestration/plan-restructuring-scenarios.json
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - git diff --check
validation:
  - python3 tests/test-plan-execution-state.py
  - git diff --check
acceptance:
  - Replace the unconditional post-authoritative replan rule with an evidence-based classification that distinguishes one independently repairable defect from a change that requires reconstructing the source plan; elapsed time, implementation difficulty, and repeated investigation alone must not select either outcome.
  - Enter `repair_required` only when one observed defect has bounded write and validation scope, can be accepted independently, leaves every source acceptance item and accepted safety condition unchanged, does not change external-effect authority, and does not leave multiple independently validatable invariants coupled.
  - Make `repair_required` terminal for the affected execution-ledger run so candidate generation, correction, validation, apply, completion, and archival remain blocked for that run; never use it to continue the failed candidate lifecycle or to bypass the one-authoritative-run and correction-budget gates.
  - After the repair plan is checked, require a fresh source-plan digest, source HEAD, candidate lifecycle, and execution ledger, then return the source plan and active index to `in_progress` without new user approval only when requirements, safety conditions, scope, validation authority, and external-effect authorization remain unchanged.
  - Keep `replan_required` mandatory for scope, required-spec, or security-boundary drift, multiple independently validatable invariants that remain coupled, exhausted candidate or parent-remediation budgets, and post-authoritative discoveries that require changing source-plan boundaries, methods, validation authority, or acceptance mapping.
  - Preserve atomic restructuring and exact acceptance mapping for every `replan_required` path, preserve dirty product work, and reject any attempt to relabel requirement or security-boundary change as an independent repair.
  - Add deterministic median, edge, negative, and untuned holdout scenarios that cover the Plan 119 localized validation-authorization incident, same-run continuation rejection, deferred-source resumption after a checked repair, scope and security drift, coupled invariants, exhausted budgets, altered authority, and unauthorized requirement replacement.
  - Keep root and generated agent policy, plan workflow, orchestration Skill, execution-ledger schema, fixtures, and deterministic checks aligned, preserve supported non-destructive Copier updates, run the authoritative suite exactly once for an otherwise acceptable policy candidate, and finish with zero unresolved High or Medium independent-review findings.
replan_source: docs/plan/active/120-limit-plan-stop-scope-and-resume-local-repairs.md
replan_contract: docs/plan/replanned/contracts/120-limit-plan-stop-scope-and-resume-local-repairs.json
integration_gates:
  - plan 122 must retain and prove every source acceptance item after this classification invariant is checked
successor_plans:
  - docs/plan/active/121-bind-repair-classification-to-unchanged-boundaries.md
  - docs/plan/active/122-integrate-bounded-repair-lifecycle.md
inherited_acceptance_digests:
  - sha256:8898adaa364a4932f3660cf4f5c47114cfd7e9687d06f7cc62e73dbf1ba65a3d
  - sha256:cfd2b46510f6bd3533c62c3e1503dc2d3010b1995e49ed5163cdf81cd509dbaf
  - sha256:5948c72448f7d7d118ab173f9a56b625194b98ed698a878ba21573a7b9ba2c1f
  - sha256:54255e9fb54c80aba47dee344b89680d0f78239f90793711f99adefd6e5ec94d
  - sha256:3f22e83f645a804faff92f5c76d5f3282436ba9c71d11fbe054c9eb8cc1e27e1
  - sha256:d7f246113a7eab876a763129f839d293c7e8d8cf02958093933cda4eb99aba19
  - sha256:5190311890ea0c0a26c5398ebd7eb6c998c331c65fec90036e89b5139805d911
  - sha256:ecca71c4a2aa0f3679c22cdcc72cd5aea1b5464de1532ea6d05f3fdadae8625f
checked_summary_ja: 修復分類を元planのscope、検証権限、不変条件を含む変更前後の境界へ結合する。

## Decisions

- Extend canonical classification evidence with strict unchanged source scope, validation authority, and invariant-boundary predicates.
- Classify every false predicate to a hard replan reason atomically under the same ledger lock.
- Recompute the stored evidence digest from embedded canonical classification bytes during every ledger read.
- Use bounded parent implementation only for this remaining validation-authority invariant and require one independent read-only review before validation.

## Tasks

- [x] Add failing tests for each missing unchanged predicate and its atomic hard-stop reason.
- [x] Complete the exact evidence schema and root/template byte-identical ledger implementation.
- [x] Obtain zero unresolved High or Medium independent-review findings and run the focused validation once.
- [x] Archive and commit this slice before Plan 122 begins.

## Validation Notes

- This successor preserves the mapped source acceptance text exactly.
- The source plan stopped after two independently reviewed parent-direct remediation rounds still left one Medium classification gap.
- Independent read-only review reported High 0 and Medium 0 after checking the canonical predicates, atomic transition, digest binding, and history replay boundary.
- Focused validation passed: `python3 tests/test-plan-execution-state.py` (19 tests), root/template script byte comparison, and `git diff --check` for the Plan 121 write scope.
- The parent-owned external execution ledger ended active after the accepted review and focused-validation events; no unresolved risks remain in this slice.
