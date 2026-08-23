# Verify Plan 176 successor acceptance

status: in_progress
primary_invariant: Plans 177 through 179 resume only after the checked guardian implementation and both durable replan contracts prove the unchanged Plan 176 acceptance boundary
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
  - AGENTS.md
  - copier.yml
  - references/orchestration.md
  - scripts/project_workflow/copier_inventory.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/180-admit-live-validation-witness-guardian.md
  - docs/plan/replanned/2026/08/16-31/176-establish-live-validation-witness-provenance.md
  - docs/plan/replanned/2026/08/16-31/163-capture-validation-witness-migration-provenance.md
  - docs/plan/replanned/contracts/163-capture-validation-witness-migration-provenance.json
  - docs/plan/active/177-align-validation-witness-provenance-policy.md
  - docs/plan/active/178-wire-validation-witness-copier-transition.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - pytest tests/test-copier-migration.py
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - pytest tests/test-copier-migration.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"pytest tests/test-copier-migration.py"}
replan_source: docs/plan/active/176-establish-live-validation-witness-provenance.md
replan_contract: docs/plan/replanned/contracts/176-establish-live-validation-witness-provenance.json
integration_gates:
  - Plan 180 must be checked and its exact checked archive path must replace the active context path before validation starts
  - the Plan 176 and Plan 163 replan contracts must both resolve without ambiguous active, checked, or replanned successor state
  - Plan 177 must not start until this plan is checked and its exact checked archive path replaces the active dependency
successor_plans:
  - docs/plan/active/180-admit-live-validation-witness-guardian.md
  - docs/plan/active/181-verify-plan176-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: checked済みguardian実装と二段の再計画契約を確認し、Plan 177以降の再開条件を確定する。

## Decisions

- Plan 176 successor acceptance means this separate verification of the checked Plan 180 implementation and nested Plan 176 and Plan 163 replan contracts before Plan 177 resumes.
- The six declared product paths are preservation-only coverage required by the atomic restructuring contract because they were dirty when Plan 176 stopped.
- Do not edit, stage, or commit those six paths in this plan; Plans 177 and 178 remain their executable owners, and any need to change them here requires `replan_required`.
- Commit only parent-owned plan lifecycle files after verification passes.
- Keep Plan 179 as the operational migration dependency consumed by Plans 164 through 167.

## Tasks

- [ ] Replace the active Plan 180 context with its exact checked archive path and confirm its accepted commit contains only the reviewed script-and-test implementation.
- [ ] Verify the Plan 176 contract, the ancestor Plan 163 contract, and every active, checked, or replanned successor identity without changing product files.
- [ ] Confirm the six preservation-only dirty paths remain unstaged and continue to match their Plan 177 or Plan 178 ownership.
- [ ] Complete fresh independent review and focused validation with zero unresolved High or Medium findings, then archive and commit only plan lifecycle changes.

## Validation Notes

- This plan exists because an atomic hard replan requires one integration successor even though Plan 180 contains the complete Plan 176 implementation scope.
- The broad write scope records preservation coverage and does not authorize bypassing the narrower implementation owners in Plans 177 and 178.
- Plans 177, 178, and 179 retain their existing Plan 163 lineage and exact inherited acceptance text.
