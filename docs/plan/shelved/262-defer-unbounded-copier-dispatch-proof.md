# Defer unbounded Copier dispatch proof

status: shelved
shelved_reason: owner directed on 2026-09-02 that this static proof not be implemented because it exceeds the bounded validator authority
shelved_at: 2026-09-02
primary_invariant: do not claim that a static fixture validator proves every sourced Copier wrapper dispatch is real when doing so requires modelling shell control flow, command lookup, source activation, and dynamic command values beyond the validator's bounded authority
replan_sources:
  - docs/plan/active/261-source-aware-copier-dispatch.md
replan_contract: docs/plan/replanned/contracts/261-defer-unbounded-copier-dispatch-proof.json
integration_gates:
  - this plan must remain unimplemented unless the owner explicitly authorizes a bounded validation surface that does not require complete shell or command-lookup semantics
successor_plans:
  - docs/plan/active/262-defer-unbounded-copier-dispatch-proof.md
inherited_acceptance_digests:
  - sha256:4eb4303761f318ee3b775f758771b9cbc4cccbb5cbdca2a509cb315f93bd01f4
integration_source_ids:
  - 261
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: high
write_scope:
  - scripts/project_workflow/shell_execution.py
  - scripts/project_workflow/copier_fixture_validator.py
  - tests/test-shell-execution.py
  - tests/test-copier-fixture-validator.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/09/01-15/249-reject-sourced-library-command-shadowing.md
  - tests/copier-update.sh
  - tests/lib-copier.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-shell-execution.py
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-shell-execution.py
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Reject a sourced Copier wrapper whose only Copier dispatch sits on a command list the shell can skip, while accepting a wrapper whose every normal exit reaches one direct Copier or `uv run copier` dispatch.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:4eb4303761f318ee3b775f758771b9cbc4cccbb5cbdca2a509cb315f93bd01f4","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
predecessor_plans:
  - docs/plan/checked/2026/09/01-15/249-reject-sourced-library-command-shadowing.md
checked_summary_ja: 静的validatorの責務を超えるCopier dispatchの完全証明を実装対象から外す。

## Decisions

- Do not implement the source-aware dispatch proof. Independent review showed that its required proof includes coupled shell control flow, command lookup, source activation, redirection recovery, and dynamic command-value semantics.
- Retain the inherited acceptance unchanged in this shelved successor. The owner may reactivate it only with an explicitly bounded validation surface that does not require reimplementing shell semantics.
- Keep the existing sourced-library shadowing checks and the runtime fixture validation. They remain the supported assurance boundary.

## Tasks

- [ ] Resume only after the owner authorizes a bounded replacement validation surface.

## Validation Notes

- The owner directed on 2026-09-02 that the Plan 261 implementation not be introduced after independent review found unresolved High findings in the required shell-semantics proof.
