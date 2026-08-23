# Bind live plan baselines and execution manifests

status: deferred
completion_deferred_reason: Plans 188, 189, 164, and 105 must be checked and their exact checked archive paths must replace the active predecessors before implementation.
primary_invariant: every live successor and dependency edge receives the accepted preservation, predecessor, and companion validation baseline without changing existing contract bytes, source acceptance, or product bytes
task_types:
  - planning_docs
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - docs/plan/active/165-enforce-validation-witness-maps.md
  - docs/plan/active/166-unify-copier-update-source-inventory.md
  - docs/plan/active/167-integrate-validation-witness-enforcement.md
  - docs/plan/active/179-integrate-validation-witness-migration-provenance.md
  - docs/plan/active/184-verify-plan178-successor-acceptance.md
  - docs/plan/active/185-complete-bounded-copier-fixture-runtime.md
  - docs/plan/active/186-bind-connected-copier-fixture-checker.md
  - docs/plan/active/187-verify-plan183-successor-acceptance.md
  - docs/plan/active/191-freeze-bounded-copier-fixture-validator.md
  - docs/plan/active/192-freeze-resource-evaluation-contract.md
  - docs/plan/active/193-collect-resource-evaluation-evidence.md
  - docs/plan/active/194-apply-resource-evaluation-outcome.md
  - docs/plan/active/195-verify-plan133-successor-acceptance.md
  - docs/plan/plan.md
  - docs/plan/replanned/baselines/live-validation-successors-v1.json
preservation_scope:
  - scripts/check-copier-template.py
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/189-enforce-active-plan-predecessors.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - docs/plan/replanned/2026/08/16-31/116-evaluate-plan-worker-orchestration.md
  - docs/plan/replanned/2026/08/16-31/130-map-acceptance-validation-witnesses.md
  - docs/plan/replanned/2026/08/16-31/163-capture-validation-witness-migration-provenance.md
  - docs/plan/replanned/2026/08/16-31/178-wire-validation-witness-copier-transition.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - docs/plan/replanned/contracts/116-evaluate-plan-worker-orchestration.json
  - docs/plan/replanned/contracts/130-map-acceptance-validation-witnesses.json
  - docs/plan/replanned/contracts/133-evaluate-resource-bounded-orchestration.json
  - docs/plan/replanned/contracts/163-capture-validation-witness-migration-provenance.json
  - docs/plan/replanned/contracts/178-wire-validation-witness-copier-transition.json
  - docs/plan/replanned/contracts/183-build-bounded-copier-transition-fixture.json
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-root-agent-policy.py
  - git diff --check
validation:
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-root-agent-policy.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Bind every current live successor to the accepted companion validation baseline and predecessor and preservation manifests without changing existing replan-contract bytes, acceptance text, safety conditions, or product bytes.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:253605228652141b4235578e7e0a6f606db9bb4d884582f49df4795794c21046","stage":"focused","witness":"python3 scripts/restructure-plan.py --verify"}
predecessor_plans:
  - docs/plan/active/188-separate-replan-preservation-authority.md
  - docs/plan/active/189-enforce-active-plan-predecessors.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - docs/plan/active/105-admit-reconstructed-plan-validation-commands.md
integration_gates:
  - Plans 188, 189, 164, and 105 must be checked and their exact checked archive paths must be present before migration starts
  - preserve scripts/check-copier-template.py and tests/copier-update.sh without editing, staging, or committing them
  - Plan 191 remains deferred until this migration is checked and its exact checked archive path replaces this active predecessor
checked_summary_ja: 現行plan chainを保持範囲、依存先、validation baselineの新schemaへ移行する。

## Decisions

- contracted_validation_baseline means the versioned authoritative validation and witness projection stored for current schema-1 lineages in docs/plan/replanned/baselines/live-validation-successors-v1.json without modifying those contracts.
- Create one schema-1 companion record bound to the exact digest of each unchanged contract with live successors.
- Preserve every contract byte, source content, acceptance text and digest, safety condition, archived history, and successor lineage exactly.
- Add preservation_scope only to read-only preservation plans and retain product write_scope only on the owning implementation plans.
- Add predecessor_plans to every deferred successor, remove downstream plans from read-only context_files, and make exactly Plan 191 eligible after this migration.
- Bind each live successor path, acceptance digest, normalized authoritative validation sequence and digest, witness schema, and witness-map digest in the companion record.
- Use bounded parent implementation and independent review because this plan changes durable lifecycle evidence and active validation inputs.

## Tasks

- [ ] Create the bounded companion baseline for the five live lineage contracts and the Plan 133 replacement contract without modifying those contract files.
- [ ] Update active plans with exact predecessor and preservation fields, remove downstream context cycles, and preserve every acceptance map.
- [ ] Verify that exactly one unfinished plan is in_progress and every later plan is deferred behind an exact predecessor.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 191 with the exact checked predecessor path.

## Validation Notes

- This plan owns lifecycle and companion-baseline artifacts only and must leave both uncommitted product candidates and every existing replan contract byte-identical and unstaged.
