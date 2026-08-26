# Enable direct active source reconstruction

status: checked
primary_invariant: schema-3 can reconstruct an exact ordered active-plan source chain without historical contract ownership while preserving all existing contract-successor, acceptance, graph, archive, and transaction guarantees
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
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/200-enable-coupled-lineage-reconstruction.md
  - docs/plan/active/201-reconstruct-shell-parser-lineage.md
  - docs/plan/active/207-preserve-canonical-lifecycle-bytes.md
  - docs/plan/active/208-bind-journal-replacement-identity.md
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
  - Permit schema-3 reconstruction of an ordered direct active source chain without fabricating historical contract ownership while preserving all existing contract-successor checks.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:4dc4da8e0691fb176ed6382cefc8d14f422bc51ff3053b4f237d449b53f5e117","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/206-enforce-per-source-integration-coverage.md
integration_gates:
  - begin only from the exact checked Plan 206 archive and a clean worktree
  - preserve historical schema-1, schema-2, and schema-3 contract bytes and verification behavior
  - preserve the stricter contract-successor source route without implicit fallback
  - keep root and generated restructure commands byte-identical
  - do not archive or otherwise reconstruct stopped Plans 207, 208, 200, or 201 in this capability plan
  - Plan 213 remains deferred until this plan is checked and its exact checked archive replaces the active predecessor
  - Plan 210 remains deferred behind Plan 213 and the successors created by Plan 213
checked_summary_ja: historical contract未所有のexact active plan chainをschema-3で安全に再構築できるようにする。

## Decisions

- A direct active source means an exact indexed active plan that is not claimed as a live successor by a historical replan contract and is admitted under the bounded schema-3 active-source rules.
- Add an explicit source-kind discriminant; never infer direct-active status after contract-successor verification fails.
- Continue accepting historical schema-3 source records in their committed shape and emit the discriminant only in newly created contracts.
- Require every direct active source to exist exactly once in the active index, be unclaimed by all verified contracts, have no replan lineage fields, and match its bound original digest and current HEAD.
- Require the first source to be canonically `replan_required`; derive each later source's stopped bytes only through the existing bounded lifecycle transformation and require it to depend directly or transitively on an earlier source.
- Allow contract-successor and direct-active sources in one ordered transaction only when each source independently satisfies its declared route and no path is claimed twice.
- Preserve per-source integration coverage, complete graph verification, exact dirty snapshot, destination nonexistence, archive identity, rebind authorization, journal recovery, and immutable historical bytes.
- Add a two-direct-source scenario equivalent to stopped Plan 200 plus dependent Plan 201, including rejection of forged ownership, stale index state, missing dependency, duplicate claim, and noncanonical stopping.
- Use bounded parent implementation and fresh independent review because this plan extends durable lineage semantics.

## Tasks

- [x] Add the explicit direct-active source representation to schema-3 specification, contract emission, and durable verification.
- [x] Preserve the exact historical contract-successor representation and reject implicit route changes.
- [x] Add positive direct/direct and mixed-route tests plus ownership, dependency, lifecycle, acceptance, graph, and historical-compatibility negatives.
- [x] Align the root and generated Plan Workflow policy with the new bounded source route.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, archive, commit, and activate Plan 213 with this plan's exact checked archive as predecessor and context.

## Validation Notes

- This capability exists to make ordinary stopped active plans formally reconstructable; it does not weaken contract ownership for plans already claimed by a historical contract.
- Plan 209 changes capability only and must not archive Plans 200 or 201 itself.
- Plan 209 now precedes the stopped Plan 207/208 reconstruction because that reconstruction requires the direct-active source route owned here.
- Focused validation passed with `python3 tests/test-plan-restructure.py`, `python3 scripts/restructure-plan.py --verify`, and `git diff --check`.
- Independent review reported no unresolved High or Medium findings; the one Low finding on nonstring `source_kind` error handling was fixed and covered by a test.
- The authoritative validation suite completed successfully once.
