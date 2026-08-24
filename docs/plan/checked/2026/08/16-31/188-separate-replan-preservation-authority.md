# Separate replan preservation from write authority

status: checked
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/102-select-runnable-active-plan.md
primary_invariant: restructuring preserves every declared dirty product path without granting that path to candidate generation, validation, apply, staging, or commit
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
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - docs/plan/replanned/contracts/183-build-bounded-copier-transition-fixture.json
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-root-agent-policy.py
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-root-agent-policy.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Separate exact dirty-product preservation coverage from executable write authority, and reject overlap or use of preservation coverage to authorize candidate, validation, apply, stage, or commit effects.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:852f2498d16d25d44ff1b3de200528e6ed70a43b22ddb05e1d981a6144efb32c","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
integration_gates:
  - Plan 102 is checked at docs/plan/checked/2026/08/16-31/102-select-runnable-active-plan.md
  - preserve scripts/check-copier-template.py and tests/copier-update.sh without editing, staging, or committing them
  - Plan 189 remains deferred until this plan is checked and its exact checked archive path replaces this active predecessor
checked_summary_ja: 未commit差分の保持対象と実際の書込権限を分離し、保持指定から実装権限を導出できないようにする。

## Decisions

- preservation_scope means the exact dirty product paths that restructuring must retain but that the plan is not authorized to edit, stage, or commit.
- Extend restructuring specifications and contracts with preservation_scope while retaining write_scope as the only product-write authority.
- Permit preservation coverage to satisfy dirty-path retention only; reject its use in worker contracts, patch admission, validation authority, apply, staging, and commit checks.
- Reject duplicate, overlapping, non-normalized, missing, or silently dropped preservation entries and preserve schema-1 verification compatibility.
- Keep root and generated policy and restructuring implementations semantically aligned.
- Use bounded parent implementation and independent review because this plan changes lifecycle and security validation authority.

## Tasks

- [x] Extend the root and generated restructuring schema, verifier, and atomic rollback tests.
- [x] Enforce disjoint preservation_scope and write_scope effects at every candidate and parent-owned lifecycle boundary.
- [x] Add positive, tampering, overlap, dropped-path, and legacy schema tests.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, archive, commit, and activate Plan 189 with the exact checked predecessor path.

## Validation Notes

- This plan changes no preserved product candidate bytes.
- The user authorized the active-plan reconstruction on 2026-08-24.
- Focused validation passed with 22 restructuring tests, the root agent policy check, and `git diff --check`.
- Independent read-only review found zero unresolved High or Medium correctness or security findings.
- The authoritative validation suite passed once: `python3 tests/test-plan-restructure.py`, `python3 scripts/check-root-agent-policy.py`, `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, and `git diff --check`.
