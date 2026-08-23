# Admit reconstructed-plan validation commands

status: deferred
completion_deferred_reason: Plan 164 must be checked and its exact checked archive path must replace the active predecessor before implementation.
primary_invariant: every new validation command used by the reconstructed active chain is admitted by an exact root allowlist rule before dependent activation without expanding generated-project-specific authority
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
  - scripts/plan_validation_commands.py
  - tests/validation_tools/plan.py
preservation_scope:
  - scripts/check-copier-template.py
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Admit only the exact reconstructed-plan validation commands needed by Plans 190, 191, 185, and 186 in the root allowlist, while preserving generated-project-specific authority and shared semantic command families.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:cac00ac6f45d5ceda22dea50a283e173be051aa97fc0ae7a73636c7f56e681b3","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
predecessor_plans:
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
integration_gates:
  - Plan 164 must be checked and its exact checked archive path must replace this active predecessor before implementation
  - preserve scripts/check-copier-template.py and tests/copier-update.sh without editing, staging, or committing them
  - Plan 190 remains deferred until this plan is checked and its exact checked archive path replaces its active predecessor
checked_summary_ja: 再構築後のroot planが使う新しい検証commandだけをroot allowlistへ追加し、生成先固有の権限境界を保つ。

## Decisions

- Admit exactly `python3 scripts/restructure-plan.py --verify`, `python3 tests/test-copier-fixture.py`, `python3 -m py_compile scripts/project_workflow/copier_fixture.py tests/test-copier-fixture.py`, and `python3 scripts/project_workflow/copier_fixture.py --check tests/copier-update.sh`.
- Reject alternate paths, extra arguments, shell syntax, reordered arguments, and broader interpreter or script prefixes.
- Preserve generated-project-only namespace and legacy-bridge authority; align only shared command families semantically and do not add root-only fixture paths to the generated allowlist.
- Use bounded parent implementation and independent review because command admission is validation authority.

## Tasks

- [ ] Add the four exact command forms to the root validation policy only.
- [ ] Add positive and negative tests for exact argv identity and every near-match rejection.
- [ ] Prove the generated policy still rejects root-only fixture and replan commands while its existing project-local families remain unchanged.
- [ ] Run check-plan against Plans 190, 191, 185, and 186.
- [ ] Complete focused validation and independent review, archive, commit, and activate Plan 190.

## Validation Notes

- This plan admits commands only; it does not implement or run the bounded fixture or complete Copier transition.
