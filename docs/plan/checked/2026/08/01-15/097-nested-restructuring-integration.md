# Integrate nested restructuring verification

status: checked
primary_invariant: a two-level restructuring chain preserves every ancestor acceptance item and fails closed on every durable-state ambiguity
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
replan_source: docs/plan/active/094-nested-plan-restructuring.md
replan_contract: docs/plan/replanned/contracts/094-nested-plan-restructuring.json
integration_gates:
  - replace the stopped Plan 096 naming boundary with exact checked and replanned archive identity
  - preserve every contract filename accepted by the creation grammar
  - run the full authoritative suite exactly once after independent acceptance
successor_plans:
  - docs/plan/active/095-structural-nested-replan-metadata.md
  - docs/plan/active/096-replanned-successor-resolution.md
  - docs/plan/active/097-nested-restructuring-integration.md
inherited_acceptance_digests:
  - sha256:0908ad93990decf1b54c1f77a5be7dd1c0c4901c204cec31541a5c9dffa5d176
  - sha256:8f60d17735beaa4d9e88df751a9d4794d2c1da8accc9d28443bc1cab5bc9f977
  - sha256:a846884e1c61fdd2afee0222a064addcb6bfd043b29c2d1f7deb6461d99d63a3
  - sha256:3ae4971903cb6dec78aa12df5b218a8c8bad002223d7d036c84f559a3f497698
  - sha256:d2dec1d47d512a1c1ceaf64e2a60467f2b44a517b62a57624372f56303193df1
  - sha256:d745ca0186995e7c8bdec00d17b5909eac74c09d9bdbadeb9998b8afabd160f4
checked_summary_ja: 二段階の再計画契約と異常系を統合検証した。

## Decisions

- Exercise both ancestor and nested contracts in one disposable repository.
- Cover body preservation, noncanonical accepted manifest layout, and every index-state ambiguity.
- Bind checked and replanned archive basenames exactly to the expected active source basename while retaining accepted same-ID contract filenames.
- Keep the full repository suite as the only authoritative validation attempt.

## Tasks

- [x] Complete the two-level positive and tampering matrix.
- [x] Reject renamed checked archives and accept immediate verification for alternate same-ID contract filenames.
- [x] Preserve root/template parity after the final durable-identity implementation.
- [x] Confirm root/template parity and Copier inventory.
- [x] Run independent review and the authoritative full suite.
- [x] Archive and commit the integration plan before lineage-certification Plans 098 and 099.

## Validation Notes

- This integration successor copies every Plan 094 acceptance item exactly.
- Plan 096 stopped after two parent-direct Medium review rounds. This plan owns the remaining exact archive-path and compatible contract-name rules before the full validation gate.
- Independent review found zero High, Medium, or Low findings after the exact checked-archive and creation-compatible contract-name fixes.
- Authoritative validation passed once: 19 plan-restructure tests, Copier static check, workflow lint, smoke suite, change-aware validation for all changed paths, and `git diff --check`.
