# Rewrite the complete nested-plan manifest

status: in_progress
primary_invariant: the Plan 095 implementation satisfies the structural acceptance inherited from stopped Plan 093
task_types:
  - planning_docs
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
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
  - git diff --check
acceptance:
  - Keep root and generated restructuring scripts byte-identical.
  - Add regression coverage for a two-level restructuring chain.
replan_source: docs/plan/active/093-structural-nested-replan-metadata.md
replan_contract: docs/plan/replanned/contracts/093-structural-nested-replan-metadata.json
integration_gates:
  - plan 095 must be completed and committed first
  - plan 097 must independently confirm the same inherited acceptance
successor_plans:
  - docs/plan/active/096-complete-nested-manifest-rewrite.md
  - docs/plan/active/097-nested-manifest-integration.md
inherited_acceptance_digests:
  - sha256:3ae4971903cb6dec78aa12df5b218a8c8bad002223d7d036c84f559a3f497698
  - sha256:d2dec1d47d512a1c1ceaf64e2a60467f2b44a517b62a57624372f56303193df1
checked_summary_ja: 本文見出しより前のマニフェスト全体を構造的に再構成した。

## Decisions

- Reuse the accepted Plan 095 implementation; do not introduce a second archive-rewrite implementation.
- Verify the first `## ` boundary, field-order variants, and complete body-suffix equality from durable tests.

## Tasks

- [ ] Confirm Plan 095 covers reordered fields, key whitespace, literal markers, indentation, and blank lines.
- [ ] Confirm the complete body suffix and root/template parity.
- [ ] Record focused validation evidence and archive without duplicate implementation.

## Validation Notes

- Plan 095 owns the shared implementation because numeric execution order precedes this lineage-certification plan.
