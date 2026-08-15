# Replace nested restructuring metadata structurally

status: replan_required
primary_invariant: nested restructuring replaces only top-level lineage fields and preserves the Markdown body byte-for-byte
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
replan_reason_codes:
  - parent_remediation_budget_exhausted
replan_source: docs/plan/active/094-nested-plan-restructuring.md
replan_contract: docs/plan/replanned/contracts/094-nested-plan-restructuring.json
integration_gates:
  - plan 096 must add index-aware durable successor resolution after archive rewriting is stable
  - plan 097 must prove the combined source acceptance
successor_plans:
  - docs/plan/active/095-structural-nested-replan-metadata.md
  - docs/plan/active/096-replanned-successor-resolution.md
  - docs/plan/active/097-nested-restructuring-integration.md
inherited_acceptance_digests:
  - sha256:3ae4971903cb6dec78aa12df5b218a8c8bad002223d7d036c84f559a3f497698
  - sha256:d2dec1d47d512a1c1ceaf64e2a60467f2b44a517b62a57624372f56303193df1
checked_summary_ja: 再計画メタデータだけを構造的に置換し、計画本文を保持した。

## Decisions

- Identify the manifest boundary before rewriting prior lineage.
- Remove prior scalar and list fields by parsed top-level field ranges, not indentation-specific regular expressions.
- Preserve the body suffix exactly and cover accepted noncanonical list indentation and blank separators.

## Tasks

- [ ] Replace regex lineage cleanup with structural manifest-range rewriting.
- [ ] Add body-preservation and noncanonical-list regression cases.
- [ ] Preserve root/template byte parity.
- [ ] Run focused validation, independent review, archive, and commit.

## Validation Notes

- Plan 094 stopped after two parent-direct Medium review rounds; its dirty script and test paths are wholly covered by this successor.
- Plan 095 stopped before authoritative validation after two parent-direct reviews found parser-boundary and field-order mismatches. The successor must use the first `## ` heading as the body boundary and compare the complete body suffix byte-for-byte.
