# Integrate durable successor lineage

status: checked
primary_invariant: every durable successor record is selected by exact source identity and remains compatible with contracts accepted at creation
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
  - Resolve each durable contract successor from active, checked, or replanned history without treating replanned work as completed.
  - Require a replanned successor to retain the expected acceptance and inherited digest mapping.
  - Fail closed on missing, ambiguous, or mismatched replanned successor records.
  - Keep root and generated restructuring scripts byte-identical.
  - Add regression coverage for a two-level restructuring chain.
replan_source: docs/plan/active/096-replanned-successor-resolution.md
replan_contract: docs/plan/replanned/contracts/096-replanned-successor-resolution.json
integration_gates:
  - plans 097, 098, 099, and 100 must be completed and committed first
successor_plans:
  - docs/plan/active/100-durable-successor-lineage.md
  - docs/plan/active/101-durable-successor-integration.md
inherited_acceptance_digests:
  - sha256:0908ad93990decf1b54c1f77a5be7dd1c0c4901c204cec31541a5c9dffa5d176
  - sha256:8f60d17735beaa4d9e88df751a9d4794d2c1da8accc9d28443bc1cab5bc9f977
  - sha256:a846884e1c61fdd2afee0222a064addcb6bfd043b29c2d1f7deb6461d99d63a3
  - sha256:3ae4971903cb6dec78aa12df5b218a8c8bad002223d7d036c84f559a3f497698
  - sha256:d2dec1d47d512a1c1ceaf64e2a60467f2b44a517b62a57624372f56303193df1
checked_summary_ja: 耐久索引のパス識別と二段階再計画を統合検証した。

## Decisions

- Exercise creation and immediate verification with both canonical and accepted alternate contract filenames.
- Reject renamed checked archives even when their numeric prefixes still match.
- Keep the full ancestor acceptance matrix as the final lineage gate.

## Tasks

- [x] Confirm the accepted contract-name and renamed-checked regression cases.
- [x] Confirm root/template parity and static inventory.
- [x] Run independent review and focused validation.
- [x] Archive the final Plan 096 lineage record.

## Validation Notes

- This integration plan copies every source acceptance item exactly.
- Independent read-only review found zero High, Medium, or Low findings and separately verified alternate contract filenames accepted by creation.
- Focused validation passed: 19 plan-restructure tests, Copier static check, durable contract verification, root/template byte parity, and `git diff --check`.
