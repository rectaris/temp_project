# Verify nested plan restructuring lineage

status: replan_required
primary_invariant: a successor that is itself durably replanned remains valid evidence in every ancestor restructuring contract
task_types:
  - planning_docs
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - docs/plan/
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-copier-template.py
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Resolve each durable contract successor from active, checked, or replanned history without treating replanned work as completed.
  - Require a replanned successor to retain the expected acceptance and inherited digest mapping.
  - Fail closed on missing, ambiguous, or mismatched replanned successor records.
  - Keep root and generated restructuring scripts byte-identical.
  - Add regression coverage for a two-level restructuring chain.
  - Finish with zero unresolved High or Medium independent-review findings.
replan_reason_codes:
  - parent_remediation_budget_exhausted
checked_summary_ja: 再計画された後継計画を祖先の契約検証でも正しく追跡できるようにした。

## Decisions

- Resolve replanned successors through `docs/plan/replanned.md`; do not add them to the checked index.
- Validate the successor's archived lineage and acceptance before accepting it as the live durable record.
- Keep the original contract content immutable and follow the successor by plan ID.

## Tasks

- [ ] Add a two-level restructuring regression fixture.
- [ ] Resolve replanned successors in durable contract verification.
- [ ] Preserve root/template parity and fail-closed ambiguity checks.
- [ ] Run focused and authoritative validation, archive, and commit.

## Validation Notes

- A generated project successfully restructured Plan 105 into Plans 106 and 107, then `restructure-plan.py --verify` rejected the older Plan 103 contract only because its Plan 105 successor had moved from active to replanned history.
- Run `temp-project-plan092a-20260815` stopped before authoritative validation after two parent-direct reviews found unsafe Markdown-range deletion and incomplete active-index ambiguity detection. Requirements and acceptance remain unchanged for successor restructuring.
