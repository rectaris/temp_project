# Accept historical schema-1 preservation metadata

status: checked
primary_invariant: immutable schema-1 replan contracts remain verifiable without treating partial historical preservation metadata as schema-2 authority
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - docs/plan/active/190-migrate-live-plan-contracts.md
  - docs/plan/plan.md
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/188-separate-replan-preservation-authority.md
  - docs/plan/checked/2026/08/16-31/189-enforce-active-plan-predecessors.md
  - docs/plan/checked/2026/08/16-31/164-bind-replan-contract-validation-baseline.md
  - docs/plan/active/190-migrate-live-plan-contracts.md
  - docs/plan/replanned/contracts/133-evaluate-resource-bounded-orchestration.json
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Verify immutable schema-1 replan contracts with partial preservation metadata by requiring valid declared coverage and write-scope separation without applying schema-2 exact-once adoption, while preserving strict schema-2 enforcement and every historical contract byte.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:23ad07dd94f121424bc0c89a60cef00ba6683cabef2d4f9ff9a50f9c9608c54d","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/188-separate-replan-preservation-authority.md
  - docs/plan/checked/2026/08/16-31/189-enforce-active-plan-predecessors.md
  - docs/plan/checked/2026/08/16-31/164-bind-replan-contract-validation-baseline.md
integration_gates:
  - preserve every existing replan-contract byte, source acceptance item, successor lineage, and product byte
  - keep schema-2 preservation coverage exact, complete, unique, and disjoint from every successor write_scope
  - Plan 190 remains deferred until this plan is checked and its exact checked archive path replaces the active predecessor
checked_summary_ja: schema 1の不完全な保持情報をschema 2の権限として扱わず、既存契約を変更せず検証可能にする。

## Decisions

- historical-schema1-preservation-compatibility means validating declared preservation coverage in immutable schema-1 contracts without requiring schema-2 exact-once adoption across every embedded successor.
- For schema 1, validate every declared preservation path, keep the complete declared preservation set disjoint from every preservation-declaring successor write_scope, require the declared union to equal dirty_product_paths when any successor declares preservation_scope, and permit repeated coverage across sequential successors.
- For schema 2, retain the current all-successor schema consistency, exact-once coverage, live-plan equality, and write-scope separation checks.
- Treat an omitted schema-1 preservation_scope as absence of historical preservation authority; do not derive write, validation, apply, staging, or commit authority from it.
- plan190-verifier-prerequisite means the checked verifier correction and successful repository contract verification required before Plan 190 resumes.
- Keep root and generated restructuring implementations byte-aligned and use bounded parent implementation with independent review because this changes lifecycle validation authority.

## Tasks

- [x] Add explicit schema-version handling for historical partial preservation metadata without changing any contract.
- [x] Add positive Plan 133-shaped coverage and negative missing-coverage, cross-successor overlap, and schema-2 regression tests.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, archive, commit, and reactivate Plan 190 with this exact checked predecessor.

## Validation Notes

- The current repository failure is `contract successors mix preservation schemas for 133`.
- This plan changes verifier behavior and tests only; Plan 190 retains ownership of companion publication and active-plan metadata migration.
- Focused validation passed: `python3 tests/test-plan-restructure.py`, `python3 scripts/check-copier-template.py`, and `git diff --check`.
- Independent review reported zero High or Medium findings; its two Low test-coverage findings were addressed before authoritative validation.
- Authoritative validation passed once: `python3 tests/test-plan-restructure.py`, `python3 scripts/check-copier-template.py`, `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, and `git diff --check`.
