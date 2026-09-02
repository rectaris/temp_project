# Replan reachable pre-schema fixture constructions

status: deferred
completion_deferred_reason: parent-direct remediation budget is exhausted while the candidate changes remain preserved outside this plan's write scope
primary_invariant: preserve the exact accepted reachability requirement while stopping further implementation until a clean, independently reviewable execution boundary is available
replan_sources:
  - docs/plan/active/250-require-reachable-fixture-constructions.md
replan_contract: docs/plan/replanned/contracts/250-require-reachable-fixture-constructions.json
successor_plans:
  - docs/plan/active/263-replan-reachable-fixture-constructions.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
integration_source_ids:
  - 250
integration_gates:
  - do not modify the preserved candidate paths through this plan
  - establish a clean implementation boundary before resuming the inherited acceptance item
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - docs/plan/active/263-replan-reachable-fixture-constructions.md
preservation_scope:
  - scripts/project_workflow/copier_fixture_validator.py
  - tests/test-copier-fixture-validator.py
context_files:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/replanned/contracts/250-require-reachable-fixture-constructions.json
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
checked_summary_ja: 親実装の修正予算を使い切ったため、保持済み候補を変更せずに再開可能な実行境界を再構成する。

## Tasks

- [ ] Preserve the inherited acceptance item and the existing candidate paths without modifying them.
- [ ] Establish a clean execution boundary and reconstruct a bounded implementation plan before resuming validation-authority changes.

## Validation Notes

- Deferred after the parent-direct remediation budget was exhausted. The preserved candidate paths are intentionally outside this plan's write scope.
