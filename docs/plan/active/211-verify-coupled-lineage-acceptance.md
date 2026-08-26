# Verify coupled lineage acceptance

status: in_progress
implementation_tier: 2
primary_invariant: one durable locked transaction can replace a stopped active successor and its immutable dependent successor while applying only exact authorized reference projections in later dependents and leaving every historical contract byte, acceptance item, write scope, validation authority, and unaffected predecessor edge unchanged
replan_sources:
  - docs/plan/active/200-enable-coupled-lineage-reconstruction.md
  - docs/plan/active/201-reconstruct-shell-parser-lineage.md
replan_contract: docs/plan/replanned/contracts/200-enable-coupled-lineage-reconstruction.json
integration_gates:
  - combined successors must satisfy every source acceptance item
  - activate only after Plan 210 is checked and its exact checked archive replaces the active predecessor
  - bind every acceptance clause to an enforcing code path and an executable negative test before claiming acceptance
  - preserve the checked Plan 206, 209, 213, 215, 216, 217, 218, 219, and 220 behavior without weakening any existing check
  - keep root and generated restructure commands byte-identical
  - Plan 212 remains deferred until this plan is checked and its exact checked archive replaces the active predecessor
successor_plans:
  - docs/plan/active/211-verify-coupled-lineage-acceptance.md
  - docs/plan/active/212-reconstruct-shell-parser-lineage.md
inherited_acceptance_digests:
  - sha256:3cc1064bb989622dab9eaca79fc89afaba85b8aabd7191dd4935882d8ba797ef
integration_source_ids:
  - 200
reserved_by: 210
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/replanned/2026/08/16-31/200-enable-coupled-lineage-reconstruction.md
  - docs/plan/checked/2026/08/16-31/206-enforce-per-source-integration-coverage.md
  - docs/plan/checked/2026/08/16-31/209-enable-direct-active-source-reconstruction.md
  - docs/plan/checked/2026/08/16-31/215-enforce-canonical-lifecycle-verification.md
  - docs/plan/checked/2026/08/16-31/216-bind-journal-replacement-identity.md
  - docs/plan/checked/2026/08/16-31/217-enforce-plan-id-reservations.md
  - docs/plan/checked/2026/08/16-31/218-restore-terminal-checked-archive-status.md
  - docs/plan/checked/2026/08/16-31/219-honor-activation-context-rebinding.md
  - docs/plan/checked/2026/08/16-31/220-resolve-active-plan-context-references.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 -m py_compile scripts/restructure-plan.py template/.project-agent-workflow/scripts/restructure-plan.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Provide one atomic, fail-closed lifecycle operation that reconstructs a stopped successor with its immutable dependent successor and exact bounded dependent rebindings while preserving existing contract bytes, acceptance, write scopes, validation authority, and the complete active predecessor graph.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:3cc1064bb989622dab9eaca79fc89afaba85b8aabd7191dd4935882d8ba797ef","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/210-reconstruct-coupled-capability-lineage.md
checked_summary_ja: coupled lineage reconstructionのacceptance条項を強制pathと否定testへ一対一で束縛し、不足する強制とtestを補う。

## Decisions

- Coupled lineage acceptance verification means proving each clause of the inherited Plan 200 acceptance against one enforcing code path and one executable negative test in the current repository.
- Decompose the inherited acceptance into seven verifiable clauses: atomicity, fail-closed preflight, stopped-successor replacement, immutable dependent replacement, exact bounded dependent rebinding, historical byte and acceptance and write-scope and validation-authority preservation, and complete active predecessor graph preservation.
- Treat the checked Plans 206, 209, 213, 215, 216, 217, 218, 219, and 220 as the existing enforcement baseline; this plan may extend that baseline but must not weaken any check it already accepts.
- Record the clause-to-enforcement binding in `tests/test-plan-restructure.py` as executable coverage rather than prose, so a removed enforcement path fails the focused suite.
- Add a missing negative test for every clause that currently has no direct rejecting case, and prefer a hold-out case that mutates one enforced condition at a time.
- Keep the authoritative validation suite inherited from Plan 200 unchanged; this plan adds coverage and never removes or weakens an admitted command.
- Keep `scripts/restructure-plan.py` and `template/.project-agent-workflow/scripts/restructure-plan.py` byte-identical, and keep the root and generated Plan Workflow coupled-reconstruction policy semantically aligned.
- Record the clause decomposition in the Plan Workflow specification so a later reader can reproduce the acceptance argument without reading the test source.
- Use bounded parent implementation and fresh independent review because this plan asserts final acceptance over lifecycle and validation-authority code.

## Tasks

- [ ] Enumerate the seven acceptance clauses and bind each to its exact enforcing function in `scripts/restructure-plan.py`.
- [ ] Identify every clause without a direct rejecting test and record the coverage gap before writing code.
- [ ] Add the missing negative and hold-out tests so each clause fails independently when its enforcement is removed.
- [ ] Add executable clause-coverage assertions that reject a silently deleted enforcement binding.
- [ ] Keep root and generated restructuring scripts byte-identical and align the root and generated Plan Workflow policy with the recorded clause decomposition.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 212 with this plan's exact checked archive as predecessor.

## Validation Notes

- This successor owns final acceptance of the original Plan 200 requirement; the checked prerequisite plans do not.
- This plan performs no plan-lifecycle restructuring of Plans 197, 198, or 201.
- Coverage additions must not relax an existing rejection path to make a new test pass.
