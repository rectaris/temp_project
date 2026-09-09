# Prove self-projecting replan contract authority

status: checked
primary_invariant: an in-progress integration plan whose lineage is a schema-2 or schema-3 replan contract proves its authoritative command identity from evidence the plan cannot author, and stays refused until it can
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
implementation_tier: 2
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
  - docs/plan/checked/2026/09/01-15/165-enforce-validation-witness-maps.md
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
  - docs/plan/checked/2026/09/01-15/165-enforce-validation-witness-maps.md
integration_gates:
  - Plan 165 must be checked before this plan starts, because it owns the companion authority check this plan widens
  - do not weaken or remove any rejection Plan 165 added; this plan only admits a case that is currently refused
  - do not edit scripts/restructure-plan.py in this plan; it stays the canonical publisher and is read as evidence only
checked_summary_ja: schema-2/3契約を持つ計画が権威を証明できるようにし、証明できない間は拒否を保つ。

## Decisions

- Refuse a schema-2 or schema-3 lineage until it can be proven, rather than trusting the contract file. Plan 165 accepted such a contract when its shape matched what the restructuring transaction emits, and an independent review authored a full-shaped contract that carried arbitrary authoritative commands. Shape conformity is not publication evidence, because the contract is an ordinary working-tree file the same actor can write.
- Decide the evidence source before writing any check. The companion baseline works for schema-1 lineage because the restructuring transaction publishes it once and never rewrites it. Schema-2 and schema-3 transactions publish the projection inside the contract instead, so there is no second record to compare against and the evidence has to come from somewhere the plan author does not control.
- Take that evidence from committed history at `HEAD`. The contract must hold its committed bytes, the committed `docs/plan/replanned.md` must register it, and every archive that committed index binds to the contract must be terminal `replanned` history that names the same contract and lists this plan in `successor_plans`. Plan execution writes working-tree files only; staging and commits stay parent-authorized, so committed publication is the boundary between authoring a contract and publishing one. `scripts/restructure-plan.py` already holds published contracts and archives to their committed bytes, so this reads the publisher's own invariant instead of restating its verification.
- Treat reimplementing the canonical contract verifier inside `planlib.py` as a rejected option on its own. `scripts/restructure-plan.py` owns that verification, it is outside this write scope, and a second copy would drift from the publisher without any check binding the two.
- Reject running `scripts/restructure-plan.py --verify` from `planlib.py` as the proof. It verifies the whole repository, so an unrelated lifecycle disagreement would refuse an otherwise provable plan, and it would make one plan's check depend on a script a generated project may not have installed.
- Reject widening the companion baseline to schema-2 and schema-3 lineage. Only the restructuring transaction may publish that record, and it lives outside this write scope.
- Keep the refusal fail-closed while the gap is open. A future schema-2 or schema-3 successor plan is rejected with a named reason rather than admitted, so the gap costs a refusal that a reader can act on instead of a silent acceptance.
- Bound the guarantee explicitly. It separates plan authorship from publication; an actor that can commit a forged contract, its archive, and the index row is outside it, exactly as with the migration provenance snapshot.
- Accept a fail-closed window between restructuring and its commit. `scripts/restructure-plan.py` writes the contract, the archive, the index row, and the successor plan into the working tree and leaves the commit to the parent, so a fresh schema-2 or schema-3 successor is refused with `published replan contract is not committed history` until that transaction is committed. Commit the restructuring transaction before running a plan check against its successor. This is not a regression, because the state Plan 165 committed refuses the same lineage unconditionally.

## Tasks

- [x] Reproduce the forged-contract admission read-only against the state Plan 165 committed, and record what the current refusal reports instead.
- [x] Decide the evidence source that a plan author cannot write, and record why the rejected alternatives do not hold.
- [x] Admit a provable schema-2 and schema-3 lineage through that evidence, keeping every rejection Plan 165 added.
- [x] Add rejection coverage for a full-shaped forged contract, not only an abbreviated stub.
- [x] Confirm every published schema-2 and schema-3 contract in the repository is admitted, so the change adds no false refusal.
- [x] Complete one fresh independent read-only review and focused validation with zero unresolved High or Medium findings.

## Validation Notes

- Reproduced against the state Plan 165 committed: a full-shaped schema-3 contract with an invalid `created_at`, an invalid `source_head`, and a weakened authoritative sequence is refused with `in-progress integration plan has no published companion validation authority`. The admission itself is closed; this plan turns that blanket refusal back into a proof.
- Evidence source: committed history at `HEAD`. `verify_published_contract_publication` requires the contract to hold its committed bytes, the committed `docs/plan/replanned.md` to register it, and every archive that index binds to the contract to be terminal `replanned` history naming the same contract and listing this plan in `successor_plans`.
- No false refusal: all 22 published schema-2 and schema-3 successors that carry `validation_witness_schema: 1` are admitted when their manifest is replayed against their own published contract; the remaining published contracts are schema-1 and keep the companion baseline path.
- Rejection coverage added for a full-shaped forged contract in three separate positions, substituted over a published contract, present only in the working tree, and committed without lineage, and for post-publication contract drift, for an index row that exists only in the working tree, for archive lineage that does not create the plan, for a weakened authoritative sequence, for a remapped witness digest, for schema-3 mappings from an unknown source or out of published source order, and for history taken from an enclosing repository.
- Every rejection subtest was confirmed to fail at its intended check rather than at an earlier one.
- Independent read-only review: no High and no Medium findings. Two Low findings were resolved in this plan. The pre-commit refusal window is now recorded in the decisions above, and the forged-contract subtest that previously failed at the missing-repository check before reaching the forged bytes was split into three cases that each reach a distinct refusal.
- Repository suites: `scripts/lint-project-workflow.sh` and `tests/smoke.sh` pass.
