# Admit lineage rebinding for backlog and legacy contract successors

status: checked
primary_invariant: a lineage rebinding of a plan whose live bytes diverge from its contract baseline stays bound by committed evidence and the immutable record chain, and adds enforcement rather than removing it
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
implementation_tier: 2
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - tests/test-plan-restructure.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/240-reconcile-pre-boundary-lifecycle-and-replanned-lineage.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - A lineage rebinding keeps the immutable record chain on projected plan content while the live file receives the same exact replacements, and rejects any live divergence that is not a lifecycle-field difference.
  - A legacy contract successor whose live bytes already diverge from its contract base may start a lineage chain only from its own committed bytes at HEAD, and every later record stays bound by the immutable chain.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:363e53d06f262a7f5885a9a35dff75f960ae30f9d44e4dfc616a8e1480b554fa","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:5eab5a2c38ab16371263e0128cb253c353cf2ef9905ddb6a2169084121205e97","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/240-reconcile-pre-boundary-lifecycle-and-replanned-lineage.md
integration_gates:
  - do not relax the contract-identity comparison for a contract that enforces projection semantics
  - do not admit a legacy lineage baseline that is not the committed bytes at HEAD
checked_summary_ja: contract baseと生きたbytesが既に食い違うbacklog planとlegacy successorについて、commit済みの証拠と不変な記録連鎖に縛った上でlineage rebindingを許可する。

## Decisions

- Keep the record chain and the live file separate. Plan 186 already left `deferred` for `backlog`, so its chain-final projection and its live bytes differ by lifecycle fields. The record stays on the projection and the same replacements are applied to the live file, so neither relation is loosened.
- Accept a `backlog` baseline in lifecycle evolution instead of pinning a rebound backlog plan byte for byte. Pinning would make reactivation impossible, and the plan already had this freedom through its contract base.
- Let a legacy successor start its chain from its own committed bytes. Plan 187 belongs to a schema-1 contract that never enforced projection semantics, and its live write scope, preservation scope, and predecessors already diverge from the contract base. Comparing that baseline against the contract base can only fail, so the baseline is bound to the committed bytes at `HEAD` instead.
- The carve-out is narrow. It applies only to the first `lineage_rebind` record of a non-enforcing contract; every enforcing contract keeps the full contract-identity comparison, and after the first record the chain binds the plan more tightly than before.

## Tasks

- [x] Keep the lineage record chain on projected content and write the live file separately.
- [x] Accept a backlog baseline in lifecycle evolution.
- [x] Admit a legacy first lineage record bound to the committed live bytes.
- [x] Mirror the tool and document all three rules in the root and template plan workflow specifications.
- [x] Add regression tests for the backlog baseline, the divergent chain, and the uncommitted legacy baseline.

## Validation Notes

- Focused validation passed: `python3 tests/test-plan-restructure.py` with 156 tests, `python3 scripts/restructure-plan.py --verify`, `python3 scripts/check-copier-template.py`, and `git diff --check`.
- The authoritative suite passed once: `python3 tests/test-plan-restructure.py`, `python3 scripts/restructure-plan.py --verify`, `python3 scripts/check-copier-template.py`, `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, and `git diff --check`.
- The first lint run reported `multiple runnable plans in active index: 228, 241`, which is the root single-runnable-plan rule and not a defect in this change. The suite was rerun after this plan was archived.
- Plan 186 exercised the divergent chain and Plan 187 exercised the legacy baseline. Both rebindings were applied under Plan 228 and lineage verification stayed green.
- No helper agents were used.
