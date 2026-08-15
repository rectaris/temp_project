# Resolve replanned successors from durable indexes

status: replanned
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
replan_reason_codes:
  - parent_remediation_budget_exhausted
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/094-replanned-successor-resolution.md
replan_contract: docs/plan/replanned/contracts/094-replanned-successor-resolution.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/098-durable-successor-lineage.md
  - docs/plan/active/099-durable-successor-integration.md
inherited_acceptance_digests:
  - sha256:0908ad93990decf1b54c1f77a5be7dd1c0c4901c204cec31541a5c9dffa5d176
  - sha256:8f60d17735beaa4d9e88df751a9d4794d2c1da8accc9d28443bc1cab5bc9f977
  - sha256:a846884e1c61fdd2afee0222a064addcb6bfd043b29c2d1f7deb6461d99d63a3
  - sha256:3ae4971903cb6dec78aa12df5b218a8c8bad002223d7d036c84f559a3f497698
  - sha256:d2dec1d47d512a1c1ceaf64e2a60467f2b44a517b62a57624372f56303193df1
checked_summary_ja: active・checked・replanned の索引から後継計画を排他的に解決した。

## Decisions

- Rewrite the complete manifest prefix through the first `## ` heading and preserve the complete body suffix byte-for-byte.
- Read active, checked, and replanned indexes as the authority for durable state.
- Reject duplicate, stale, missing, or cross-state records before selecting a file.
- Validate a replanned successor's source content, archive lineage, acceptance, and inherited digest mapping without classifying it as checked.

## Tasks

- [ ] Finish structural nested-manifest rewriting and complete-body regression coverage.
- [ ] Add active-index parsing and exact successor record matching.
- [ ] Add stale, duplicate, missing-file, and cross-state ambiguity tests.
- [ ] Validate replanned source and archive lineage against ancestor expectations.
- [ ] Preserve root/template byte parity and run focused validation.

## Validation Notes

- The stopped Plan 093 dirty paths are inside this plan's write scope. This plan replaces its boundary strategy before implementing successor resolution.
- Two parent-direct remediation reviews still found Medium durable-path identity mismatches. Execution is stopped and the remaining naming rules move to a new integration boundary without changing acceptance.
