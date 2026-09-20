# Repair parent-direct execution lifecycle records

status: backlog
implementation_mode: parent_direct
primary_invariant: Every lifecycle-bound execution-ledger event names the bound lifecycle record, and parent-direct lifecycle digests remain reachable without rewriting historical ledgers.
replan_sources:
  - docs/plan/active/367-repair-parent-direct-lifecycle-records.md
replan_contract: docs/plan/replanned/contracts/367-repair-parent-direct-lifecycle-records.json
successor_plans:
  - docs/plan/active/369-repair-parent-direct-lifecycle-records-successor.md
inherited_acceptance_digests:
  - sha256:79f9eb1703f67a4a53106c7ad256420bcf80b362b5d214382c97972e68dd1498
  - sha256:10a34048c59d774cb3a0415270bff365a52c2e05b8cd25eb57ab5e1a69e9de81
  - sha256:d7c50fe41b82ed8b2044cf542e6bf0bd679d6fadcfa9c38e07b828c700e03f9d
integration_source_ids:
  - 367
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Plan 374 is now deferred at published baseline 358a819, so plan 369 is the sole runnable plan and the authoritative serial-plan policy can evaluate this implementation.","kind":"existing_mechanism"}
  - {"evidence":"A real parent-direct run of plan 374 stopped at descope_required and its descope_plan gate refused: check requires the bound lifecycle path and the latest recorded digest, while the run recorded a digest that no file at that path carries.","kind":"reproduced_defect"}
  - {"evidence":"initial_state binds candidate_lifecycle_identity_digest from run id plus lifecycle path; check also rechecks that identity and the latest recorded file digest.","kind":"existing_mechanism"}
  - {"evidence":"record currently checks only candidate_lifecycle_digest equals file_digest(args.lifecycle_state) for lifecycle-bound events, so an unbound file can be named.","kind":"existing_mechanism"}
  - {"evidence":"canonical_digest hashes compact sorted JSON; file_digest hashes raw bytes, so a bound file containing the same compact parent-direct identity object reaches the existing digest gate.","kind":"bounded_prototype"}
  - {"evidence":"scripts/plan-execution-state.py and template/.project-agent-workflow/scripts/plan-execution-state.py are byte-identical at the planning baseline.","kind":"existing_mechanism"}
completion_conditions:
  - record rejects every lifecycle-bound event whose --lifecycle-state path does not match the ledger-bound lifecycle identity before accepting its content digest.
  - parent_direct execution materializes a bound canonical lifecycle record whose digest equals the recorded parent-direct identity, so execution, completion, archive, repair_plan and descope_plan gates can pass.
  - existing ledger histories remain readable without byte rewriting, the root script stays byte-aligned with the generated-project mirror, and the root and template plan-workflow specifications describe the parent-direct lifecycle record identically.
completion_witness_map:
  - {"condition_sha256":"sha256:e64dd08f20e88f882e712e3d1249bd9e683a1cef92a773dd18c3bf06e6f58589","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:554694a568f90d5a04adae2756615698ca8f0f82b011d756c71e8f72a6b4c8b9","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:fc4b1a4cd535b30b4c2c7223510a192373b0574f0f506e77609fea2cd6810394","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/plan/active/374-publish-and-verify-separate-session-plan-results.md
  - docs/plan/checked/2026/09/16-31/372-bind-parallel-plans-to-separate-session-owners.md
  - scripts/project_workflow/plan_authoring.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Lifecycle-bound record operations reject unbound lifecycle paths and still verify content digests for the bound path.
  - Parent-direct runs have a real bound lifecycle record, and check accepts execution, completion, archive, repair_plan and descope_plan when other gate predicates are satisfied.
  - Historical ledger bytes are not migrated or rewritten, and the root execution-ledger script and plan-workflow specification remain aligned with their generated template copies.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:79f9eb1703f67a4a53106c7ad256420bcf80b362b5d214382c97972e68dd1498","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:10a34048c59d774cb3a0415270bff365a52c2e05b8cd25eb57ab5e1a69e9de81","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:d7c50fe41b82ed8b2044cf542e6bf0bd679d6fadcfa9c38e07b828c700e03f9d","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Do not modify plan 374, its stopped execution ledger, or any parent-owned execution record held outside the repository.
  - Do not add a migration that rewrites historical execution-ledger bytes; preserve archived and stopped ledgers as readable records.
  - Do not change parallel-session assembly, publication, or retirement code owned by plan 374.
checked_summary_ja: parent-direct 実行の lifecycle 記録を束縛パス上に実体化し、record にも check と同じ束縛同一性検査を課して、停止中の gate を到達可能にする。

## Decisions

- Use a materialized parent-direct lifecycle record at the ledger-bound lifecycle path. The file bytes are the compact sorted JSON identity object already used for parent-direct review identity, so file_digest equals the recorded digest.
- Add the same lifecycle identity check to record that check already enforces, before accepting lifecycle-bound event content digests. Do not add a caller-selected identity override.
- Keep historical ledgers readable without migration. Enforce the stronger path check at new record boundaries and cover legacy-shaped histories with regression tests instead of rewriting stored events.
- Change scripts/plan-execution-state.py and template/.project-agent-workflow/scripts/plan-execution-state.py together and use check-copier-template to verify generated-project alignment.

## Tasks

- [ ] Add shared helpers for the parent-direct lifecycle identity object, its compact bytes, digest, and bound-path materialization or verification.
- [ ] Thread the bound lifecycle path into parent-direct preflight, review, and lifecycle-bound record flows so they write or verify the canonical lifecycle record before appending events.
- [ ] Make record reject a lifecycle-bound event when lifecycle_identity_digest(run_id, --lifecycle-state) differs from the ledger's candidate_lifecycle_identity_digest, matching check behavior.
- [ ] Add regression tests for off-path record rejection, missing parent-direct lifecycle materialization, all reachable check operations, unchanged candidate-mode lifecycle JSON behavior, legacy history readability, and root/template alignment.
- [ ] State the parent-direct lifecycle record and the record-side bound-path check in docs/agent/SPEC_PLAN_WORKFLOW.md and mirror it into the template specification.

## Validation Notes

- Reconstruction authorization: 「normalize_374_then_resume_367」. The source run confirmed `scope_drift`, plan 374 was normalized to `deferred` in commit `358a819`, and all five dirty implementation paths are promoted byte-for-byte to this parent-direct successor.

- Run lint with the repository virtual environment on PATH when the system ruff is absent.
