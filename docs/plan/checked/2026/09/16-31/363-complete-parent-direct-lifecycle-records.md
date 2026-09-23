# Complete parent-direct execution lifecycle records

status: checked
implementation_mode: parent_direct
primary_invariant: Every lifecycle-bound execution-ledger event names the bound lifecycle record, and parent-direct lifecycle digests remain reachable without rewriting historical ledgers.
replan_sources:
  - docs/plan/active/369-repair-parent-direct-lifecycle-records-successor.md
replan_contract: docs/plan/replanned/contracts/369-repair-parent-direct-lifecycle-records-successor.json
successor_plans:
  - docs/plan/active/363-complete-parent-direct-lifecycle-records.md
inherited_acceptance_digests:
  - sha256:79f9eb1703f67a4a53106c7ad256420bcf80b362b5d214382c97972e68dd1498
  - sha256:10a34048c59d774cb3a0415270bff365a52c2e05b8cd25eb57ab5e1a69e9de81
  - sha256:d7c50fe41b82ed8b2044cf542e6bf0bd679d6fadcfa9c38e07b828c700e03f9d
integration_source_ids:
  - 369
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
  - {"evidence":"Plan 362 is checked at f699a19 and the bounded ValueError correction is published at 1f8d1b3, so the successor can start from the current accepted workflow policy and implementation.","kind":"existing_mechanism"}
  - {"evidence":"The retained plan 369 patch applies cleanly to 1f8d1b3 with git apply --check; its raw bytes are preserved outside the repository with digest sha256:8d2b396b6129dd55938d7c45c3c8aaa3a3c118c61d411ae1e0d8956a55f5da31 for semantic transplant evidence.","kind":"bounded_prototype"}
  - {"evidence":"The plan-369 owner-resolution ledger was stopped at replan_required after confirming that its accepted two-file correction omitted the retained five-file implementation target.","kind":"reproduced_defect"}
  - {"evidence":"The source plan acceptance text and digests remain unchanged, while the implementation method changes from exact dirty-byte continuation to patch-based integration on the current descendant baseline.","kind":"mechanical_transformation"}
completion_conditions:
  - The retained plan 369 patch is applied only after this successor passes its execution gate, and its intended lifecycle binding, formal-review gating, legacy recovery and opaque-lifecycle compatibility behavior is integrated with the checked owner-resolution implementation.
  - Focused tests prove unbound-path refusal, parent-direct lifecycle materialization, zero-lifecycle formal-review refusal, legacy continuation recovery, arbitrary-size opaque lifecycle compatibility and uncaught JSON ValueError conversion on the current baseline.
  - Existing execution ledgers remain byte-unchanged, root and generated files remain aligned, and completion, archive, repair_plan and descope_plan gates satisfy the inherited acceptance on the published descendant commit.
completion_witness_map:
  - {"condition_sha256":"sha256:d45db15c685702e01d518420a79692e7b2a9512dd7c4bee2c8e590e7b76a7322","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:634a83d192a1894236d8336b14ddaded00961dd2750d7d975b4536c0b5488411","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:5f38f68727db61ab6c77945c80575b7a191998df8fc2ed2f980e4f83e8aee053","witness":"python3 scripts/check-copier-template.py"}
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
  - docs/plan/checked/2026/09/16-31/362-add-terminal-owner-resolution.md
  - docs/plan/replanned/contracts/367-repair-parent-direct-lifecycle-records.json
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
  - Apply the retained patch only after the successor execution gate succeeds; preserve its external digest as provenance and resolve integration against 1f8d1b3 without restoring stale full-file bytes.
  - Do not modify plan 374 or any epoch-0 through epoch-4 plan 369 ledger, continuation registry, reviewer registry, authorization or owner-acceptance record.
  - Treat any patch rejection, unclassified path, acceptance drift, root/template mismatch or regression of the four-review owner-resolution policy as a stop, not permission to drop source changes.
checked_summary_ja: plan 369 の保持済み差分を現行 baseline に意味的に移植し、parent-direct lifecycle の到達可能性と履歴互換性を完成させる。

## Decisions

- Preserve the raw retained patch outside the repository as provenance, but use the owner-authorized semantic transplant onto the current descendant baseline instead of restoring stale full-file bytes.
- Keep every inherited acceptance item and the primary invariant unchanged; this reconstruction changes only the integration method after the prior owner-resolution omitted the retained implementation target.
- Start from commit 1f8d1b3, which includes the checked plan 362 policy and the bounded ValueError correction. Apply the retained patch only after the fresh successor execution gate.
- Reconcile overlapping script and test changes explicitly, retaining both owner-resolution safeguards and plan 369 lifecycle behavior. Do not select one side wholesale.
- Preserve all external execution ledgers and registries byte-for-byte. The successor receives a fresh execution chain because the prior epoch-4 target was incomplete, not because its review budget is being reset.

## Tasks

- [x] Initialize the successor parent-direct execution at the published current baseline and pass its review-route and execution gates before product writes.
- [x] Apply the retained plan 369 patch and resolve its overlap with plan 362 and 1f8d1b3 while keeping root and generated scripts byte-aligned.
- [x] Reconcile the plan-workflow specification and regression tests so both terminal owner resolution and parent-direct lifecycle recovery remain enforced.
- [x] Run the focused lifecycle tests and template alignment check, then bind exact-target adversarial preflight and independent review.
- [x] Run authoritative lint and smoke once after review clears High and Medium findings.
- [x] Commit and publish the reviewed implementation, archive the successor as checked, and retire both the successor task worktree and the obsolete retained plan 369 worktree without deleting the preserved patch evidence.

## Validation Notes

- Source failure: the epoch-4 owner acceptance bound only scripts/plan-execution-state.py and its generated mirror; the original five-file plan 369 implementation remained in the retained worktree and was absent from dev.
- Owner continuation authorization: 「提案の方針で進めよ。」
- Dirty-byte policy change authorized by owner response: `authorize_semantic_transplant`. The retained patch digest is sha256:8d2b396b6129dd55938d7c45c3c8aaa3a3c118c61d411ae1e0d8956a55f5da31.
- Fresh execution gates passed in epochs 0 through 3. Four formal reviews were recorded; the fourth left one Medium finding, so the terminal owner-resolution path made one bounded correction without a fifth review.
- Focused validation passed with 259 lifecycle tests and `scripts/check-copier-template.py`. Authoritative `scripts/lint-project-workflow.sh` and `tests/smoke.sh` passed once for the accepted correction.
- Owner accepted the exact correction after validation. Implementation commit: `6eea563`.
