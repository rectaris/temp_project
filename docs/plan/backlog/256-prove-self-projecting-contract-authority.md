# Prove self-projecting replan contract authority

status: backlog
primary_invariant: an in-progress integration plan whose lineage is a schema-2 or schema-3 replan contract proves its authoritative command identity from evidence the plan cannot author, and stays refused until it can
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - template/.project-agent-workflow/scripts/planlib.py
  - tests/validation_tools/plan.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/165-enforce-validation-witness-maps.md
  - docs/plan/replanned/baselines/live-validation-successors-v1.json
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
predecessor_plans:
  - docs/plan/active/165-enforce-validation-witness-maps.md
integration_gates:
  - Plan 165 must be checked before this plan starts, because it owns the companion authority check this plan widens
  - do not weaken or remove any rejection Plan 165 added; this plan only admits a case that is currently refused
  - do not edit scripts/restructure-plan.py in this plan; it stays the canonical publisher and is read as evidence only
checked_summary_ja: schema-2/3契約を持つ計画が権威を証明できるようにし、証明できない間は拒否を保つ。

## Decisions

- Refuse a schema-2 or schema-3 lineage until it can be proven, rather than trusting the contract file. Plan 165 accepted such a contract when its shape matched what the restructuring transaction emits, and an independent review authored a full-shaped contract that carried arbitrary authoritative commands. Shape conformity is not publication evidence, because the contract is an ordinary working-tree file the same actor can write.
- Decide the evidence source before writing any check. The companion baseline works for schema-1 lineage because the restructuring transaction publishes it once and never rewrites it. Schema-2 and schema-3 transactions publish the projection inside the contract instead, so there is no second record to compare against and the evidence has to come from somewhere the plan author does not control.
- Treat reimplementing the canonical contract verifier inside `planlib.py` as a rejected option on its own. `scripts/restructure-plan.py` owns that verification, it is outside this write scope, and a second copy would drift from the publisher without any check binding the two.
- Keep the refusal fail-closed while the gap is open. A future schema-2 or schema-3 successor plan is rejected with a named reason rather than admitted, so the gap costs a refusal that a reader can act on instead of a silent acceptance.

## Tasks

- [ ] Reproduce the forged-contract admission read-only against the state Plan 165 committed, and record what the current refusal reports instead.
- [ ] Decide the evidence source that a plan author cannot write, and record why the rejected alternatives do not hold.
- [ ] Admit a provable schema-2 and schema-3 lineage through that evidence, keeping every rejection Plan 165 added.
- [ ] Add rejection coverage for a full-shaped forged contract, not only an abbreviated stub.
- [ ] Confirm every published schema-2 and schema-3 contract in the repository is admitted, so the change adds no false refusal.
- [ ] Complete one fresh independent read-only review and focused validation with zero unresolved High or Medium findings.

## Validation Notes

- Pending. The admission is recorded as a High finding of the fourth independent review of Plan 165 and was reproduced in the main session.
- Reproduction: a schema-3 object carrying the exact top-level and successor field sets the transaction emits, with an invalid `created_at`, an invalid `source_head`, an empty `sources` list, unrelated successor content, and projection values chosen to match a weakened live plan, was accepted as published authority.
- Plan 165 closed this by refusing every contract without a companion baseline record, so the current state is a refusal rather than an admission. This plan owns turning that refusal back into a proof.
