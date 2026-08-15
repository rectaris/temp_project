# Certify durable successor lineage

status: checked
primary_invariant: the Plan 097 implementation satisfies every durable-successor acceptance item inherited from stopped Plan 096
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
  - Resolve each durable contract successor from active, checked, or replanned history without treating replanned work as completed.
  - Require a replanned successor to retain the expected acceptance and inherited digest mapping.
  - Fail closed on missing, ambiguous, or mismatched replanned successor records.
  - Keep root and generated restructuring scripts byte-identical.
  - Add regression coverage for a two-level restructuring chain.
replan_source: docs/plan/active/096-replanned-successor-resolution.md
replan_contract: docs/plan/replanned/contracts/096-replanned-successor-resolution.json
integration_gates:
  - plan 097 must complete the exact archive and contract naming rules and authoritative validation first
  - plan 101 must independently confirm the same inherited acceptance
successor_plans:
  - docs/plan/active/100-durable-successor-lineage.md
  - docs/plan/active/101-durable-successor-integration.md
inherited_acceptance_digests:
  - sha256:0908ad93990decf1b54c1f77a5be7dd1c0c4901c204cec31541a5c9dffa5d176
  - sha256:8f60d17735beaa4d9e88df751a9d4794d2c1da8accc9d28443bc1cab5bc9f977
  - sha256:a846884e1c61fdd2afee0222a064addcb6bfd043b29c2d1f7deb6461d99d63a3
  - sha256:3ae4971903cb6dec78aa12df5b218a8c8bad002223d7d036c84f559a3f497698
  - sha256:d2dec1d47d512a1c1ceaf64e2a60467f2b44a517b62a57624372f56303193df1
checked_summary_ja: Plan 097 の耐久パス識別実装が継承要件を満たすことを確認した。

## Decisions

- Reuse the accepted Plan 097 implementation and do not add another resolver.
- Bind checked and replanned archive basenames exactly to the expected active-plan basename.
- Retain the contract filename grammar accepted by restructuring creation for historical compatibility.

## Tasks

- [x] Confirm Plan 097 covers exact checked/replanned archive identity and accepted contract-name compatibility.
- [x] Confirm wrong-ID, renamed-path, duplicate, and cross-state negatives.
- [x] Record focused validation evidence and archive without duplicate implementation.

## Validation Notes

- Plan 097 owns the remaining shared implementation because it executes before this lineage-certification plan.
- Commit `322aed4` binds active, checked, and replanned archive identity while accepting every contract filename allowed by creation.
- Focused validation passed: 19 plan-restructure tests and the Copier static check, including wrong-ID, renamed-path, duplicate, and cross-state cases.
