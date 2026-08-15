# Integrate nested manifest rewriting

status: in_progress
primary_invariant: every accepted manifest ordering produces one canonical lineage block and an unchanged Markdown body
task_types:
  - planning_docs
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - tests/test-plan-restructure.py
context_files:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
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
  - git diff --check
acceptance:
  - Keep root and generated restructuring scripts byte-identical.
  - Add regression coverage for a two-level restructuring chain.
replan_source: docs/plan/active/093-structural-nested-replan-metadata.md
replan_contract: docs/plan/replanned/contracts/093-structural-nested-replan-metadata.json
integration_gates:
  - plans 095 and 096 must be completed and committed first
successor_plans:
  - docs/plan/active/096-complete-nested-manifest-rewrite.md
  - docs/plan/active/097-nested-manifest-integration.md
inherited_acceptance_digests:
  - sha256:3ae4971903cb6dec78aa12df5b218a8c8bad002223d7d036c84f559a3f497698
  - sha256:d2dec1d47d512a1c1ceaf64e2a60467f2b44a517b62a57624372f56303193df1
checked_summary_ja: マニフェスト順序の異常系と本文完全一致を統合検証した。

## Decisions

- Compare the complete source and archive suffixes from the first `## ` heading.
- Exercise checked summary and prior lineage both before and after one another.
- Reject duplicate or missing structural fields before writing the transition.

## Tasks

- [ ] Confirm the accepted field-order and complete-body regression matrix.
- [ ] Confirm root/template parity and static inventory.
- [ ] Run independent review and focused validation.
- [ ] Archive the final Plan 093 lineage record.

## Validation Notes

- This integration plan copies both source acceptance items exactly.
